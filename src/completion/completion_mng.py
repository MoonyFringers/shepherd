# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.


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
