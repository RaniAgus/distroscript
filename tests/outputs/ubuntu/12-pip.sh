#!/bin/bash

sudo apt-get install -y python3-pip

sudo apt-get install -y build-essential

pip install -U kazam

printf "%s\n" "[Desktop Entry]" "Name=Kazam" "Comment=Screen recording tool" "Exec=kazam" "Icon=kazam" "Terminal=false" "Type=Application" "Categories=AudioVideo;Recorder;" "StartupNotify=true" | tee ~/.local/share/applications/kazam.desktop

pip install -U yt-dlp[default]
