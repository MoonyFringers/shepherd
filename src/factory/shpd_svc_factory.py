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

from config import ConfigMng, EnvironmentCfg, ServiceCfg
from docker import DockerComposeSvc
from service import Service, ServiceFactory
from util import Constants


class ShpdServiceFactory(ServiceFactory):
    """Concrete service factory that resolves service backend from `svcCfg`."""

    def __init__(self, configMng: ConfigMng):
        self.configMng = configMng

    @override
    @classmethod
    def get_name_impl(cls) -> str:
        return "shpd-svc-factory"

    @override
    def new_service_from_cfg_impl(
        self,
        envCfg: EnvironmentCfg,
        svcCfg: ServiceCfg,
        cli_flags: dict[str, Any] | None = None,
    ) -> Service:
        """
        Instantiate a concrete service implementation for the configured
        backend.
        """
        match svcCfg.factory:
            case Constants.SVC_FACTORY_DEFAULT:
                return DockerComposeSvc(
                    self.configMng, envCfg, svcCfg, cli_flags=cli_flags
                )
            case _:
                raise ValueError(f"""Unknown service type: {svcCfg.template},
                    plugins not supported yet!""")
