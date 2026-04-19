# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Integration tests for remote push/pull/dehydrate/hydrate/prune flows
against real FTP and SFTP backends running in Docker containers.

Each test receives a ``backend_cfg`` fixture parametrized over ``ftp`` and
``sftp``, giving 12 test runs total (6 tests × 2 backends).  Docker containers
are started once per session via the ``remote_backends`` fixture in conftest.py.

Marker: ``integration`` + ``docker``.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest

from config.config import EnvironmentCfg, RemoteCfg
from remote.backend import RemoteBackend
from remote.remote_mng import RemoteMng
from storage.snapshot import IndexCatalogue, SnapshotManifest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.docker,
    pytest.mark.skipif(
        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        ).returncode
        != 0,
        reason="Docker daemon not available",
    ),
]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(params=["ftp", "sftp"])
def backend_cfg(
    remote_backends: dict[str, RemoteCfg], request: pytest.FixtureRequest
) -> RemoteCfg:
    return remote_backends[request.param]  # type: ignore[index]


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------


def _make_env_cfg(
    tag: str = "my-env",
    dehydrated: Optional[bool] = None,
) -> EnvironmentCfg:
    return EnvironmentCfg(
        template="default",
        factory="docker-compose",
        tag=tag,
        services=[],
        probes=[],
        networks=[],
        volumes=[],
        dehydrated=dehydrated,
    )


def _make_push_mng(
    cfg: RemoteCfg,
    env_cfg: EnvironmentCfg,
    env_path: str,
) -> tuple[RemoteMng, MagicMock]:
    configMng = MagicMock()
    configMng.get_remotes.return_value = [cfg]
    configMng.get_remote.return_value = cfg
    configMng.get_default_remote.return_value = None
    configMng.get_environment.return_value = env_cfg
    configMng.constants.APP_VERSION = "0.0.0-test"
    configMng.config.envs_path = str(Path(env_path).parent)

    env_mock = MagicMock()
    env_mock.get_path.return_value = env_path
    env_mock.get_volume_tar_streams.return_value = []
    env_mock.is_running.return_value = False

    env_mng = MagicMock()
    env_mng.get_environment_from_cfg.return_value = env_mock

    # _build_backend NOT mocked — real FTP/SFTP connection
    return RemoteMng(configMng), env_mng


def _make_pull_mng(
    cfg: RemoteCfg,
    envs_path: str,
    existing_env_cfg: Optional[EnvironmentCfg] = None,
) -> RemoteMng:
    configMng = MagicMock()
    configMng.get_remotes.return_value = [cfg]
    configMng.get_remote.return_value = cfg
    configMng.get_default_remote.return_value = None
    configMng.get_environment.return_value = existing_env_cfg
    configMng.constants.APP_VERSION = "0.0.0-test"
    configMng.config.envs_path = envs_path

    mng = RemoteMng(configMng)
    mng._build_cache = MagicMock(  # type: ignore[method-assign]
        return_value=MagicMock(
            contains=lambda h: False,
            get=lambda h: None,
            put=lambda h, d: None,
        )
    )
    return mng


def _make_prune_mng(cfg: RemoteCfg) -> RemoteMng:
    configMng = MagicMock()
    configMng.get_remotes.return_value = [cfg]
    configMng.get_remote.return_value = cfg
    configMng.get_default_remote.return_value = None

    return RemoteMng(configMng)


