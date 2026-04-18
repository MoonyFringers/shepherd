import click
from fixture_plugin.helpers import complete_observability

from config import (
    ConfigMng,
    EnvironmentCfg,
    EnvironmentTemplateCfg,
    ServiceCfg,
)
from config.config import RemoteCfg
from docker import DockerComposeEnv, DockerComposeSvc
from environment import Environment, EnvironmentFactory
from plugin import (
    PluginCommandSpec,
    PluginCompletionSpec,
    PluginEnvFactorySpec,
    PluginRemoteBackendSpec,
    PluginSvcFactorySpec,
    ShepherdPlugin,
)
from remote import RemoteBackend
from service import Service, ServiceFactory


class FakeRemoteBackend(RemoteBackend):
    """Minimal no-op backend for plugin registry tests."""

    def __init__(self, cfg: RemoteCfg) -> None:
        pass

    def exists(self, path: str) -> bool:
        return False

    def upload(self, path: str, data: bytes) -> None:
        pass

    def download(self, path: str) -> bytes:
        return b""

    def list_prefix(self, prefix: str) -> list[str]:
        return []

    def delete(self, path: str) -> None:
        pass

    def close(self) -> None:
        pass


class FixturePluginServiceFactory(ServiceFactory):
    def new_service_from_cfg_impl(
        self,
        envCfg: EnvironmentCfg,
        svcCfg: ServiceCfg,
        cli_flags: dict[str, object] | None = None,
    ) -> Service:
        return DockerComposeSvc(
            self.config, envCfg, svcCfg, cli_flags=cli_flags
        )

    @classmethod
    def get_name_impl(cls) -> str:
        return "fixture-plugin-svc"


class FixturePluginEnvironmentFactory(EnvironmentFactory):
    def __init__(
        self,
        configMng: ConfigMng,
        svcFactory: ServiceFactory,
        cli_flags: dict[str, object] | None = None,
    ):
        self.configMng = configMng
        self.svcFactory = svcFactory
        self.cli_flags = cli_flags or {}

    def new_environment_impl(
        self, env_tmpl_cfg: EnvironmentTemplateCfg, env_tag: str
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


class RuntimeFixturePlugin(ShepherdPlugin):
    def get_commands(self):
        @click.command(name="tail")
        @click.argument("target", required=False)
        def tail(target: str | None):
            click.echo(f"plugin-tail:{target or 'default'}")

        @click.command(name="doctor")
        @click.argument("subject", required=False)
        def doctor(subject: str | None):
            click.echo(f"plugin-doctor:{subject or 'default'}")

        return [
            PluginCommandSpec(
                scope="observability",
                verb="tail",
                command=tail,
            ),
            PluginCommandSpec(scope="env", verb="doctor", command=doctor),
        ]

    def get_completion_providers(self):
        return [
            PluginCompletionSpec(
                scope="observability",
                provider=complete_observability,
            ),
            PluginCompletionSpec(scope="env", provider=complete_observability),
        ]

    def get_env_factories(self):
        return [
            PluginEnvFactorySpec(
                id="baseline-factory",
                provider=FixturePluginEnvironmentFactory,
            )
        ]

    def get_service_factories(self):
        return [
            PluginSvcFactorySpec(
                id="api-factory",
                provider=FixturePluginServiceFactory,
            )
        ]

    def get_remote_backends(self):
        return [
            PluginRemoteBackendSpec(
                type_id="fake-store",
                provider=FakeRemoteBackend,
            )
        ]
