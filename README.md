# distroscript

Generate installation scripts for various Linux distributions based on a
declarative YAML configuration file.

```txt
distroscript.py [-h] --os OS [--out OUT] config_path

Generate installation scripts from YAML config.

positional arguments:
  config_path  Path to the YAML configuration file.

options:
  -h, --help   show this help message and exit
  --os OS      Target operating system (e.g., 'ubuntu', 'fedora').
  --out OUT    Output shell script file path (optional, defaults to stdout).
```

> [!NOTE]
> For now, only `fedora` is fully supported, but I plan to add support for
> `ubuntu`, `popos` and `mint` in the future.

## Dependencies

- Ubuntu / Debian

```bash
sudo apt-get install python3 python3-pyyaml python3-jsonschema
```

- Fedora / Red Hat / CentOS

```bash
sudo dnf install python3 python3-pyyaml python3-jsonschema
```

- MacOS

```bash
brew install python3 pyyaml jsonschema
```

## Schema Validation

The configuration files are validated against a JSON Schema specification (`src/schema.json`) 
that defines the structure and constraints for all supported package types and their properties.

The validation happens automatically after reading the YAML file and before processing begins. 
If validation fails, the script will exit with a detailed error message showing:
- The path to the invalid field
- A description of what's wrong

This helps catch configuration errors early, such as:
- Missing required fields (e.g., `url` for tar packages)
- Invalid package type names
- Incorrect property types (e.g., string instead of array)
- Unsupported properties for a given package type

## Basic Usage

The YAML configuration file should defines the packages to be installed as a
key, and it's value is a list of methods to install the package in different
packaging systems.

Example:

```yaml
git:
  - type: apt
    packages:
      - git
  - type: dnf
    packages:
      - git
```

Then, when generating the installation script, the output will depend on the
`--os` argument provided.

For example, for `--os fedora`, the generated script will use `dnf` to install
`git`:

```txt
> distroscript.py --os fedora config.yaml
#!/bin/bash

sudo dnf install -y git
```

For `--os ubuntu`, it will use `apt`:

```txt
> distroscript.py --os ubuntu config.yaml
#!/bin/bash

sudo apt-get install -y git
```

## Features by Example

Below are simple examples for each major feature.

### 1. Install a package with different methods per OS

- By declaring multiple methods under the same package:

```yaml
git:
  - type: apt
    packages: [git]
  - type: dnf
    packages: [git]
```

> [!TIP]
> When `packages` is not included, the package name is assumed to be the same as the key:
>
> ```yaml
> git:
>   - type: apt
>   - type: dnf
> ```

> [!TIP]
> When declaring a simple string, it is expanded as the `type` property:
>
> ```yaml
> git:
>   - apt
>   - dnf
> ```

### 2. Add dependencies between packages

- By declaring another package:

```yaml
pip:
  - type: apt
    packages:
      - python3-pip
    depends_on:
      - zsh

zsh: [apt]
```

- By inlining the dependency as another **Package**:

```yaml
pip:
  - type: apt
    packages: [python3-pip]
    depends_on:
      - type: apt
        packages: [zsh]
```

> [!WARNING]
> If dependency is not declared, distroscript will output a TODO comment, so
> the user can manually add it to the configuration file later if needed.

### 3. Run commands before or after install

- All packages could define `pre_install` and `post_install` steps as a list
  of **Commands** to be executed before or after the installation.

```yaml
zsh:
  - type: apt
    pre_install: [...]
    post_install: [...]
```

- Type `shell` inlines the content into the destination script:

```yml
zsh:
  - type: apt
    post_install:
      - type: shell
        content: |
          chsh -s "$(which zsh)" "$USER"
```

> [!TIP]
> It's the default in case we provide a simple string:
>
> ```yaml
> zsh:
>   - type: apt
>     post_install: |
>       chsh -s "$(which zsh)" "$USER"
> ```

- Type `tee` writes content to a file, useful to add desktop entries or config files:

```yaml
kazam:
  - type: pip
    post_install:
      - type: tee
        destination: "$HOME/.local/share/applications/kazam.desktop"
        content: |
          [Desktop Entry]
          Name=Kazam
          Exec=kazam
          ...
```

> [!TIP]
> By default, it overwrites the file, but if `append: true` is set, it appends
> to the file so existing content is preserved:
>
> ```yaml
> zsh:
>   - type: apt
>     post_install:
>       - type: tee
>         destination: "$HOME/.zshrc"
>         append: true
>         content: |
>           # pip
>           export PATH="$HOME/.local/bin:$PATH"
> ```

> [!TIP]
> You can also specify `sudo: true` to write the file to a destination that
> requires elevated permissions:
>
> ```yaml
> dnf-automatic:
>   - type: dnf
>     post_install:
>       - type: tee
>         destination: /etc/dnf/automatic.conf
>         sudo: true
>         content: |
>           [commands]
>           apply_updates=True
> ```

> [!TIP]
> You can specify `mkdir: true` to create the destination directory before writing
> the file:
>
> ```yaml
> kazam:
>   - type: pip
>     post_install:
>       - type: tee
>         destination: "$HOME/.local/share/applications/kazam.desktop"
>         mkdir: true
>         content: |
>           [Desktop Entry]
>           Name=Kazam
>           Exec=kazam
>           ...
> ```

### 4. Install from Flatpak, Snap, Pip, Tar, Zip, GitHub, File, Shell, or AppImage

For these types, if specified `--os` does not include the required command, it
will be included as a dependency, as if we declared it in `depends_on` as
a single string.

