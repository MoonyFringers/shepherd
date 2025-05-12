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


import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Constants:
    """Constants for the application."""

    # Configuration and environment variables

    SHPD_CONFIG_VALUES_FILE: str
    SHPD_DIR: str

    @property
    def SHPD_CONFIG_FILE(self) -> str:
        return os.path.join(self.SHPD_DIR, ".shpd.json")

    @property
    def SHPD_ENVS_DIR(self) -> str:
        return os.path.join(self.SHPD_DIR, "envs")

    @property
    def SHPD_ENV_IMGS_DIR(self) -> str:
        return os.path.join(self.SHPD_DIR, ".env_imgs")

    @property
    def SHPD_CERTS_DIR(self) -> str:
        return os.path.join(self.SHPD_DIR, ".certs")

    @property
    def SHPD_SSH_DIR(self) -> str:
        return os.path.join(self.SHPD_DIR, ".ssh")

    @property
    def SHPD_SSHD_DIR(self) -> str:
        return os.path.join(self.SHPD_DIR, ".sshd")

    # Application metadata

    APP_NAME: str = "shepctl"
    APP_VERSION: str = "0.0.0"
    APP_AUTHOR: str = "Lunatic Fringers"
    APP_LICENSE: str = "MIT"
    APP_URL: str = "https://github.com/LunaticFringers/shepherd"

    # Environment types

    ENV_TYPE_DOCKER_COMPOSE: str = "docker-compose"
