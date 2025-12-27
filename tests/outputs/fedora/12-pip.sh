#!/bin/bash

sudo dnf install -y python3-pip

sudo dnf install -y make cmake gcc gcc-c++

sudo dnf install -y python3-wheel zlib-devel

pip install -U kazam

printf "%s\n" "[Desktop Entry]" "Name=Kazam" "Comment=Screen recording tool" "Exec=kazam" "Icon=kazam" "Terminal=false" "Type=Application" "Categories=AudioVideo;Recorder;" "StartupNotify=true" | tee ~/.local/share/applications/kazam.desktop

pip install -U yt-dlp[default]
