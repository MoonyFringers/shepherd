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
from rich.text import Text

from environment.render import (
    build_env_status_summary,
    build_probe_error_from_results,
    build_probe_status_tree,
)
from util.util import Util

GroupedStatus: TypeAlias = dict[str, list[list[str]]]
GateStatus: TypeAlias = dict[str, Optional[bool]]
CollectStatusResult: TypeAlias = tuple[GroupedStatus, bool, bool, bool]
ContainerStateMap: TypeAlias = dict[str, str]
ProbeStateMap: TypeAlias = dict[tuple[str, str], str]
SummaryStateMap: TypeAlias = dict[str, str]

# Default/guard timing knobs used by wait loops.
# With the default manager poll of 1.0s:
# - UI refresh uses at least 8 Hz (tick every 125 ms).
# - Gate probe evaluation is throttled to at most every 2.0s.
MIN_STATUS_POLL_SECONDS = 0.001
MIN_LIVE_REFRESH_PER_SECOND = 8
MIN_GATE_EVAL_INTERVAL_SECONDS = 1.0
TRANSITION_FLASH_DURATION_SECONDS = 1.5
READY_HIGHLIGHT_DURATION_SECONDS = 3.0


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


def _plain_markup(markup: str) -> str:
    return Text.from_markup(markup).plain


def _probe_state_key(markup: str) -> str:
    if "[green]" in markup or "[bold green]" in markup:
        return "ok"
    if "[red]" in markup or "[bold red]" in markup:
        return "failed"
    return "pending"


def _collect_container_states(grouped: GroupedStatus) -> ContainerStateMap:
    states: ContainerStateMap = {}
    for service, items in grouped.items():
        for item in items:
            container = item[1]
            states[f"{service}/{container}"] = _plain_markup(item[2])
    return states


def _collect_probe_states(grouped: GroupedStatus) -> ProbeStateMap:
    states: ProbeStateMap = {}
    for service, items in grouped.items():
        if not items or len(items[0]) <= 3:
            continue
        probe_details = items[0][3]
        if not probe_details or probe_details == "[dim]-[/dim]":
            continue
        for probe_detail in probe_details.split(", "):
            probe_tag = _plain_markup(probe_detail)
            states[(service, probe_tag)] = _probe_state_key(probe_detail)
    return states


def _collect_summary_states(grouped: GroupedStatus) -> SummaryStateMap:
    return dict(build_env_status_summary(grouped))


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
    build_env_status: Callable[..., Any]
    remaining_timeout_seconds: Callable[[float, Optional[int]], Optional[int]]


