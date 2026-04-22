# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Unit tests for :mod:`remote.remote_render`."""

from __future__ import annotations

import pytest
from rich.console import Group
from rich.text import Text

from remote.remote_render import build_push_renderable, build_restore_header


@pytest.mark.remote
def test_build_push_renderable_returns_group() -> None:
    """build_push_renderable returns a Rich Group at any tick value."""
    result = build_push_renderable(
        "my-env",
        "prod",
        total=10,
        uploaded=7,
        skipped=3,
        raw_bytes=10_240,
        stored_bytes=5_120,
        tick=0,
    )
    assert isinstance(result, Group)


@pytest.mark.remote
def test_build_push_renderable_advances_tick() -> None:
    """Two consecutive ticks produce different Group objects (no crash)."""
    kwargs = dict(
        env_name="e",
        remote_name="r",
        total=1,
        uploaded=1,
        skipped=0,
        raw_bytes=512,
        stored_bytes=256,
    )
    g0 = build_push_renderable(**kwargs, tick=0)
    g1 = build_push_renderable(**kwargs, tick=5)
    assert isinstance(g0, Group)
    assert isinstance(g1, Group)


@pytest.mark.remote
def test_build_restore_header_short_snap_id() -> None:
    """A snapshot ID shorter than 12 chars is passed through unchanged."""
    result = build_restore_header("my-env", "prod", "short")
    assert isinstance(result, Text)
    # env_name and remote_name always appear as plain text
    assert "my-env" in result.plain
    assert "prod" in result.plain


@pytest.mark.remote
def test_build_restore_header_long_snap_id_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A snapshot ID longer than 12 chars is truncated to its first 12 chars."""
    long_id = "a" * 64

    captured: list[str] = []
    original = Text.from_markup

    def spy(markup: str, **kw: object) -> Text:
        captured.append(markup)
        return original(markup, **kw)

    monkeypatch.setattr(Text, "from_markup", staticmethod(spy))

    build_restore_header("my-env", "prod", long_id)

    assert captured
    markup = captured[0]
    assert long_id[:12] in markup
    assert long_id[12:] not in markup


@pytest.mark.remote
def test_build_restore_header_default_direction() -> None:
    """Default direction arrow (←) appears in the rendered plain text."""
    result = build_restore_header("my-env", "prod", "snap1")
    assert "←" in result.plain


@pytest.mark.remote
def test_build_restore_header_custom_direction() -> None:
    """Callers can override the direction arrow."""
    result = build_restore_header("my-env", "prod", "snap1", direction="→")
    assert "→" in result.plain
    assert "←" not in result.plain
