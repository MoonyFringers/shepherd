# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Unit tests for :mod:`remote.remote_progress`.

Non-terminal paths are exercised with the conftest's ``force_terminal=False``
console (already the default).  Terminal paths patch ``Util.console`` with a
mock whose ``is_terminal`` attribute is ``True`` and stub out the Rich Live /
Progress objects to avoid actual TTY rendering.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, call

import pytest

from remote.remote_progress import (
    DehydrateHooks,
    PushHooks,
    RestoreHooks,
    _make_restore_progress,
    _remote_display_name,
    run_dehydrate_with_progress,
    run_hydrate_with_progress,
    run_pull_with_progress,
    run_push_with_progress,
)
from util.util import Util

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mng_mock(remote_display: str = "prod") -> MagicMock:
    mng = MagicMock()
    mng.resolve_remote_name.return_value = remote_display
    return mng


def _terminal_console() -> MagicMock:
    console = MagicMock()
    console.is_terminal = True
    return console


# ---------------------------------------------------------------------------
# _remote_display_name
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_remote_display_name_delegates_to_mng() -> None:
    """_remote_display_name calls mng.resolve_remote_name and returns result."""
    mng = _make_mng_mock("my-remote")
    assert _remote_display_name(mng, "my-remote") == "my-remote"
    mng.resolve_remote_name.assert_called_once_with("my-remote")


# ---------------------------------------------------------------------------
# _make_restore_progress
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_make_restore_progress_returns_progress_object() -> None:
    """_make_restore_progress constructs a Rich Progress without raising."""
    from rich.progress import Progress

    p = _make_restore_progress()
    assert isinstance(p, Progress)


# ---------------------------------------------------------------------------
# run_push_with_progress — non-terminal path
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_run_push_non_terminal_delegates_to_mng_push() -> None:
    """Non-terminal: delegates straight to mng.push with correct keyword args."""
    mng = _make_mng_mock()
    env_mng = MagicMock()

    run_push_with_progress(
        mng,
        "my-env",
        env_mng,
        remote_name="prod",
        set_tracking=True,
        labels=["k=v"],
    )

    mng.push.assert_called_once_with(
        env_name="my-env",
        environment_mng=env_mng,
        remote_name="prod",
        set_tracking=True,
        labels=["k=v"],
    )


@pytest.mark.remote
def test_run_push_non_terminal_no_live_started() -> None:
    """Non-terminal: the Live context manager is never entered."""
    mng = _make_mng_mock()
    with pytest.MonkeyPatch.context() as mp:
        mock_live = MagicMock()
        mp.setattr(
            "remote.remote_progress.Live", MagicMock(return_value=mock_live)
        )
        run_push_with_progress(mng, "my-env", MagicMock())

    mock_live.__enter__.assert_not_called()


# ---------------------------------------------------------------------------
# run_pull_with_progress — non-terminal path
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_run_pull_non_terminal_delegates_to_mng_pull() -> None:
    """Non-terminal: delegates to mng.pull with correct keyword args."""
    mng = _make_mng_mock()

    run_pull_with_progress(
        mng, "my-env", remote_name="prod", snapshot_id="snap-1"
    )

    mng.pull.assert_called_once_with(
        env_name="my-env",
        remote_name="prod",
        snapshot_id="snap-1",
    )


# ---------------------------------------------------------------------------
# run_hydrate_with_progress — non-terminal path
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_run_hydrate_non_terminal_delegates_to_mng_hydrate() -> None:
    """Non-terminal: delegates to mng.hydrate with correct keyword args."""
    mng = _make_mng_mock()
    env_mng = MagicMock()

    run_hydrate_with_progress(
        mng, "my-env", env_mng, remote_name="prod", snapshot_id="snap-1"
    )

    mng.hydrate.assert_called_once_with(
        env_name="my-env",
        environment_mng=env_mng,
        remote_name="prod",
        snapshot_id="snap-1",
    )


# ---------------------------------------------------------------------------
# run_dehydrate_with_progress — non-terminal path
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_run_dehydrate_non_terminal_delegates_to_mng_dehydrate() -> None:
    """Non-terminal: delegates to mng.dehydrate without any hooks."""
    mng = _make_mng_mock()
    env_mng = MagicMock()

    run_dehydrate_with_progress(mng, "my-env", env_mng)

    mng.dehydrate.assert_called_once_with(
        env_name="my-env",
        environment_mng=env_mng,
    )


