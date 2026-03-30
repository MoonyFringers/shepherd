# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.io.


from typing import Any, override

from config import ConfigMng, EnvironmentCfg, EnvironmentTemplateCfg
from docker import DockerComposeEnv
from environment import Environment, EnvironmentFactory
from service import ServiceFactory


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
        if self.configMng.is_core_env_factory_id(env_tmpl_cfg.factory):
            return DockerComposeEnv(
                self.configMng,
                self.svcFactory,
                self.configMng.env_cfg_from_tag(env_tmpl_cfg, env_tag),
                cli_flags=self.cli_flags,
            )

        plugin_runtime_mng = self.configMng.pluginRuntimeMng
        if plugin_runtime_mng is None:
            raise ValueError(
                f"Unknown environment factory: {env_tmpl_cfg.factory}"
            )
        plugin_factory = plugin_runtime_mng.build_environment_factory(
            self.configMng.get_canonical_env_factory_id(env_tmpl_cfg.factory),
            self.configMng,
            self.svcFactory,
            self.cli_flags,
        )
        if plugin_factory is None:
            raise ValueError(
                f"Unknown environment factory: {env_tmpl_cfg.factory}"
            )
        return plugin_factory.new_environment(env_tmpl_cfg, env_tag)

    @override
    def new_environment_cfg_impl(self, envCfg: EnvironmentCfg) -> Environment:
        """
        Rehydrate an environment instance from an existing config object.

        Used for operations on already persisted environments.
        """
        if self.configMng.is_core_env_factory_id(envCfg.factory):
            return DockerComposeEnv(
                self.configMng,
                self.svcFactory,
                envCfg,
                cli_flags=self.cli_flags,
            )

        plugin_runtime_mng = self.configMng.pluginRuntimeMng
        if plugin_runtime_mng is None:
            raise ValueError(f"Unknown environment factory: {envCfg.factory}")
        plugin_factory = plugin_runtime_mng.build_environment_factory(
            self.configMng.get_canonical_env_factory_id(envCfg.factory),
            self.configMng,
            self.svcFactory,
            self.cli_flags,
        )
        if plugin_factory is None:
            raise ValueError(f"Unknown environment factory: {envCfg.factory}")
        return plugin_factory.new_environment_cfg(envCfg)
