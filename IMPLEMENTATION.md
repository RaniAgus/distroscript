# Implementation Design for Install Script Generator

## Overview

This document outlines an object-oriented design in Python to implement the
Install Script Generator spec. The design follows SOLID principles to ensure the
code is clean, maintainable, and extensible. New package types and pre/post
install script types can be added by implementing interfaces or extending base
classes without modifying existing code.

## Architecture

The system uses a modular architecture with clear separation of concerns:

- **Parser**: Reads and parses the YAML configuration
- **Package System**: Handles different installation methods
- **Script System**: Manages pre/post install scripts
- **Generator**: Orchestrates the script generation process

## Core Classes and Interfaces

### 1. Package System

#### Abstract Base Class: `Package`

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class Package(ABC):
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.dependencies: List[str] = config.get('depends_on', [])
        self.pre_install_scripts: List[InstallScript] = []
        self.post_install_scripts: List[InstallScript] = []

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

    def add_pre_install_script(self, script: InstallScript):
        self.pre_install_scripts.append(script)

    def add_post_install_script(self, script: InstallScript):
        self.post_install_scripts.append(script)

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
```

#### Concrete Package Classes

Each package type extends the `Package` base class:

```python
class DnfPackage(Package):
    def generate_install_commands(self, os_type: str) -> List[str]:
        if os_type != 'fedora':
            return []
        packages = self.config.get('packages', [self.name])
        return [f'sudo dnf install -y {" ".join(packages)}']

    def is_available_for_os(self, os_type: str) -> bool:
        return os_type == 'fedora'

class AptPackage(Package):
    def generate_install_commands(self, os_type: str) -> List[str]:
        if os_type != 'ubuntu':
            return []
        packages = self.config.get('packages', [self.name])
        return [f'sudo apt install -y {" ".join(packages)}']

    def is_available_for_os(self, os_type: str) -> bool:
        return os_type == 'ubuntu'

class GithubPackage(Package):
    def generate_install_commands(self, os_type: str) -> List[str]:
        repo = self.config['repo']
        install_script = self.config['install_script']
        commands = [
            f'git clone https://github.com/{repo}.git {self.name}',
            f'(cd {self.name}',
        ]
        commands.extend([f'  {line}' for line in install_script.split('\n') if line.strip()])
        commands.extend([
            f')',
            f'rm -rf {self.name}'
        ])
        return commands

    def is_available_for_os(self, os_type: str) -> bool:
        return True  # Available for both OS types

class BashPackage(Package):
    def generate_install_commands(self, os_type: str) -> List[str]:
        # Generate separate script file
        script_content = f'#!/bin/bash\n\n{self.config["script"]}'
        # In actual implementation, write to file
        return [f'./{self.name}.sh']

    def is_available_for_os(self, os_type: str) -> bool:
        return True
```

### 2. Script System

#### Abstract Base Class: `InstallScript`

```python
from abc import ABC, abstractmethod

class InstallScript(ABC):
    @abstractmethod
    def generate(self) -> List[str]:
        """Generate shell commands for this script"""
        pass
```

#### Concrete Script Classes

```python
class BashScript(InstallScript):
    def __init__(self, script: str):
        self.script = script

    def generate(self) -> List[str]:
        return [self.script]

class TeeScript(InstallScript):
    def __init__(self, destination: str, content: str, sudo: bool = False):
        self.destination = destination
        self.content = content
        self.sudo = sudo

    def generate(self) -> List[str]:
        lines = self.content.split('\n')
        printf_cmd = "printf '%s\\n' " + ' '.join(f"'{line}'" for line in lines)
        tee_cmd = f'{"sudo " if self.sudo else ""}tee {self.destination}'
        return [f'{printf_cmd} | {tee_cmd}']
```

### 3. Factory Classes

#### Package Factory

```python
from typing import Dict, Any, Type

class PackageFactory:
    _package_types: Dict[str, Type[Package]] = {
        'dnf': DnfPackage,
        'apt': AptPackage,
        'github': GithubPackage,
        'bash': BashPackage,
        # Add more types here
    }

    @classmethod
    def register_package_type(cls, type_name: str, package_class: Type[Package]):
        cls._package_types[type_name] = package_class

    @classmethod
    def create_package(cls, name: str, config: Dict[str, Any]) -> Package:
        if isinstance(config, str):
            config = {'type': config}

        package_type = config.get('type')
        if package_type not in cls._package_types:
            raise ValueError(f"Unknown package type: {package_type}")

        return cls._package_types[package_type](name, config)
