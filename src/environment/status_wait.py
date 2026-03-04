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
from rich.markup import escape

from util.util import Util

GroupedStatus: TypeAlias = dict[str, list[list[str]]]
GateStatus: TypeAlias = dict[str, Optional[bool]]
CollectStatusResult: TypeAlias = tuple[GroupedStatus, bool, bool, bool]

# Default/guard timing knobs used by wait loops.
# With the default manager poll of 1.0s:
# - UI refresh uses at least 8 Hz (tick every 125 ms).
# - Gate probe evaluation is throttled to at most every 2.0s.
MIN_STATUS_POLL_SECONDS = 0.001
MIN_LIVE_REFRESH_PER_SECOND = 8
MIN_GATE_EVAL_INTERVAL_SECONDS = 1.0


def render_moving_shadow_text(
    phrase: str,
    tick: int,
    *,
    base_style: str = "grey50",
    highlight_style: str = "bold white",
    trail_styles: tuple[str, ...] = ("white", "grey62"),
) -> str:
    """
    Render a phrase with a moving highlight and trailing "shadow".

    The effect is deterministic for a given `tick` and works for any input
    phrase. Whitespace is preserved unstyled, and only non-whitespace
    characters participate in the animation cycle.
    """
    if not phrase:
        return ""

    visible_positions = [
        idx for idx, char in enumerate(phrase) if not char.isspace()
    ]
    if not visible_positions:
        return escape(phrase)

    n = len(visible_positions)
    head_visible_idx = tick % n

    style_by_visible_idx: dict[int, str] = {
        visible_idx: base_style for visible_idx in range(n)
    }
    style_by_visible_idx[head_visible_idx] = highlight_style
    for offset, style in enumerate(trail_styles, start=1):
        trail_visible_idx = (head_visible_idx - offset) % n
        style_by_visible_idx[trail_visible_idx] = style

    visible_rank_by_pos = {
        pos: visible_idx for visible_idx, pos in enumerate(visible_positions)
    }

    out: list[str] = []
    for pos, char in enumerate(phrase):
        escaped_char = escape(char)
        if char.isspace():
            out.append(escaped_char)
            continue
        visible_idx = visible_rank_by_pos[pos]
        out.append(
            f"[{style_by_visible_idx[visible_idx]}]{escaped_char}"
            f"[/{style_by_visible_idx[visible_idx]}]"
        )
    return "".join(out)


