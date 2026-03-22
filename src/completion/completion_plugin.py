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