def _make_dehydrate_mng(
    cfg: RemoteCfg,
    env_cfg: EnvironmentCfg,
    env_path: str,
) -> tuple[RemoteMng, MagicMock]:
    """Dehydrate is local-only; wires configMng so env_dir resolves correctly."""
    configMng = MagicMock()
    configMng.get_remotes.return_value = [cfg]
    configMng.get_remote.return_value = cfg
    configMng.get_default_remote.return_value = None
    configMng.get_environment.return_value = env_cfg
    configMng.constants.APP_VERSION = "0.0.0-test"
    # dehydrate computes env_dir as envs_path / env_name
    configMng.config.envs_path = str(Path(env_path).parent)

    env_mock = MagicMock()
    env_mock.get_path.return_value = env_path
    env_mock.is_running.return_value = False

    env_mng = MagicMock()
    env_mng.get_environment_from_cfg.return_value = env_mock

    return RemoteMng(configMng), env_mng


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.docker
def test_push_first_time(
    backend_cfg: RemoteCfg,
    tmp_path: Path,
) -> None:
    """push uploads chunks, manifest, and index on first push."""
    env_name = f"env-push-first-{backend_cfg.type}"
    env_dir = tmp_path / env_name
    env_dir.mkdir()
    (env_dir / "sentinel.bin").write_bytes(os.urandom(4 * 1024 * 1024))

    mng, env_mng = _make_push_mng(
        backend_cfg, _make_env_cfg(env_name), str(env_dir)
    )
    mng.push(env_name, env_mng, remote_name=backend_cfg.name)

    with mng._build_backend(backend_cfg) as backend:
        index_bytes = backend.download(RemoteBackend.index_path())
        catalogue = IndexCatalogue.from_dict(json.loads(index_bytes))
        assert env_name in catalogue.environments

        latest_bytes = backend.download(RemoteBackend.latest_path(env_name))
        latest = json.loads(latest_bytes)
        snapshot_id = latest["snapshot_id"]

        manifest_bytes = backend.download(
            RemoteBackend.snapshot_path(env_name, snapshot_id)
        )
        manifest = SnapshotManifest.from_dict(json.loads(manifest_bytes))
        assert manifest.chunk_count >= 1

        for chunk_hash in manifest.chunks:
            assert backend.exists(RemoteBackend.chunk_path(chunk_hash))


@pytest.mark.integration
@pytest.mark.docker
def test_push_second_time_no_new_chunks(
    backend_cfg: RemoteCfg,
    tmp_path: Path,
) -> None:
    """Pushing unchanged data a second time uploads zero new chunks."""
    env_name = f"env-push-second-{backend_cfg.type}"
    env_dir = tmp_path / env_name
    env_dir.mkdir()
    (env_dir / "sentinel.bin").write_bytes(os.urandom(4 * 1024 * 1024))

    mng, env_mng = _make_push_mng(
        backend_cfg, _make_env_cfg(env_name), str(env_dir)
    )
    mng.push(env_name, env_mng, remote_name=backend_cfg.name)

    with mng._build_backend(backend_cfg) as backend:
        manifest_bytes = backend.download(
            RemoteBackend.snapshot_path(
                env_name,
                json.loads(
                    backend.download(RemoteBackend.latest_path(env_name))
                )["snapshot_id"],
            )
        )
        chunks_after_first = set(
            SnapshotManifest.from_dict(json.loads(manifest_bytes)).chunks
        )

    mng.push(env_name, env_mng, remote_name=backend_cfg.name)

    with mng._build_backend(backend_cfg) as backend:
        manifest_bytes = backend.download(
            RemoteBackend.snapshot_path(
                env_name,
                json.loads(
                    backend.download(RemoteBackend.latest_path(env_name))
                )["snapshot_id"],
            )
        )
        chunks_after_second = set(
            SnapshotManifest.from_dict(json.loads(manifest_bytes)).chunks
        )

    assert chunks_after_first == chunks_after_second


@pytest.mark.integration
@pytest.mark.docker
def test_pull_creates_env(
    backend_cfg: RemoteCfg,
    tmp_path: Path,
) -> None:
    """pull restores env directory; sentinel bytes are identical to original."""
    env_name = f"env-pull-{backend_cfg.type}"
    src_dir = tmp_path / "src" / env_name
    src_dir.mkdir(parents=True)
    sentinel_data = os.urandom(4 * 1024 * 1024)
    (src_dir / "sentinel.bin").write_bytes(sentinel_data)

    push_mng, env_mng = _make_push_mng(
        backend_cfg, _make_env_cfg(env_name), str(src_dir)
    )
    push_mng.push(env_name, env_mng, remote_name=backend_cfg.name)

    fresh_envs = str(tmp_path / "dest")
    os.makedirs(fresh_envs, exist_ok=True)
    pull_mng = _make_pull_mng(backend_cfg, fresh_envs)
    pull_mng.pull(env_name, remote_name=backend_cfg.name)

    restored = Path(fresh_envs) / env_name / "env" / "sentinel.bin"
    assert restored.exists(), f"restored file not found at {restored}"
    assert restored.read_bytes() == sentinel_data


