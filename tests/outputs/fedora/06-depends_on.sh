#!/bin/bash

sudo dnf install -y dnf5-plugins

# TODO: Add installation command for package: dnf5-plugins

sudo dnf install -y kernel kernel-core kernel-modules kernel-modules-core kernel-modules-extra kernel-tools kernel-tools-libs kernel-headers kernel-devel

wget -q https://www.virtualbox.org/download/oracle_vbox_2016.asc -O- | sudo rpm --import -

sudo dnf install -y VirtualBox-7.2
