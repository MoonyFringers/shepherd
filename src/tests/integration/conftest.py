# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

from __future__ import annotations

import ftplib
import os
import subprocess
import time
from pathlib import Path
from typing import Generator

import paramiko
import pytest
from click.testing import CliRunner

from config.config import RemoteCfg, RemoteChunkCfg
from shepctl import cli

_COMPOSE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "remote"
    / "docker-compose.yml"
)

_CHUNK_CFG = RemoteChunkCfg(
    min_size_kb=64,
    avg_size_kb=256,
    max_size_kb=1024,
)


def _wait_ftp_ready(
    host: str, port: int, user: str, password: str, timeout: float = 30.0
) -> None:
    """Probe until an FTP login succeeds (not just TCP open)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            ftp = ftplib.FTP()
            ftp.connect(host, port, timeout=2)
            ftp.login(user, password)
            ftp.quit()
            return
        except Exception:
            time.sleep(0.5)
    raise TimeoutError(f"FTP {host}:{port} not ready after {timeout}s")


def _wait_sftp_ready(
    host: str,
    port: int,
    user: str,
    password: str,
    upload_dir: str = "upload",
    timeout: float = 30.0,
) -> None:
    """Probe until SFTP auth succeeds AND upload_dir is visible in root.

    atmoz/sftp creates the upload subdir asynchronously in its entrypoint;
    TCP-ready and even auth-ready are not enough — we must wait for the dir.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        transport = None
        try:
            transport = paramiko.Transport((host, port))
            transport.connect(username=user, password=password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            if sftp and upload_dir in sftp.listdir("/"):
                sftp.close()
                transport.close()
                return
            if sftp:
                sftp.close()
        except Exception:
            pass
        finally:
            if transport and transport.is_active():
                transport.close()
        time.sleep(0.5)
    raise TimeoutError(f"SFTP {host}:{port} not ready after {timeout}s")


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

    prev = os.environ.get("SHPD_CONF")
    os.environ["SHPD_CONF"] = str(config_file)

    yield temp_home

    CliRunner().invoke(cli, ["env", "halt"])
    if prev is None:
        os.environ.pop("SHPD_CONF", None)
    else:
        os.environ["SHPD_CONF"] = prev


@pytest.fixture
def shpd_gated_env(tmp_path: Path):
    """
    Set up a temporary shepherd home with the probe-gated env config
    (web ungated + api gated on the trivially-passing 'warmup' probe).
    Tears down running containers after the test (best-effort).
    """
    temp_home = tmp_path / "home"
    temp_home.mkdir()

    config_file = temp_home / ".shpd.conf"
    values = read_fixture("gated", "values.conf")
    config_file.write_text(values.replace("${test_path}", str(temp_home)))

    shpd_yaml = temp_home / ".shpd.yaml"
    shpd_yaml.write_text(read_fixture("gated", "shpd.yaml"))

    prev = os.environ.get("SHPD_CONF")
    os.environ["SHPD_CONF"] = str(config_file)

    yield temp_home

    CliRunner().invoke(cli, ["env", "halt"])
    if prev is None:
        os.environ.pop("SHPD_CONF", None)
    else:
        os.environ["SHPD_CONF"] = prev


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

    prev = os.environ.get("SHPD_CONF")
    os.environ["SHPD_CONF"] = str(config_file)

    yield temp_home

    CliRunner().invoke(cli, ["env", "halt"])
    if prev is None:
        os.environ.pop("SHPD_CONF", None)
    else:
        os.environ["SHPD_CONF"] = prev


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(scope="session")
def remote_backends() -> Generator[dict[str, RemoteCfg], None, None]:
    """Start FTP + SFTP containers once for the whole session."""
    subprocess.run(
        ["docker", "compose", "-f", str(_COMPOSE), "up", "-d"],
        check=True,
    )
    try:
        _wait_ftp_ready("127.0.0.1", 2121, "ftpuser", "ftppass")
        _wait_sftp_ready("127.0.0.1", 2222, "sftpuser", "sftppass")
        yield {
            "ftp": RemoteCfg(
                name="ftp",
                type="ftp",
                host="127.0.0.1",
                port=2121,
                user="ftpuser",
                password="ftppass",
                # delfer/alpine-ftp-server places home at /ftp/<user>;
                # vsftpd is not chrooted so we use the absolute server path.
                root_path="/ftp/ftpuser",
                chunk=_CHUNK_CFG,
            ),
            "sftp": RemoteCfg(
                name="sftp",
                type="sftp",
                host="127.0.0.1",
                port=2222,
                user="sftpuser",
                password="sftppass",
                root_path="/upload",
                chunk=_CHUNK_CFG,
            ),
        }
    finally:
        subprocess.run(
            ["docker", "compose", "-f", str(_COMPOSE), "down", "-v"],
            check=True,
        )