def wait_for_env_state(
    env: Any,
    timeout_seconds: Optional[int],
    action: Optional[Callable[[], Any]],
    wait_until_up: bool,
    watch_after: bool,
    progress_label: str = "Starting",
    keep_output: bool = False,
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
    # Human-readable labels reused in logs and timeout/progress messages.
    phase = "up" if wait_until_up else "down"
    phase_gerund = "starting" if wait_until_up else "stopping"
    timeout_target = "up" if wait_until_up else "down"
    quiet_mode = hooks.is_quiet()

    action_error: Optional[BaseException] = None
    # The optional start/stop action runs on a worker thread while the main
    # thread polls state and renders progress. `action_done` tracks whether
    # that side effect has finished, independent of the observed env status.
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
        animated = render_moving_shadow_text(progress_label, tick)
        if remaining is None:
            return animated
        return f"{animated} " f"[dim]({remaining}s)[/dim]"

    # Gates are only meaningful while waiting for readiness, not for stop.
    hidden_columns = {"Gates"} if not wait_until_up else None
    ready_status = "[bold green]Ready[/bold green]"
    ready_flash_status = "[bold black on green]Ready[/bold black on green]"
    ready_transition_started_at: Optional[float] = None
    last_container_states: ContainerStateMap = {}
    last_probe_states: ProbeStateMap = {}
    last_summary_states: SummaryStateMap = {}
    container_transition_started_at: dict[str, float] = {}
    probe_transition_started_at: dict[tuple[str, str], float] = {}
    summary_transition_started_at: dict[str, float] = {}

    if wait_until_up:
        # Only "up" waits care about readiness probes. "Down" waits complete
        # solely from container state plus the action thread finishing.
        required_gate_tags = hooks.get_required_gate_tags(env)
        # Probe results start as unknown (`None`) until the first sampled
        # evaluation completes.
        gate_status: GateStatus = {tag: None for tag in required_gate_tags}
        # Probe checks are heavier than status polls; sample at a lower cadence.
        next_gate_eval_at = time.monotonic() + max(
            MIN_GATE_EVAL_INTERVAL_SECONDS, hooks.status_poll_seconds * 2
        )

        def condition_met(
            all_running: bool,
            any_running: bool,
            current_gate_status: Optional[GateStatus],
        ) -> bool:
            del any_running
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

        def get_gate_status() -> Optional[GateStatus]:
            nonlocal gate_status, next_gate_eval_at
            now = time.monotonic()
            if now < next_gate_eval_at:
                return gate_status
            gate_status = hooks.evaluate_gate_status(env, required_gate_tags)
            # Avoid running probes on every visual refresh tick.
            next_gate_eval_at = now + max(
                MIN_GATE_EVAL_INTERVAL_SECONDS,
                hooks.status_poll_seconds * 2,
            )
            return gate_status

    else:

        def condition_met(
            all_running: bool,
            any_running: bool,
            current_gate_status: Optional[GateStatus],
        ) -> bool:
            del all_running, current_gate_status
            return (not any_running) and not in_action()

        def get_gate_status() -> Optional[GateStatus]:
            return None

    def current_status_suffix(
        remaining: Optional[int],
        tick: int,
        *,
        show_ready: bool = False,
    ) -> Optional[str]:
        nonlocal ready_transition_started_at
        # Only "up" waits decorate the table title with animated/progressive
        # readiness text. Stop waits use plain tables plus separate progress
        # lines while the action is still in flight.
        if not wait_until_up:
            return None
        if show_ready:
            now = time.monotonic()
            if ready_transition_started_at is None:
                ready_transition_started_at = now
            elapsed = now - ready_transition_started_at
            if (
                Util.console.is_terminal
                and elapsed < READY_HIGHLIGHT_DURATION_SECONDS
            ):
                return ready_flash_status
            return ready_status
        ready_transition_started_at = None
        return starting_suffix(remaining, tick)

    def build_status_renderable(
        grouped: GroupedStatus,
        *,
        remaining: Optional[int],
        tick: int,
        show_ready: bool = False,
    ) -> Any:
        now = time.monotonic()
        flashing_containers = {
            key
            for key, started_at in container_transition_started_at.items()
            if now - started_at < TRANSITION_FLASH_DURATION_SECONDS
        }
        flashing_probes = {
            key
            for key, started_at in probe_transition_started_at.items()
            if now - started_at < TRANSITION_FLASH_DURATION_SECONDS
        }
        flashing_summary_keys = {
            key
            for key, started_at in summary_transition_started_at.items()
            if now - started_at < TRANSITION_FLASH_DURATION_SECONDS
        }
        # Centralize all table-side decorations so the render loops can focus
        # on state transitions instead of repeatedly wiring optional panels.
        return hooks.build_env_status(
            env.envCfg.tag,
            grouped,
            hidden_columns=hidden_columns,
            status_suffix=current_status_suffix(
                remaining, tick, show_ready=show_ready
            ),
            command_log=(
                env.get_command_log() if env.is_command_log_enabled() else None
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
            flashing_containers=flashing_containers,
            flashing_probes=flashing_probes,
            flashing_summary_keys=flashing_summary_keys,
        )

    def render_progress_text(remaining: Optional[int], tick: int) -> str:
        # Used only when there is not yet a stable table snapshot to render,
        # or when an in-flight action would make an empty snapshot misleading.
        title = f"[white]{env.envCfg.tag}[/white]"
        if wait_until_up:
            return f"{title} {starting_suffix(remaining, tick)}"
        if remaining is not None:
            title = f"{title} [dim]({remaining}s)[/dim]"
        return f"{title} [dim]({phase_gerund}...)[/dim]"

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
                    build_status_renderable(
                        grouped,
                        remaining=remaining,
                        tick=0,
                        show_ready=True,
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
        # `completed` means the requested steady state has been observed at
        # least once. In watch mode we keep rendering after that point; in
        # non-watch mode we return immediately after the final update.
        completed = False
        # UI animation/render cadence is decoupled from status polling cadence.
        ui_tick_count = 0
        next_ui_tick_at = time.monotonic()
        # `next_status_poll_at` is shared with the polling thread and starts at
        # zero so the first sample happens immediately.
        next_status_poll_at = 0.0
        # Snapshot fields below are written by the polling thread and read by
        # the UI thread.
        snapshot_lock = threading.Lock()
        stop_polling = threading.Event()
        poll_error: Optional[BaseException] = None
        # Latest sampled readiness gates, or `None` when stop waits / no probes
        # are involved.
        latest_gate_status: Optional[GateStatus] = None
        grouped: GroupedStatus = {}
        all_running = False
        any_running = False
        # `has_containers` means the environment currently resolves to at
        # least one tracked container. This differs from `grouped`: the row
        # structure can still be empty before the first successful poll.
        has_containers = False
        # `has_snapshot` flips to true after the polling thread has produced
        # one complete status sample. Until then, the UI can only show a
        # generic progress line because there is no stable table data yet.
        has_snapshot = False
        snapshot_revision: int = 0

        def run_status_polling() -> None:
            nonlocal poll_error
            nonlocal next_status_poll_at
            nonlocal latest_gate_status
            nonlocal grouped
            nonlocal all_running
            nonlocal any_running
            nonlocal has_containers
            nonlocal has_snapshot
            nonlocal snapshot_revision
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
                        snapshot_revision += 1
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
        seen_snapshot_revision: int = -1
        try:
            while True:
                if action_error is not None:
                    # Preserve the last rendered state so the user can
                    # read the command log and error context after exit.
                    live.transient = False
                    if not keep_output:
                        raise action_error
                    # keep_output: keep the display live until Ctrl+C so
                    # the user can inspect the command log at leisure.
                if poll_error is not None:
                    raise poll_error
                with snapshot_lock:
                    snap_has_snapshot = has_snapshot
                    snap_has_containers = has_containers
                    snap_grouped = grouped
                    snap_all_running = all_running
                    snap_any_running = any_running
                    snap_gate_status = latest_gate_status
                    snap_revision = snapshot_revision
                remaining = hooks.remaining_timeout_seconds(
                    started, timeout_seconds
                )

                if snap_revision != seen_snapshot_revision:
                    current_container_states = _collect_container_states(
                        snap_grouped
                    )
                    current_probe_states = _collect_probe_states(snap_grouped)
                    current_summary_states = _collect_summary_states(
                        snap_grouped
                    )
                    now = time.monotonic()

                    for key, state in current_container_states.items():
                        if key in last_container_states and (
                            last_container_states[key] != state
                        ):
                            container_transition_started_at[key] = now
                    for key, state in current_probe_states.items():
                        if key in last_probe_states and (
                            last_probe_states[key] != state
                        ):
                            probe_transition_started_at[key] = now
                    for key, value in current_summary_states.items():
                        if key in last_summary_states and (
                            last_summary_states[key] != value
                        ):
                            summary_transition_started_at[key] = now

                    for key in list(container_transition_started_at):
                        if key not in current_container_states:
                            container_transition_started_at.pop(key, None)
                    for key in list(probe_transition_started_at):
                        if key not in current_probe_states:
                            probe_transition_started_at.pop(key, None)
                    for key in list(summary_transition_started_at):
                        if key not in current_summary_states:
                            summary_transition_started_at.pop(key, None)

                    last_container_states = current_container_states
                    last_probe_states = current_probe_states
                    last_summary_states = current_summary_states
                    seen_snapshot_revision = snap_revision

                if not snap_has_snapshot:
                    # No poll has completed yet, so we have no trustworthy
                    # table rows to render. Show only a progress headline.
                    live.update(render_progress_text(remaining, ui_tick_count))
                elif not snap_has_containers or not snap_grouped:
                    # A snapshot exists, but it resolved to no visible
                    # containers/rows. During an in-flight start/stop action
                    # this can be transient, so keep showing progress instead
                    # of flashing a misleading empty-state message.
                    if in_action():
                        live.update(
                            render_progress_text(remaining, ui_tick_count)
                        )
                    else:
                        # Once the action is finished, an empty snapshot means
                        # there is nothing left to render as a table.
                        live.stop()
                        Util.console.print(
                            f"[yellow]No services found for "
                            f"environment '{env.envCfg.tag}'[/yellow]"
                        )
                        return
                else:
                    show_ready = wait_until_up and condition_met(
                        snap_all_running, snap_any_running, snap_gate_status
                    )
                    live.update(
                        build_status_renderable(
                            snap_grouped,
                            remaining=remaining,
                            tick=ui_tick_count,
                            show_ready=show_ready,
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
                                build_status_renderable(
                                    snap_grouped,
                                    remaining=remaining,
                                    tick=ui_tick_count,
                                    show_ready=True,
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


def watch_probe_state(
    env: Any,
    *,
    probe_tag: Optional[str],
    title: str,
    poll_seconds: int = 5,
) -> None:
    """
    Continuously run probes and render results via a Rich Live display.

    Runs until the user interrupts with Ctrl+C. Checks run in a background
    thread so the UI can animate while a check is in progress. The poll
    interval is measured from when the previous check finished, so slow
    probes never cause back-to-back runs. While a check is running the
    title is animated and the error panel is hidden (it belongs to the
    previous cycle). When command logging is enabled the recent-commands
    panel is rendered below the probe tree.
    """
    ui_tick_seconds = 1.0 / MIN_LIVE_REFRESH_PER_SECOND

    results_lock = threading.Lock()
    last_results: list[Any] = []
    # 0.0 ensures the first check fires immediately on entry.
    last_check_finished_at: list[float] = [0.0]
    check_running = threading.Event()

    def run_check() -> None:
        results = env.check_probes(
            probe_tag=probe_tag,
            fail_fast=False,
            timeout_seconds=120,
        )
        with results_lock:
            last_results[:] = results
        last_check_finished_at[0] = time.monotonic()
        check_running.clear()

    with Live(
        refresh_per_second=MIN_LIVE_REFRESH_PER_SECOND,
        console=Util.console,
        transient=True,
        screen=False,
    ) as live:
        try:
            tick = 0
            while True:
                now = time.monotonic()

                # Kick off a new check when idle and the poll interval
                # has elapsed since the last check finished.
                if not check_running.is_set() and (
                    now >= last_check_finished_at[0] + poll_seconds
                ):
                    check_running.set()
                    threading.Thread(target=run_check, daemon=True).start()

                running = check_running.is_set()
                with results_lock:
                    current_results = list(last_results)

                animated_title = (
                    f"{title} " f"{render_moving_shadow_text('Checking', tick)}"
                    if running
                    else title
                )
                # Suppress the error panel while a new check is in flight
                # to avoid showing stale output from the previous cycle.
                probe_error = (
                    None
                    if running
                    else build_probe_error_from_results(current_results)
                )
                command_log = (
                    env.get_command_log()
                    if env.is_command_log_enabled()
                    else None
                )
                command_log_limit = (
                    env.get_command_log_limit()
                    if command_log is not None
                    else None
                )
                live.update(
                    build_probe_status_tree(
                        current_results,
                        title=animated_title,
                        probe_error=probe_error,
                        command_log=command_log,
                        command_log_limit=command_log_limit,
                    )
                )
                time.sleep(ui_tick_seconds)
                tick += 1
        except KeyboardInterrupt:
            pass
