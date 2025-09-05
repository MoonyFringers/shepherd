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


class CompletionSvcMng(AbstractCompletionMng):

    COMMANDS_SVC = [
        "build",
        "up",
        "halt",
        "stdout",
        "shell",
        "get",
        "reload",
    ]

    def __init__(self, cli_flags: dict[str, bool], configMng: ConfigMng):
        self.cli_flags = cli_flags
        self.configMng = configMng

    def is_command_chosen(self, args: list[str]) -> bool:
        """
        Checks if the second argument is a valid command
        for the chosen category.
        """
        if not args or len(args) < 1:
            return False
        command = args[0]
        return command in self.COMMANDS_SVC

    @override
    def get_completions(self, args: list[str]) -> list[str]:
        if not self.is_command_chosen(args):
            return self.COMMANDS_SVC

        command = args[0]
        match command:
            case "build":
                return self.get_build_completions(args[1:])
            case "up":
                return self.get_up_completions(args[1:])
            case "halt":
                return self.get_halt_completions(args[1:])
            case "stdout":
                return self.get_stdout_completions(args[1:])
            case "shell":
                return self.get_shell_completions(args[1:])
            case "get":
                return self.get_render_target_cfg_completions(args[1:])
            case "reload":
                return self.get_reload_completions(args[1:])
            case _:
                return []

    def is_svc_template_chosen(self, args: list[str]) -> bool:
        if len(args) < 1:
            return False
        resource_template = args[0]
        return resource_template in self.configMng.get_resource_templates(
            self.configMng.constants.RESOURCE_TYPE_SVC
        )

    def get_svc_templates(self, args: list[str]) -> list[str]:
        return self.configMng.get_resource_templates(
            self.configMng.constants.RESOURCE_TYPE_SVC
        )

    def get_build_completions(self, args: list[str]) -> list[str]:
        if not self.is_svc_template_chosen(args):
            return self.get_svc_templates(args)
        return []

    def is_svc_tag_chosen(self, args: list[str]) -> bool:
        if len(args) < 1:
            return False
        svc_tag = args[0]
        return svc_tag in self.get_svc_tags(args)

    def get_svc_tags(self, args: list[str]) -> list[str]:
        env = self.configMng.get_active_environment()
        if env:
            return self.configMng.get_service_tags(env)
        return []

    def get_up_completions(self, args: list[str]) -> list[str]:
        if not self.is_svc_tag_chosen(args):
            return self.get_svc_tags(args)
        return []

    def get_halt_completions(self, args: list[str]) -> list[str]:
        if not self.is_svc_tag_chosen(args):
            return self.get_svc_tags(args)
        return []

    def get_stdout_completions(self, args: list[str]) -> list[str]:
        if not self.is_svc_tag_chosen(args):
            return self.get_svc_tags(args)
        return []

    def get_shell_completions(self, args: list[str]) -> list[str]:
        if not self.is_svc_tag_chosen(args):
            return self.get_svc_tags(args)
        return []

    def get_render_target_cfg_completions(self, args: list[str]) -> list[str]:
        if not self.is_svc_tag_chosen(args):
            return self.get_svc_tags(args)
        return []

    def get_reload_completions(self, args: list[str]) -> list[str]:
        if not self.is_svc_tag_chosen(args):
            return self.get_svc_tags(args)
        return []
