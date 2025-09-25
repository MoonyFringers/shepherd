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

    def __init__(self, cli_flags: dict[str, bool], configMng: ConfigMng):
        self.cli_flags = cli_flags
        self.configMng = configMng

    @override
    def get_completions(self, args: list[str]) -> list[str]:
        command = args[0]
        match command:
            case "add":
                return self.get_add_completions(args[2:])
            case "build":
                return self.get_build_completions(args[1:])
            case "up":
                return self.get_start_completions(args[2:])
            case "halt":
                return self.get_stop_completions(args[2:])
            case "logs":
                return self.get_logs_completions(args[1:])
            case "shell":
                return self.get_shell_completions(args[1:])
            case "get":
                return self.get_render_completions(args[2:])
            case "reload":
                return self.get_reload_completions(args[2:])
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

    def get_start_completions(self, args: list[str]) -> list[str]:
        if not self.is_svc_tag_chosen(args):
            return self.get_svc_tags(args)
        return []

    def get_stop_completions(self, args: list[str]) -> list[str]:
        if not self.is_svc_tag_chosen(args):
            return self.get_svc_tags(args)
        return []

    def get_logs_completions(self, args: list[str]) -> list[str]:
        if not self.is_svc_tag_chosen(args):
            return self.get_svc_tags(args)
        return []

    def get_shell_completions(self, args: list[str]) -> list[str]:
        if not self.is_svc_tag_chosen(args):
            return self.get_svc_tags(args)
        return []

    def get_render_completions(self, args: list[str]) -> list[str]:
        if not self.is_svc_tag_chosen(args):
            return self.get_svc_tags(args)
        return []

    def get_reload_completions(self, args: list[str]) -> list[str]:
        if not self.is_svc_tag_chosen(args):
            return self.get_svc_tags(args)
        return []

    def is_svc_class_chosen(self, args: list[str]) -> bool:
        if len(args) < 3:
            return False
        svc_class = args[2]
        return svc_class in self.get_svc_classes(args)

    def get_svc_classes(self, args: list[str]) -> list[str]:
        env = self.configMng.get_active_environment()
        if env:
            return self.configMng.get_resource_classes(
                env, self.configMng.constants.RESOURCE_TYPE_SVC
            )
        return []

    def is_svc_tag_produced(self, args: list[str]) -> bool:
        if len(args) < 2:
            return False
        return True

    def get_add_completions(self, args: list[str]) -> list[str]:
        if not self.is_svc_template_chosen(args):
            return self.get_svc_templates(args)
        if not self.is_svc_tag_produced(args):
            return []
        if not self.is_svc_class_chosen(args):
            return self.get_svc_classes(args)
        return []
