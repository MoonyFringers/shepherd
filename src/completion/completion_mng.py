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


from abc import ABC, abstractmethod
from typing import Any

from config import ConfigMng


class AbstractCompletionMng(ABC):
    """
    Internal base class for built-in scope completion managers.

    Concrete managers implement completion for one CLI scope, such as `env`,
    `svc`, `probe`, or the built-in administrative `plugin` scope. The
    top-level `CompletionMng` routes the raw argv to one of these managers once
    it has identified the active scope and verb.

    This abstraction is intentionally internal to Shepherd's built-in
    completion package. External plugins use the public plugin API from
    `plugin.api` instead of subclassing this base directly.
    """

    def __init__(self, cli_flags: dict[str, Any], configMng: ConfigMng):
        self.cli_flags = cli_flags
        self.configMng = configMng

    def get_completions(self, args: list[str]) -> list[str]:
        """
        Return scope-local completion suggestions for raw CLI argv.

        `args` still contains the scope and verb tokens. Individual managers
        are free to dispatch directly on that raw argv or slice it further for
        command-local helper methods.
        """
        return self.get_completions_impl(args)

    @abstractmethod
    def get_completions_impl(self, args: list[str]) -> list[str]:
        """Implement scope-specific completion logic."""
        pass
