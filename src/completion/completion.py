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
from completion.completion_probe import CompletionProbeMng
from completion.completion_svc import CompletionSvcMng
from config import ConfigMng


class CompletionMng(AbstractCompletionMng):

    # Mapping of verbs to valid categories
    VERB_CATEGORIES = {
        "get": ["env", "svc", "probe"],
        "add": ["env", "svc"],
        "clone": ["env"],
        "rename": ["env"],
        "checkout": ["auto-env"],
        "delete": ["env"],
        "list": ["auto-env"],
        "up": ["env", "svc"],
        "halt": ["env", "svc"],
        "reload": ["env", "svc"],
        "status": ["env"],
        "logs": ["auto-svc"],
        "shell": ["auto-svc"],
        "build": ["auto-svc"],
        "check": ["probe"],
    }

    def __init__(self, cli_flags: dict[str, bool], configMng: ConfigMng):
        self.cli_flags = cli_flags
        self.configMng = configMng
        self.completionEnvMng = CompletionEnvMng(cli_flags, configMng)
        self.completionSvcMng = CompletionSvcMng(cli_flags, configMng)
        self.completionProbeMng = CompletionProbeMng(cli_flags, configMng)

    @property
    def VERBS(self) -> list[str]:
        """return all verbs from the mapping."""
        return list(self.VERB_CATEGORIES.keys())

    def is_verb_chosen(self, args: list[str]) -> bool:
        if not args or len(args) < 1:
            return False
        return args[0] in self.VERBS

    def is_category_chosen(self, args: list[str]) -> bool:
        if not args or len(args) < 2:
            return False
        verb = args[0]
        category = args[1]
        return category in self.VERB_CATEGORIES.get(verb, [])

    def get_auto_category(self, args: list[str]) -> Optional[str]:
        if not args:
            return None
        verb = args[0]
        if self.VERB_CATEGORIES.get(verb, [])[0].startswith("auto-"):
            return self.VERB_CATEGORIES[verb][0].split("-")[1]
        else:
            return None

    def get_completion_manager(
        self, args: list[str], auto_category: Optional[str] = None
    ) -> Optional[AbstractCompletionMng]:
        # Priority: use auto_category if provided, otherwise try args[1]
        category = auto_category or (args[1] if len(args) > 1 else None)
        if not category:
            return None

        if category == "env":
            return self.completionEnvMng
        if category == "svc":
            return self.completionSvcMng
        if category == "probe":
            return self.completionProbeMng

        return None

    @override
    def get_completions_impl(self, args: list[str]) -> list[str]:
        if not self.is_verb_chosen(args):
            return self.VERBS

        auto_category = self.get_auto_category(args)

        if not auto_category and not self.is_category_chosen(args):
            # suggest only valid categories for this verb
            verb = args[0]
            return self.VERB_CATEGORIES.get(verb, [])

        completion_manager = self.get_completion_manager(args, auto_category)
        if completion_manager:
            return completion_manager.get_completions(args)

        return []
