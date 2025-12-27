#!/bin/bash

TMP_DIR=$(mktemp -d)
git clone https://github.com/mumuki/cspec.git $TMP_DIR
(
  cd $TMP_DIR
  make
  sudo make install
)
rm -rf $TMP_DIR

TMP_DIR=$(mktemp -d)
git clone https://github.com/sisoputnfrba/so-commons-library.git $TMP_DIR
(
  cd $TMP_DIR
  make
  sudo make install
)
rm -rf $TMP_DIR