@pytest.mark.integration
@pytest.mark.docker
def test_dehydrate_strips_data(
    backend_cfg: RemoteCfg,
    tmp_path: Path,
) -> None:
    """dehydrate removes local env dir and sets dehydrated=True."""
    env_name = f"env-dehy-{backend_cfg.type}"
    env_dir = tmp_path / env_name
    env_dir.mkdir()
    (env_dir / "sentinel.bin").write_bytes(os.urandom(4 * 1024 * 1024))

    env_cfg = _make_env_cfg(env_name)
    push_mng, env_mng = _make_push_mng(backend_cfg, env_cfg, str(env_dir))
    push_mng.push(env_name, env_mng, remote_name=backend_cfg.name)

    dehy_mng, dehy_env_mng = _make_dehydrate_mng(
        backend_cfg, env_cfg, str(env_dir)
    )
    dehy_mng.dehydrate(env_name, dehy_env_mng)

    assert not env_dir.exists()
    assert env_cfg.dehydrated is True


@pytest.mark.integration
@pytest.mark.docker
def test_hydrate_restores_data(
    backend_cfg: RemoteCfg,
    tmp_path: Path,
) -> None:
    """hydrate restores env after dehydrate; bytes are identical to original."""
    env_name = f"env-hydrate-{backend_cfg.type}"
    env_dir = tmp_path / env_name
    env_dir.mkdir()
    sentinel_data = os.urandom(4 * 1024 * 1024)
    (env_dir / "sentinel.bin").write_bytes(sentinel_data)

    env_cfg = _make_env_cfg(env_name)
    push_mng, env_mng = _make_push_mng(backend_cfg, env_cfg, str(env_dir))
    push_mng.push(env_name, env_mng, remote_name=backend_cfg.name)

    dehy_mng, dehy_env_mng = _make_dehydrate_mng(
        backend_cfg, env_cfg, str(env_dir)
    )
    dehy_mng.dehydrate(env_name, dehy_env_mng)
    assert not env_dir.exists()

    envs_path = str(tmp_path)
    hydrate_mng = _make_pull_mng(
        backend_cfg,
        envs_path,
        existing_env_cfg=_make_env_cfg(env_name, dehydrated=True),
    )
    hydrate_mng.hydrate(env_name, remote_name=backend_cfg.name)

    restored = Path(envs_path) / env_name / "env" / "sentinel.bin"
    assert restored.exists(), f"restored file not found at {restored}"
    assert restored.read_bytes() == sentinel_data


@pytest.mark.integration
@pytest.mark.docker
def test_prune_removes_orphans(
    backend_cfg: RemoteCfg,
    tmp_path: Path,
) -> None:
    """prune removes orphan chunks; referenced chunks remain intact."""
    env_name = f"env-prune-{backend_cfg.type}"
    env_dir = tmp_path / env_name
    env_dir.mkdir()
    (env_dir / "sentinel.bin").write_bytes(os.urandom(4 * 1024 * 1024))

    push_mng, env_mng = _make_push_mng(
        backend_cfg, _make_env_cfg(env_name), str(env_dir)
    )
    push_mng.push(env_name, env_mng, remote_name=backend_cfg.name)

    orphan_hash = "aa" * 32
    with push_mng._build_backend(backend_cfg) as backend:
        backend.upload(RemoteBackend.chunk_path(orphan_hash), b"orphan-data")
        assert backend.exists(RemoteBackend.chunk_path(orphan_hash))

        manifest_bytes = backend.download(
            RemoteBackend.snapshot_path(
                env_name,
                json.loads(
                    backend.download(RemoteBackend.latest_path(env_name))
                )["snapshot_id"],
            )
        )
        referenced = SnapshotManifest.from_dict(
            json.loads(manifest_bytes)
        ).chunks

    prune_mng = _make_prune_mng(backend_cfg)
    prune_mng.prune(remote_name=backend_cfg.name, dry_run=False)

    with push_mng._build_backend(backend_cfg) as backend:
        assert not backend.exists(RemoteBackend.chunk_path(orphan_hash))
        for chunk_hash in referenced:
            assert backend.exists(RemoteBackend.chunk_path(chunk_hash))
