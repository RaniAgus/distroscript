#!/bin/bash

sudo apt-get install -y flatpak

flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo

flatpak install -y flathub org.kde.kdenlive

flatpak install -y flathub net.pcsx2.PCSX2

flatpak install -y flathub com.github.jeromerobert.pdfarranger

flatpak install -y flathub com.obsproject.Studio

flatpak install -y flathub com.discordapp.Discord

flatpak install -y flathub com.github.maoschanz.drawing
