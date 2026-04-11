# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from shepctl import cli


def read_fixture(*parts: str) -> str:
    here = Path(__file__).resolve().parent
    return (here / "fixtures" / Path(*parts)).read_text(encoding="utf-8")


@pytest.fixture
def shpd_env(tmp_path: Path):
    """
    Set up a temporary shepherd home with the basic nginx env config.
    Tears down running containers after the test (best-effort).
    """
    temp_home = tmp_path / "home"
    temp_home.mkdir()

    config_file = temp_home / ".shpd.conf"
    values = read_fixture("basic", "values.conf")
    config_file.write_text(values.replace("${test_path}", str(temp_home)))

    shpd_yaml = temp_home / ".shpd.yaml"
    shpd_yaml.write_text(read_fixture("basic", "shpd.yaml"))

    os.environ["SHPD_CONF"] = str(config_file)

    yield temp_home

    CliRunner().invoke(cli, ["env", "halt"])


@pytest.fixture
def shpd_gated_env(tmp_path: Path):
    """
    Set up a temporary shepherd home with the probe-gated env config
    (web ungated + cache gated on the 'ready' probe).
    Tears down running containers after the test (best-effort).
    """
    temp_home = tmp_path / "home"
    temp_home.mkdir()

    config_file = temp_home / ".shpd.conf"
    values = read_fixture("gated", "values.conf")
    config_file.write_text(values.replace("${test_path}", str(temp_home)))

    shpd_yaml = temp_home / ".shpd.yaml"
    shpd_yaml.write_text(read_fixture("gated", "shpd.yaml"))

    os.environ["SHPD_CONF"] = str(config_file)

    yield temp_home

    CliRunner().invoke(cli, ["env", "halt"])


@pytest.fixture
def shpd_redis_gated_env(tmp_path: Path):
    """
    Two-level probe-gated env: cache (redis) starts ungated, frontend
    (nginx) starts only after the cache-ready probe connects to the live
    redis. This exercises a real health-check gate rather than a trivial
    always-passing probe.
    """
    temp_home = tmp_path / "home"
    temp_home.mkdir()

    config_file = temp_home / ".shpd.conf"
    values = read_fixture("gated_redis", "values.conf")
    config_file.write_text(values.replace("${test_path}", str(temp_home)))

    shpd_yaml = temp_home / ".shpd.yaml"
    shpd_yaml.write_text(read_fixture("gated_redis", "shpd.yaml"))

    os.environ["SHPD_CONF"] = str(config_file)

    yield temp_home

    CliRunner().invoke(cli, ["env", "halt"])


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()
