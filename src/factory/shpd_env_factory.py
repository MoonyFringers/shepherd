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

from config import ConfigMng, EnvironmentCfg, EnvironmentTemplateCfg
from docker import DockerComposeEnv
from environment import Environment, EnvironmentFactory
from service import ServiceFactory
from util import Constants


class ShpdEnvironmentFactory(EnvironmentFactory):

    def __init__(self, configMng: ConfigMng, svcFactory: ServiceFactory):
        self.configMng = configMng
        self.svcFactory = svcFactory

    @override
    def new_environment(
        self,
        env_tmpl_cfg: EnvironmentTemplateCfg,
        env_tag: str,
    ) -> Environment:
        """
        Create an environment.
        """
        match env_tmpl_cfg.factory:
            case Constants.ENV_FACTORY_DEFAULT:
                return DockerComposeEnv(
                    self.configMng,
                    self.svcFactory,
                    self.configMng.env_cfg_from_tag(env_tmpl_cfg, env_tag),
                )
            case _:
                raise ValueError(
                    f"Unknown environment factory: {env_tmpl_cfg.factory}"
                )

    @override
    def new_environment_cfg(self, envCfg: EnvironmentCfg) -> Environment:
        """
        Get an environment.
        """
        match envCfg.factory:
            case Constants.ENV_FACTORY_DEFAULT:
                return DockerComposeEnv(self.configMng, self.svcFactory, envCfg)
            case _:
                raise ValueError(
                    f"Unknown environment factory: {envCfg.factory}"
                )
