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

@dataclass(frozen=True)
class Package(ABC):
    pre_install: tuple[Command, ...] = field(default_factory=tuple)
    post_install: tuple[Command, ...] = field(default_factory=tuple)
    flags: tuple[str, ...] = field(default_factory=tuple)
    dependencies: tuple[str, ...] = field(default_factory=tuple)

    def print(self) -> str:
        result = ""

        for cmd in self.pre_install:
            result += f"{cmd.print()}\n"

        result += self.print_package() + "\n"

        for cmd in self.post_install:
            result += f"\n{cmd.print()}"

        return result

    @abstractmethod
    def print_package(self) -> str:
        pass

    def resolve(self, all_packages: dict[str, list[Package]]) -> list[Package]:
        return [self]


@dataclass(frozen=True)
class DnfPackage(Package):
    packages: tuple[str, ...] = field(default_factory=tuple)

    def print_package(self) -> str:
        return f"sudo dnf install -y {' '.join(self.packages)} {' '.join(self.flags)}".strip()


@dataclass(frozen=True)
class AptPackage(Package):
    packages: tuple[str, ...] = field(default_factory=tuple)

    def print_package(self) -> str:
        return f"sudo apt-get install -y {' '.join(self.packages)} {' '.join(self.flags)}".strip()


@dataclass(frozen=True)
class SnapPackage(Package):
    packages: tuple[str, ...] = field(default_factory=tuple)

    def print_package(self) -> str:
        return f"sudo snap install {' '.join(self.packages)} {' '.join(self.flags)}".strip()


@dataclass(frozen=True)
class FlatpakPackage(Package):
    remote: str = field(default="flathub")
    packages: tuple[str, ...] = field(default_factory=tuple)

    def print_package(self) -> str:
        return f"flatpak install -y {self.remote} {' '.join(self.packages)} {' '.join(self.flags)}".strip()


@dataclass(frozen=True)
class UndefinedPackage(Package):
    name: str = field(default="undefined")

    def print_package(self) -> str:
        return f"# TODO: Add installation command for package: {self.name}"

    def resolve(self, all_packages: dict[str, list[Package]]) -> list[Package]:
        return all_packages.get(self.name, super().resolve(all_packages))


@dataclass(frozen=True)
class Command:
    @abstractmethod
    def print(self) -> str:
        pass


@dataclass(frozen=True)
class ShellCommand(Command):
    command: str

    def print(self) -> str:
        return self.command


@dataclass(frozen=True)
class TeeCommand(Command):
    content: str
    destination: str
    sudo: bool = False

    def print(self) -> str:
        sudo = "sudo " if self.sudo else ""
        content = self.content.removesuffix('\n').replace('\n', '" "')
        return f'printf "%s\\n" "{content}" | {sudo}tee {self.destination}'


def create_packages_list(item: dict, default: str) -> list[str]:
    if 'packages' in item:
        return item['packages']
    else:
        return [default]


def create_install_commands(commands: any) -> list[str]:
    if commands is None:
        return []

    if isinstance(commands, str):
        commands = {
            'type': 'shell',
            'command': commands
        }

    if isinstance(commands, dict):
        if commands.get('type') == 'shell':
            return [ShellCommand(command=commands['command'])]
        elif commands.get('type') == 'tee':
            return [TeeCommand(
                content=commands.get('content'),
                destination=commands.get('destination'),
                sudo=commands.get('sudo', False)
            )]

    if isinstance(commands, list):
        cmd_list: list[Command] = []
        for cmd in commands:
            for c in create_install_commands(cmd):
                cmd_list.append(c)
        return cmd_list

    print(f"Unknown command format: {commands}")
    return []


def create_common_package_fields(name: str, item: dict, platform: str) -> tuple[list[Command], list[Command], dict[str, Package]]:
    pre_install = create_install_commands(item.get('pre_install'))
    post_install = create_install_commands(item.get('post_install'))
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
            packages=tuple(packages),
            pre_install=tuple(pre_install),
            post_install=tuple(post_install),
            flags=tuple(flags),
            dependencies=tuple(deps.keys()),
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
            packages=tuple(packages),
            pre_install=tuple(pre_install),
            post_install=tuple(post_install),
            flags=tuple(flags),
            dependencies=tuple(deps.keys()),
        )
    ]


def create_snapd_package(name: str, item: dict, platform: str) -> list[Package]:
    if platform not in ['ubuntu', 'debian', 'fedora', 'centos', 'rhel']:
        return []

    packages = create_packages_list(item, name)
    pre_install, post_install, deps = create_common_package_fields(name, item, platform)
    flags = item.get('flags', [])

    if 'classic' in item and item['classic']:
        flags.append('--classic')

    deps['snapd'] = UndefinedPackage(name='snapd')

    return [
        *deps.values(),
        SnapPackage(
            packages=tuple(packages),
            pre_install=tuple(pre_install),
            post_install=tuple(post_install),
            flags=tuple(flags),
            dependencies=tuple(deps.keys()),
        )
    ]


def create_flatpak_package(name: str, item: dict, platform: str) -> list[Package]:
    if platform not in ['ubuntu', 'debian', 'fedora', 'centos', 'rhel']:
        return []

    packages = create_packages_list(item, name)
    pre_install, post_install, deps = create_common_package_fields(name, item, platform)
    flags = item.get('flags', [])

    deps['flatpak'] = UndefinedPackage(name='flatpak')

    remote = "flathub"
    if 'remote' in item:
        remote = item['remote']

    return [
        *deps.values(),
        FlatpakPackage(
            packages=tuple(packages),
            pre_install=tuple(pre_install),
            post_install=tuple(post_install),
            flags=tuple(flags),
            dependencies=tuple(deps.keys()),
            remote=remote,
        )
    ]


def create_undefined_package(name: str, item: dict, platform: str) -> list[Package]:
    return [UndefinedPackage(name=name)]


PACKAGE_FACTORIES = {
    'dnf': create_dnf_package,
    'apt': create_apt_package,
    'snapd': create_snapd_package,
    'flatpak': create_flatpak_package,
}

def load_package(name: str, item: dict, platform: str) -> list[Package]:
    package_list: list[Package] = []

    factory = PACKAGE_FACTORIES.get(item.get('type'), create_undefined_package)

    for pkg in factory(name, item, platform):
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


def sort_packages(packages: dict[str, list[Package]]) -> list[Package]:
    sorted_packages: list[Package] = []
    seen: set[Package] = set()

    for pkg_list in packages.values():
        for pkg in pkg_list:
            for resolved in pkg.resolve(packages):
                if resolved not in seen:
                    seen.add(resolved)
                    sorted_packages.append(resolved)

    return sorted_packages


def main(args: argparse.Namespace) -> None:
    """
    Usage: installscript.py <config.yaml> --os <os_name> [--out <output.sh>]
    """
    with open(args.config_path, 'r') as file:
        config = yaml.safe_load(file)

        packages = load_packages(config, args.os)

        script_content = "#!/bin/bash\n\n"

        for pkg in sort_packages(packages):
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
    args_parser.add_argument("config_path", help="Path to the YAML configuration file.")
    args_parser.add_argument("--os", required=True, help="Target operating system (e.g., 'ubuntu', 'fedora').")
    args_parser.add_argument("--out", help="Output shell script file path (optional, defaults to stdout).")
    args = args_parser.parse_args(sys.argv[1:])
    main(args)
