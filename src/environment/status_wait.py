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

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeAlias

from rich.live import Live

from util.util import Util

GroupedStatus: TypeAlias = dict[str, list[list[str]]]
GateStatus: TypeAlias = dict[str, Optional[bool]]
CollectStatusResult: TypeAlias = tuple[GroupedStatus, bool, bool, bool]


@dataclass(frozen=True)
class WaitForEnvStateHooks:
    """Callback/value bundle used by `wait_for_env_state`."""

    status_poll_seconds: float
    is_quiet: Callable[[], bool]
    get_required_gate_tags: Callable[[Any], set[str]]
    evaluate_gate_status: Callable[[Any, set[str]], GateStatus]
    collect_env_status: Callable[
        [Any, Optional[GateStatus]], CollectStatusResult
    ]
    build_env_status_table: Callable[..., Any]
    remaining_timeout_seconds: Callable[[float, Optional[int]], Optional[int]]


def wait_for_env_state(
    env: Any,
    timeout_seconds: Optional[int],
    action: Optional[Callable[[], Any]],
    wait_until_up: bool,
    watch_after: bool,
    *,
    hooks: WaitForEnvStateHooks,
) -> None:
    """
    Wait until an environment reaches the requested steady state.

    The optional `action` (start/stop/reload) runs asynchronously while we
    keep polling status. Probe-gate evaluation is throttled independently from
    UI refresh to avoid executing probe checks on every render tick.

    Readiness policy for `wait_until_up=True`:
    - Always requires "all tracked containers are running".
    - Additionally requires all `hooks.get_required_gate_tags(...)` probes to
      be true when at least one required tag exists.
    - If no required tags exist (e.g. no `ready.when_probes` and no service
      gate probes), readiness falls back to running-container state only.
    """
    phase = "up" if wait_until_up else "down"
    phase_gerund = "starting" if wait_until_up else "stopping"
    timeout_target = "up" if wait_until_up else "down"
    quiet_mode = hooks.is_quiet()

    action_error: Optional[BaseException] = None
    action_done = threading.Event()

    if action:

        def run_action() -> None:
            nonlocal action_error
            try:
                action()
            except BaseException as e:
                action_error = e
            finally:
                action_done.set()

        threading.Thread(target=run_action, daemon=True).start()
    else:
        action_done.set()

    def raise_action_error() -> None:
        if action_error is not None:
            raise action_error

    def in_action() -> bool:
        return not action_done.is_set()

    def condition_met(
        all_running: bool,
        any_running: bool,
        current_gate_status: Optional[GateStatus],
    ) -> bool:
        if wait_until_up:
            if not all_running or in_action():
                return False
            if not required_gate_tags:
                # No readiness probes required: container-running state
                # is enough.
                return True
            if current_gate_status is None:
                return False
            return all(
                current_gate_status.get(tag) is True
                for tag in required_gate_tags
            )
        return (not any_running) and not in_action()

    required_gate_tags = hooks.get_required_gate_tags(env)
    gate_status: GateStatus = {tag: None for tag in required_gate_tags}
    hidden_columns = {"Gates"} if not wait_until_up else None
    # Probe checks are heavier than status polls; sample at a lower cadence.
    next_gate_eval_at = time.monotonic() + max(
        1.0, hooks.status_poll_seconds * 2
    )

    def get_gate_status() -> Optional[GateStatus]:
        nonlocal gate_status, next_gate_eval_at
        if not wait_until_up or not required_gate_tags:
            return None
        now = time.monotonic()
        if now < next_gate_eval_at:
            return gate_status
        gate_status = hooks.evaluate_gate_status(env, required_gate_tags)
        # Avoid running probes on every visual refresh tick.
        next_gate_eval_at = now + max(1.0, hooks.status_poll_seconds * 2)
        return gate_status

    started = time.monotonic()
    logging.debug(
        "wait_for_env_%s started for env='%s' (timeout=%s, terminal=%s)",
        phase,
        env.envCfg.tag,
        timeout_seconds,
        Util.console.is_terminal,
    )
    # Quiet mode: no intermediate rendering, only polling and eventual
    # return/error.
    if quiet_mode:
        completed = False
        while True:
            raise_action_error()
            current_gate_status = get_gate_status()
            grouped, all_running, any_running, has_containers = (
                hooks.collect_env_status(
                    env,
                    current_gate_status,
                )
            )
            remaining = hooks.remaining_timeout_seconds(
                started, timeout_seconds
            )
            if not has_containers or not grouped:
                if not in_action():
                    return
            elif condition_met(all_running, any_running, current_gate_status):
                return

            if (
                not completed
                and timeout_seconds is not None
                and remaining is not None
            ):
                if remaining <= 0:
                    Util.print_error_and_die(
                        "Timed out waiting for environment "
                        f"'{env.envCfg.tag}' to be {timeout_target}."
                    )
            time.sleep(hooks.status_poll_seconds)

    # Non-terminal output (e.g. pipes/CI): print the final table once.
    if not Util.console.is_terminal:
        while True:
            raise_action_error()
            remaining = hooks.remaining_timeout_seconds(
                started, timeout_seconds
            )
            if timeout_seconds is not None and remaining is not None:
                if remaining <= 0:
                    Util.print_error_and_die(
                        "Timed out waiting for environment "
                        f"'{env.envCfg.tag}' to be {timeout_target}."
                    )
            current_gate_status = get_gate_status()
            grouped, all_running, any_running, has_containers = (
                hooks.collect_env_status(
                    env,
                    current_gate_status,
                )
            )
            logging.debug(
                "wait_for_env_%s non-terminal poll env='%s': "
                "groups=%d has_containers=%s all_running=%s any_running=%s "
                "in_action=%s remaining=%s",
                phase,
                env.envCfg.tag,
                len(grouped),
                has_containers,
                all_running,
                any_running,
                in_action(),
                remaining,
            )

            if not has_containers or not grouped:
                if not in_action():
                    Util.console.print(
                        f"[yellow]No services found for "
                        f"environment '{env.envCfg.tag}'[/yellow]"
                    )
                    return
            elif condition_met(all_running, any_running, current_gate_status):
                Util.console.print(
                    hooks.build_env_status_table(
                        env.envCfg.tag,
                        grouped,
                        hidden_columns=hidden_columns,
                        status_suffix=(
                            "[bold green](Ready)[/bold green]"
                            if wait_until_up
                            else None
                        ),
                        remaining_seconds=(
                            None if wait_until_up else remaining
                        ),
                        command_log=(
                            env.get_command_log()
                            if env.is_command_log_enabled()
                            else None
                        ),
                        command_log_limit=(
                            env.get_command_log_limit()
                            if env.is_command_log_enabled()
                            else None
                        ),
                        command_error=env.get_command_error(),
                        command_error_limit=(
                            env.get_command_log_limit()
                            if env.is_command_log_enabled()
                            else None
                        ),
                    )
                )
                return
            time.sleep(hooks.status_poll_seconds)

    # Interactive terminal: continuously render progress with Live.
    live_refresh_per_second = max(
        4, int(1 / max(hooks.status_poll_seconds, 0.001))
    )
    with Live(
        refresh_per_second=live_refresh_per_second,
        console=Util.console,
        transient=True,
        screen=False,
    ) as live:
        completed = False
        while True:
            raise_action_error()
            current_gate_status = get_gate_status()
            grouped, all_running, any_running, has_containers = (
                hooks.collect_env_status(
                    env,
                    current_gate_status,
                )
            )
            remaining = hooks.remaining_timeout_seconds(
                started, timeout_seconds
            )
            logging.debug(
                "wait_for_env_%s poll env='%s': groups=%d "
                "has_containers=%s all_running=%s any_running=%s "
                "in_action=%s remaining=%s",
                phase,
                env.envCfg.tag,
                len(grouped),
                has_containers,
                all_running,
                any_running,
                in_action(),
                remaining,
            )

            if not has_containers or not grouped:
                if in_action():
                    title = f"[white]{env.envCfg.tag}[/white]"
                    if remaining is not None:
                        title = (
                            f"{title} " f"[dim](Time left: {remaining}s)[/dim]"
                        )
                    live.update(f"{title} [dim]({phase_gerund}...)[/dim]")
                else:
                    live.stop()
                    Util.console.print(
                        f"[yellow]No services found for "
                        f"environment '{env.envCfg.tag}'[/yellow]"
                    )
                    return
            else:
                show_ready = wait_until_up and completed
                live.update(
                    hooks.build_env_status_table(
                        env.envCfg.tag,
                        grouped,
                        hidden_columns=hidden_columns,
                        status_suffix=(
                            "[bold green](Ready)[/bold green]"
                            if show_ready
                            else None
                        ),
                        remaining_seconds=(None if show_ready else remaining),
                        command_log=(
                            env.get_command_log()
                            if env.is_command_log_enabled()
                            else None
                        ),
                        command_log_limit=(
                            env.get_command_log_limit()
                            if env.is_command_log_enabled()
                            else None
                        ),
                        command_error=env.get_command_error(),
                        command_error_limit=(
                            env.get_command_log_limit()
                            if env.is_command_log_enabled()
                            else None
                        ),
                    )
                )

            if condition_met(all_running, any_running, current_gate_status):
                logging.debug(
                    "wait_for_env_%s complete env='%s'",
                    phase,
                    env.envCfg.tag,
                )
                if not watch_after:
                    if wait_until_up:
                        live.update(
                            hooks.build_env_status_table(
                                env.envCfg.tag,
                                grouped,
                                hidden_columns=hidden_columns,
                                status_suffix=(
                                    "[bold green](Ready)[/bold green]"
                                    if wait_until_up
                                    else None
                                ),
                                command_log=(
                                    env.get_command_log()
                                    if env.is_command_log_enabled()
                                    else None
                                ),
                                command_log_limit=(
                                    env.get_command_log_limit()
                                    if env.is_command_log_enabled()
                                    else None
                                ),
                                command_error=env.get_command_error(),
                                command_error_limit=(
                                    env.get_command_log_limit()
                                    if env.is_command_log_enabled()
                                    else None
                                ),
                            )
                        )
                    return
                completed = True

            if (
                not completed
                and timeout_seconds is not None
                and remaining is not None
            ):
                if remaining <= 0:
                    live.stop()
                    Util.print_error_and_die(
                        "Timed out waiting for environment "
                        f"'{env.envCfg.tag}' to be {timeout_target}."
                    )
            time.sleep(hooks.status_poll_seconds)
