# Install Script Generator Spec

## Overview

This tool generates shell scripts to install packages on Fedora (dnf) or Ubuntu
(apt) using a declarative YAML file. It selects the best installation method per
package and OS, handles dependencies, and respects special rules for certain
types.

## Input

- **YAML file** describing packages and installation methods (see install.yml).
- Each package can have multiple install methods (dnf, apt, snapd, pip, etc.).
- Each method is an object or a string (string means just the type).
- Only Fedora (dnf) and Ubuntu (apt) are supported.
- Types `snapd`, `pip`, `zsh` are only available if their own package is
  specified in the file.
- Each package can have a `depends_on` list (dependencies must be installed
  first, and cannot be grouped with the main package in a single command).
- If `depends_on` item is a string, check if it’s a package in the file.
- If a dependency is not present in the YAML, a "which" check should be output to the resulting script, and a warning should be printed.
- If a package item is a string, it defaults to the "type" property.
- If no `packages` list is specified, use the package name as the package name.

## Output

- For a given OS (fedora/ubuntu), generate a shell script that installs all
  packages using the most appropriate method.
- Respect `depends_on`: install dependencies first, in separate commands.
- Do not group packages with dependencies in the same command.
- Only use `snapd`, `pip`, `zsh` if their own package is present.
- For each package, select the best method for the OS.

## Example

### Input YAML (simplified)

```yaml
snapd:
  - apt
  - dnf

pip:
  - dnf

1password:
  - dnf
    packages: [https://downloads.1password.com/linux/rpm/stable/x86_64/1password-latest.rpm]
    post_install: echo "done"
1password-cli:
  - dnf
    depends_on:
      - 1password
```

#### Expected Output (fedora)

```bash
# Install snapd (required for snapd type), pip (required for pip type) and 1password
sudo dnf install -y \
  snapd \
  python3-pip \
  "https://downloads.1password.com/linux/rpm/stable/x86_64/1password-latest.rpm"

# Run post_install scripts
echo "done"

# Install 1password-cli (depends_on: 1password, so install separately)
sudo dnf install -y 1password-cli
```

#### Expected Output (ubuntu)

```bash
# Install snapd (required for snapd type)
sudo apt install -y \
  snapd

```

## Additional Types and Their Shell Script Translations

### 1. **deb**

- For Ubuntu only.
- For each package URL:

  ```bash
  TEMP_FILE=$(mktemp)
  curl -o "$TEMP_FILE" <package_url>
  sudo apt install "$TEMP_FILE"
  rm "$TEMP_FILE"
  ```

#### Example deb

- Input:

  ```yaml
  mypackage:
    - type: deb
      packages: [https://example.com/mypackage.deb]
  ```

- Output:

  ```bash
  TEMP_FILE=$(mktemp)
  curl -o "$TEMP_FILE" https://example.com/mypackage.deb
  sudo apt install "$TEMP_FILE"
  rm "$TEMP_FILE"
  ```

### 2. **flatpak**

- For both Fedora and Ubuntu (if flatpak is available).
- For each package:

  ```bash
  flatpak install -y <package>
  ```

#### Example flatpak

- Input:

  ```yaml
  myflatpak:
    - type: flatpak
      packages: [com.example.MyApp]
  ```

- Output:

  ```bash
  flatpak install -y com.example.MyApp
  ```

### 3. **github**

- For both Fedora and Ubuntu.
- For each github repo:

  ```bash
  git clone https://github.com/<repo>.git <package_name>
  (
    cd <package_name>
    <install_script>
  )
  rm -rf <package_name>
  ```

  - The cloned directory should always match the YAML key (package name).

#### Example github

- Input:

  ```yaml
  mytools:
    - type: github
      repo: user/mytool
      install_script: |
        make
        sudo make install
  ```

- Output:

  ```bash
  git clone https://github.com/user/mytool.git mytools
  (
    cd mytools
    make
    sudo make install
  )
  rm -rf mytools
  ```

### 4. **file**

- For both Fedora and Ubuntu.
- For each file:

  ```bash
  curl -fsSL "<url>" | sudo tee <destination>
  ```

- If `sudo: true` is not specified, omit `sudo`.

#### Example file

- Input:

  ```yaml
  myconfig:
    - type: file
      url: https://example.com/config.conf
      destination: /etc/myconfig.conf
      sudo: true
  ```

- Output:

  ```bash
  curl -fsSL "https://example.com/config.conf" | sudo tee /etc/myconfig.conf
  ```

### 5. **tarball**

- For both Fedora and Ubuntu.
- For each tarball:

  ```bash
  curl -fsSL "<url>" | sudo tar xvzC "<destination>"
  ```

  - If `sudo: true` is not specified, omit `sudo`.

#### Example tarball

- Input:

  ```yaml
  myapp:
    - type: tarball
      url: https://example.com/myapp.tar.gz
      destination: /opt/myapp
      sudo: true
  ```

- Output:

  ```bash
  curl -fsSL "https://example.com/myapp.tar.gz" | sudo tar xvzC "/opt/myapp"
  ```

### 6. **bash**

- For both Fedora and Ubuntu.
- For each script, a new script file should be generated with /bin/bash shebang, and it should be invoked from the main script:

  ```bash
  #!/bin/bash

  <script>
  ```

  - The script file name should match the package name (e.g., `<package_name>.sh`).

#### Example bash

- Input:

  ```yaml
  myinstaller:
    - type: bash
      script: >
        curl -s https://example.com/install.sh | bash
  ```

- Output:

  ```bash
  #!/bin/bash

  curl -s https://example.com/install.sh | bash
  ```

  - The main script will invoke `./myinstaller.sh`

## Pre/Post Install Scripts

Packages can specify `pre_install` and `post_install` fields to run scripts
before or after installation.

- Each entry in `pre_install` or `post_install` can be:
  - An object with a `type` (e.g., `bash`, `tee`, etc.) and associated fields.
  - A string, which is assumed to be a Bash script (equivalent to
    `{ type: bash, script: <string> }`).
- The `tee` type is supported for writing configuration files.
- If multiple entries are provided (as a list), they should be executed in the order listed.
- All pre_install scripts are run before the main install command for the
  package.
- All post_install scripts are run after the main install command for the
  package.

### Example tee post_install

```yaml
mypackage:
  - type: apt
    post_install:
      - type: tee
        destination: /etc/myconfig.conf
        content: |
          [section]
          key=value
        sudo: true
```

Output:

```bash
sudo apt install -y mypackage

printf '%s\n' '[section]' 'key=value' | sudo tee /etc/myconfig.conf
```

### Example bash pre_install

```yaml
mypackage:
  - type: apt
    pre_install: |
      echo "Preparing to install mypackage"
```

Output:

```bash
echo "Preparing to install mypackage"

sudo apt install -y mypackage
```

### Example bash pre_install (expanded form)

```yaml
mypackage:
  - type: apt
    pre_install:
      - type: bash
        script: |
          echo "Preparing to install mypackage"
```

Output:

```bash
echo "Preparing to install mypackage"
sudo apt install -y mypackage
```
