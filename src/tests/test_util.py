# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from util.util import Util


def read_fixture(*parts: str) -> str:
    """
    Read a test fixture file under tests/fixtures.
    Usage: read_fixture("cfg", "base.yaml")
    """
    here = Path(__file__).resolve().parent
    fixtures_dir = here / "fixtures"
    return (fixtures_dir.joinpath(*parts)).read_text(encoding="utf-8")


def test_print_error_and_die_uses_minimal_error_prefix(
    mocker: MockerFixture,
):
    console = mocker.Mock()
    mocker.patch.object(Util, "console", console)

    with pytest.raises(SystemExit) as excinfo:
        Util.print_error_and_die("test failure")

    assert excinfo.value.code == 1
    console.print.assert_called_once_with(
        "[red]Error:[/red] test failure",
        highlight=False,
    )
