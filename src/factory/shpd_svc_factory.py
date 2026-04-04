# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.


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
