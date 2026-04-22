# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Orchestration layer for remote operation progress display.

Hook dataclasses are defined here and passed as optional parameters into
``RemoteMng`` methods.  All Rich rendering is isolated in ``remote_render``;
``remote_mng`` itself has no Rich dependency.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Optional

from rich.live import Live
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
)

from util import Util

from .remote_render import build_push_renderable, build_restore_header

if TYPE_CHECKING:
    from remote.remote_mng import RemoteMng

_UI_HZ = 8
_UI_TICK = 1.0 / _UI_HZ


# ------------------------------------------------------------------
# Hook dataclasses — imported by remote_mng under TYPE_CHECKING
# ------------------------------------------------------------------


@dataclass(frozen=True)
class PushHooks:
    """Callbacks injected into ``RemoteMng.push``."""

    on_chunk: Callable[[int, int, bool], None]
    on_complete: Callable[[str, int, int, int, int], None]
    on_start: Optional[Callable[[], None]] = None


@dataclass(frozen=True)
class RestoreHooks:
    """Callbacks injected into ``RemoteMng.pull`` / ``RemoteMng.hydrate``."""

    on_manifest: Callable[[int, str], None]
    on_chunk: Callable[[bool], None]
    on_complete: Callable[[str, int, int, int], None]


@dataclass(frozen=True)
class DehydrateHooks:
    """Callbacks injected into ``RemoteMng.dehydrate``."""

    on_phase: Callable[[str], None]


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _remote_display_name(mng: RemoteMng, remote_name: Optional[str]) -> str:
    return mng.resolve_remote_name(remote_name)


def _make_restore_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        MofNCompleteColumn(),
        TextColumn("[dim]·  {task.fields[from_cache]} from cache[/dim]"),
        console=Util.console,
        transient=True,
    )


def _run_restore_with_progress(
    mng: RemoteMng,
    env_name: str,
    remote_display: str,
    call_restore: Callable[[RestoreHooks], None],
    summary_verb: str,
) -> None:
    task_holder: list[Any] = []
    from_cache_count = [0]
    complete: list[tuple[str, int, int, int]] = []

    progress = _make_restore_progress()

    def on_manifest(total_chunks: int, snap_id: str) -> None:
        progress.console.print(
            build_restore_header(env_name, remote_display, snap_id)
        )
        task_id = progress.add_task(
            f"Downloading {total_chunks} chunk(s)",
            total=total_chunks,
            from_cache=0,
        )
        task_holder.append(task_id)

    def on_chunk(from_cache: bool) -> None:
        if not task_holder:
            return
        progress.advance(task_holder[0])
        if from_cache:
            from_cache_count[0] += 1
            progress.update(task_holder[0], from_cache=from_cache_count[0])

    def on_complete(
        snap_id: str, downloaded: int, from_cache: int, stored_bytes: int
    ) -> None:
        complete.append((snap_id, downloaded, from_cache, stored_bytes))

    hooks = RestoreHooks(
        on_manifest=on_manifest, on_chunk=on_chunk, on_complete=on_complete
    )

    with progress:
        call_restore(hooks)

    if complete:
        snap_id, downloaded, from_cache, stored_bytes = complete[0]
        Util.print(
            f"{summary_verb} '{env_name}' ← '{remote_display}' "
            f"[{snap_id}]: "
            f"{downloaded} chunk(s) downloaded, "
            f"{from_cache} from cache, "
            f"{Util.fmt_bytes(stored_bytes)} stored."
        )


# ------------------------------------------------------------------
# run_push_with_progress
# ------------------------------------------------------------------


