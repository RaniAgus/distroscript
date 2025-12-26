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

class Package(ABC):
    @abstractmethod
    def install_command(self) -> str:
        pass


@dataclass
class DnfPackage(Package):
  packages: list[str] = field(default_factory=list)

  def install_command(self) -> str:
      return f"sudo dnf install -y {' '.join(self.packages)}"


@dataclass
class AptPackage(Package):
  packages: list[str] = field(default_factory=list)

  def install_command(self) -> str:
      return f"sudo apt-get install -y {' '.join(self.packages)}"


def create_dnf_package(item: dict, platform: str) -> list[DnfPackage]:
    if platform not in ['fedora', 'centos', 'rhel']:
        return []

    return [DnfPackage(packages=item['packages'])]


def create_apt_package(item: dict, platform: str) -> list[AptPackage]:
    if platform not in ['ubuntu', 'debian']:
        return []

    return [AptPackage(packages=item['packages'])]


def load_package(config: list[dict], platform: str) -> list[Package]:
    package_list: list[Package] = []

    for item in config:
        if item.get('type') == 'dnf':
            for pkg in create_dnf_package(item, platform):
                package_list.append(pkg)

        elif item.get('type') == 'apt':
            for pkg in create_apt_package(item, platform):
                package_list.append(pkg)

        if len(package_list) > 0:
            break

    return package_list


def load_packages(config: dict, platform: str) -> dict[str, list[Package]]:
    packages: dict[str, list[Package]] = {}

    for name, pkg_list in config.items():
        packages[name] = load_package(pkg_list, platform)

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

    script_content = "#!/bin/bash\n"

    for _, pkgs in packages.items():
        for pkg in pkgs:
            script_content += f"\n{pkg.install_command()}"

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
