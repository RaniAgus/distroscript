#!/usr/bin/env python3
"""
Install Script Generator

Generates shell scripts to install packages on Fedora (dnf) or Ubuntu (apt)
using a declarative YAML file.
"""

import yaml
import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Type, Optional


class InstallScript(ABC):
    """Abstract base class for install scripts (pre/post install)"""

    @abstractmethod
    def generate(self) -> List[str]:
        """Generate shell commands for this script"""
        pass


class BashScript(InstallScript):
    """Bash script execution"""

    def __init__(self, script: str):
        self.script = script

    def generate(self) -> List[str]:
        return [self.script]


class TeeScript(InstallScript):
    """Write content to a file using tee"""

    def __init__(self, destination: str, content: str, sudo: bool = False):
        self.destination = destination
        self.content = content
        self.sudo = sudo

    def generate(self) -> List[str]:
        lines = self.content.split('\n')
        printf_cmd = "printf '%s\\n' " + ' '.join(f"'{line}'" for line in lines)
        tee_cmd = f'{"sudo " if self.sudo else ""}tee {self.destination}'
        return [f'{printf_cmd} | {tee_cmd}']


class ScriptFactory:
    """Factory for creating install script objects"""

    _script_types: Dict[str, Type[InstallScript]] = {
        'bash': BashScript,
        'tee': TeeScript,
    }

    @classmethod
    def register_script_type(cls, type_name: str, script_class: Type[InstallScript]):
        cls._script_types[type_name] = script_class

    @classmethod
    def create_script(cls, config: Any) -> InstallScript:
        if isinstance(config, str):
            return BashScript(config)

        script_type = config.get('type', 'bash')
        if script_type not in cls._script_types:
            raise ValueError(f"Unknown script type: {script_type}")

        if script_type == 'bash':
            return BashScript(config['script'])
        elif script_type == 'tee':
            return TeeScript(
                config['destination'],
                config['content'],
                config.get('sudo', False)
            )
        else:
            # For other types, assume they have a constructor that takes the config
            return cls._script_types[script_type](**config)


class Package(ABC):
    """Abstract base class for packages"""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.dependencies: List[str] = config.get('depends_on', [])
        self.pre_install_scripts: List[InstallScript] = []
        self.post_install_scripts: List[InstallScript] = []

        # Parse pre_install scripts
        if 'pre_install' in config:
            scripts = config['pre_install']
            if not isinstance(scripts, list):
                scripts = [scripts]
            for script_config in scripts:
                script = ScriptFactory.create_script(script_config)
                self.pre_install_scripts.append(script)

        # Parse post_install scripts
        if 'post_install' in config:
            scripts = config['post_install']
            if not isinstance(scripts, list):
                scripts = [scripts]
            for script_config in scripts:
                script = ScriptFactory.create_script(script_config)
                self.post_install_scripts.append(script)

        # Add implicit dependencies
        self.dependencies.extend(self.get_implicit_dependencies())

    def get_implicit_dependencies(self) -> List[str]:
        """Get implicit dependencies for this package type"""
        return []

    @abstractmethod
    def generate_install_commands(self, os_type: str) -> List[str]:
        """Generate the shell commands for installing this package"""
        pass

    @abstractmethod
    def is_available_for_os(self, os_type: str) -> bool:
        """Check if this package type is available for the given OS"""
        pass

    def get_dependencies(self) -> List[str]:
        """Get list of dependencies"""
        return self.dependencies

    def generate_pre_install_commands(self) -> List[str]:
        commands = []
        for script in self.pre_install_scripts:
            commands.extend(script.generate())
        return commands

    def generate_post_install_commands(self) -> List[str]:
        commands = []
        for script in self.post_install_scripts:
            commands.extend(script.generate())
        return commands

    def write_script_file(self, os_type: str):
        """Write script file if applicable. Override in subclasses."""
        pass


class DnfPackage(Package):
    """DNF package for Fedora"""

    def generate_install_commands(self, os_type: str) -> List[str]:
        if os_type != 'fedora':
            return []

        commands = []

        # Handle repo configuration
        if 'repo' in self.config:
            repo = self.config['repo']
            if 'file' in repo:
                commands.append(f'sudo dnf config-manager --add-repo {repo["file"]}')
            elif 'name' in repo and 'file' in repo:
                # For gh-cli style
                commands.append(f'sudo dnf config-manager --add-repo {repo["file"]}')

        packages = self.config.get('packages', [self.name])
        commands.append(f'sudo dnf install -y {" ".join(packages)}')
        return commands

    def is_available_for_os(self, os_type: str) -> bool:
        return os_type == 'fedora'


class AptPackage(Package):
    """APT package for Ubuntu"""

    def generate_install_commands(self, os_type: str) -> List[str]:
        if os_type != 'ubuntu':
            return []
        packages = self.config.get('packages', [self.name])
        return [f'sudo apt install -y {" ".join(packages)}']

    def is_available_for_os(self, os_type: str) -> bool:
        return os_type == 'ubuntu'


