#!/bin/bash

bash -c "$(curl -fsSL "https://sh.rustup.rs")"

sudo apt-get install -y zsh

sh -c "$(wget "https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh" -O -)"
chsh -s $(which zsh)

zsh -c "$(curl -fsSL "https://get.sdkman.io")"

bash -c "$(curl -fsSL "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/install_manual.sh")"
