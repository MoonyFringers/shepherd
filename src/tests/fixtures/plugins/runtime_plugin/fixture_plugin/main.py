import click
from fixture_plugin.helpers import complete_observability

from plugin import (
    PluginCommandSpec,
    PluginCompletionSpec,
    PluginFactorySpec,
    PluginTemplateSpec,
    ShepherdPlugin,
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
        return [PluginTemplateSpec(id="baseline", provider={"kind": "env"})]

    def get_service_templates(self):
        return [PluginTemplateSpec(id="api", provider={"kind": "svc"})]

    def get_env_factories(self):
        return [
            PluginFactorySpec(id="baseline-factory", provider="env-factory")
        ]

    def get_service_factories(self):
        return [PluginFactorySpec(id="api-factory", provider="svc-factory")]
