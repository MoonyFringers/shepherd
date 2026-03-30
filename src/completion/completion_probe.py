# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.io.


from typing import Any, override

from completion.completion_mng import AbstractCompletionMng
from config import ConfigMng


class CompletionProbeMng(AbstractCompletionMng):
    """Probe argument completer for `probe get` and `probe check` flows."""

    def __init__(self, cli_flags: dict[str, Any], configMng: ConfigMng):
        self.cli_flags = cli_flags
        self.configMng = configMng

    @override
    def get_completions_impl(self, args: list[str]) -> list[str]:
        """Dispatch probe completion by verb using scope-local offsets."""
        if len(args) < 2:
            return []
        command = args[1]
        match command:
            case "get":
                return self.get_render_completions(args[2:])
            case "check":
                return self.get_check_completions(args[2:])
            case _:
                return []

    def is_probe_tag_chosen(self, args: list[str]) -> bool:
        if len(args) < 1:
            return False
        svc_tag = args[0]
        return svc_tag in self.get_probe_tags(args)

    def get_probe_tags(self, args: list[str]) -> list[str]:
        env = self.configMng.get_active_environment()
        if env:
            return self.configMng.get_probe_tags(env)
        return []

    def get_render_completions(self, args: list[str]) -> list[str]:
        if not self.is_probe_tag_chosen(args):
            return self.get_probe_tags(args)
        return []

    def get_check_completions(self, args: list[str]) -> list[str]:
        if not self.is_probe_tag_chosen(args):
            return self.get_probe_tags(args)
        return []
