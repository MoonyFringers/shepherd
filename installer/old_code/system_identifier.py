#!/usr/bin/env python3

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

import platform
import distro
from dataclasses import dataclass
from typing import Optional


def get_os_info() -> OsInfo:
    """
    Identifies the operating system type, distribution, and codename.
    
    Returns:
        OsInfo: A dataclass containing system type, distribution, and codename
        
    Raises:
        ValueError: If the operating system is not supported
    """
    system = platform.system().lower()
    
    if system in ("windows", "win32", "darwin"):
        raise ValueError(f"Unsupported operating system: {system}")
    
    elif system == "linux":
        dist_id = distro.id().lower()
        code_name = distro.codename().lower()
        return OsInfo(system=system, distro=dist_id, codename=code_name)
    
    # Fallback for other systems
    return OsInfo(system=system)

class SystemIdentifiers:
    class OS:
        LINUX_DEBIAN = "Debian derived Linux with apt available"
        OTHER_LINUX = "Other Linux"
        WINDOWS = "Windows"
        UNKNOWN_SYSTEM = "Unknown system"

    class Dependencies:
        KEYRING_PATH = "/usr/share/keyrings/docker-archive-keyring.gpg"

        @staticmethod
        def get_architecture():
            """
            Determines the architecture of the current machine and returns a standardized string representation.

            Returns:
                str: A string representing the architecture. Possible values are:
                    - 'amd64' for x86_64 architecture
                    - 'arm64' for aarch64 architecture
                    - 'armhf' for armv7l architecture
                    - The original architecture string for any other architecture
            """
            arch = platform.machine()
            if arch == 'x86_64':
                return 'amd64'
            elif arch == 'aarch64':
                return 'arm64'
            elif arch == 'armv7l':
                return 'armhf'
            else:
                return arch

        @staticmethod
        def get_repo_string():
            """
            Constructs the repository string for Docker based on the system architecture and keyring path.

            Returns:
                str: The repository string for Docker.
            """
            if SystemIdentifiers.get_os() == SystemIdentifiers.OS.LINUX_DEBIAN:
                return (
                    "deb [arch=" + SystemIdentifiers.Dependencies.get_architecture() + " signed-by="
                    + SystemIdentifiers.Dependencies.KEYRING_PATH
                    + "] https://download.docker.com/linux/debian $(lsb_release -cs) stable"
                )
            else:
                return "Unsupported OS for Docker repository"

        DOCKER = "Docker"
        DOCKER_COMPOSE = "Docker Compose"