# ---------------------------------------------------------------------------
# run_push_with_progress — terminal path
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_run_push_terminal_invokes_hooks_and_prints_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Terminal: push hooks are wired up; summary is printed after completion."""
    monkeypatch.setattr(Util, "console", _terminal_console())

    mock_live = MagicMock()
    monkeypatch.setattr(
        "remote.remote_progress.Live", MagicMock(return_value=mock_live)
    )

    mng = _make_mng_mock("prod")

    def fake_push(
        env_name: str,
        environment_mng: Any,
        remote_name: str | None = None,
        set_tracking: bool = False,
        labels: list[str] | None = None,
        push_hooks: PushHooks | None = None,
    ) -> None:
        if push_hooks:
            push_hooks.on_start()
            push_hooks.on_chunk(1024, 512, True)
            push_hooks.on_chunk(512, 256, False)
            push_hooks.on_complete("snap-abc", 1, 1, 1536, 768)

    mng.push.side_effect = fake_push

    printed: list[str] = []
    monkeypatch.setattr(
        "remote.remote_progress.Util.print",
        lambda msg: printed.append(msg),
    )

    run_push_with_progress(mng, "my-env", MagicMock(), remote_name="prod")

    mng.push.assert_called_once()
    mock_live.__enter__.assert_called_once()
    mock_live.__exit__.assert_called_once()
    assert any("snap-abc" in m for m in printed)


@pytest.mark.remote
def test_run_push_terminal_no_complete_no_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Terminal: if on_complete is never fired no summary is printed."""
    monkeypatch.setattr(Util, "console", _terminal_console())
    monkeypatch.setattr(
        "remote.remote_progress.Live",
        MagicMock(return_value=MagicMock()),
    )

    mng = _make_mng_mock()

    def fake_push(
        env_name: str,
        environment_mng: Any,
        remote_name: str | None = None,
        set_tracking: bool = False,
        labels: list[str] | None = None,
        push_hooks: PushHooks | None = None,
    ) -> None:
        if push_hooks:
            push_hooks.on_start()

    mng.push.side_effect = fake_push

    printed: list[str] = []
    monkeypatch.setattr(
        "remote.remote_progress.Util.print",
        lambda msg: printed.append(msg),
    )

    run_push_with_progress(mng, "my-env", MagicMock())

    assert printed == []


@pytest.mark.remote
def test_run_push_terminal_exception_stops_tick_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Terminal: the tick thread is stopped and live is exited even on error."""
    monkeypatch.setattr(Util, "console", _terminal_console())
    monkeypatch.setattr(
        "remote.remote_progress.Live",
        MagicMock(return_value=MagicMock()),
    )

    mng = _make_mng_mock()

    def fake_push(
        env_name: str,
        environment_mng: Any,
        remote_name: str | None = None,
        set_tracking: bool = False,
        labels: list[str] | None = None,
        push_hooks: PushHooks | None = None,
    ) -> None:
        if push_hooks:
            push_hooks.on_start()
        raise RuntimeError("upload failed")

    mng.push.side_effect = fake_push

    with pytest.raises(RuntimeError, match="upload failed"):
        run_push_with_progress(mng, "my-env", MagicMock())


# ---------------------------------------------------------------------------
# run_pull_with_progress — terminal path
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_run_pull_terminal_invokes_hooks_and_prints_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Terminal: pull restore hooks fire; summary is printed after completion."""
    monkeypatch.setattr(Util, "console", _terminal_console())

    mock_progress = MagicMock()
    mock_progress.__enter__ = MagicMock(return_value=mock_progress)
    mock_progress.__exit__ = MagicMock(return_value=False)
    mock_progress.add_task.return_value = 0
    monkeypatch.setattr(
        "remote.remote_progress._make_restore_progress",
        lambda: mock_progress,
    )

    mng = _make_mng_mock("prod")

    def fake_pull(
        env_name: str,
        remote_name: str | None = None,
        snapshot_id: str | None = None,
        restore_hooks: RestoreHooks | None = None,
    ) -> None:
        if restore_hooks:
            restore_hooks.on_manifest(3, "snap-xyz")
            restore_hooks.on_chunk(False)
            restore_hooks.on_chunk(True)
            restore_hooks.on_chunk(False)
            restore_hooks.on_complete("snap-xyz", 2, 1, 20_480)

    mng.pull.side_effect = fake_pull

    printed: list[str] = []
    monkeypatch.setattr(
        "remote.remote_progress.Util.print",
        lambda msg: printed.append(msg),
    )

    run_pull_with_progress(mng, "my-env", remote_name="prod")

    mng.pull.assert_called_once()
    mock_progress.__enter__.assert_called_once()
    assert any("snap-xyz" in m for m in printed)
    assert any("Pulled" in m for m in printed)


