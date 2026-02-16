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


class CompletionEnvMng(AbstractCompletionMng):

    def __init__(self, cli_flags: dict[str, bool], configMng: ConfigMng):
        self.cli_flags = cli_flags
        self.configMng = configMng

    @override
    def get_completions_impl(self, args: list[str]) -> list[str]:
        command = args[0]
        match command:
            case "add":
                return self.get_add_completions(args[2:])
            case "clone":
                return self.get_clone_completions(args[2:])
            case "rename":
                return self.get_rename_completions(args[2:])
            case "checkout":
                return self.get_checkout_completions(args[1:])
            case "delete":
                return self.get_delete_completions(args[2:])
            case "list":
                return self.get_list_completions(args[1:])
            case "up":
                return self.get_start_completions(args[2:])
            case "halt":
                return self.get_stop_completions(args[2:])
            case "get":
                return self.get_render_completions(args[2:])
            case "reload":
                return self.get_reload_completions(args[2:])
            case "status":
                return self.get_status_completions(args[2:])
            case _:
                return []

    def is_env_template_chosen(self, args: list[str]) -> bool:
        if not args or len(args) < 1:
            return False
        env_template = args[0]
        return env_template in self.configMng.get_environment_template_tags()

    def is_src_env_tag_chosen(self, args: list[str]) -> bool:
        if not args or len(args) < 1:
            return False
        src_env_tag = args[0]
        return any(
            env.tag == src_env_tag for env in self.configMng.get_environments()
        )

    def get_add_completions(self, args: list[str]) -> list[str]:
        if not self.is_env_template_chosen(args):
            return self.configMng.get_environment_template_tags()
        return []

    def get_clone_completions(self, args: list[str]) -> list[str]:
        if not self.is_src_env_tag_chosen(args):
            return [env.tag for env in self.configMng.get_environments()]
        return []

    def get_rename_completions(self, args: list[str]) -> list[str]:
        if not self.is_src_env_tag_chosen(args):
            return [env.tag for env in self.configMng.get_environments()]
        return []

    def get_checkout_completions(self, args: list[str]) -> list[str]:
        if not self.is_src_env_tag_chosen(args):
            return [
                env.tag
                for env in self.configMng.get_environments()
                if not env.status.active
            ]
        return []

    def get_delete_completions(self, args: list[str]) -> list[str]:
        if not self.is_src_env_tag_chosen(args):
            return [env.tag for env in self.configMng.get_environments()]
        return []

    def get_list_completions(self, args: list[str]) -> list[str]:
        return []

    def get_start_completions(self, args: list[str]) -> list[str]:
        return []

    def get_stop_completions(self, args: list[str]) -> list[str]:
        return []

    def get_render_completions(self, args: list[str]) -> list[str]:
        if not self.is_src_env_tag_chosen(args):
            return [env.tag for env in self.configMng.get_environments()]
        return []

    def get_reload_completions(self, args: list[str]) -> list[str]:
        return []

    def get_status_completions(self, args: list[str]) -> list[str]:
        return []
