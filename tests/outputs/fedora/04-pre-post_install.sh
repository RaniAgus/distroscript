#!/bin/bash

echo "Preparing to install htop dnf package..."

sudo dnf install -y htop

printf "%s\n" "htop installation complete." "timestamp=$(date)" | sudo tee /tmp/htop_install.log
