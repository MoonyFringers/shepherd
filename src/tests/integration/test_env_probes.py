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


def test_gated_service_starts_after_probe_passes(
    shpd_gated_env: Path, runner: CliRunner
):
    # env up runs the full gate/probe loop: web starts immediately,
    # then the 'ready' probe fires against the live cache container,
    # and cache starts once the probe passes.
    result = runner.invoke(cli, ["env", "up"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, ["env", "status"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, ["env", "halt"])
    assert result.exit_code == 0, result.output


def test_env_reload_is_safe(shpd_gated_env: Path, runner: CliRunner):
    result = runner.invoke(cli, ["env", "up"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, ["env", "reload"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, ["env", "halt"])
    assert result.exit_code == 0, result.output


def test_real_healthcheck_gate_opens_after_redis_is_ready(
    shpd_redis_gated_env: Path, runner: CliRunner
):
    # cache (redis) starts ungated; frontend (nginx) is gated on the
    # cache-ready probe which runs `redis-cli -h cache ping`.  The gate
    # opens as soon as redis is accepting connections (~1 s), then
    # frontend starts.  This exercises a real service health-check rather
    # than a trivially-passing probe.
    result = runner.invoke(cli, ["env", "up"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, ["env", "status"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, ["env", "halt"])
    assert result.exit_code == 0, result.output
