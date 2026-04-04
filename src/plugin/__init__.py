# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

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
from .context import (
    PluginConfigView,
    PluginContext,
    PluginEnvironmentView,
    PluginServiceView,
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
    "PluginConfigView",
    "PluginContext",
    "PluginEnvFactorySpec",
    "PluginEnvironmentView",
    "PluginMng",
    "PluginRegistry",
    "PluginRuntimeMng",
    "PluginServiceView",
    "PluginSvcFactorySpec",
    "ShepherdPlugin",
    "SvcFactoryProvider",
]
