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


REQUIRED_PKGS = [
    "bc",
    "jq",
    "curl",
    "rsync",
    "apt-transport-https",
    "ca-certificates",
    "software-properties-common",
    "gnupg",
    "lsb-release",
]

REQUIRED_PYTHON_PKGS = ["python3-venv", "python3-pip"]

REQUIRED_DOCKER_PKGS = [
    "docker.io",
    "docker-ce",
    "docker-ce-cli",
    "containerd.io",
    "docker-compose",
    "docker-compose-plugin",
]

INSTALL_COMMANDS = {
    "debian": ["sudo", "apt-get", "install", "-y"],
    "ubuntu": ["sudo", "apt-get", "install", "-y"],
    "fedora": ["sudo", "dnf", "install", "-y"],
    "centos": ["sudo", "yum", "install", "-y"],
    "arch": ["sudo", "pacman", "-S", "--noconfirm"],
}

UPDATE_COMMANDS = {
    "debian": "sudo apt update",
    "ubuntu": "sudo apt update",
    "fedora": "sudo dnf update",
    "centos": "sudo yum update",
    "arch": "sudo pacman -Syu",
}

GPG_KEYS = {
    "debian": "https://download.docker.com/linux/debian/gpg",
    "ubuntu": "https://download.docker.com/linux/ubuntu/gpg",
    "fedora": "https://download.docker.com/linux/fedora/gpg",
    "centos": "https://download.docker.com/linux/centos/gpg",
    "arch": "https://download.docker.com/linux/archlinux/gpg",
}

REPO_PATHS = {
    "debian": "/etc/apt/sources.list.d/docker.list",
    "ubuntu": "/etc/apt/sources.list.d/docker.list",
    "fedora": "/etc/yum.repos.d/docker.repo",
    "centos": "/etc/yum.repos.d/docker.repo",
    "arch": "/etc/pacman.d/mirrorlist.d/docker.list",
}

REPO_STRINGS = {
    "debian": "deb [arch={architecture} \
                signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
                https://download.docker.com/linux/debian {release} stable",
    "ubuntu": "deb [arch={architecture} \
                signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
                https://download.docker.com/linux/ubuntu {release} stable",
    "fedora": """[docker]
name=Docker CE Stable - $basearch
baseurl=https://download.docker.com/linux/fedora/$releasever/$basearch/stable
enabled=1
gpgcheck=1
gpgkey=/etc/pki/rpm-gpg/RPM-GPG-KEY-docker""",
    "centos": """[docker]
name=Docker CE Stable - $basearch
baseurl=https://download.docker.com/linux/centos/$releasever/$basearch/stable
enabled=1
gpgcheck=1
gpgkey=/etc/pki/rpm-gpg/RPM-GPG-KEY-docker""",
    "arch": "Server = https://download.docker.com/linux/archlinux/$arch/stable",
}

KEYRING_PATH = "/usr/share/keyrings/docker-archive-keyring.gpg"

ARCH_MAPPING = {
    ("32bit", "ELF"): "i386",
    ("64bit", "ELF"): "amd64",
    ("32bit", "WindowsPE"): "i386",
    ("64bit", "WindowsPE"): "amd64",
    ("64bit", "Mach-O"): "amd64",
    ("arm", ""): "arm64",
    ("aarch64", ""): "arm64",
}

SHEPCTL_SOURCE_URL = (
    "https://github.com/LunaticFringers/shepherd/archive/refs/tags/v"
    "{version}.tar.gz"
)
