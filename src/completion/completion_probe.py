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


from typing import override

from completion.completion_mng import AbstractCompletionMng
from config import ConfigMng


class CompletionProbeMng(AbstractCompletionMng):

    def __init__(self, cli_flags: dict[str, bool], configMng: ConfigMng):
        self.cli_flags = cli_flags
        self.configMng = configMng

    @override
    def get_completions(self, args: list[str]) -> list[str]:
        command = args[0]
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
