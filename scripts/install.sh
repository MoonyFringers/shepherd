#!/bin/bash

# Copyright (c) 2025 Lunatic Fringers
#
# This file is part of Shepherd Core Stack
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

export RED='\033[0;31m'
export NC='\033[0m'
export YELLOW='\033[0;33m'
export GREEN='\033[0;32m'
export BLUE='\033[0;36m'

skip_ensure_deps=false
PY_SRC_DIR="$(realpath "$(dirname "$0")/../src")"

INSTALL_SHEPCTL_DIR=$(realpath ${INSTALL_SHEPCTL_DIR:-"/opt/shepctl"})
SYMLINK_DIR=${SYMLINK_DIR:-"/usr/local/bin"}
URL="https://github.com/LunaticFringers/shepherd/releases/download/v$VER/shepctl-$VER.tar.gz"

set -e

usage(){
  cat << EOF
usage: install.sh [options]

  -m, --install-method      Specify the installation method (binary or source). Default is binary.
  -v, --verbose             Enable verbose mode.
  -s, --skip-deps           Skip ensure dependencies
  -h, --help                Show help.

commands:
  install                   Install shepctl as system tool (root privileges are required).
  uninstall                 Uninstall shepctl (root privileges are required).
EOF
}

if [ "$(id -u)" -ne 0 ]; then
  echo "This script requires privileges to install."
  exit 1
fi

