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


def add_container_field_defaults(node: object) -> None:
    """
    Recursively add default values for `ContainerCfg` fields that older
    fixture literals/files predate (e.g. `labels`, `ingress`), wherever a
    `containers:` list or a single `container:` mapping appears, at any
    nesting depth. Keeps fixture-comparison tests from having to be
    hand-edited every time an optional `ContainerCfg` field is added.

    This is deliberately separate from the flat, per-call-site
    `expected.setdefault("field", None)` calls used elsewhere for top-level
    scalar fields (e.g. `ready`, `tracking_remote`): those apply once at a
    known key path, while `ContainerCfg` fields recur at arbitrary nesting
    depth (services -> containers, probes -> container, ...), so a single
    flat `setdefault` per comparison site can't cover them. Prefer this
    helper specifically for new optional `ContainerCfg` fields; keep using
    flat `setdefault` calls for new top-level/service-level scalar fields.
    """
    defaults: dict[str, object] = {
        "labels": [],
        "ingress": None,
        "ingress_port": None,
        "endpoints": None,
        "command": [],
        "network_mode": None,
        "user": None,
        "group_add": [],
        "cpus": None,
        "memory": None,
        "cpuset": None,
    }
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "containers" and isinstance(value, list):
                for container in value:
                    if isinstance(container, dict):
                        for field_name, default in defaults.items():
                            container.setdefault(field_name, default)
                        _add_build_field_defaults(container)
            if key == "container" and isinstance(value, dict):
                for field_name, default in defaults.items():
                    value.setdefault(field_name, default)
                _add_build_field_defaults(value)
            add_container_field_defaults(value)
    elif isinstance(node, list):
        for item in node:
            add_container_field_defaults(item)


def _add_build_field_defaults(container: dict[str, object]) -> None:
    """Default for `ContainerCfg.build.args`, mirroring
    `add_container_field_defaults`'s own rationale but for a field nested
    one level deeper, inside `build:`."""
    build = container.get("build")
    if isinstance(build, dict):
        build.setdefault("args", None)


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
