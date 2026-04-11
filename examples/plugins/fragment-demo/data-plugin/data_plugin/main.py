"""Data Plugin — entry point.

This plugin is intentionally *declarative-only*: all of its contribution
lives in ``plugin.yaml`` (a service template and a fragment).  The Python
entry-point class is required by Shepherd's plugin loader but does not need
to register any commands, factories, or completion providers.

When to use this pattern
------------------------
Use a purely declarative plugin when the plugin's value is in the template
definitions and fragments it contributes rather than in runtime behaviour.
The four getter methods simply return empty sequences, which is valid for any
capability that the plugin does not declare in its ``capabilities`` block.

Because ``capabilities`` is not set in this plugin's ``plugin.yaml``, Shepherd
does not call the getters and the plugin loads with no runtime overhead beyond
the initial import.
"""

from __future__ import annotations

from typing import Sequence

from plugin import (
    PluginCommandSpec,
    PluginCompletionSpec,
    PluginContext,
    PluginEnvFactorySpec,
    PluginSvcFactorySpec,
    ShepherdPlugin,
)


class DataPlugin(ShepherdPlugin):
    """Entry-point class for the Data Plugin.

    All contributions are declared in ``plugin.yaml`` — this class exists
    solely to satisfy the plugin loader's ``entrypoint`` requirement.
    """

    def __init__(self, context: PluginContext) -> None:
        super().__init__(context)

    def get_commands(self) -> Sequence[PluginCommandSpec]:
        return []

    def get_completion_providers(self) -> Sequence[PluginCompletionSpec]:
        return []

    def get_env_factories(self) -> Sequence[PluginEnvFactorySpec]:
        return []

    def get_service_factories(self) -> Sequence[PluginSvcFactorySpec]:
        return []
