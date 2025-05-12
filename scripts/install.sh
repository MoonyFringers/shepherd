#!/bin/bash
set -e

if [ -z "$VER" ]; then
  echo "Error: Specify the version to install."
  exit 1
fi

INSTALL_DIR=${INSTALL_DIR:-"/usr/local/bin"}
URL="https://github.com/LunaticFringers/shepherd/releases/download/v$VER/shepctl-$VER.tar.gz"
TEMP_DIR=$(mktemp -d)

if [ "$(id -u)" -ne 0 ]; then
  echo "This script requires sudo privileges to install."
  exit 1
fi

echo "Installing shepctl version $VER..."
echo "Downloading from URL $URL"
curl -fsSL "$URL" -o "$TEMP_DIR/shepctl.tar.gz"

echo "Extracting the package..."
tar -xzvf "$TEMP_DIR/shepctl.tar.gz" -C "$TEMP_DIR"

echo "Installing shepctl binary to $INSTALL_DIR..."
mv "$TEMP_DIR/shepctl" "$INSTALL_DIR/shepctl"

chmod +x "$INSTALL_DIR/shepctl"
rm -rf "$TEMP_DIR"

if command -v shepctl > /dev/null; then
  echo "shepctl installed successfully! You can run it using the 'shepctl' command."
else
  echo "Installation failed."
  exit 1
fi
