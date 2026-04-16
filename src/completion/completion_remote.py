# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

import logging
from typing import TYPE_CHECKING, Any, Optional, override

from completion.completion_mng import AbstractCompletionMng
from config import ConfigMng

if TYPE_CHECKING:
    from remote import RemoteMng


class CompletionRemoteMng(AbstractCompletionMng):
    """Remote scope completer.

    Handles argument and option-value completion for the ``remote`` command
    group.  Where completion requires a live index (``remote get`` ENV_NAME),
    the call is delegated to :class:`~remote.remote_mng.RemoteMng` against the
    default remote; network failures are silently swallowed so that a
    temporarily unavailable remote never breaks the shell prompt.
    """

    def __init__(
        self,
        cli_flags: dict[str, Any],
        configMng: ConfigMng,
        remoteMng: "Optional[RemoteMng]" = None,
    ) -> None:
        self.cli_flags = cli_flags
        self.configMng = configMng
        self.remoteMng = remoteMng

    @override
    def get_completions_impl(self, args: list[str]) -> list[str]:
        if len(args) < 2:
            return []
        match args[1]:
            case "delete":
                return self._complete_remote_name(args[2:])
            case "envs":
                return self._complete_remote_option(args[2:])
            case "get":
                return self._complete_get(args[2:])
            case _:
                # "add" and "list" have no dynamic positional completions —
                # their flags are served entirely by the static CONTEXT_OPTIONS
                # table in CompletionMng.
                return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _remote_names(self, prefix: str = "") -> list[str]:
        """Return registered remote names, optionally filtered by *prefix*."""
        names = [r.name for r in self.configMng.get_remotes()]
        if prefix:
            return [n for n in names if n.startswith(prefix)]
        return names

    def _complete_remote_name(self, args: list[str]) -> list[str]:
        """Complete a single positional remote-name argument."""
        if not args:
            return self._remote_names()
        if len(args) == 1:
            prefix = args[0]
            # Return empty once an exact name has been chosen (mirrors the
            # env-delete / plugin-id pattern).
            if any(r.name == prefix for r in self.configMng.get_remotes()):
                return []
            return self._remote_names(prefix=prefix)
        return []

    def _complete_remote_option(self, args: list[str]) -> list[str]:
        """Complete the value of ``--remote``.

        Called directly for ``remote envs`` and as a sub-check inside
        :meth:`_complete_get`.  The dynamic-option fallback in
        :class:`~completion.completion.CompletionMng` injects the ``--remote``
        token (and optional partial value) at the tail of *args* when the user
        is in the middle of typing ``--remote <name>``.
        """
        if not args:
            return []
        if args[-1] == "--remote":
            return self._remote_names()
        if len(args) >= 2 and args[-2] == "--remote":
            return self._remote_names(prefix=args[-1])
        return []

    def _complete_get(self, args: list[str]) -> list[str]:
        """Complete arguments for ``remote get``.

        Priority order:
        1. If ``--remote`` value is expected (injected by dynamic-option
           fallback) → return registered remote names.
        2. Otherwise complete the ENV_NAME positional from the default
           remote's index catalogue.
        """
        # --remote value completion
        if args and (
            args[-1] == "--remote"
            or (len(args) >= 2 and args[-2] == "--remote")
        ):
            return self._complete_remote_option(args)

        # ENV_NAME positional — --remote <val> pairs are already stripped from
        # args by CompletionMng._parse_args; remaining "-" tokens are flags
        positional = [a for a in args if not a.startswith("-")]
        if not positional:
            return self._env_names()
        if len(positional) == 1:
            return self._env_names(prefix=positional[0])
        return []

    def _env_names(self, prefix: str = "") -> list[str]:
        """Return environment names from the default remote's index.

        Falls back to ``[]`` on any error (no default remote, network
        unavailable, etc.) so that completion never blocks the shell.
        """
        if self.remoteMng is None:
            return []
        try:
            _, catalogue = self.remoteMng.list_envs(remote_name=None)
            names = list(catalogue.environments.keys())
            if prefix:
                return [n for n in names if n.startswith(prefix)]
            return names
        except Exception as exc:
            logging.debug("remote completion: env-name lookup failed: %s", exc)
            return []
