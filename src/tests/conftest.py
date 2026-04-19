# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Shared pytest fixtures for the unit-test suite."""

from __future__ import annotations

import pytest
from rich.console import Console

pytest_plugins = ["fixtures.fake_remote"]


@pytest.fixture(autouse=True)
def _no_rich_color(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace Util.console with a plain, no-color Console for every test.

    ``Util.console`` is a class-level attribute initialized at import time.
    If pytest runs in a colour-capable terminal the Rich Console caches
    colour support and emits ANSI escape codes even when CliRunner captures
    stdout, making plain-string assertions fail.  Patching it here ensures
    consistent, colour-free output across all environments.
    """
    from util.util import Util

    monkeypatch.setattr(
        Util, "console", Console(force_terminal=False, no_color=True)
    )
