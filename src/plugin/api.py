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
from typing import Any, Sequence


@dataclass(frozen=True)
class PluginCommandSpec:
    """One scope/verb pair contributed by a plugin."""

    scope: str
    verb: str


@dataclass(frozen=True)
class PluginCompletionSpec:
    """
    One completion provider contribution keyed by scope.

    `provider` is intentionally untyped in this step because the runtime
    loader only stores provider objects in the registry; it does not invoke
    them yet. A later completion-integration step will narrow this to the
    concrete callable or provider protocol the completion engine expects.
    """

    scope: str
    provider: Any


@dataclass(frozen=True)
class PluginTemplateSpec:
    """
    One template contribution declared by a plugin.

    `provider` carries the plugin-owned object or data structure that
    describes the template payload. The loader treats it as opaque for now and
    only registers it under the canonical `plugin-id/template-id` name.
    """

    id: str
    provider: Any


@dataclass(frozen=True)
class PluginFactorySpec:
    """
    One factory contribution declared by a plugin.

    `provider` carries the concrete factory object published by the plugin.
    The runtime layer currently validates and stores it only; env and service
    flows will start consuming these provider objects in a later rollout step.
    """

    id: str
    provider: Any


class ShepherdPlugin(ABC):
    """
    Root runtime interface implemented by external plugins.

    A concrete plugin exposes its capabilities by overriding the contribution
    getters below. Returning an empty sequence means that the plugin does not
    participate in that extension area.
    """

    def get_commands(self) -> Sequence[PluginCommandSpec]:
        """Return scope and verb contributions declared by the plugin."""
        return ()

    def get_completion_providers(self) -> Sequence[PluginCompletionSpec]:
        """Return completion providers grouped by the scopes they serve."""
        return ()

    def get_env_templates(self) -> Sequence[PluginTemplateSpec]:
        """Return environment templates owned by the plugin."""
        return ()

    def get_service_templates(self) -> Sequence[PluginTemplateSpec]:
        """Return service templates owned by the plugin."""
        return ()

    def get_env_factories(self) -> Sequence[PluginFactorySpec]:
        """Return environment factories owned by the plugin."""
        return ()

    def get_service_factories(self) -> Sequence[PluginFactorySpec]:
        """Return service factories owned by the plugin."""
        return ()
