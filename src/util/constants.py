# Copyright (c) 2025 Moony Fringers
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


import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Constants:
    """Constants for the application."""

    # Configuration and environment variables

    SHPD_CONFIG_VALUES_FILE: str
    SHPD_PATH: str

    @property
    def SHPD_CONFIG_FILE(self) -> str:
        return os.path.join(self.SHPD_PATH, ".shpd.yaml")

    @property
    def SHPD_CERTS_DIR(self) -> str:
        return os.path.join(self.SHPD_PATH, ".certs")

    @property
    def SHPD_SSH_DIR(self) -> str:
        return os.path.join(self.SHPD_PATH, ".ssh")

    @property
    def SHPD_SSHD_DIR(self) -> str:
        return os.path.join(self.SHPD_PATH, ".sshd")

    # Logging configuration

    LOG_FILE: str
    LOG_LEVEL: str
    RAW_LOG_STDOUT: str
    LOG_FORMAT: str

    @property
    def LOG_STDOUT(self) -> bool:
        return self.RAW_LOG_STDOUT == "true"

    # Application metadata

    APP_NAME: str = "shepctl"
    APP_VERSION: str = "0.0.0"
    APP_AUTHOR: str = "Moony Fringers"
    APP_LICENSE: str = "MIT"
    APP_URL: str = "https://github.com/MoonyFringers/shepherd"

    # Environment templates:

    ENV_TEMPLATE_DEFAULT: str = "default"

    # Environment types

    ENV_FACTORY_DEFAULT: str = "docker-compose"

    @property
    def ENV_FACTORIES(self) -> list[str]:
        return [
            self.ENV_FACTORY_DEFAULT,
        ]

    # Service templates:

    SVC_TEMPLATE_DEFAULT: str = "default"
    SVC_TAG_DEFAULT: str = "service-default"

    # Service factories:

    SVC_FACTORY_DEFAULT: str = "docker"

    # Resource types

    RESOURCE_TYPE_SVC: str = "svc"

    @property
    def RESOURCE_TYPES(self) -> list[str]:
        return [
            self.RESOURCE_TYPE_SVC,
        ]

    # Default configuration values

    NET_KEY_DEFAULT: str = "shpdnet"
    NET_NAME_DEFAULT: str = "envnet"

    @property
    def DEFAULT_CONFIG(self) -> dict[Any, Any]:
        return {
            "env_templates": [
                {
                    "tag": self.ENV_TEMPLATE_DEFAULT,
                    "factory": self.ENV_FACTORY_DEFAULT,
                    "service_templates": [
                        {
                            "template": self.SVC_TEMPLATE_DEFAULT,
                            "tag": self.SVC_TAG_DEFAULT,
                        }
                    ],
                    "networks": [
                        {
                            "tag": self.NET_KEY_DEFAULT,
                            "name": self.NET_NAME_DEFAULT,
                            "external": "true",
                        }
                    ],
                }
            ],
            "service_templates": [
                {
                    "tag": self.SVC_TEMPLATE_DEFAULT,
                    "factory": self.SVC_FACTORY_DEFAULT,
                    "image": "",
                    "ingress": "false",
                    "envvars": {},
                    "ports": [],
                    "properties": {},
                    "subject_alternative_name": None,
                },
            ],
            "shpd_registry": {
                "ftp_server": "${shpd_registry}",
                "ftp_user": "${shpd_registry_ftp_usr}",
                "ftp_psw": "${shpd_registry_ftp_psw}",
                "ftp_shpd_path": "${shpd_registry_ftp_shpd_path}",
                "ftp_env_imgs_path": "${shpd_registry_ftp_imgs_path}",
            },
            "envs_path": "${envs_path}",
            "volumes_path": "${volumes_path}",
            "host_inet_ip": "${host_inet_ip}",
            "domain": "${domain}",
            "dns_type": "${dns_type}",
            "ca": {
                "country": "${ca_country}",
                "state": "${ca_state}",
                "locality": "${ca_locality}",
                "organization": "${ca_org}",
                "organizational_unit": "${ca_org_unit}",
                "common_name": "${ca_cn}",
                "email": "${ca_email}",
                "passphrase": "${ca_passphrase}",
            },
            "cert": {
                "country": "${cert_country}",
                "state": "${cert_state}",
                "locality": "${cert_locality}",
                "organization": "${cert_org}",
                "organizational_unit": "${cert_org_unit}",
                "common_name": "${cert_cn}",
                "email": "${cert_email}",
                "subject_alternative_names": None,
            },
            "staging_area": {
                "volumes_path": "${staging_area_volumes_path}",
                "images_path": "${staging_area_images_path}",
            },
            "envs": [],
        }


# Installer and system constants

# List of required system packages for Shepherd installation
REQUIRED_PKGS: list[str] = [
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

# List of required Python packages for Shepherd
REQUIRED_PYTHON_PKGS: list[str] = ["python3-venv", "python3-pip"]

# List of required Docker-related packages
REQUIRED_DOCKER_PKGS: list[str] = [
    "docker.io",
    "docker-ce",
    "docker-ce-cli",
    "containerd.io",
    "docker-compose",
    "docker-compose-plugin",
]

# Mapping of distro names to install commands for system packages
INSTALL_COMMANDS: dict[str, list[str]] = {
    "debian": ["sudo", "apt-get", "install", "-y"],
    "ubuntu": ["sudo", "apt-get", "install", "-y"],
}

# Mapping of distro names to update commands for package lists
UPDATE_COMMANDS: dict[str, str] = {
    "debian": "sudo apt update",
    "ubuntu": "sudo apt update",
}

# Mapping of distro names to Docker GPG key URLs
GPG_KEYS: dict[str, str] = {
    "debian": "https://download.docker.com/linux/debian/gpg",
    "ubuntu": "https://download.docker.com/linux/ubuntu/gpg",
}

# Mapping of distro names to Docker repository file paths
REPO_PATHS: dict[str, str] = {
    "debian": "/etc/apt/sources.list.d/docker.list",
    "ubuntu": "/etc/apt/sources.list.d/docker.list",
}

# Mapping of distro names to Docker repository configuration strings
REPO_STRINGS: dict[str, str] = {
    "debian": (
        "deb [arch={architecture} signed-by=/usr/share/keyrings/"
        "docker-archive-keyring.gpg] "
        "https://download.docker.com/linux/debian "
        "{release} stable"
    ),
    "ubuntu": (
        "deb [arch={architecture} signed-by=/usr/share/keyrings/"
        "docker-archive-keyring.gpg] "
        "https://download.docker.com/linux/ubuntu "
        "{release} stable"
    ),
}

# Path to Docker's keyring file
KEYRING_PATH: str = "/usr/share/keyrings/docker-archive-keyring.gpg"

# Mapping of (architecture, linkage) to Docker architecture strings
ARCH_MAPPING: dict[tuple[str, str], str] = {
    ("32bit", "ELF"): "i386",
    ("64bit", "ELF"): "amd64",
    ("32bit", "WindowsPE"): "i386",
    ("64bit", "WindowsPE"): "amd64",
    ("64bit", "Mach-O"): "amd64",
    ("arm", ""): "arm64",
    ("aarch64", ""): "arm64",
}

# URL template for downloading shepctl source tarballs
SHEPCTL_SOURCE_URL: str = (
    "https://github.com/MoonyFringers/shepherd/archive/refs/tags/v"
    "{version}.tar.gz"
)

# URL template for downloading shepctl source tarballs
SHEPCTL_BINARY_URL: str = (
    "https://github.com/MoonyFringers/shepherd/releases/download/"
    "v{version}/shepctl-{version}.tar.gz"
)