function ensure_deps_debian_like() {
  echo "Checking base dependencies..."

  REQUIRED_PKGS=(
    bc
    jq
    curl
    rsync
    apt-transport-https
    ca-certificates
    software-properties-common
    gnupg
    lsb-release
  )

  MISSING_PKGS=()
  for pkg in "${REQUIRED_PKGS[@]}"; do
    if ! dpkg -s "$pkg" &>/dev/null; then
      MISSING_PKGS+=("$pkg")
    fi
  done

  if [[ ${#MISSING_PKGS[@]} -gt 0 ]]; then
    echo "Installing missing dependencies: ${MISSING_PKGS[*]}"
    apt-get update
    apt-get install -y --no-install-recommends "${MISSING_PKGS[@]}"
  else
    echo "All base dependencies are already installed."
  fi

  # Ensure Python >= 3.12 and pip
  if ! python3 --version | grep -qE "3\.(1[2-9]|[2-9][0-9])"; then
    echo "Installing Python 3.12+..."
    apt-get install -y python3 python3-venv python3-pip
  else
    echo "Python is already installed: $(python3 --version)"
  fi

  # Docker GPG key and repository
  KEYRING_PATH="/usr/share/keyrings/docker-archive-keyring.gpg"
  if [[ ! -f "$KEYRING_PATH" ]]; then
    echo "Adding Docker GPG key..."
    curl -fsSL https://download.docker.com/linux/$(. /etc/os-release && echo "$ID")/gpg | gpg --dearmor -o "$KEYRING_PATH"
  else
    echo "Docker GPG key already exists."
  fi

  RELEASE_CODENAME=$(lsb_release -cs)
  ARCH=$(dpkg --print-architecture)
  REPO_STRING="deb [arch=${ARCH} signed-by=${KEYRING_PATH}] https://download.docker.com/linux/$(. /etc/os-release && echo "$ID") $RELEASE_CODENAME stable"
  SOURCES_LIST="/etc/apt/sources.list.d/docker.list"

  if [[ ! -f "$SOURCES_LIST" ]] || ! grep -Fxq "$REPO_STRING" "$SOURCES_LIST"; then
    echo "Adding Docker repository..."
    echo "$REPO_STRING" | tee "$SOURCES_LIST" > /dev/null
    apt-get update
  else
    echo "Docker repository already exists."
  fi

  if ! dpkg -s docker-ce &>/dev/null; then
    echo "Installing Docker..."
    apt-get install -y docker-ce docker-ce-cli containerd.io
    NEW_DOCKER_INSTALL=true
  else
    echo "Docker is already installed."
    NEW_DOCKER_INSTALL=false
  fi

  echo "Docker version: $(docker --version)"

  if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
  else
    echo "Docker Compose is already installed."
  fi

  echo "Docker Compose version: $(docker-compose --version)"

  systemctl enable docker

  if [[ "$NEW_DOCKER_INSTALL" == true ]]; then
    groupadd -f docker
    usermod -aG docker "$USER"
    echo "Docker installed and user added to docker group."
    echo "Please log out and back in for group membership to apply."
  fi
}

function uninstall(){
  echo -e "${BLUE}Uninstalling shepctl...${NC}"

  rm -rf $INSTALL_SHEPCTL_DIR
  rm -rf $SYMLINK_DIR/shepctl
  echo "shepctl uninstalled"
}

function install_binary(){
  if [[ -z "$VER" || -z "$URL" || -z "$INSTALL_SHEPCTL_DIR" ]]; then
    echo "Error: VER, URL, and INSTALL_SHEPCTL_DIR must be set."
    return 1
  fi

  TEMP_DIR=$(mktemp -d)
  echo "Installing shepctl version $VER..."
  echo "Downloading from URL $URL"
  if ! curl -fsSL "$URL" -o "$TEMP_DIR/shepctl.tar.gz"; then
    echo "Download failed!"
    rm -rf "$TEMP_DIR"
    return 1
  fi

  echo "Extracting the package..."
  if ! tar -xzvf "$TEMP_DIR/shepctl.tar.gz" -C "$TEMP_DIR"; then
    echo "Extraction failed!"
    rm -rf "$TEMP_DIR"
    return 1
  fi

  echo "Installing shepctl binary to $INSTALL_SHEPCTL_DIR..."
  if ! mv "$TEMP_DIR/shepctl" "$INSTALL_SHEPCTL_DIR/shepctl"; then
    echo "Failed to move binary!"
    rm -rf "$TEMP_DIR"
    return 1
  fi

  chmod +x "$INSTALL_SHEPCTL_DIR/shepctl"
  echo "Creating symlink in $SYMLINK_DIR..."
  ln -sf "$INSTALL_SHEPCTL_DIR/shepctl" "$SYMLINK_DIR/shepctl"

  echo "Cleaning up..."
  rm -rf "$TEMP_DIR"

  if command -v shepctl > /dev/null; then
    echo "shepctl installed successfully! You can run it using the 'shepctl' command."
  else
    echo "Installation failed."
    exit 1
  fi

  echo "shepctl version $VER installed successfully!"
}

install_sources() {
  if [[ -z "$INSTALL_SHEPCTL_DIR" ]]; then
    echo "Error: INSTALL_SHEPCTL_DIR must be set."
    return 1
  fi

  echo "Installing shepctl from source..."
  if [[ ! -d "$PY_SRC_DIR" ]]; then
    echo "Source directory not found: $PY_SRC_DIR"
    return 1
  fi

  echo "Copying Python source files to $INSTALL_SHEPCTL_DIR..."
  mkdir -p "$INSTALL_SHEPCTL_DIR"
  cd "$PY_SRC_DIR"
  find . -name '*.py' -print0 | while IFS= read -r -d '' file; do
    mkdir -p "$INSTALL_SHEPCTL_DIR/$(dirname "$file")"
    cp "$file" "$INSTALL_SHEPCTL_DIR/$file"
  done

  echo "Fixing permissions..."
  sudo chown -R "$USER":"$USER" "$INSTALL_SHEPCTL_DIR"
  find "$INSTALL_SHEPCTL_DIR" -type f -name '*.py' -exec chmod 644 {} \;

  echo "Creating Python virtual environment..."
  python3 -m venv "$INSTALL_SHEPCTL_DIR/.venv"
  chown -R "$USER":"$USER" "$INSTALL_SHEPCTL_DIR/.venv"

  echo "Installing dependencies into virtual environment..."
  if [[ -f "$PY_SRC_DIR/requirements.txt" ]]; then
    "$INSTALL_SHEPCTL_DIR/.venv/bin/pip" install --upgrade pip
    "$INSTALL_SHEPCTL_DIR/.venv/bin/pip" install -r "$PY_SRC_DIR/requirements.txt"
  else
    echo "requirements.txt not found in $PY_SRC_DIR"
    return 1
  fi

  echo "Creating wrapper script in $SYMLINK_DIR/shepctl..."
  mkdir -p "$SYMLINK_DIR"
  tee "$SYMLINK_DIR/shepctl" > /dev/null <<EOF
#!/bin/bash
exec "$INSTALL_SHEPCTL_DIR/.venv/bin/python" "$INSTALL_SHEPCTL_DIR/shepctl.py" "\$@"
EOF
  chmod +x "$SYMLINK_DIR/shepctl"

  echo "shepctl installed from source with isolated dependencies."
  echo "You can now run it with: shepctl"
}

install() {
  if [[ "$skip_ensure_deps" != true ]]; then
    echo -e "${BLUE}Ensuring dependencies...${NC}"
    if grep -qiE "ubuntu|debian|pop|mint" /etc/os-release; then
      ensure_deps_debian_like
    else
      echo "Unrecognized or unsupported distro. Please ensure dependencies manually."
    fi
  fi

  if [[ -d "$INSTALL_SHEPCTL_DIR" ]]; then
    rm -rf "$INSTALL_SHEPCTL_DIR"
  fi
  mkdir -p "$INSTALL_SHEPCTL_DIR"

  case "$INSTALL_METHOD" in
    binary)
      install_binary
      ;;
    source)
      install_sources
      ;;
    *)
      echo "Error: Unknown install method '$INSTALL_METHOD'"
      exit 1
      ;;
  esac
}

############
# ENTRYPOINT
############

OPTIONS=vshm:
LONGOPTIONS=verbose,skip-deps,help,install-method:
PARSED=$(getopt --options=$OPTIONS --longoptions=$LONGOPTIONS --name "$0" -- "$@")

if [[ $? -ne 0 ]]; then
  exit 2
fi

eval set -- "$PARSED"

INSTALL_METHOD="binary"

while true; do
  case "$1" in
    -v|--verbose)
      export verbose=true
      shift
      ;;
    -s|--skip-deps)
      export skip_ensure_deps=true
      shift
      ;;
    -m|--install-method)
      INSTALL_METHOD="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      echo "Unexpected option: $1"
      exit 3
      ;;
  esac
done

usage_err=false

case ${1} in
  install)
    install || exit 1
    ;;
  uninstall)
    uninstall || exit 1
    ;;
  *)
    usage_err=true
    ;;
esac

if [[ $usage_err == true ]]; then
  usage
  exit 1
fi
