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


from typing import Optional, override

from completion.completion_env import CompletionEnvMng
from completion.completion_mng import AbstractCompletionMng
from completion.completion_svc import CompletionSvcMng
from config import ConfigMng


class CompletionMng(AbstractCompletionMng):

    CATEGORIES = ["env", "svc"]

    def __init__(self, cli_flags: dict[str, bool], configMng: ConfigMng):
        self.cli_flags = cli_flags
        self.configMng = configMng
        self.completionEnvMng = CompletionEnvMng(cli_flags, configMng)
        self.completionSvcMng = CompletionSvcMng(cli_flags, configMng)

    def is_category_chosen(self, args: list[str]) -> bool:
        """
        Checks if the first argument is a valid category.
        """
        if not args or len(args) < 1:
            return False
        return args[0] in self.CATEGORIES

    def get_completion_manager(
        self, args: list[str]
    ) -> Optional[AbstractCompletionMng]:
        """
        Returns the appropriate completion manager based on the category.
        """

        category = args[0]
        if category == "env":
            return self.completionEnvMng
        elif category == "svc":
            return self.completionSvcMng
        else:
            return None

    @override
    def get_completions(self, args: list[str]) -> list[str]:
        """
        Returns a list of completions based on the provided arguments.
        """

        if not self.is_category_chosen(args):
            return self.CATEGORIES

        completion_manager = self.get_completion_manager(args)
        if completion_manager:
            return completion_manager.get_completions(args[1:])

        return []
