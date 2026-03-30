# Copyright (c) 2025 Moony Fringers
#
# This file is part of Shepherd Core Stack
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Protocol,
    Sequence,
    TypeAlias,
    runtime_checkable,
)

import click

from config import ConfigMng
from environment import EnvironmentFactory
from plugin.context import PluginContext
from service import ServiceFactory


@runtime_checkable
class CompletionProvider(Protocol):
    """
    Object-based completion provider shape.

    Implement this protocol when you want to encapsulate completion logic
    in a class instead of a bare function.  The runtime accepts either a
    ``CompletionProvider`` instance or a plain callable — see
    :data:`CompletionProviderType`.
    """

    def get_completions(self, args: list[str]) -> list[str]:
        """Return completion suggestions for the given raw argument list."""
        ...


# ---------------------------------------------------------------------------
# Provider type aliases — use these to annotate your provider arguments.
# ---------------------------------------------------------------------------

CompletionProviderType: TypeAlias = (
    Callable[[list[str]], list[str]] | CompletionProvider
)
"""
Accepted value for :attr:`PluginCompletionSpec.provider`.

Either a bare callable ``f(args: list[str]) -> list[str]`` *or* an object
that implements the :class:`CompletionProvider` protocol.
"""

SvcFactoryProvider: TypeAlias = (
    ServiceFactory | Callable[[ConfigMng], ServiceFactory]
)
"""
Accepted value for :attr:`PluginSvcFactorySpec.provider`.

Pass the **class** (not an instance) of your ``ServiceFactory`` subclass —
the runtime calls it with ``(configMng,)`` to produce the instance.  A
pre-built instance or a builder callable with the same signature are also
accepted.
"""

EnvFactoryProvider: TypeAlias = (
    EnvironmentFactory
    | Callable[
        [ConfigMng, ServiceFactory, dict[str, Any] | None],
        EnvironmentFactory,
    ]
)
"""
Accepted value for :attr:`PluginEnvFactorySpec.provider`.

Pass the **class** of your ``EnvironmentFactory`` subclass — the runtime
calls it with ``(configMng, svc_factory, cli_flags)`` to produce the
instance.  A pre-built instance or a builder callable with the same
signature are also accepted.
"""


@dataclass(frozen=True)
class PluginCommandSpec:
    """
    One executable scope and verb contribution declared by a plugin.

    ``command`` must be a ready-to-register Click command for the declared
    verb. Shepherd validates that the Click command name matches ``verb``
    before exposing it through the runtime registry.
    """

    scope: str
    verb: str
    command: click.Command


@dataclass(frozen=True)
class PluginCompletionSpec:
    """
    One completion provider contribution keyed by scope.

    ``provider`` must be a callable ``f(args: list[str]) -> list[str]``.
    If you have a class implementing :class:`CompletionProvider`, pass its
    bound method: ``provider=my_obj.get_completions``.

    The runtime validates the shape before adding the provider to the
    registry.
    """

    scope: str
    provider: Callable[[list[str]], list[str]]


@dataclass(frozen=True)
class PluginEnvFactorySpec:
    """
    One environment factory contribution declared by a plugin.

    ``provider`` must satisfy :data:`EnvFactoryProvider` — typically the
    **class** of your ``EnvironmentFactory`` subclass.  The runtime
    instantiates it with ``(configMng, svc_factory, cli_flags)`` on demand.
    """

    id: str
    provider: EnvFactoryProvider


@dataclass(frozen=True)
class PluginSvcFactorySpec:
    """
    One service factory contribution declared by a plugin.

    ``provider`` must satisfy :data:`SvcFactoryProvider` — typically the
    **class** of your ``ServiceFactory`` subclass.  The runtime instantiates
    it with ``(configMng,)`` on demand.
    """

    id: str
    provider: SvcFactoryProvider


class ShepherdPlugin(ABC):
    """
    Root runtime interface implemented by external plugins.

    Shepherd instantiates the concrete subclass with a :class:`PluginContext`
    that provides access to the core config, environment, and service
    managers.  Store it and use it in command handlers:

    .. code-block:: python

        class MyPlugin(ShepherdPlugin):
            def __init__(self, context: PluginContext) -> None:
                super().__init__(context)
                # self.context is now available

    A concrete plugin exposes its capabilities by overriding the
    contribution getters below.  Returning an empty sequence means that the
    plugin does not participate in that extension area.
    """

    def __init__(self, context: PluginContext) -> None:
        self.context = context

    def get_commands(self) -> Sequence[PluginCommandSpec]:
        """Return scope and verb contributions declared by the plugin."""
        return ()

    def get_completion_providers(self) -> Sequence[PluginCompletionSpec]:
        """Return completion providers grouped by the scopes they serve."""
        return ()

    def get_env_factories(self) -> Sequence[PluginEnvFactorySpec]:
        """Return environment factories owned by the plugin."""
        return ()

    def get_service_factories(self) -> Sequence[PluginSvcFactorySpec]:
        """Return service factories owned by the plugin."""
        return ()
