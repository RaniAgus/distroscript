#!/bin/bash

sudo dnf config-manager addrepo --from-repofile=https://cli.github.com/packages/rpm/gh-cli.repo

sudo dnf install -y gh --repo gh-cli