class SnapdPackage(Package):
    """Snapd package or snap package"""

    def generate_install_commands(self, os_type: str) -> List[str]:
        if self.name == 'snapd':
            # Install snapd itself
            packages = self.config.get('packages', [self.name])
            if os_type == 'fedora':
                return [f'sudo dnf install -y {" ".join(packages)}']
            elif os_type == 'ubuntu':
                return [f'sudo apt install -y {" ".join(packages)}']
            return []
        else:
            # Install snap package
            packages = self.config.get('packages', [self.name])
            classic = self.config.get('classic', False)
            flag = ' --classic' if classic else ''
            commands = []
            for pkg in packages:
                commands.append(f'sudo snap install {pkg}{flag}')
            return commands

    def is_available_for_os(self, os_type: str) -> bool:
        return os_type in ['fedora', 'ubuntu']

    def get_implicit_dependencies(self) -> List[str]:
        if self.name != 'snapd':
            return ['snapd']

        raise ValueError("snapd cannot depend on snapd")


class PipPackage(Package):
    """Pip package"""

    def generate_install_commands(self, os_type: str) -> List[str]:
        packages = self.config.get('packages', [self.name])
        return [f'pip3 install {" ".join(packages)}']

    def is_available_for_os(self, os_type: str) -> bool:
        return True

    def get_implicit_dependencies(self) -> List[str]:
        if self.name != 'pip':
            return ['pip']

        raise ValueError("pip cannot depend on pip")


class DebPackage(Package):
    """DEB package for Ubuntu"""

    def generate_install_commands(self, os_type: str) -> List[str]:
        if os_type != 'ubuntu':
            return []
        packages = self.config.get('packages', [])
        commands = []
        for pkg_url in packages:
            commands.extend([
                f'TEMP_FILE=$(mktemp)',
                f'curl -o "$TEMP_FILE" {pkg_url}',
                f'sudo apt install "$TEMP_FILE"',
                f'rm "$TEMP_FILE"'
            ])
        return commands

    def is_available_for_os(self, os_type: str) -> bool:
        return os_type == 'ubuntu'


class FlatpakPackage(Package):
    """Flatpak package"""

    def generate_install_commands(self, os_type: str) -> List[str]:
        packages = self.config.get('packages', [self.name])
        commands = []
        for pkg in packages:
            commands.append(f'flatpak install -y {pkg}')
        return commands

    def is_available_for_os(self, os_type: str) -> bool:
        return True


class GithubPackage(Package):
    """GitHub repository package"""

    def generate_install_commands(self, os_type: str) -> List[str]:
        repo = self.config['repo']
        install_script = self.config['install_script']
        commands = [
            f'git clone https://github.com/{repo}.git {self.name}',
            f'(',
            f'  cd {self.name}',
        ]
        for line in install_script.split('\n'):
            line = line.strip()
            if line:
                commands.append(f'  {line}')
        commands.extend([
            f')',
            f'rm -rf {self.name}'
        ])
        return commands

    def is_available_for_os(self, os_type: str) -> bool:
        return True


class FilePackage(Package):
    """File download package"""

    def generate_install_commands(self, os_type: str) -> List[str]:
        url = self.config['url']
        destination = self.config['destination']
        sudo = self.config.get('sudo', False)
        tee_cmd = f'{"sudo " if sudo else ""}tee {destination}'
        return [f'curl -fsSL "{url}" | {tee_cmd}']

    def is_available_for_os(self, os_type: str) -> bool:
        return True


class TarballPackage(Package):
    """Tarball extraction package"""

    def generate_install_commands(self, os_type: str) -> List[str]:
        url = self.config['url']
        destination = self.config['destination']
        sudo = self.config.get('sudo', False)
        tar_cmd = f'{"sudo " if sudo else ""}tar xvzC "{destination}"'
        return [f'curl -fsSL "{url}" | {tar_cmd}']

    def is_available_for_os(self, os_type: str) -> bool:
        return True


class BashPackage(Package):
    """Bash script package"""

    def generate_install_commands(self, os_type: str) -> List[str]:
        # This will be handled in the generator by writing the script file
        return [f'./{self.name}.sh']

    def is_available_for_os(self, os_type: str) -> bool:
        return True

    def write_script_file(self, os_type: str):
        script_content = f'#!/bin/bash\n\n{self.config["script"]}'
        with open(f'{self.name}.sh', 'w') as f:
            f.write(script_content)
        os.chmod(f'{self.name}.sh', 0o755)


class ZshPackage(Package):
    """Zsh script package"""

    def generate_install_commands(self, os_type: str) -> List[str]:
        # This will be handled in the generator by writing the script file
        return [f'zsh ./{self.name}.zsh']

    def is_available_for_os(self, os_type: str) -> bool:
        return True

    def get_implicit_dependencies(self) -> List[str]:
        return ['zsh']

    def write_script_file(self, os_type: str):
        script_content = f'#!/bin/zsh\n\n{self.config["script"]}'
        with open(f'{self.name}.zsh', 'w') as f:
            f.write(script_content)
        os.chmod(f'{self.name}.zsh', 0o755)


