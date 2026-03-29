"""Factory contributions for the Hello Plugin.

Shepherd supports two shapes for a factory provider
(see ``EnvFactoryProvider`` / ``SvcFactoryProvider`` in the plugin API):

  1. A **class** — the runtime instantiates it by calling the constructor
     with the appropriate arguments.  This is the recommended approach.

  2. A pre-built **instance** — useful when the factory holds no per-call
     state.

  3. A **callable** (function or lambda) — the runtime calls it with the
     same arguments as the constructor and expects a factory instance back.

This module uses the class shape (option 1) for both factories.

Service factory constructor signature
--------------------------------------
    __init__(self, config: ConfigMng)

Shepherd calls ``HelloServiceFactory(configMng)`` and stores the result.

Environment factory constructor signature
------------------------------------------
    __init__(
        self,
        configMng: ConfigMng,
        svcFactory: ServiceFactory,
        cli_flags: dict[str, Any] | None = None,
    )

Shepherd calls ``HelloEnvironmentFactory(configMng, svcFactory, cli_flags)``
and stores the result.  Note: the ``EnvironmentFactory`` base class takes a
different signature — you must override ``__init__`` to accept
``svcFactory`` as the second positional argument.
"""

from __future__ import annotations

from typing import Any

from config import ConfigMng, EnvironmentCfg, EnvironmentTemplateCfg, ServiceCfg
from docker import DockerComposeEnv, DockerComposeSvc
from environment import Environment, EnvironmentFactory
from service import Service, ServiceFactory


class HelloServiceFactory(ServiceFactory):
    """Service factory for the Hello Plugin.

    Delegates to ``DockerComposeSvc`` — the built-in Docker Compose backend.
    Replace the body of ``new_service_from_cfg_impl`` with your own
    ``Service`` subclass to use a custom runtime.
    """

    # ServiceFactory.__init__ takes (self, config: ConfigMng) — no override
    # needed here.  Shepherd calls HelloServiceFactory(configMng).

    @classmethod
    def get_name_impl(cls) -> str:
        return "hello-plugin-svc"

    def new_service_from_cfg_impl(
        self,
        envCfg: EnvironmentCfg,
        svcCfg: ServiceCfg,
        cli_flags: dict[str, Any] | None = None,
    ) -> Service:
        return DockerComposeSvc(
            self.config, envCfg, svcCfg, cli_flags=cli_flags
        )


class HelloEnvironmentFactory(EnvironmentFactory):
    """Environment factory for the Hello Plugin.

    Delegates to ``DockerComposeEnv`` — the built-in Docker Compose backend.
    Replace the body of the ``new_environment_*`` methods with your own
    ``Environment`` subclass to use a custom runtime.
    """

    # EnvironmentFactory.__init__ only accepts (config, cli_flags).
    # We must override it to also accept svcFactory, because Shepherd calls
    # HelloEnvironmentFactory(configMng, svcFactory, cli_flags).
    def __init__(
        self,
        configMng: ConfigMng,
        svcFactory: ServiceFactory,
        cli_flags: dict[str, Any] | None = None,
    ) -> None:
        self.configMng = configMng
        self.svcFactory = svcFactory
        self.cli_flags = cli_flags or {}

    def new_environment_impl(
        self,
        env_tmpl_cfg: EnvironmentTemplateCfg,
        env_tag: str,
    ) -> Environment:
        return DockerComposeEnv(
            self.configMng,
            self.svcFactory,
            self.configMng.env_cfg_from_tag(env_tmpl_cfg, env_tag),
            cli_flags=self.cli_flags,
        )

    def new_environment_cfg_impl(self, envCfg: EnvironmentCfg) -> Environment:
        return DockerComposeEnv(
            self.configMng,
            self.svcFactory,
            envCfg,
            cli_flags=self.cli_flags,
        )
