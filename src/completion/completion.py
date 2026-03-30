# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.io.


from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, override

from completion.completion_env import CompletionEnvMng
from completion.completion_mng import AbstractCompletionMng
from completion.completion_plugin import CompletionPluginMng
from completion.completion_probe import CompletionProbeMng
from completion.completion_svc import CompletionSvcMng
from config import ConfigMng

if TYPE_CHECKING:
    from plugin import PluginRegistry


class CompletionMng(AbstractCompletionMng):
    """
    Top-level completion router.

    Completion is now routed by `scope` first and then by verb within that
    scope, mirroring the Click command tree.
    """

    CORE_SCOPE_VERBS = {
        "plugin": [
            "install",
            "list",
            "get",
            "enable",
            "disable",
            "remove",
        ],
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
    SCOPE_VERBS = CORE_SCOPE_VERBS

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
            OptionSpec(tokens=("-t", "--timeout"), takes_value=True),
            OptionSpec(tokens=("-w", "--watch")),
            OptionSpec(tokens=("--keep-output",)),
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
        ("probe", "check"): (
            OptionSpec(tokens=("-a", "--all")),
            OptionSpec(tokens=("-w", "--watch")),
            OptionSpec(tokens=("--show-commands",)),
            OptionSpec(tokens=("--show-commands-limit",), takes_value=True),
        ),
        ("plugin", "install"): (OptionSpec(tokens=("--force",)),),
    }

    def __init__(
        self,
        cli_flags: dict[str, Any],
        configMng: ConfigMng,
        plugin_registry: "PluginRegistry | None" = None,
    ):
        self.cli_flags = cli_flags
        self.configMng = configMng
        self.plugin_registry = plugin_registry
        self.completionEnvMng = CompletionEnvMng(cli_flags, configMng)
        self.completionPluginMng = CompletionPluginMng(cli_flags, configMng)
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
        return list(self.scope_verbs.keys())

    @property
    def scope_verbs(self) -> dict[str, list[str]]:
        """Return core verbs merged with plugin-contributed scope verbs."""
        merged = {
            scope: list(verbs) for scope, verbs in self.CORE_SCOPE_VERBS.items()
        }
        if self.plugin_registry is None:
            return merged

        for scope, commands in self.plugin_registry.commands.items():
            verbs = merged.setdefault(scope, [])
            for verb in commands:
                if verb not in verbs:
                    verbs.append(verb)
        return merged

    def is_scope_chosen(self, args: list[str]) -> bool:
        return bool(args) and args[0] in self.SCOPES

    def is_verb_chosen(self, args: list[str]) -> bool:
        if len(args) < 2:
            return False
        return args[1] in self.scope_verbs.get(args[0], [])

    def get_completion_manager(
        self, scope: Optional[str]
    ) -> Optional[AbstractCompletionMng]:
        if scope == "env":
            return self.completionEnvMng
        if scope == "plugin":
            return self.completionPluginMng
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
                if token in self.scope_verbs.get(scope, []):
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

    def _get_runtime_provider_completions(
        self, scope: str, sanitized_args: list[str]
    ) -> list[str]:
        """Execute plugin completion providers registered for one scope."""
        if self.plugin_registry is None:
            return []

        suggestions: list[str] = []
        for provider_spec in self.plugin_registry.completion_providers.get(
            scope, []
        ):
            provider = provider_spec.provider
            if callable(provider):
                suggestions.extend(
                    self._normalize_provider_suggestions(
                        provider(sanitized_args)
                    )
                )
                continue
            get_completions = getattr(provider, "get_completions", None)
            if callable(get_completions):
                suggestions.extend(
                    self._normalize_provider_suggestions(
                        get_completions(sanitized_args)
                    )
                )
        return suggestions

    def _normalize_provider_suggestions(self, values: Any) -> list[str]:
        """Normalize plugin completion provider output to string suggestions."""
        if isinstance(values, str):
            return [values]
        return [value for value in values if isinstance(value, str)]

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
            suggestions = list(self.scope_verbs.get(scope, []))
            if not suggestions:
                suggestions.extend(
                    self._get_option_suggestions(
                        context_options, used_options=used_options
                    )
                )
            return self._unique(suggestions)

        provider_suggestions = self._get_runtime_provider_completions(
            scope, sanitized_args
        )
        completion_manager = self.get_completion_manager(scope)
        if completion_manager:
            suggestions = completion_manager.get_completions(sanitized_args)
            suggestions.extend(provider_suggestions)
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

        if provider_suggestions:
            return self._unique(provider_suggestions)

        return []
