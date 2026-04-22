# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Pure Rich renderables for remote operation progress displays."""

from __future__ import annotations

from rich.console import Group
from rich.text import Text
from rich.tree import Tree

from environment.status_wait import render_moving_shadow_text
from util import Util


def build_push_renderable(
    env_name: str,
    remote_name: str,
    total: int,
    uploaded: int,
    skipped: int,
    raw_bytes: int,
    stored_bytes: int,
    *,
    tick: int,
) -> Group:
    """Live push display: animated spinner tree + running counters."""
    tree = Tree(
        f"[bold white]{env_name}[/bold white]"
        f" [dim]→[/dim] [cyan]{remote_name}[/cyan]",
        guide_style="dim",
    )
    tree.add(render_moving_shadow_text("Uploading", tick))
    counters = Text.from_markup(
        f"[dim]Chunks[/dim]   {total} processed"
        f"  ·  [green]{uploaded} new[/green]"
        f"  ·  [dim]{skipped} skipped[/dim]\n"
        f"[dim]Data[/dim]     {Util.fmt_bytes(raw_bytes)} raw"
        f"  ·  {Util.fmt_bytes(stored_bytes)} stored"
    )
    return Group(tree, counters)


def build_restore_header(
    env_name: str,
    remote_name: str,
    snapshot_id: str,
    *,
    direction: str = "←",
) -> Text:
    """Static header printed above the pull/hydrate progress bar."""
    short_id = snapshot_id[:12] if len(snapshot_id) > 12 else snapshot_id
    return Text.from_markup(
        f"[bold white]{env_name}[/bold white]"
        f" [dim]{direction}[/dim] [cyan]{remote_name}[/cyan]"
        f"  [dim][{short_id}][/dim]"
    )
