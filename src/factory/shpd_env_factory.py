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


from typing import Any, override

from config import ConfigMng, EnvironmentCfg, EnvironmentTemplateCfg
from docker import DockerComposeEnv
from environment import Environment, EnvironmentFactory
from service import ServiceFactory
from util import Constants


class ShpdEnvironmentFactory(EnvironmentFactory):
    """Concrete environment factory that dispatches to backend
    implementations."""

    def __init__(
        self,
        configMng: ConfigMng,
        svcFactory: ServiceFactory,
        cli_flags: dict[str, Any] | None = None,
    ):
        self.configMng = configMng
        self.svcFactory = svcFactory
        self.cli_flags = cli_flags or {}

    @override
    def new_environment_impl(
        self,
        env_tmpl_cfg: EnvironmentTemplateCfg,
        env_tag: str,
    ) -> Environment:
        """
        Materialize an environment instance from a template reference.

        The template is first converted to an `EnvironmentCfg` snapshot for
        `env_tag`, then routed to the backend-specific environment class.
        """
        match env_tmpl_cfg.factory:
            case Constants.ENV_FACTORY_DEFAULT:
                return DockerComposeEnv(
                    self.configMng,
                    self.svcFactory,
                    self.configMng.env_cfg_from_tag(env_tmpl_cfg, env_tag),
                    cli_flags=self.cli_flags,
                )
            case _:
                raise ValueError(
                    f"Unknown environment factory: {env_tmpl_cfg.factory}"
                )

    @override
    def new_environment_cfg_impl(self, envCfg: EnvironmentCfg) -> Environment:
        """
        Rehydrate an environment instance from an existing config object.

        Used for operations on already persisted environments.
        """
        match envCfg.factory:
            case Constants.ENV_FACTORY_DEFAULT:
                return DockerComposeEnv(
                    self.configMng,
                    self.svcFactory,
                    envCfg,
                    cli_flags=self.cli_flags,
                )
            case _:
                raise ValueError(
                    f"Unknown environment factory: {envCfg.factory}"
                )