This allows the user to provide an installation method for the package manager
itself if needed.

**Flatpak:**

```yaml
kdenlive:
  - type: flatpak
    packages: [org.kde.kdenlive]
    # depends_on: [flatpak] # Added implicitly if running on an OS without flatpak pre-installed
```

**Snap:**

```yaml
code:
  - type: snapd
    packages: [code]
    classic: true # Optional: adds the --classic flag
    # depends_on: [snapd] # Added implicitly if running on an OS without snapd pre-installed
```

**Pip:**

```yaml
yt-dlp:
  - type: pip
    packages: ["yt-dlp[default]"]
    # depends_on: [pip] # Added implicitly if running on an OS without pip pre-installed
```

**Tar:**

```yaml
go:
  - type: tar
    url: "https://go.dev/dl/go1.20.5.linux-amd64.tar.gz"
    destination: /usr/local
    sudo: true # Optional: use sudo to extract to destination
```

**Zip:**

```yaml
jetbrains-nf:
  - type: zip
    url: "https://github.com/ryanoasis/nerd-fonts/releases/download/v3.0.2/JetBrainsMono.zip"
    destination: /usr/share/fonts/JetBrainsMonoNerdFont
    sudo: true # Optional: use sudo to extract to destination
```

**GitHub:**

```yaml
cspec:
  - type: github
    repository: mumuki/cspec
    install: |
      make
      sudo make install
```

**File:**

```yaml
doctest:
  - type: file
    url: https://raw.githubusercontent.com/doctest/doctest/v2.4.12/doctest/doctest.h
    destination: /usr/local/include/doctest/doctest.h
    sudo: true # Optional: use sudo to write to destination
    silent: true # Optional: suppress output after download
    executable: false # Optional: make the file executable after download
```

**Shell:**

- By providing an url:

```yaml
rust:
  - type: shell
    url: https://sh.rustup.rs
    shell: bash # Optional: specify the shell to use (default: bash).
                # Will be added as a dependency if not preinstalled in the target OS.
```

- By providing an inline script:

```yaml
oh-my-zsh:
  - type: shell
    script: |
      sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
    shell: zsh # Optional: specify the shell to use (default: bash).
               # Will be added as a dependency if not preinstalled in the target OS.
```

**AppImage:**

```yaml
duckstation:
  - type: appimage
    url: https://github.com/stenzek/duckstation/releases/download/latest/DuckStation-x64.AppImage
    name: DuckStation
    icon_name: org.duckstation.DuckStation
    categories:
      - Game
      - Emulator
```

AppImages are downloaded to `$HOME/.local/bin/`, a desktop entry is created in
`$HOME/.local/share/applications/`, and icons are extracted automatically when `icon_name` is specified.

> [!NOTE]
> AppImage packages require the `url` field. The `name`, `icon_name`, and `categories` fields are optional.
> The `name` field defaults to the package name, `icon_name` enables desktop icon extraction when provided,
> and `categories` defaults to "Application".

### 5. Use custom flags for package managers

```yaml
gh:
  - type: dnf
    flags:
      - "--repo gh-cli"
    pre_install: |
      sudo dnf config-manager addrepo --from-repofile=https://cli.github.com/packages/rpm/gh-cli.repo

gleam:
  - type: dnf
    copr: frostyx/gleam
    pre_install: |
      sudo dnf copr enable frostyx/gleam -y
```

> [!TIP]
> For `dnf`, you can also specify `repo`, `repofile` and/or `copr` properties:
>
> ```yaml
> gh:
>   - type: dnf
>     repo: gh-cli
>     repofile: https://cli.github.com/packages/rpm/gh-cli.repo
>
> gleam:
>   - type: dnf
>     copr: frostyx/gleam
> ```

### 6. Add desktop entries or config files

```yaml
kazam:
  - type: pip
    post_install:
      - type: tee
        destination: "$HOME/.local/share/applications/kazam.desktop"
        content: |
          [Desktop Entry]
          Name=Kazam
          Exec=kazam
          ...
```

### 7. Merging multiple packages to a single install command

If multiple packages use the same installation method and are not codependant,
they will be merged into a single command to optimize the installation process.

```yaml
jq: [apt]

htop: [apt]

zsh: [apt]

pip:
  - type: apt
    packages: [python3-pip]
    depends_on: [zsh]
```

Output:

```bash
#!/bin/bash

sudo apt-get install -y jq htop zsh

sudo apt-get install -y python3-pip
```

### 8. Combine everything for complex setups

```yaml
docker:
  - type: dnf
    packages:
      - docker
      - docker-ce
      - docker-ce-cli
      - containerd.io
      - docker-buildx-plugin
      - docker-compose-plugin
    repofile: https://download.docker.com/linux/fedora/docker-ce.repo
    depends_on:
      - type: dnf
        packages: [dnf5-plugins]
    post_install: |
      sudo systemctl enable --now docker
      sudo groupadd -f docker
      sudo usermod -aG docker "$USER"
```

Output:

```bash
#!/bin/bash

sudo dnf install -y dnf5-plugins docker docker-ce docker-ce-cli \
  containerd.io docker-buildx-plugin docker-compose-plugin

sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo

sudo systemctl enable --now docker
sudo groupadd -f docker
sudo usermod -aG docker "$USER"
```

## License

This project is licensed under the BSD 3-Clause License. See the
[LICENSE](LICENSE) file for details.

## Author

Agustin Ranieri - [@RaniAgus](https://github.com/RaniAgus)
