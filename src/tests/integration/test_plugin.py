# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

from __future__ import annotations

import shutil
import tarfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from shepctl import cli

pytestmark = pytest.mark.integration

# hello-plugin lives at examples/plugins/hello-plugin/ relative to repo root.
# From src/tests/integration/ we go up three levels to reach the repo root.
_HELLO_PLUGIN_SRC = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "examples"
    / "plugins"
    / "hello-plugin"
)


def _make_hello_plugin_archive(tmp_path: Path) -> Path:
    plugin_copy = tmp_path / "hello-plugin"
    shutil.copytree(_HELLO_PLUGIN_SRC, plugin_copy)
    archive = tmp_path / "hello-plugin.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(plugin_copy, arcname="hello-plugin")
    return archive


def test_plugin_install_and_list(
    shpd_env: Path, runner: CliRunner, tmp_path: Path
):
    archive = _make_hello_plugin_archive(tmp_path)

    result = runner.invoke(cli, ["plugin", "install", str(archive)])
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, ["plugin", "list"])
    assert result.exit_code == 0, result.output
    assert "hello-plugin" in result.output


def test_plugin_command_available_after_install(
    shpd_env: Path, runner: CliRunner, tmp_path: Path
):
    archive = _make_hello_plugin_archive(tmp_path)
    runner.invoke(cli, ["plugin", "install", str(archive)])

    result = runner.invoke(cli, ["hello", "greet"])
    assert result.exit_code == 0, result.output
    assert "Hello, world!" in result.output

    result = runner.invoke(cli, ["hello", "greet", "Alice"])
    assert result.exit_code == 0, result.output
    assert "Hello, Alice!" in result.output


def test_plugin_remove(shpd_env: Path, runner: CliRunner, tmp_path: Path):
    archive = _make_hello_plugin_archive(tmp_path)
    runner.invoke(cli, ["plugin", "install", str(archive)])

    result = runner.invoke(cli, ["plugin", "remove", "hello-plugin"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, ["plugin", "list"])
    assert result.exit_code == 0, result.output
    assert "hello-plugin" not in result.output
