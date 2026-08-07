# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

import subprocess
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
    err_console = mocker.Mock()
    mocker.patch.object(Util, "err_console", err_console)

    with pytest.raises(SystemExit) as excinfo:
        Util.print_error_and_die("test failure")

    assert excinfo.value.code == 1
    err_console.print.assert_called_once_with(
        "[red]Error:[/red] test failure",
        highlight=False,
    )


def test_print_error_and_die_does_not_use_stdout_console(
    mocker: MockerFixture,
):
    """Regression test for #270: error output must not corrupt stdout,
    since shell completion (`shepctl __complete ...`) requires stdout to
    contain only completion candidates."""
    console = mocker.Mock()
    err_console = mocker.Mock()
    mocker.patch.object(Util, "console", console)
    mocker.patch.object(Util, "err_console", err_console)

    with pytest.raises(SystemExit):
        Util.print_error_and_die("test failure")

    console.print.assert_not_called()
    err_console.print.assert_called_once()


def test_run_command_failure_prints_to_err_console(mocker: MockerFixture):
    """Regression test for #270: run_command's failure path must also go
    to err_console, not the stdout console."""
    console = mocker.Mock()
    err_console = mocker.Mock()
    mocker.patch.object(Util, "console", console)
    mocker.patch.object(Util, "err_console", err_console)
    mocker.patch(
        "util.util.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, ["false"]),
    )

    with pytest.raises(SystemExit):
        Util.run_command(["false"], check=True)

    console.print.assert_not_called()
    err_console.print.assert_called_once()


def test_run_command_failure_no_check_returns_error(mocker: MockerFixture):
    """When check=False, a failed command returns the error instead of
    exiting, but still reports via err_console, not stdout."""
    console = mocker.Mock()
    err_console = mocker.Mock()
    mocker.patch.object(Util, "console", console)
    mocker.patch.object(Util, "err_console", err_console)
    error = subprocess.CalledProcessError(1, ["false"])
    mocker.patch("util.util.subprocess.run", side_effect=error)

    result = Util.run_command(["false"], check=False)

    assert result is error
    console.print.assert_not_called()
    err_console.print.assert_called_once()
