# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from shepctl import cli

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        subprocess.run(
            ["docker", "info"], capture_output=True, timeout=5
        ).returncode
        != 0,
        reason="Docker daemon not available",
    ),
]


def test_basic_env_up_down(shpd_env: Path, runner: CliRunner):
    result = runner.invoke(cli, ["env", "up"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, ["env", "status"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, ["env", "halt"])
    assert result.exit_code == 0, result.output


def test_env_up_is_idempotent(shpd_env: Path, runner: CliRunner):
    result = runner.invoke(cli, ["env", "up"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, ["env", "up"])
    assert result.exit_code == 0, result.output


def test_env_halt_on_stopped_env_is_safe(shpd_env: Path, runner: CliRunner):
    # halt without a prior up should not crash
    result = runner.invoke(cli, ["env", "halt"])
    assert result.exit_code == 0, result.output
