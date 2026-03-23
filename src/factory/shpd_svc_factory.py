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
        if self.configMng.is_core_svc_factory_id(svcCfg.factory):
            return DockerComposeSvc(
                self.configMng, envCfg, svcCfg, cli_flags=cli_flags
            )

        plugin_runtime_mng = self.configMng.pluginRuntimeMng
        if plugin_runtime_mng is None:
            raise ValueError(f"Unknown service factory: {svcCfg.factory}")
        plugin_factory = plugin_runtime_mng.build_service_factory(
            self.configMng.get_canonical_svc_factory_id(svcCfg.factory),
            self.configMng,
        )
        if plugin_factory is None:
            raise ValueError(f"Unknown service factory: {svcCfg.factory}")
        return plugin_factory.new_service_from_cfg(
            envCfg, svcCfg, cli_flags=cli_flags
        )
