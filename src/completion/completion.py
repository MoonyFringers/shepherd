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

    It first resolves the command verb, then routes to a domain-specific
    completion manager (`env`, `svc`, `probe`) based on either explicit
    category tokens or implicit `auto-*` categories.
    """

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
        ("up", None): (
            OptionSpec(tokens=("--details",)),
            OptionSpec(tokens=("--show-commands",)),
            OptionSpec(tokens=("--show-commands-limit",), takes_value=True),
            OptionSpec(tokens=("--timeout",), takes_value=True),
            OptionSpec(tokens=("-w", "--watch")),
        ),
        ("up", "env"): (
            OptionSpec(tokens=("--details",)),
            OptionSpec(tokens=("--show-commands",)),
            OptionSpec(tokens=("--show-commands-limit",), takes_value=True),
            OptionSpec(tokens=("--timeout",), takes_value=True),
            OptionSpec(tokens=("-w", "--watch")),
        ),
        ("halt", None): (OptionSpec(tokens=("--no-wait",)),),
        ("halt", "env"): (OptionSpec(tokens=("--no-wait",)),),
        ("reload", "env"): (
            OptionSpec(tokens=("--details",)),
            OptionSpec(tokens=("--show-commands",)),
            OptionSpec(tokens=("--show-commands-limit",), takes_value=True),
            OptionSpec(tokens=("-w", "--watch")),
        ),
        ("status", None): (
            OptionSpec(tokens=("--details",)),
            OptionSpec(tokens=("--show-commands",)),
            OptionSpec(tokens=("--show-commands-limit",), takes_value=True),
            OptionSpec(tokens=("-w", "--watch")),
        ),
        ("status", "env"): (
            OptionSpec(tokens=("--details",)),
            OptionSpec(tokens=("--show-commands",)),
            OptionSpec(tokens=("--show-commands-limit",), takes_value=True),
            OptionSpec(tokens=("-w", "--watch")),
        ),
        ("get", "env"): (
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
        ("get", "probe"): (
            OptionSpec(
                tokens=("-o", "--output"),
                takes_value=True,
                choices=("yaml", "json"),
            ),
            OptionSpec(tokens=("-t", "--target")),
            OptionSpec(tokens=("-r", "--resolved")),
            OptionSpec(tokens=("-a", "--all")),
        ),
        ("get", "svc"): (
            OptionSpec(
                tokens=("-o", "--output"),
                takes_value=True,
                choices=("yaml", "json"),
            ),
            OptionSpec(tokens=("-t", "--target")),
            OptionSpec(tokens=("-r", "--resolved")),
            OptionSpec(tokens=("--details",)),
        ),
        ("check", "probe"): (OptionSpec(tokens=("-a", "--all")),),
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
        """
        Resolve implicit category for verbs that do not expose it in argv.

        Example: `logs <svc>` maps to `auto-svc`, so completion is delegated
        directly to the service completion manager.
        """
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
        """Select the concrete completion manager for the resolved category."""
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

    def _match_option(self, token: str) -> Optional[OptionSpec]:
        """
        Resolve one raw argv token to a known option spec.

        The matcher accepts:
        - exact flag tokens like `--watch`
        - long options with inline values like `--output=yaml`
        - compact short options with inline values like `-oyaml`
        """
        spec = self._option_by_token.get(token)
        if spec:
            return spec
        if token.startswith("--") and "=" in token:
            # Support long-form inline values like `--output=yaml`.
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
                # Support compact short-form values like `-oyaml`.
                return candidate
        return None

    def _parse_args(
        self, args: list[str]
    ) -> tuple[
        list[str], Optional[str], Optional[str], set[str], Optional[OptionSpec]
    ]:
        """
        Split raw argv into positional routing tokens and option state.

        Completion needs more than a simple "strip flags" pass because shell
        completion usually sends the argument currently being edited as the
        final token in `args`. For value-taking options this means the last
        token can be:
        - the option name itself: `--output`
        - an empty current arg after a space: `--output ""`
        - a partial value: `--output y`
        - a fully typed value: `--output yaml`

        This parser returns:
        - `sanitized`: argv with option tokens and consumed option values
          removed, used for verb/category/positional completion routing
        - `verb` / `category`: resolved command context from positional tokens
        - `used_options`: flags already present, so we do not keep suggesting
          them
        - `expect_value_for`: the option that still owns the current final
          token when that token is an empty or partial value
        """
        sanitized: list[str] = []
        verb: Optional[str] = None
        category: Optional[str] = None
        used_options: set[str] = set()
        expect_value_for: Optional[CompletionMng.OptionSpec] = None

        for idx, token in enumerate(args):
            if expect_value_for is not None:
                if idx == len(args) - 1:
                    # Shell completion often passes the "current" argument as
                    # the final token. Keep the option in a pending state for
                    # empty or partial values so `get_completions_impl` can
                    # suggest the option's allowed choices.
                    if token == "" or token not in expect_value_for.choices:
                        break
                    # A fully matched final token (e.g. `yaml`) is treated as
                    # consumed so completion can move on to the next argument.
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
                    # Defer the next raw token to the option-value parser.
                    expect_value_for = option
                continue

            sanitized.append(token)
            if verb is None and token in self.VERBS:
                verb = token
                continue
            if (
                verb is not None
                and category is None
                and token in self.VERB_CATEGORIES.get(verb, [])
            ):
                category = token

        return sanitized, verb, category, used_options, expect_value_for

    def _get_context_options(
        self, verb: Optional[str], category: Optional[str]
    ) -> list[OptionSpec]:
        if verb is None:
            return list(self.GLOBAL_OPTIONS)
        if category is None:
            options = list(self.CONTEXT_OPTIONS.get((verb, None), ()))
        else:
            options = list(self.CONTEXT_OPTIONS.get((verb, category), ()))
        seen: set[tuple[str, ...]] = set()
        deduped: list[CompletionMng.OptionSpec] = []
        for spec in options:
            if spec.tokens in seen:
                continue
            seen.add(spec.tokens)
            deduped.append(spec)
        return deduped

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
        """
        Completion flow:
        1. parse raw argv into positional routing tokens plus option state
        2. if a value-taking option owns the current token, complete values
        3. otherwise complete verbs / categories / positional args by context
        4. merge in context-appropriate flag suggestions
        """
        sanitized_args, verb, category, used_options, expect_value_for = (
            self._parse_args(args)
        )
        last_token = args[-1] if args else ""
        last_option = self._match_option(last_token) if last_token else None
        option_prefix: Optional[str] = None
        if last_token.startswith("-"):
            option_prefix = last_token

        if expect_value_for is not None:
            if last_token in expect_value_for.tokens:
                return list(expect_value_for.choices)
            if not last_token.startswith("-"):
                return [
                    choice
                    for choice in expect_value_for.choices
                    if not last_token or choice.startswith(last_token)
                ]

        if not verb:
            if option_prefix is not None:
                return self._get_option_suggestions(
                    list(self.GLOBAL_OPTIONS),
                    used_options=used_options,
                    prefix=option_prefix,
                )
            return list(self.VERBS)

        auto_category = self.get_auto_category(sanitized_args)
        context_options = self._get_context_options(verb, category)

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

        if not auto_category and not self.is_category_chosen(sanitized_args):
            # suggest only valid categories for this verb
            suggestions = list(self.VERB_CATEGORIES.get(verb, []))
            if not suggestions:
                suggestions.extend(
                    self._get_option_suggestions(
                        context_options, used_options=used_options
                    )
                )
            return self._unique(suggestions)

        completion_manager = self.get_completion_manager(
            sanitized_args, auto_category
        )
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
