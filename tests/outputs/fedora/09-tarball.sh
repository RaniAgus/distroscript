#!/bin/bash

curl -fsSL "https://go.dev/dl/$(curl -fsSL 'https://golang.org/VERSION?m=text' | head -n1).linux-amd64.tar.gz" | sudo tar xzvC /usr/local

sudo dnf install -y jq

curl -fsSL "$(curl -fsSL "https://data.services.jetbrains.com/products/releases?code=TBA&latest=true&type=release" | jq -r '.TBA[0].downloads.linux.link')" | sudo tar xzvC /opt

/opt/jetbrains-toolbox-*/bin/jetbrains-toolbox
