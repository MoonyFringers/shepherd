"""App Plugin — entry point.

This plugin is intentionally *declarative-only*: all of its contribution
lives in ``plugin.yaml`` (a service template, a dependency declaration, and
an env_template that imports a fragment from data-plugin).  The Python
entry-point class is required by Shepherd's plugin loader but does not need
to register any commands, factories, or completion providers.

Fragment embedding pattern
--------------------------
When a plugin wants to compose a fragment contributed by another plugin it:

1.  Declares the provider in ``depends_on`` with an appropriate version
    constraint.  Shepherd loads the provider first, ensuring the fragment is
    already registered when the embedder's env_template is processed.

2.  References the fragment as ``"<provider-id>/<fragment-tag>"`` in the
    ``fragments`` list of the env_template.

3.  Supplies per-import values via the ``with:`` block.  Each entry maps a
    placeholder name (without ``${}`` delimiters) to a concrete value or a
    new ``${VAR}`` expression that falls through to global resolution.
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


class AppPlugin(ShepherdPlugin):
    """Entry-point class for the App Plugin.

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
