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


from dataclasses import dataclass
from typing import Any, Optional, override

from completion.completion_env import CompletionEnvMng
from completion.completion_mng import AbstractCompletionMng
from completion.completion_probe import CompletionProbeMng
from completion.completion_svc import CompletionSvcMng
from config import ConfigMng


class CompletionMng(AbstractCompletionMng):
    """
    Top-level completion router.

    Completion is now routed by `scope` first and then by verb within that
    scope, mirroring the Click command tree.
    """

    SCOPE_VERBS = {
        "env": [
            "get",
            "add",
            "clone",
            "rename",
            "checkout",
            "delete",
            "list",
            "up",
            "halt",
            "reload",
            "status",
        ],
        "svc": ["get", "add", "up", "halt", "reload", "build", "logs", "shell"],
        "probe": ["get", "check"],
    }

    @dataclass(frozen=True)
    class OptionSpec:
        tokens: tuple[str, ...]
        takes_value: bool = False
        choices: tuple[str, ...] = ()

    GLOBAL_OPTIONS = (
        OptionSpec(tokens=("-v", "--verbose")),
        OptionSpec(tokens=("--quiet",)),
        OptionSpec(tokens=("-y", "--yes")),
    )
    CONTEXT_OPTIONS = {
        ("env", "up"): (
            OptionSpec(tokens=("--show-commands",)),
            OptionSpec(tokens=("--show-commands-limit",), takes_value=True),
            OptionSpec(tokens=("--timeout",), takes_value=True),
            OptionSpec(tokens=("-w", "--watch")),
        ),
        ("env", "halt"): (OptionSpec(tokens=("--no-wait",)),),
        ("env", "reload"): (
            OptionSpec(tokens=("--show-commands",)),
            OptionSpec(tokens=("--show-commands-limit",), takes_value=True),
            OptionSpec(tokens=("-w", "--watch")),
        ),
        ("env", "status"): (
            OptionSpec(tokens=("--show-commands",)),
            OptionSpec(tokens=("--show-commands-limit",), takes_value=True),
            OptionSpec(tokens=("-w", "--watch")),
        ),
        ("env", "get"): (
            OptionSpec(
                tokens=("-o", "--output"),
                takes_value=True,
                choices=("yaml", "json"),
            ),
            OptionSpec(tokens=("-t", "--target")),
            OptionSpec(tokens=("--by-gate",)),
            OptionSpec(tokens=("-r", "--resolved")),
            OptionSpec(tokens=("--details",)),
        ),
        ("probe", "get"): (
            OptionSpec(
                tokens=("-o", "--output"),
                takes_value=True,
                choices=("yaml", "json"),
            ),
            OptionSpec(tokens=("-t", "--target")),
            OptionSpec(tokens=("-r", "--resolved")),
            OptionSpec(tokens=("-a", "--all")),
        ),
        ("svc", "get"): (
            OptionSpec(
                tokens=("-o", "--output"),
                takes_value=True,
                choices=("yaml", "json"),
            ),
            OptionSpec(tokens=("-t", "--target")),
            OptionSpec(tokens=("-r", "--resolved")),
            OptionSpec(tokens=("--details",)),
        ),
        ("probe", "check"): (OptionSpec(tokens=("-a", "--all")),),
    }

    def __init__(self, cli_flags: dict[str, Any], configMng: ConfigMng):
        self.cli_flags = cli_flags
        self.configMng = configMng
        self.completionEnvMng = CompletionEnvMng(cli_flags, configMng)
        self.completionSvcMng = CompletionSvcMng(cli_flags, configMng)
        self.completionProbeMng = CompletionProbeMng(cli_flags, configMng)
        self._option_by_token: dict[str, CompletionMng.OptionSpec] = {}
        for spec in self.GLOBAL_OPTIONS:
            for token in spec.tokens:
                self._option_by_token[token] = spec
        for specs in self.CONTEXT_OPTIONS.values():
            for spec in specs:
                for token in spec.tokens:
                    self._option_by_token[token] = spec

    @property
    def SCOPES(self) -> list[str]:
        return list(self.SCOPE_VERBS.keys())

    def is_scope_chosen(self, args: list[str]) -> bool:
        return bool(args) and args[0] in self.SCOPES

    def is_verb_chosen(self, args: list[str]) -> bool:
        if len(args) < 2:
            return False
        return args[1] in self.SCOPE_VERBS.get(args[0], [])

    def get_completion_manager(
        self, scope: Optional[str]
    ) -> Optional[AbstractCompletionMng]:
        if scope == "env":
            return self.completionEnvMng
        if scope == "svc":
            return self.completionSvcMng
        if scope == "probe":
            return self.completionProbeMng
        return None

    def _match_option(self, token: str) -> Optional[OptionSpec]:
        spec = self._option_by_token.get(token)
        if spec:
            return spec
        if token.startswith("--") and "=" in token:
            name, _, _value = token.partition("=")
            return self._option_by_token.get(name)
        for name, candidate in self._option_by_token.items():
            if (
                candidate.takes_value
                and name.startswith("-")
                and not name.startswith("--")
                and token.startswith(name)
                and token != name
            ):
                return candidate
        return None

    def _parse_args(
        self, args: list[str]
    ) -> tuple[
        list[str], Optional[str], Optional[str], set[str], Optional[OptionSpec]
    ]:
        sanitized: list[str] = []
        scope: Optional[str] = None
        verb: Optional[str] = None
        used_options: set[str] = set()
        expect_value_for: Optional[CompletionMng.OptionSpec] = None

        for idx, token in enumerate(args):
            if expect_value_for is not None:
                if idx == len(args) - 1:
                    if token == "" or token not in expect_value_for.choices:
                        break
                expect_value_for = None
                continue

            option = self._match_option(token)
            if option is not None:
                used_options.update(option.tokens)
                if option.takes_value:
                    if token.startswith("--") and "=" in token:
                        continue
                    if any(
                        token.startswith(name) and token != name
                        for name in option.tokens
                        if name.startswith("-") and not name.startswith("--")
                    ):
                        continue
                    expect_value_for = option
                continue

            sanitized.append(token)
            if scope is None and token in self.SCOPES:
                scope = token
                continue
            if verb is None and scope is not None:
                if token in self.SCOPE_VERBS.get(scope, []):
                    verb = token

        return sanitized, scope, verb, used_options, expect_value_for

    def _get_context_options(
        self, scope: Optional[str], verb: Optional[str]
    ) -> list[OptionSpec]:
        if scope is None:
            return list(self.GLOBAL_OPTIONS)
        if verb is None:
            return []
        return list(self.CONTEXT_OPTIONS.get((scope, verb), ()))

    def _get_option_suggestions(
        self,
        options: list[OptionSpec],
        *,
        used_options: set[str],
        prefix: str = "",
    ) -> list[str]:
        suggestions: list[str] = []
        for spec in options:
            if all(token in used_options for token in spec.tokens):
                continue
            for token in spec.tokens:
                if prefix and not token.startswith(prefix):
                    continue
                suggestions.append(token)
        return suggestions

    def _unique(self, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    @override
    def get_completions_impl(self, args: list[str]) -> list[str]:
        sanitized_args, scope, verb, used_options, expect_value_for = (
            self._parse_args(args)
        )
        last_token = args[-1] if args else ""
        last_option = self._match_option(last_token) if last_token else None
        option_prefix: Optional[str] = (
            last_token if last_token.startswith("-") else None
        )

        if expect_value_for is not None:
            if last_token in expect_value_for.tokens:
                return list(expect_value_for.choices)
            if not last_token.startswith("-"):
                return [
                    choice
                    for choice in expect_value_for.choices
                    if not last_token or choice.startswith(last_token)
                ]

        if not scope:
            if option_prefix is not None:
                return self._get_option_suggestions(
                    list(self.GLOBAL_OPTIONS),
                    used_options=used_options,
                    prefix=option_prefix,
                )
            return list(self.SCOPES)

        context_options = self._get_context_options(scope, verb)

        if option_prefix is not None and not (
            last_option is not None
            and last_option.takes_value
            and last_token not in last_option.tokens
        ):
            return self._get_option_suggestions(
                context_options,
                used_options=used_options,
                prefix=option_prefix,
            )

        if not verb:
            suggestions = list(self.SCOPE_VERBS.get(scope, []))
            if not suggestions:
                suggestions.extend(
                    self._get_option_suggestions(
                        context_options, used_options=used_options
                    )
                )
            return self._unique(suggestions)

        completion_manager = self.get_completion_manager(scope)
        if completion_manager:
            suggestions = completion_manager.get_completions(sanitized_args)
            if option_prefix is not None:
                suggestions.extend(
                    self._get_option_suggestions(
                        context_options,
                        used_options=used_options,
                        prefix=option_prefix,
                    )
                )
            elif not suggestions:
                suggestions.extend(
                    self._get_option_suggestions(
                        context_options, used_options=used_options
                    )
                )
            return self._unique(suggestions)

        return []