def run_push_with_progress(
    mng: RemoteMng,
    env_name: str,
    environment_mng: Any,
    remote_name: Optional[str] = None,
    set_tracking: bool = False,
    labels: Optional[list[str]] = None,
) -> None:
    if not Util.console.is_terminal:
        mng.push(
            env_name=env_name,
            environment_mng=environment_mng,
            remote_name=remote_name,
            set_tracking=set_tracking,
            labels=labels,
        )
        return

    remote_display = _remote_display_name(mng, remote_name)

    lock = threading.Lock()
    total = [0]
    uploaded = [0]
    skipped = [0]
    raw = [0]
    stored = [0]
    complete: list[tuple[str, int, int, int, int]] = []

    def on_chunk(raw_size: int, stored_size: int, is_new: bool) -> None:
        with lock:
            total[0] += 1
            raw[0] += raw_size
            stored[0] += stored_size
            if is_new:
                uploaded[0] += 1
            else:
                skipped[0] += 1

    def on_complete(
        snapshot_id: str,
        n_uploaded: int,
        n_skipped: int,
        n_raw: int,
        n_stored: int,
    ) -> None:
        complete.append((snapshot_id, n_uploaded, n_skipped, n_raw, n_stored))

    stop_tick = threading.Event()
    tick = [0]
    live = Live(
        refresh_per_second=_UI_HZ,
        console=Util.console,
        transient=True,
    )
    live_started = [False]
    tick_thread_holder: list[threading.Thread] = []

    def on_start() -> None:
        live.__enter__()
        live_started[0] = True

        def _tick_loop() -> None:
            while not stop_tick.is_set():
                with lock:
                    t = total[0]
                    u = uploaded[0]
                    s = skipped[0]
                    r = raw[0]
                    st = stored[0]
                live.update(
                    build_push_renderable(
                        env_name, remote_display, t, u, s, r, st, tick=tick[0]
                    )
                )
                tick[0] += 1
                time.sleep(_UI_TICK)

        t = threading.Thread(target=_tick_loop, daemon=True)
        t.start()
        tick_thread_holder.append(t)

    hooks = PushHooks(
        on_chunk=on_chunk, on_complete=on_complete, on_start=on_start
    )

    try:
        mng.push(
            env_name=env_name,
            environment_mng=environment_mng,
            remote_name=remote_name,
            set_tracking=set_tracking,
            labels=labels,
            push_hooks=hooks,
        )
    finally:
        stop_tick.set()
        if tick_thread_holder:
            tick_thread_holder[0].join()
        if live_started[0]:
            live.__exit__(None, None, None)

    if complete:
        snapshot_id, n_up, n_sk, _, n_st = complete[0]
        Util.print(
            f"Pushed '{env_name}' → '{remote_display}' "
            f"[{snapshot_id}]: "
            f"{n_up} chunk(s) uploaded, "
            f"{n_sk} already present, "
            f"{Util.fmt_bytes(n_st)} stored."
        )


# ------------------------------------------------------------------
# run_pull_with_progress
# ------------------------------------------------------------------


def run_pull_with_progress(
    mng: RemoteMng,
    env_name: str,
    remote_name: Optional[str] = None,
    snapshot_id: Optional[str] = None,
) -> None:
    if not Util.console.is_terminal:
        mng.pull(
            env_name=env_name,
            remote_name=remote_name,
            snapshot_id=snapshot_id,
        )
        return

    remote_display = _remote_display_name(mng, remote_name)
    _run_restore_with_progress(
        mng,
        env_name,
        remote_display,
        lambda hooks: mng.pull(
            env_name=env_name,
            remote_name=remote_name,
            snapshot_id=snapshot_id,
            restore_hooks=hooks,
        ),
        "Pulled",
    )


# ------------------------------------------------------------------
# run_hydrate_with_progress
# ------------------------------------------------------------------


def run_hydrate_with_progress(
    mng: RemoteMng,
    env_name: str,
    environment_mng: Any,
    remote_name: Optional[str] = None,
    snapshot_id: Optional[str] = None,
) -> None:
    if not Util.console.is_terminal:
        mng.hydrate(
            env_name=env_name,
            environment_mng=environment_mng,
            remote_name=remote_name,
            snapshot_id=snapshot_id,
        )
        return

    remote_display = _remote_display_name(mng, remote_name)
    _run_restore_with_progress(
        mng,
        env_name,
        remote_display,
        lambda hooks: mng.hydrate(
            env_name=env_name,
            environment_mng=environment_mng,
            remote_name=remote_name,
            snapshot_id=snapshot_id,
            restore_hooks=hooks,
        ),
        "Hydrated",
    )


# ------------------------------------------------------------------
# run_dehydrate_with_progress
# ------------------------------------------------------------------


def run_dehydrate_with_progress(
    mng: RemoteMng,
    env_name: str,
    environment_mng: Any,
) -> None:
    if not Util.console.is_terminal:
        mng.dehydrate(
            env_name=env_name,
            environment_mng=environment_mng,
        )
        return

    def on_phase(label: str) -> None:
        Util.print(f"  [dim]→[/dim] {label}...")

    mng.dehydrate(
        env_name=env_name,
        environment_mng=environment_mng,
        dehydrate_hooks=DehydrateHooks(on_phase=on_phase),
    )
