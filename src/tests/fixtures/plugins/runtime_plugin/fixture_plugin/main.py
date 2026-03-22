from fixture_plugin.helpers import COMPLETION_PROVIDER

from plugin import (
    PluginCommandSpec,
    PluginCompletionSpec,
    PluginFactorySpec,
    PluginTemplateSpec,
    ShepherdPlugin,
)


class RuntimeFixturePlugin(ShepherdPlugin):
    def get_commands(self):
        return [
            PluginCommandSpec(scope="observability", verb="tail"),
            PluginCommandSpec(scope="env", verb="doctor"),
        ]

    def get_completion_providers(self):
        return [
            PluginCompletionSpec(
                scope="observability",
                provider=COMPLETION_PROVIDER,
            )
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
