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
from typing import Any, Callable, Optional, TypeAlias

from rich.live import Live

from util.util import Util

GroupedStatus: TypeAlias = dict[str, list[list[str]]]
GateStatus: TypeAlias = dict[str, Optional[bool]]
CollectStatusResult: TypeAlias = tuple[GroupedStatus, bool, bool, bool]


def wait_for_env_state(
    env: Any,
    timeout_seconds: Optional[int],
    action: Optional[Callable[[], Any]],
    wait_until_up: bool,
    watch_after: bool,
    *,
    status_poll_seconds: float,
    is_quiet: Callable[[], bool],
    get_required_gate_tags: Callable[[Any], set[str]],
    evaluate_gate_status: Callable[[Any, set[str]], GateStatus],
    collect_env_status: Callable[
        [Any, Optional[GateStatus]],
        CollectStatusResult,
    ],
    build_env_status_table: Callable[..., Any],
    remaining_timeout_seconds: Callable[[float, Optional[int]], Optional[int]],
) -> None:
    phase = "up" if wait_until_up else "down"
    phase_gerund = "starting" if wait_until_up else "stopping"
    timeout_target = "up" if wait_until_up else "down"
    quiet_mode = is_quiet()

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

    def condition_met(all_running: bool, any_running: bool) -> bool:
        if wait_until_up:
            return all_running and not in_action()
        return (not any_running) and not in_action()

    required_gate_tags = get_required_gate_tags(env)
    gate_status: GateStatus = {tag: None for tag in required_gate_tags}
    hidden_columns = {"Gates"} if not wait_until_up else None
    next_gate_eval_at = time.monotonic() + max(1.0, status_poll_seconds * 2)

    def get_gate_status() -> Optional[GateStatus]:
        nonlocal gate_status, next_gate_eval_at
        if not wait_until_up or not required_gate_tags:
            return None
        now = time.monotonic()
        if now < next_gate_eval_at:
            return gate_status
        gate_status = evaluate_gate_status(env, required_gate_tags)
        # Avoid running probes on every visual refresh tick.
        next_gate_eval_at = now + max(1.0, status_poll_seconds * 2)
        return gate_status

    started = time.monotonic()
    logging.debug(
        "wait_for_env_%s started for env='%s' (timeout=%s, terminal=%s)",
        phase,
        env.envCfg.tag,
        timeout_seconds,
        Util.console.is_terminal,
    )
    if quiet_mode:
        completed = False
        while True:
            raise_action_error()
            current_gate_status = get_gate_status()
            grouped, all_running, any_running, has_containers = (
                collect_env_status(
                    env,
                    current_gate_status,
                )
            )
            remaining = remaining_timeout_seconds(started, timeout_seconds)
            if not has_containers or not grouped:
                if not in_action():
                    return
            elif condition_met(all_running, any_running):
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
            time.sleep(status_poll_seconds)

    if not Util.console.is_terminal:
        while True:
            raise_action_error()
            remaining = remaining_timeout_seconds(started, timeout_seconds)
            if timeout_seconds is not None and remaining is not None:
                if remaining <= 0:
                    Util.print_error_and_die(
                        "Timed out waiting for environment "
                        f"'{env.envCfg.tag}' to be {timeout_target}."
                    )
            current_gate_status = get_gate_status()
            grouped, all_running, any_running, has_containers = (
                collect_env_status(
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
            elif condition_met(all_running, any_running):
                Util.console.print(
                    build_env_status_table(
                        env.envCfg.tag,
                        grouped,
                        hidden_columns=hidden_columns,
                        remaining_seconds=remaining,
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
            time.sleep(status_poll_seconds)

    live_refresh_per_second = max(4, int(1 / max(status_poll_seconds, 0.001)))
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
                collect_env_status(
                    env,
                    current_gate_status,
                )
            )
            remaining = remaining_timeout_seconds(started, timeout_seconds)
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
                live.update(
                    build_env_status_table(
                        env.envCfg.tag,
                        grouped,
                        hidden_columns=hidden_columns,
                        remaining_seconds=remaining,
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

            if condition_met(all_running, any_running):
                logging.debug(
                    "wait_for_env_%s complete env='%s'",
                    phase,
                    env.envCfg.tag,
                )
                if not watch_after:
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
            time.sleep(status_poll_seconds)