```

#### Script Factory

```python
class ScriptFactory:
    _script_types: Dict[str, Type[InstallScript]] = {
        'bash': BashScript,
        'tee': TeeScript,
        # Add more script types here
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
        # Handle other types
```

### 4. Main Generator Class

```python
import yaml
from typing import Dict, List, Any

class InstallScriptGenerator:
    def __init__(self):
        self.packages: Dict[str, Package] = {}

    def load_yaml(self, yaml_file: str):
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f)

        for name, methods in data.items():
            # Find the best method for each OS
            # For simplicity, assume first method is used
            method = methods[0] if methods else {}
            package = PackageFactory.create_package(name, method)

            # Add pre/post install scripts
            if 'pre_install' in method:
                scripts = method['pre_install']
                if not isinstance(scripts, list):
                    scripts = [scripts]
                for script_config in scripts:
                    script = ScriptFactory.create_script(script_config)
                    package.add_pre_install_script(script)

            if 'post_install' in method:
                scripts = method['post_install']
                if not isinstance(scripts, list):
                    scripts = [scripts]
                for script_config in scripts:
                    script = ScriptFactory.create_script(script_config)
                    package.add_post_install_script(script)

            self.packages[name] = package

    def generate_script(self, os_type: str) -> str:
        commands = []
        installed = set()

        def install_package(package: Package):
            if package.name in installed:
                return

            # Handle dependencies
            for dep in package.get_dependencies():
                if dep in self.packages:
                    install_package(self.packages[dep])
                else:
                    # External dependency check
                    commands.append(f'which {dep} || {{ echo "Warning: {dep} not found"; exit 1; }}')

            # Pre-install scripts
            commands.extend(package.generate_pre_install_commands())

            # Install commands
            install_cmds = package.generate_install_commands(os_type)
            commands.extend(install_cmds)

            # Post-install scripts
            commands.extend(package.generate_post_install_commands())

            installed.add(package.name)

        # Install all packages
        for package in self.packages.values():
            install_package(package)

        return '\n'.join(commands)
```

## SOLID Principles Compliance

### Single Responsibility Principle (SRP)

- Each class has a single, well-defined responsibility
- `Package` classes handle package installation
- `InstallScript` classes handle script generation
- `PackageFactory` and `ScriptFactory` handle object creation
- `InstallScriptGenerator` orchestrates the process

### Open/Closed Principle (OCP)

- New package types can be added by extending `Package` and registering with
  `PackageFactory`
- New script types can be added by extending `InstallScript` and registering
  with `ScriptFactory`
- Existing code doesn't need modification

### Liskov Substitution Principle (LSP)

- All `Package` subclasses can be used wherever `Package` is expected
- All `InstallScript` subclasses can be used wherever `InstallScript` is
  expected

### Interface Segregation Principle (ISP)

- `Package` and `InstallScript` interfaces are focused and minimal
- Clients only depend on methods they use

### Dependency Inversion Principle (DIP)

- High-level modules (`InstallScriptGenerator`) don't depend on low-level
  modules
- Both depend on abstractions (`Package`, `InstallScript`)
- Factories provide dependency injection

## Usage Example

```python
generator = InstallScriptGenerator()
generator.load_yaml('install.yml')
script = generator.generate_script('fedora')
print(script)
```

## Extensibility

To add a new package type (e.g., `snap`):

```python
class SnapPackage(Package):
    def generate_install_commands(self, os_type: str) -> List[str]:
        packages = self.config.get('packages', [self.name])
        return [f'sudo snap install {" ".join(packages)}']

    def is_available_for_os(self, os_type: str) -> bool:
        return True

PackageFactory.register_package_type('snap', SnapPackage)
```

To add a new script type (e.g., `wget`):

```python
class WgetScript(InstallScript):
    def __init__(self, url: str, destination: str):
        self.url = url
        self.destination = destination

    def generate(self) -> List[str]:
        return [f'wget -O {self.destination} {self.url}']

ScriptFactory.register_script_type('wget', WgetScript)
```

This design ensures the system remains clean, maintainable, and easily
extensible while following SOLID principles.
