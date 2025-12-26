#!/usr/bin/env python3

"""
Installation script generator.

Generates shell scripts for installing software packages on different Linux distributions, by
receiving a declarative YAML configuration file as input.
"""

from dataclasses import dataclass, field
from abc import ABC, abstractmethod

import argparse
import sys
import yaml

@dataclass
class Package(ABC):
    pre_install: list[Command] = field(default_factory=list)
    post_install: list[Command] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)

    def print(self) -> str:
        result = ""

        for cmd in self.pre_install:
            result += f"{cmd.print()}\n"

        result += self.print_package() + "\n"

        if len(self.post_install) > 0:
            result += "\n"

        for cmd in self.post_install:
            result += f"{cmd.print()}\n"

        return result

    @abstractmethod
    def print_package(self) -> str:
        pass

@dataclass
class DnfPackage(Package):
  packages: list[str] = field(default_factory=list)

  def print_package(self) -> str:
      return f"sudo dnf install -y {' '.join(self.packages)} {' '.join(self.flags)}".strip()


@dataclass
class AptPackage(Package):
  packages: list[str] = field(default_factory=list)

  def print_package(self) -> str:
      return f"sudo apt-get install -y {' '.join(self.packages)} {' '.join(self.flags)}".strip()


@dataclass
class UndefinedPackage(Package):
    name: str = field(default="undefined")

    def print_package(self) -> str:
        return f"# TODO: Add installation command for package: {self.name}"


@dataclass
class Command:
    @abstractmethod
    def print(self) -> str:
        pass


@dataclass
class ShellCommand(Command):
    command: str

    def print(self) -> str:
        return self.command


def create_packages_list(item: dict, default: str) -> list[str]:
    if 'packages' in item:
        return item['packages']
    else:
        return [default]


def create_install_commands(item: dict, key: str) -> list[str]:
    if not key in item:
        return []

    commands = item[key]

    if isinstance(commands, str):
        return [ShellCommand(command=commands)]

    print(f"Unknown command format for key '{key}': {commands}")
    return []


def create_common_package_fields(name: str, item: dict, platform: str) -> tuple[list[Command], list[Command], dict[str, Package]]:
    pre_install = create_install_commands(item, 'pre_install')
    post_install = create_install_commands(item, 'post_install')
    deps = load_dependencies(name, item.get('depends_on', []), platform)
    return pre_install, post_install, deps


def create_dnf_package(name: str, item: dict, platform: str) -> list[DnfPackage]:
    if platform not in ['fedora', 'centos', 'rhel']:
        return []

    packages = create_packages_list(item, name)
    pre_install, post_install, deps = create_common_package_fields(name, item, platform)
    flags = item.get('flags', [])

    if 'repofile' in item:
        repo_file = item['repofile']
        pre_install.append(ShellCommand(
            command=f"sudo dnf config-manager addrepo --from-repofile={repo_file}\n"
        ))

    if 'repo' in item:
        flags.append(f"--repo {item['repo']}")

    return [
        *deps.values(),
        DnfPackage(
            packages=packages,
            pre_install=pre_install,
            post_install=post_install,
            flags=flags,
            dependencies=list(deps.keys()),
        )
    ]


def create_apt_package(name: str, item: dict, platform: str) -> list[AptPackage]:
    if platform not in ['ubuntu', 'debian']:
        return []

    packages=create_packages_list(item, name)
    pre_install, post_install, deps = create_common_package_fields(name, item, platform)
    flags = item.get('flags', [])

    return [
        *deps.values(),
        AptPackage(
            packages=packages,
            pre_install=pre_install,
            post_install=post_install,
            flags=flags,
            dependencies=list(deps.keys()),
        )
    ]


def load_package(name: str, item: dict, platform: str) -> list[Package]:
    package_list: list[Package] = []

    if item.get('type') == 'dnf':
        for pkg in create_dnf_package(name, item, platform):
            package_list.append(pkg)

    elif item.get('type') == 'apt':
        for pkg in create_apt_package(name, item, platform):
            package_list.append(pkg)

    return package_list


def load_dependencies(name: str, config: list[dict], platform: str) -> dict[str, Package]:
    dependencies: dict[str, Package] = {}

    for i, item in enumerate(config):
        if isinstance(item, str):
            dependencies[item] = UndefinedPackage(name=item)
            continue

        for j, pkg in enumerate(load_package(name, item, platform)):
            dependencies[f"{name}-deps-{i}-{j}"] = pkg

    return dependencies


def load_package_list(name: str, config: list[dict], platform: str) -> list[Package]:
    package_list: list[Package] = []

    for item in config:
        if isinstance(item, str):
            item = {'type': item}

        for pkg in load_package(name, item, platform):
            package_list.append(pkg)

    return package_list


def load_packages(config: dict, platform: str) -> dict[str, list[Package]]:
    packages: dict[str, list[Package]] = {}

    for name, pkg_list in config.items():
        packages[name] = load_package_list(name, pkg_list, platform)

    return packages


def load_config(file_path: str, platform: str) -> dict[str, list[Package]]:
    with open(file_path, 'r') as file:
        config = yaml.safe_load(file)

    return load_packages(config, platform)


def main(args: argparse.Namespace) -> None:
    """
    Usage: installscript.py <config.yaml> --os <os_name> [--out <output.sh>]
    """
    packages = load_config(args.config, args.os)

    script_content = "#!/bin/bash\n\n"

    for _, pkgs in packages.items():
        for pkg in pkgs:
            script_content += pkg.print() + "\n"

    while script_content.endswith('\n'):
        script_content = script_content[:-1]  # Remove the last extra newline

    if args.out:
        with open(args.out, 'w') as outfile:
            outfile.write(script_content)
    else:
        print(script_content)


if __name__ == "__main__":
    args_parser = argparse.ArgumentParser(description="Generate installation scripts from YAML config.")
    args_parser.add_argument("config", help="Path to the YAML configuration file.")
    args_parser.add_argument("--os", required=True, help="Target operating system (e.g., 'ubuntu', 'fedora').")
    args_parser.add_argument("--out", help="Output shell script file path (optional, defaults to stdout).")
    args = args_parser.parse_args(sys.argv[1:])
    main(args)
