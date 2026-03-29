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

"""Public plugin APIs shared by the CLI bootstrap and external plugins."""

from .api import (
    CompletionProvider,
    CompletionProviderType,
    EnvFactoryProvider,
    PluginCommandSpec,
    PluginCompletionSpec,
    PluginEnvFactorySpec,
    PluginSvcFactorySpec,
    ShepherdPlugin,
    SvcFactoryProvider,
)
from .plugin import PluginMng
from .runtime import (
    LoadedPlugin,
    PluginRegistry,
    PluginRuntimeMng,
)

__all__ = [
    "CompletionProvider",
    "CompletionProviderType",
    "EnvFactoryProvider",
    "LoadedPlugin",
    "PluginCommandSpec",
    "PluginCompletionSpec",
    "PluginEnvFactorySpec",
    "PluginMng",
    "PluginRegistry",
    "PluginRuntimeMng",
    "PluginSvcFactorySpec",
    "ShepherdPlugin",
    "SvcFactoryProvider",
]
