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


from typing import override

from config import ConfigMng, EnvironmentCfg
from docker_compose import DockerComposeEnv
from environment import Environment, EnvironmentFactory
from util import Constants


class ShpdEnvironmentFactory(EnvironmentFactory):

    def __init__(self, configMng: ConfigMng):
        self.configMng = configMng

    @override
    def new_environment(self, env_type: str, env_tag: str) -> Environment:
        """
        Create an environment.
        """
        match env_type:
            case Constants.ENV_TYPE_DOCKER_COMPOSE:
                return DockerComposeEnv(
                    self.configMng, EnvironmentCfg.from_tag(env_type, env_tag)
                )
            case _:
                raise ValueError(f"Unknown environment type: {env_type}")

    @override
    def get_environment(self, envCfg: EnvironmentCfg) -> Environment:
        """
        Get an environment.
        """
        match envCfg.type:
            case Constants.ENV_TYPE_DOCKER_COMPOSE:
                return DockerComposeEnv(self.configMng, envCfg)
            case _:
                raise ValueError(f"Unknown environment type: {envCfg.type}")