@dataclass(frozen=True)
class WaitForEnvStateHooks:
    """
    Callback/value bundle used by `wait_for_env_state`.

    `status_poll_seconds` controls status snapshot cadence.
    Default from `EnvironmentMng` is 1.0 second.
    """

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

    Timing defaults (with `status_poll_seconds=1.0`):
    - Status snapshots: every 1.0s.
    - Probe gate evaluation: every max(1.0, 2 * poll) => 2.0s.
    - Interactive UI tick: at least 8 Hz => every 0.125s.
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

    def starting_suffix(remaining: Optional[int], tick: int) -> str:
        animated = render_moving_shadow_text("Starting", tick)
        if remaining is None:
            return animated
        return f"{animated} " f"[dim]({remaining}s left)[/dim]"

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
        MIN_GATE_EVAL_INTERVAL_SECONDS, hooks.status_poll_seconds * 2
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
        next_gate_eval_at = now + max(
            MIN_GATE_EVAL_INTERVAL_SECONDS, hooks.status_poll_seconds * 2
        )
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
                            "[bold green]Ready[/bold green]"
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

    # Interactive terminal: render at a fixed cadence while polling status
    # independently to avoid visual jitter when polls are slow/variable.
    live_refresh_per_second = max(
        MIN_LIVE_REFRESH_PER_SECOND,
        int(1 / max(hooks.status_poll_seconds, MIN_STATUS_POLL_SECONDS)),
    )
    ui_tick_seconds = 1.0 / float(live_refresh_per_second)
    status_poll_seconds = max(
        MIN_STATUS_POLL_SECONDS, hooks.status_poll_seconds
    )
    with Live(
        refresh_per_second=live_refresh_per_second,
        console=Util.console,
        transient=True,
        screen=False,
    ) as live:
        completed = False
        ui_tick_count = 0
        next_ui_tick_at = time.monotonic()
        next_status_poll_at = 0.0
        snapshot_lock = threading.Lock()
        stop_polling = threading.Event()
        poll_error: Optional[BaseException] = None
        latest_gate_status: Optional[GateStatus] = None
        grouped: GroupedStatus = {}
        all_running = False
        any_running = False
        has_containers = False
        has_snapshot = False

        def run_status_polling() -> None:
            nonlocal poll_error
            nonlocal next_status_poll_at
            nonlocal latest_gate_status
            nonlocal grouped
            nonlocal all_running
            nonlocal any_running
            nonlocal has_containers
            nonlocal has_snapshot
            while not stop_polling.is_set():
                now = time.monotonic()
                if now < next_status_poll_at:
                    stop_polling.wait(next_status_poll_at - now)
                    continue
                try:
                    gate_status_now = get_gate_status()
                    (
                        poll_grouped,
                        poll_all_running,
                        poll_any_running,
                        (poll_has_containers),
                    ) = hooks.collect_env_status(env, gate_status_now)
                    with snapshot_lock:
                        latest_gate_status = gate_status_now
                        grouped = poll_grouped
                        all_running = poll_all_running
                        any_running = poll_any_running
                        has_containers = poll_has_containers
                        has_snapshot = True
                    logging.debug(
                        "wait_for_env_%s poll env='%s': groups=%d "
                        "has_containers=%s all_running=%s any_running=%s "
                        "in_action=%s",
                        phase,
                        env.envCfg.tag,
                        len(poll_grouped),
                        poll_has_containers,
                        poll_all_running,
                        poll_any_running,
                        in_action(),
                    )
                except BaseException as e:
                    poll_error = e
                    stop_polling.set()
                    return
                next_status_poll_at = time.monotonic() + status_poll_seconds

        next_status_poll_at = 0.0
        poll_thread = threading.Thread(target=run_status_polling, daemon=True)
        poll_thread.start()
        try:
            while True:
                raise_action_error()
                if poll_error is not None:
                    raise poll_error
                with snapshot_lock:
                    snap_has_snapshot = has_snapshot
                    snap_has_containers = has_containers
                    snap_grouped = grouped
                    snap_all_running = all_running
                    snap_any_running = any_running
                    snap_gate_status = latest_gate_status
                remaining = hooks.remaining_timeout_seconds(
                    started, timeout_seconds
                )

                if (
                    not snap_has_snapshot
                    or not snap_has_containers
                    or not snap_grouped
                ):
                    if in_action():
                        title = f"[white]{env.envCfg.tag}[/white]"
                        if wait_until_up:
                            live.update(
                                f"{title} "
                                f"{starting_suffix(remaining, ui_tick_count)}"
                            )
                        else:
                            if remaining is not None:
                                title = (
                                    f"{title} "
                                    f"[dim](Time left: {remaining}s)[/dim]"
                                )
                            live.update(
                                f"{title} [dim]({phase_gerund}...)[/dim]"
                            )
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
                            snap_grouped,
                            hidden_columns=hidden_columns,
                            status_suffix=(
                                (
                                    "[bold green]Ready[/bold green]"
                                    if show_ready
                                    else starting_suffix(
                                        remaining, ui_tick_count
                                    )
                                )
                                if wait_until_up
                                else None
                            ),
                            remaining_seconds=(
                                None
                                if wait_until_up or show_ready
                                else remaining
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

                if condition_met(
                    snap_all_running, snap_any_running, snap_gate_status
                ):
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
                                    snap_grouped,
                                    hidden_columns=hidden_columns,
                                    status_suffix=(
                                        "[bold green]Ready[/bold green]"
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
                now = time.monotonic()
                if next_ui_tick_at < now:
                    next_ui_tick_at = now
                next_ui_tick_at += ui_tick_seconds
                ui_tick_count += 1
                sleep_for = max(0.0, next_ui_tick_at - time.monotonic())
                time.sleep(sleep_for)
        finally:
            stop_polling.set()
            poll_thread.join(timeout=1.0)
