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
    factories = {}

    pre_install: tuple[Command, ...] = field(default_factory=tuple)
    post_install: tuple[Command, ...] = field(default_factory=tuple)
    flags: tuple[str, ...] = field(default_factory=tuple)
    dependencies: tuple[str, ...] = field(default_factory=tuple)

    def __init_subclass__(cls, *, type: str = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if type is not None:
            cls.factories[type] = cls

    @classmethod
    def create(cls, name: str, item: dict, platform: str) -> list[Package]:
        factory = cls.factories.get(item.get('type'), UndefinedPackage)
        return factory.create(name, item, platform)


    def print(self) -> str:
        parts = []

        for cmd in self.pre_install:
            parts.append(cmd.print())
            parts.append("\n")

        parts.append(self.print_package())
        parts.append("\n")

        for cmd in self.post_install:
            parts.append("\n")
            parts.append(cmd.print())

        return "".join(parts)

    @abstractmethod
    def print_package(self) -> str:
        pass

    def resolve(self, all_packages: dict[str, list[Package]]) -> list[Package]:
        return [self]


@dataclass(frozen=True)
class DnfPackage(Package, type='dnf'):
    packages: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def create(cls, name: str, item: dict, platform: str) -> list[Package]:
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

    def print_package(self) -> str:
        return f"sudo dnf install -y {' '.join(self.packages)} {' '.join(self.flags)}".strip()


@dataclass(frozen=True)
class AptPackage(Package, type='apt'):
    packages: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def create(cls, name: str, item: dict, platform: str) -> list[Package]:
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

    def print_package(self) -> str:
        return f"sudo apt-get install -y {' '.join(self.packages)} {' '.join(self.flags)}".strip()


@dataclass(frozen=True)
class DebPackage(Package, type='deb'):
    packages: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def create(cls, name: str, item: dict, platform: str) -> list[Package]:
        if platform not in ['ubuntu', 'debian']:
            return []

        packages = create_packages_list(item, name)
        pre_install, post_install, deps = create_common_package_fields(name, item, platform)
        flags = item.get('flags', [])

        return [
            *deps.values(),
            DebPackage(
                packages=tuple(packages),
                pre_install=tuple(pre_install),
                post_install=tuple(post_install),
                flags=tuple(flags),
                dependencies=tuple(deps.keys()),
            )
        ]

    def print_package(self) -> str:
        lines = []
        for pkg in self.packages:
            lines.append(f"TMP_FILE=$(mktemp)")
            lines.append(f"wget -O $TMP_FILE {pkg}")
            lines.append(f"sudo apt-get install -y $TMP_FILE {' '.join(self.flags)}")
            lines.append(f"rm $TMP_FILE")
        return "\n".join(lines).strip()


@dataclass(frozen=True)
class SnapPackage(Package, type='snapd'):
    packages: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def create(cls, name: str, item: dict, platform: str) -> list[Package]:
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

    def print_package(self) -> str:
        return f"sudo snap install {' '.join(self.packages)} {' '.join(self.flags)}".strip()


@dataclass(frozen=True)
class FlatpakPackage(Package, type='flatpak'):
    remote: str = field(default="flathub")
    packages: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def create(cls, name: str, item: dict, platform: str) -> list[Package]:
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

    def print_package(self) -> str:
        return f"flatpak install -y {self.remote} {' '.join(self.packages)} {' '.join(self.flags)}".strip()


@dataclass(frozen=True)
class TarPackage(Package, type='tarball'):
    url: str = field(default="")
    sudo: bool = field(default=False)
    destination: str = field(default="")

    @classmethod
    def create(cls, name: str, item: dict, platform: str) -> list[Package]:
        url = item.get('url')
        destination = item.get('destination')
        sudo = item.get('sudo', False)

        if not url or not destination:
            return [UndefinedPackage(name=name)]

        pre_install, post_install, deps = create_common_package_fields(name, item, platform)

        return [
            *deps.values(),
            TarPackage(
                url=url,
                destination=destination,
                sudo=sudo,
                pre_install=tuple(pre_install),
                post_install=tuple(post_install),
                dependencies=tuple(deps.keys()),
            )
        ]

    def print_package(self) -> str:
        return f"curl -fsSL \"{self.url}\" | {'sudo ' if self.sudo else ''}tar xzvC {self.destination}"


@dataclass(frozen=True)
class GitHubPackage(Package, type='github'):
    repository: str = field(default="")
    install: str = field(default="")

    @classmethod
    def create(cls, name: str, item: dict, platform: str) -> list[Package]:
        repository = item.get('repository')
        install = item.get('install', "")

        if not repository or not install:
            return [UndefinedPackage(name=name)]

        pre_install, post_install, deps = create_common_package_fields(name, item, platform)

        return [
            *deps.values(),
            GitHubPackage(
                repository=repository,
                install=install,
                pre_install=tuple(pre_install),
                post_install=tuple(post_install),
                dependencies=tuple(deps.keys()),
            )
        ]

    def print_package(self) -> str:
        lines = []
        lines.append(f"TMP_DIR=$(mktemp -d)")
        lines.append(f"git clone https://github.com/{self.repository}.git $TMP_DIR")
        lines.append(f"(")
        lines.append(f"  cd $TMP_DIR")
        for line in self.install.splitlines():
            lines.append(f"  {line}")
        lines.append(f")")
        lines.append(f"rm -rf $TMP_DIR")
        return "\n".join(lines).strip()


@dataclass(frozen=True)
class UndefinedPackage(Package):
    name: str = field(default="undefined")

    @classmethod
    def create(cls, name: str, item: dict, platform: str) -> list[Package]:
        return [UndefinedPackage(name=name)]

    def print_package(self) -> str:
        return f"# TODO: Add installation command for package: {self.name}"

    def resolve(self, all_packages: dict[str, list[Package]]) -> list[Package]:
        return all_packages.get(self.name, super().resolve(all_packages))


@dataclass(frozen=True)
class Command:
    factories = {}

    def __init_subclass__(cls, *, type: str = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if type is not None:
            cls.factories[type] = cls

    @classmethod
    def create(cls, item: dict) -> Command | None:
        factory = cls.factories.get(item.get('type'))
        return factory.create(item) if factory else None

    @abstractmethod
    def print(self) -> str:
        pass


@dataclass(frozen=True)
class ShellCommand(Command, type='shell'):
    command: str

    @classmethod
    def create(cls, item: dict) -> Command:
        return ShellCommand(command=item['command'])

    def print(self) -> str:
        return self.command


@dataclass(frozen=True)
class TeeCommand(Command, type='tee'):
    content: str
    destination: str
    sudo: bool = False

    @classmethod
    def create(cls, item: dict) -> Command:
        return TeeCommand(
            content=item['content'],
            destination=item['destination'],
            sudo=item.get('sudo', False)
        )

    def print(self) -> str:
        sudo = "sudo " if self.sudo else ""
        content = self.content.removesuffix('\n').replace('\n', '" "')
        return f'printf "%s\\n" "{content}" | {sudo}tee {self.destination}'


def create_packages_list(item: dict, default: str) -> list[str]:
    if 'packages' in item:
        return item['packages']
    else:
        return [default]


def create_install_commands(commands: list | dict | str) -> list[str]:
    return [
        Command.create(
            command if isinstance(command, dict)
            else {'type': 'shell', 'command': command}
        )
        for command in (commands if isinstance(commands, list) else [commands])
    ]


def create_common_package_fields(name: str, item: dict, platform: str) -> tuple[list[Command], list[Command], dict[str, Package]]:
    pre_install = create_install_commands(item.get('pre_install', []))
    post_install = create_install_commands(item.get('post_install', []))
    deps = load_dependencies(name, item.get('depends_on', []), platform)
    return pre_install, post_install, deps


def load_package(name: str, item: dict, platform: str) -> list[Package]:
    return [
        pkg
        for pkg in Package.create(name, item, platform)
    ]


def load_dependencies(name: str, config: list[dict], platform: str) -> dict[str, Package]:
    deps: dict[str, Package] = {}

    for i, item in enumerate(config):
        if isinstance(item, str):
            deps[item] = UndefinedPackage(name=item)
            continue

        for j, pkg in enumerate(load_package(name, item, platform)):
            deps[f"__{name}_{i}_{j}"] = pkg

    return deps


def load_package_list(name: str, config: list[dict], platform: str) -> list[Package]:
    return [
        pkg
        for item in config
        for pkg in load_package(
            name,
            item if isinstance(item, dict) else {"type": item},
            platform,
        )
    ]


def load_packages(config: dict, platform: str) -> dict[str, list[Package]]:
    return {
        name: load_package_list(name, pkg_list, platform)
        for name, pkg_list in config.items()
        if len(pkg_list) > 0
    }


def sort_packages(packages: dict[str, list[Package]]) -> list[Package]:
    seen: set[Package] = set()
    return [
        resolved
        for pkg_list in packages.values()
        for pkg in pkg_list
        for resolved in pkg.resolve(packages)
        if resolved not in seen and seen.add(resolved) is None
    ]


def main(args: argparse.Namespace) -> None:
    """
    Usage: installscript.py <config.yaml> --os <os_name> [--out <output.sh>]
    """
    with open(args.config_path, 'r') as file:
        config = yaml.safe_load(file)

        packages = load_packages(config, args.os)

        lines = [
            "#!/bin/bash",
            "",
            *(pkg.print() for pkg in sort_packages(packages))
        ]

        script_content = "\n".join(lines).strip()

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
