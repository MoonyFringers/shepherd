"""Hello Plugin — entry point.

Shepherd imports this module, instantiates ``HelloPlugin``, and calls the
four contribution getters below.  Each getter returns a sequence of spec
objects that tell Shepherd what the plugin contributes.

Quick reference
---------------
+------------------------------+--------------------------------------------+
| Spec type                    | What it registers                          |
+==============================+============================================+
| PluginCommandSpec            | A new ``<scope> <verb>`` CLI command       |
+------------------------------+--------------------------------------------+
| PluginCompletionSpec         | A completion provider for a scope          |
+------------------------------+--------------------------------------------+
| PluginEnvFactorySpec         | An environment factory                     |
+------------------------------+--------------------------------------------+
| PluginSvcFactorySpec         | A service factory                          |
+------------------------------+--------------------------------------------+

Factory id namespacing
----------------------
Factory ids declared here are local to the plugin (e.g. "echo-factory").
Shepherd automatically namespaces them to "hello-plugin/echo-factory" when
registering.  Use the local id inside ``plugin.yaml`` templates; Shepherd
expands it automatically.
"""

from __future__ import annotations

from typing import Sequence

from hello_plugin.commands import greet
from hello_plugin.completion import complete_hello
from hello_plugin.factories import HelloEnvironmentFactory, HelloServiceFactory

from plugin import (
    PluginCommandSpec,
    PluginCompletionSpec,
    PluginEnvFactorySpec,
    PluginSvcFactorySpec,
    ShepherdPlugin,
)


class HelloPlugin(ShepherdPlugin):
    """Entry-point class for the Hello Plugin.

    Shepherd discovers this class via the ``entrypoint`` stanza in
    ``plugin.yaml`` and calls each getter once during startup.
    """

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def get_commands(self) -> Sequence[PluginCommandSpec]:
        """Register ``shepctl hello greet [name]``.

        ``scope`` is the top-level group (e.g. ``hello``).
        ``verb`` must match the Click command's ``name``.
        ``command`` is the ready-to-register Click command object.
        """
        return [
            PluginCommandSpec(
                scope="hello",
                verb="greet",
                command=greet,
            ),
        ]

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------

    def get_completion_providers(self) -> Sequence[PluginCompletionSpec]:
        """Register a completion provider for the ``hello`` scope.

        ``provider`` must be a callable ``f(args: list[str]) -> list[str]``.
        For class-based providers that implement :class:`CompletionProvider`,
        pass the bound method: ``provider=obj.get_completions``.
        Shepherd merges results from all providers registered for a scope.
        """
        return [
            PluginCompletionSpec(
                scope="hello",
                # bare callable — the simplest provider shape
                provider=complete_hello,
            ),
        ]

    # ------------------------------------------------------------------
    # Environment factories
    # ------------------------------------------------------------------

    def get_env_factories(self) -> Sequence[PluginEnvFactorySpec]:
        """Register the ``demo-env-factory`` environment factory.

        ``id`` is the *local* factory id (no slash).  Shepherd namespaces
        it to ``hello-plugin/demo-env-factory`` in the registry.

        ``provider`` is the factory **class** — Shepherd instantiates it
        by calling
        ``HelloEnvironmentFactory(configMng, svcFactory, cli_flags)``.
        You may also pass a pre-built instance or a builder callable.
        """
        return [
            PluginEnvFactorySpec(
                id="demo-env-factory",
                provider=HelloEnvironmentFactory,
            ),
        ]

    # ------------------------------------------------------------------
    # Service factories
    # ------------------------------------------------------------------

    def get_service_factories(self) -> Sequence[PluginSvcFactorySpec]:
        """Register the ``echo-factory`` service factory.

        ``provider`` is the factory **class** — Shepherd instantiates it
        by calling ``HelloServiceFactory(configMng)``.
        """
        return [
            PluginSvcFactorySpec(
                id="echo-factory",
                provider=HelloServiceFactory,
            ),
        ]