class PackageFactory:
    """Factory for creating package objects"""

    _package_types: Dict[str, Type[Package]] = {
        'dnf': DnfPackage,
        'apt': AptPackage,
        'snapd': SnapdPackage,
        'pip': PipPackage,
        'deb': DebPackage,
        'flatpak': FlatpakPackage,
        'github': GithubPackage,
        'file': FilePackage,
        'tarball': TarballPackage,
        'bash': BashPackage,
        'zsh': ZshPackage,
    }

    @classmethod
    def register_package_type(cls, type_name: str, package_class: Type[Package]):
        cls._package_types[type_name] = package_class

    @classmethod
    def create_package(cls, name: str, config: Dict[str, Any]) -> Package:
        if isinstance(config, str):
            config = {'type': config}

        package_type = config.get('type')
        if package_type is None:
            # Assume type is the package name
            package_type = name
            config['type'] = package_type

        if package_type not in cls._package_types:
            raise ValueError(f"Unknown package type: {package_type}")

        return cls._package_types[package_type](name, config)


class InstallScriptGenerator:
    """Main generator class"""

    def __init__(self):
        self.packages: Dict[str, List[Package]] = {}  # name -> list of package variants

    def load_yaml(self, yaml_file: str):
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f)

        for name, methods in data.items():
            if not isinstance(methods, list):
                methods = [methods]

            package_variants = []
            for method in methods:
                if isinstance(method, str):
                    method = {'type': method}
                package = PackageFactory.create_package(name, method)
                package_variants.append(package)

            self.packages[name] = package_variants

    def _get_package_for_os(self, name: str, os_type: str) -> Optional[Package]:
        """Get the best package variant for the given OS"""
        if name not in self.packages:
            return None

        for package in self.packages[name]:
            if package.is_available_for_os(os_type):
                return package

        return None

    def _write_scripts(self, os_type: str):
        """Write script files for packages that need them"""
        for name, variants in self.packages.items():
            for package in variants:
                if package.is_available_for_os(os_type):
                    package.write_script_file(os_type)

    def generate_script(self, os_type: str) -> str:
        if os_type not in ['fedora', 'ubuntu']:
            raise ValueError("OS type must be 'fedora' or 'ubuntu'")

        # Write scripts first
        self._write_scripts(os_type)

        commands = []
        installed = set()

        def install_package(package_name: str):
            if package_name in installed:
                return

            package = self._get_package_for_os(package_name, os_type)
            if not package:
                return

            # Handle dependencies
            for dep in package.get_dependencies():
                if isinstance(dep, str):
                    dep_package = self._get_package_for_os(dep, os_type)
                    if dep_package:
                        install_package(dep)
                    else:
                        # External dependency check
                        commands.append(f'which {dep} || {{ echo "Warning: {dep} not found"; exit 1; }}')
                elif isinstance(dep, dict):
                    # Inline package definition
                    dep_config = dep
                    if 'type' not in dep_config:
                        # If it's a string, assume type
                        dep_config = {'type': dep}
                    temp_package = PackageFactory.create_package(f"inline_dep_{len(commands)}", dep_config)
                    if temp_package.is_available_for_os(os_type):
                        # Install inline
                        pre_cmds = temp_package.generate_pre_install_commands()
                        commands.extend(pre_cmds)
                        install_cmds = temp_package.generate_install_commands(os_type)
                        commands.extend(install_cmds)
                        post_cmds = temp_package.generate_post_install_commands()
                        commands.extend(post_cmds)

            # Pre-install scripts
            pre_cmds = package.generate_pre_install_commands()
            if pre_cmds:
                commands.extend(pre_cmds)

            # Install commands
            install_cmds = package.generate_install_commands(os_type)
            if install_cmds:
                commands.extend(install_cmds)

            # Post-install scripts
            post_cmds = package.generate_post_install_commands()
            if post_cmds:
                commands.extend(post_cmds)

            installed.add(package_name)

        # Install all packages that are available for this OS
        for name in self.packages.keys():
            if self._get_package_for_os(name, os_type):
                install_package(name)

        return '\n'.join(commands)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Generate install scripts from YAML')
    parser.add_argument('yaml_file', help='Path to the YAML configuration file')
    parser.add_argument('--os', choices=['fedora', 'ubuntu'], required=True,
                       help='Target operating system')
    parser.add_argument('--output', '-o', help='Output file (default: stdout)')

    args = parser.parse_args()

    generator = InstallScriptGenerator()
    generator.load_yaml(args.yaml_file)
    script = generator.generate_script(args.os)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(script)
        print(f"Script written to {args.output}")
    else:
        print(script)


if __name__ == '__main__':
    main()
