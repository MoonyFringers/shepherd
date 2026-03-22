import click
from fixture_plugin.helpers import complete_observability

from config import (
    ConfigMng,
    ContainerCfg,
    EnvironmentCfg,
    EnvironmentTemplateCfg,
    ServiceCfg,
    ServiceTemplateCfg,
    ServiceTemplateRefCfg,
)
from docker import DockerComposeEnv, DockerComposeSvc
from environment import Environment, EnvironmentFactory
from plugin import (
    PluginCommandSpec,
    PluginCompletionSpec,
    PluginFactorySpec,
    PluginTemplateSpec,
    ShepherdPlugin,
)
from service import Service, ServiceFactory


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

    def get_env_templates(self):
        return [
            PluginTemplateSpec(
                id="baseline",
                provider=EnvironmentTemplateCfg(
                    tag="runtime-plugin/baseline",
                    factory="runtime-plugin/baseline-factory",
                    service_templates=[
                        ServiceTemplateRefCfg(
                            template="runtime-plugin/api",
                            tag="plugin-api",
                        )
                    ],
                    probes=None,
                    networks=None,
                    volumes=None,
                ),
            )
        ]

    def get_service_templates(self):
        return [
            PluginTemplateSpec(
                id="api",
                provider=ServiceTemplateCfg(
                    tag="runtime-plugin/api",
                    factory="runtime-plugin/api-factory",
                    labels=[],
                    properties={"source": "plugin"},
                    containers=[
                        ContainerCfg(
                            image="busybox:stable-glibc",
                            tag="app",
                            container_name=None,
                            hostname=None,
                            workdir=None,
                            volumes=[],
                            environment=[],
                            ports=[],
                            networks=[],
                            extra_hosts=[],
                            inits=None,
                            build=None,
                        )
                    ],
                    start=None,
                ),
            )
        ]

    def get_env_factories(self):
        return [
            PluginFactorySpec(
                id="baseline-factory",
                provider=FixturePluginEnvironmentFactory,
            )
        ]

    def get_service_factories(self):
        return [
            PluginFactorySpec(
                id="api-factory",
                provider=FixturePluginServiceFactory,
            )
        ]
