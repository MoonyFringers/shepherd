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

    COMMANDS_ENV = [
        "init",
        "clone",
        "rename",
        "checkout",
        "delete",
        "list",
        "up",
        "halt",
        "render",
        "reload",
        "status",
        "add",
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
        return command in self.COMMANDS_ENV

    @override
    def get_completions(self, args: list[str]) -> list[str]:
        if not self.is_command_chosen(args):
            return self.COMMANDS_ENV

        command = args[0]
        match command:
            case "init":
                return self.get_init_completions(args[1:])
            case "clone":
                return self.get_clone_completions(args[1:])
            case "rename":
                return self.get_rename_completions(args[1:])
            case "checkout":
                return self.get_checkout_completions(args[1:])
            case "delete":
                return self.get_delete_completions(args[1:])
            case "list":
                return self.get_list_completions(args[1:])
            case "up":
                return self.get_up_completions(args[1:])
            case "halt":
                return self.get_halt_completions(args[1:])
            case "render":
                return self.get_render_completions(args[1:])
            case "reload":
                return self.get_reload_completions(args[1:])
            case "status":
                return self.get_status_completions(args[1:])
            case "add":
                return self.get_add_resource_completions(args[1:])
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

    def get_init_completions(self, args: list[str]) -> list[str]:
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

    def get_up_completions(self, args: list[str]) -> list[str]:
        return []

    def get_halt_completions(self, args: list[str]) -> list[str]:
        return []

    def get_render_completions(self, args: list[str]) -> list[str]:
        if not self.is_src_env_tag_chosen(args):
            return [env.tag for env in self.configMng.get_environments()]
        return []

    def get_reload_completions(self, args: list[str]) -> list[str]:
        return []

    def get_status_completions(self, args: list[str]) -> list[str]:
        return []

    def is_resource_type_chosen(self, args: list[str]) -> bool:
        if not args or len(args) < 1:
            return False
        resource_type = args[0]
        return resource_type in self.configMng.constants.RESOURCE_TYPES

    def is_resource_tag_chosen(self, args: list[str]) -> bool:
        if len(args) < 2:
            return False
        return True

    def is_resource_template_chosen(self, args: list[str]) -> bool:
        if len(args) < 3:
            return False
        resource_template = args[2]
        return resource_template in self.configMng.get_resource_templates(
            args[0]
        )

    def get_resource_templates(self, args: list[str]) -> list[str]:
        return self.configMng.get_resource_templates(args[0])

    def is_resource_class_chosen(self, args: list[str]) -> bool:
        if len(args) < 4:
            return False
        resource_class = args[3]
        return resource_class in self.get_resource_classes(args)

    def get_resource_classes(self, args: list[str]) -> list[str]:
        env = self.configMng.get_active_environment()
        if env:
            return self.configMng.get_resource_classes(env, args[0])
        return []

    def get_add_resource_completions(self, args: list[str]) -> list[str]:
        if not self.is_resource_type_chosen(args):
            return self.configMng.constants.RESOURCE_TYPES
        if not self.is_resource_tag_chosen(args):
            return []
        if not self.is_resource_template_chosen(args):
            return self.get_resource_templates(args)
        if not self.is_resource_class_chosen(args):
            return self.get_resource_classes(args)
        return []
