# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.io.

from typing import Any, override

from completion.completion_mng import AbstractCompletionMng
from config import ConfigMng


class CompletionPluginMng(AbstractCompletionMng):
    """Administrative plugin scope completer."""

    def __init__(self, cli_flags: dict[str, Any], configMng: ConfigMng):
        self.cli_flags = cli_flags
        self.configMng = configMng

    @override
    def get_completions_impl(self, args: list[str]) -> list[str]:
        """Complete plugin inventory verbs that take a plugin id argument."""
        if len(args) < 2:
            return []

        verb = args[1]
        if verb not in {"get", "enable", "disable", "remove"}:
            return []

        plugin_ids = sorted(
            [plugin.id for plugin in self.configMng.get_plugins()]
        )
        local_args = args[2:]
        if len(local_args) > 1:
            return []
        if len(local_args) == 1:
            prefix = local_args[0]
            return [
                plugin_id
                for plugin_id in plugin_ids
                if plugin_id.startswith(prefix)
            ]
        return plugin_ids
