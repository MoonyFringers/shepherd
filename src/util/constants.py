# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.


import os
from dataclasses import dataclass
from typing import Any

DEFAULT_COMPOSE_COMMAND_LOG_LIMIT = 5


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
    def SHPD_PLUGINS_DIR(self) -> str:
        return os.path.join(self.SHPD_PATH, "plugins")

    # Logging configuration

    LOG_FILE: str
    LOG_LEVEL: str
    RAW_LOG_STDOUT: str
    LOG_FORMAT: str

    @property
    def LOG_STDOUT(self) -> bool:
        """Normalize config value to boolean
        (`\"true\"` enables stdout logs)."""
        return self.RAW_LOG_STDOUT == "true"

    # Application metadata

    APP_NAME: str = "shepctl"
    APP_VERSION: str = "0.0.0"
    APP_AUTHOR: str = "Moony Fringers"
    APP_LICENSE: str = "AGPL-3.0"
    APP_URL: str = "https://github.com/MoonyFringers/shepherd"
    PLUGIN_DESCRIPTOR_FILE: str = "plugin.yaml"
    CORE_PLUGIN_ID: str = "core"

    # Environment templates:

    ENV_TEMPLATES_DIR: str = "envs"

    # Environment types

    ENV_FACTORY_DEFAULT: str = "docker-compose"

    @property
    def ENV_FACTORIES(self) -> list[str]:
        return [
            self.ENV_FACTORY_DEFAULT,
        ]

    # Service templates:

    SVC_TEMPLATES_DIR: str = "svcs"
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
        """
        Canonical skeleton used when bootstrapping a new `.shpd.yaml`.

        Placeholder values are intentionally preserved for later resolution by
        config loading/resolution flows.
        """
        return {
            "env_templates": [],
            "service_templates": [],
            "templates_path": "${templates_path}",
            "envs_path": "${envs_path}",
            "plugins": [],
            "remotes": [],
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