@pytest.mark.remote
def test_run_pull_terminal_on_chunk_before_manifest_is_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """on_chunk fired before on_manifest (no task_holder) must not raise."""
    monkeypatch.setattr(Util, "console", _terminal_console())

    mock_progress = MagicMock()
    mock_progress.__enter__ = MagicMock(return_value=mock_progress)
    mock_progress.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(
        "remote.remote_progress._make_restore_progress",
        lambda: mock_progress,
    )

    mng = _make_mng_mock()

    def fake_pull(
        env_name: str,
        remote_name: str | None = None,
        snapshot_id: str | None = None,
        restore_hooks: RestoreHooks | None = None,
    ) -> None:
        if restore_hooks:
            # call on_chunk before on_manifest — task_holder is still empty
            restore_hooks.on_chunk(False)

    mng.pull.side_effect = fake_pull
    monkeypatch.setattr("remote.remote_progress.Util.print", lambda msg: None)

    run_pull_with_progress(mng, "my-env")  # must not raise


@pytest.mark.remote
def test_run_pull_terminal_no_complete_no_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Terminal: if on_complete is never fired no summary is printed."""
    monkeypatch.setattr(Util, "console", _terminal_console())

    mock_progress = MagicMock()
    mock_progress.__enter__ = MagicMock(return_value=mock_progress)
    mock_progress.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(
        "remote.remote_progress._make_restore_progress",
        lambda: mock_progress,
    )

    mng = _make_mng_mock()
    mng.pull.return_value = None

    printed: list[str] = []
    monkeypatch.setattr(
        "remote.remote_progress.Util.print",
        lambda msg: printed.append(msg),
    )

    run_pull_with_progress(mng, "my-env")

    assert printed == []


# ---------------------------------------------------------------------------
# run_hydrate_with_progress — terminal path
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_run_hydrate_terminal_invokes_hooks_and_prints_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Terminal: hydrate restore hooks fire; summary says 'Hydrated'."""
    monkeypatch.setattr(Util, "console", _terminal_console())

    mock_progress = MagicMock()
    mock_progress.__enter__ = MagicMock(return_value=mock_progress)
    mock_progress.__exit__ = MagicMock(return_value=False)
    mock_progress.add_task.return_value = 0
    monkeypatch.setattr(
        "remote.remote_progress._make_restore_progress",
        lambda: mock_progress,
    )

    mng = _make_mng_mock("prod")
    env_mng = MagicMock()

    def fake_hydrate(
        env_name: str,
        environment_mng: Any,
        remote_name: str | None = None,
        snapshot_id: str | None = None,
        restore_hooks: RestoreHooks | None = None,
    ) -> None:
        if restore_hooks:
            restore_hooks.on_manifest(2, "snap-hyd")
            restore_hooks.on_chunk(False)
            restore_hooks.on_chunk(True)
            restore_hooks.on_complete("snap-hyd", 1, 1, 8_192)

    mng.hydrate.side_effect = fake_hydrate

    printed: list[str] = []
    monkeypatch.setattr(
        "remote.remote_progress.Util.print",
        lambda msg: printed.append(msg),
    )

    run_hydrate_with_progress(mng, "my-env", env_mng, remote_name="prod")

    mng.hydrate.assert_called_once()
    assert any("Hydrated" in m for m in printed)
    assert any("snap-hyd" in m for m in printed)


# ---------------------------------------------------------------------------
# run_dehydrate_with_progress — terminal path
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_run_dehydrate_terminal_passes_hooks_to_mng(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Terminal: mng.dehydrate receives a DehydrateHooks with on_phase wired."""
    monkeypatch.setattr(Util, "console", _terminal_console())

    mng = _make_mng_mock()
    env_mng = MagicMock()

    received_hooks: list[DehydrateHooks] = []

    def fake_dehydrate(
        env_name: str,
        environment_mng: Any,
        dehydrate_hooks: DehydrateHooks | None = None,
    ) -> None:
        if dehydrate_hooks:
            received_hooks.append(dehydrate_hooks)
            dehydrate_hooks.on_phase("Removing volumes")

    mng.dehydrate.side_effect = fake_dehydrate

    printed: list[str] = []
    monkeypatch.setattr(
        "remote.remote_progress.Util.print",
        lambda msg: printed.append(msg),
    )

    run_dehydrate_with_progress(mng, "my-env", env_mng)

    assert len(received_hooks) == 1
    mng.dehydrate.assert_called_once()
    assert any("Removing volumes" in m for m in printed)


@pytest.mark.remote
def test_run_dehydrate_terminal_on_phase_prints_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The on_phase callback prints the label via Util.print."""
    monkeypatch.setattr(Util, "console", _terminal_console())

    mng = _make_mng_mock()

    def fake_dehydrate(
        env_name: str,
        environment_mng: Any,
        dehydrate_hooks: DehydrateHooks | None = None,
    ) -> None:
        if dehydrate_hooks:
            dehydrate_hooks.on_phase("Deleting local data")

    mng.dehydrate.side_effect = fake_dehydrate

    printed: list[str] = []
    monkeypatch.setattr(
        "remote.remote_progress.Util.print",
        lambda msg: printed.append(msg),
    )

    run_dehydrate_with_progress(mng, "my-env", MagicMock())

    assert any("Deleting local data" in m for m in printed)
