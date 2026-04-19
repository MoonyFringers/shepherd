# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Integration tests for the remote push/pull/dehydrate/hydrate/prune flows.

All tests use the ``fake_remote_backend`` pytest fixture (an in-memory
:class:`~fixtures.fake_remote.FakeRemoteBackend`) — no real network or
infrastructure required.  Marker: ``shpd``.
"""

from __future__ import annotations

import json
import pathlib
from typing import Optional
from unittest.mock import MagicMock

import click
import pytest
from fixtures.fake_remote import FakeRemoteBackend

from config.config import EnvironmentCfg, RemoteCfg
from remote.backend import RemoteBackend
from remote.remote_mng import RemoteMng
from storage.snapshot import IndexCatalogue, SnapshotManifest

# ---------------------------------------------------------------------------
# Shared remote config
# ---------------------------------------------------------------------------

_REMOTE = RemoteCfg(
    name="test-ftp",
    type="ftp",
    host="localhost",
    user="u",
    password="p",
    root_path="/shpd",
)

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
    fake: FakeRemoteBackend,
    env_cfg: EnvironmentCfg,
    env_path: str,
) -> tuple[RemoteMng, MagicMock]:
    configMng = MagicMock()
    configMng.get_remotes.return_value = [_REMOTE]
    configMng.get_remote.return_value = _REMOTE
    configMng.get_default_remote.return_value = None
    configMng.get_environment.return_value = env_cfg
    configMng.constants.APP_VERSION = "0.0.0-test"
    configMng.config.envs_path = str(pathlib.Path(env_path).parent)

    env_mock = MagicMock()
    env_mock.get_path.return_value = env_path
    env_mock.get_volume_tar_streams.return_value = []
    env_mock.is_running.return_value = False

    env_mng = MagicMock()
    env_mng.get_environment_from_cfg.return_value = env_mock

    mng = RemoteMng(configMng)
    mng._build_backend = MagicMock(return_value=fake)  # type: ignore[method-assign]
    return mng, env_mng


def _make_pull_mng(
    fake: FakeRemoteBackend,
    envs_path: str,
    existing_env_cfg: Optional[EnvironmentCfg] = None,
) -> RemoteMng:
    configMng = MagicMock()
    configMng.get_remotes.return_value = [_REMOTE]
    configMng.get_remote.return_value = _REMOTE
    configMng.get_default_remote.return_value = None
    configMng.get_environment.return_value = existing_env_cfg
    configMng.constants.APP_VERSION = "0.0.0-test"
    configMng.config.envs_path = envs_path

    mng = RemoteMng(configMng)
    mng._build_backend = MagicMock(return_value=fake)  # type: ignore[method-assign]
    mng._build_cache = MagicMock(  # type: ignore[method-assign]
        return_value=MagicMock(
            contains=lambda h: False,
            get=lambda h: None,
            put=lambda h, d: None,
        )
    )
    return mng


def _make_prune_mng(fake: FakeRemoteBackend) -> RemoteMng:
    configMng = MagicMock()
    configMng.get_remotes.return_value = [_REMOTE]
    configMng.get_remote.return_value = _REMOTE
    configMng.get_default_remote.return_value = None

    mng = RemoteMng(configMng)
    mng._build_backend = MagicMock(return_value=fake)  # type: ignore[method-assign]
    return mng


def _seed_prune_backend(
    fake: FakeRemoteBackend,
    env_name: str,
    referenced_hashes: list[str],
    orphan_hashes: list[str],
) -> None:
    import datetime as _dt

    from storage.snapshot import (
        IndexCatalogue,
        IndexCatalogueEntry,
        LatestPointer,
    )

    now = (
        _dt.datetime.now(_dt.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )

    for h in referenced_hashes + orphan_hashes:
        fake._store[RemoteBackend.chunk_path(h)] = b"x"

    manifest = SnapshotManifest(
        snapshot_id="",
        environment=env_name,
        shepherd_version="0.0.0-test",
        created_at=now,
        chunks=referenced_hashes,
        chunk_count=len(referenced_hashes),
        total_size_bytes=len(referenced_hashes) * 1024,
        stored_size_bytes=len(referenced_hashes) * 512,
    )
    manifest_bytes = json.dumps(manifest.to_dict(), indent=2).encode()
    snapshot_id = SnapshotManifest.build_id(now, manifest_bytes)
    manifest.snapshot_id = snapshot_id
    manifest_bytes = json.dumps(manifest.to_dict(), indent=2).encode()

    fake._store[RemoteBackend.snapshot_path(env_name, snapshot_id)] = (
        manifest_bytes
    )
    pointer = LatestPointer(snapshot_id=snapshot_id, updated_at=now)
    fake._store[RemoteBackend.latest_path(env_name)] = json.dumps(
        pointer.to_dict()
    ).encode()

    catalogue = IndexCatalogue(updated_at=now)
    catalogue.environments[env_name] = IndexCatalogueEntry(
        latest_snapshot=snapshot_id,
        snapshot_count=1,
        last_backup=now,
        labels=[],
        total_size_bytes=len(referenced_hashes) * 1024,
        stored_size_bytes=len(referenced_hashes) * 512,
    )
    fake._store[RemoteBackend.index_path()] = json.dumps(
        catalogue.to_dict(), indent=2
    ).encode()


# ---------------------------------------------------------------------------
# push
# ---------------------------------------------------------------------------


@pytest.mark.shpd
def test_push_uploads_all_chunks_first_time(
    fake_remote_backend: FakeRemoteBackend,
    tmp_path: pathlib.Path,
) -> None:
    """push stores at least one chunk in the backend on first push."""
    env_dir = tmp_path / "my-env"
    env_dir.mkdir()
    (env_dir / "data.txt").write_bytes(b"payload" * 1024)

    mng, env_mng = _make_push_mng(
        fake_remote_backend, _make_env_cfg(), str(env_dir)
    )
    mng.push("my-env", env_mng, remote_name="test-ftp")

    chunk_paths = [
        k for k in fake_remote_backend._store if k.startswith("chunks/")
    ]
    assert len(chunk_paths) >= 1


@pytest.mark.shpd
def test_push_second_time_uploads_zero_new_chunks(
    fake_remote_backend: FakeRemoteBackend,
    tmp_path: pathlib.Path,
) -> None:
    """A second push of an unchanged env uploads no new chunks."""
    env_dir = tmp_path / "my-env"
    env_dir.mkdir()
    (env_dir / "data.txt").write_bytes(b"hello" * 1024)

    mng, env_mng = _make_push_mng(
        fake_remote_backend, _make_env_cfg(), str(env_dir)
    )
    mng.push("my-env", env_mng, remote_name="test-ftp")

    original_upload = fake_remote_backend.upload
    uploaded_on_second: list[str] = []

    def _spy(path: str, data: bytes) -> None:
        if path.startswith("chunks/"):
            uploaded_on_second.append(path)
        original_upload(path, data)

    fake_remote_backend.upload = _spy  # type: ignore[method-assign]
    mng.push("my-env", env_mng, remote_name="test-ftp")

    assert uploaded_on_second == []


@pytest.mark.shpd
def test_push_writes_manifest_and_index(
    fake_remote_backend: FakeRemoteBackend,
    tmp_path: pathlib.Path,
) -> None:
    """push writes a parseable snapshot manifest and index to the backend."""
    env_dir = tmp_path / "my-env"
    env_dir.mkdir()
    (env_dir / "f.txt").write_bytes(b"data" * 512)

    mng, env_mng = _make_push_mng(
        fake_remote_backend, _make_env_cfg(), str(env_dir)
    )
    mng.push("my-env", env_mng, remote_name="test-ftp")

    snap_paths = [
        k
        for k in fake_remote_backend._store
        if k.startswith("envs/my-env/snapshots/")
    ]
    assert len(snap_paths) == 1
    manifest = SnapshotManifest.from_dict(
        json.loads(fake_remote_backend._store[snap_paths[0]])
    )
    assert manifest.environment == "my-env"
    assert manifest.chunks

    index_raw = fake_remote_backend._store["index/index.json"]
    catalogue = IndexCatalogue.from_dict(json.loads(index_raw))
    assert "my-env" in catalogue.environments


# ---------------------------------------------------------------------------
# pull
# ---------------------------------------------------------------------------


@pytest.mark.shpd
def test_pull_creates_env_and_restores_data(
    fake_remote_backend: FakeRemoteBackend,
    tmp_path: pathlib.Path,
) -> None:
    """pull creates the env dir and registers the env in config."""
    env_dir = tmp_path / "envs" / "my-env"
    env_dir.mkdir(parents=True)
    (env_dir / "sentinel.txt").write_bytes(b"restore-check" * 100)

    push_mng, env_mng = _make_push_mng(
        fake_remote_backend, _make_env_cfg(), str(env_dir)
    )
    push_mng.push("my-env", env_mng, remote_name="test-ftp")

    fresh_envs = str(tmp_path / "fresh")
    pull_mng = _make_pull_mng(fake_remote_backend, fresh_envs)
    pull_mng.pull("my-env", remote_name="test-ftp")

    pull_mng.configMng.add_or_set_environment.assert_called_once()  # type: ignore[union-attr]
    saved = pull_mng.configMng.add_or_set_environment.call_args[0][1]  # type: ignore[union-attr]
    assert saved.dehydrated is False
    assert (pathlib.Path(fresh_envs) / "my-env").exists()


@pytest.mark.shpd
def test_pull_fails_if_env_already_registered(
    fake_remote_backend: FakeRemoteBackend,
    tmp_path: pathlib.Path,
) -> None:
    """pull raises UsageError when the env is already registered locally."""
    env_dir = tmp_path / "envs" / "my-env"
    env_dir.mkdir(parents=True)
    (env_dir / "f.txt").write_bytes(b"x" * 256)

    push_mng, env_mng = _make_push_mng(
        fake_remote_backend, _make_env_cfg(), str(env_dir)
    )
    push_mng.push("my-env", env_mng, remote_name="test-ftp")

    pull_mng = _make_pull_mng(
        fake_remote_backend,
        str(tmp_path / "fresh"),
        existing_env_cfg=_make_env_cfg(),
    )

    with pytest.raises(click.UsageError):
        pull_mng.pull("my-env", remote_name="test-ftp")


# ---------------------------------------------------------------------------
# dehydrate / hydrate
# ---------------------------------------------------------------------------


@pytest.mark.shpd
def test_dehydrate_strips_data_sets_flag(
    fake_remote_backend: FakeRemoteBackend,
    tmp_path: pathlib.Path,
) -> None:
    """dehydrate removes the env directory and sets dehydrated=True."""
    env_dir = tmp_path / "envs" / "my-env"
    env_dir.mkdir(parents=True)
    (env_dir / "compose.yml").write_bytes(b"version: '3'")

    env_cfg = _make_env_cfg()
    configMng = MagicMock()
    configMng.get_environment.return_value = env_cfg
    configMng.config.envs_path = str(tmp_path / "envs")
    mng = RemoteMng(configMng)
    mng._build_backend = MagicMock(return_value=fake_remote_backend)  # type: ignore[method-assign]

    env_mock = MagicMock()
    env_mock.is_running.return_value = False
    env_mng = MagicMock()
    env_mng.get_environment_from_cfg.return_value = env_mock

    mng.dehydrate("my-env", env_mng)

    assert not env_dir.exists()
    saved: EnvironmentCfg = configMng.add_or_set_environment.call_args[0][1]
    assert saved.dehydrated is True


@pytest.mark.shpd
def test_hydrate_restores_data_clears_flag(
    fake_remote_backend: FakeRemoteBackend,
    tmp_path: pathlib.Path,
) -> None:
    """hydrate restores env data and sets dehydrated=False."""
    env_dir = tmp_path / "envs" / "my-env"
    env_dir.mkdir(parents=True)
    (env_dir / "data.bin").write_bytes(b"hydrate-payload" * 200)

    push_mng, env_mng = _make_push_mng(
        fake_remote_backend, _make_env_cfg(), str(env_dir)
    )
    push_mng.push("my-env", env_mng, remote_name="test-ftp")

    hydrate_mng = _make_pull_mng(
        fake_remote_backend,
        str(tmp_path / "envs"),
        existing_env_cfg=_make_env_cfg(dehydrated=True),
    )
    hydrate_mng.hydrate("my-env", remote_name="test-ftp")

    hydrate_mng.configMng.add_or_set_environment.assert_called_once()  # type: ignore[union-attr]
    saved = hydrate_mng.configMng.add_or_set_environment.call_args[0][1]  # type: ignore[union-attr]
    assert saved.dehydrated is False
    assert (tmp_path / "envs" / "my-env").exists()


@pytest.mark.shpd
def test_dehydrate_hydrate_roundtrip(
    fake_remote_backend: FakeRemoteBackend,
    tmp_path: pathlib.Path,
) -> None:
    """dehydrate → hydrate round-trip restores the env directory."""
    envs_path = tmp_path / "envs"
    envs_path.mkdir()
    env_dir = envs_path / "rt-env"
    env_dir.mkdir()
    (env_dir / "sentinel.txt").write_bytes(b"round-trip payload" * 200)

    env_cfg = _make_env_cfg(tag="rt-env")
    push_mng, env_mng_push = _make_push_mng(
        fake_remote_backend, env_cfg, str(env_dir)
    )
    push_mng.configMng.config.envs_path = str(envs_path)  # type: ignore[union-attr]
    push_mng.push("rt-env", env_mng_push, remote_name="test-ftp")

    push_mng.configMng.get_environment.return_value = env_cfg  # type: ignore[union-attr]
    env_mock = MagicMock()
    env_mock.is_running.return_value = False
    env_mng_dehy = MagicMock()
    env_mng_dehy.get_environment_from_cfg.return_value = env_mock
    push_mng.dehydrate("rt-env", env_mng_dehy)
    assert not env_dir.exists()

    dehydrated_cfg = _make_env_cfg(tag="rt-env", dehydrated=True)
    pull_mng = _make_pull_mng(
        fake_remote_backend, str(envs_path), dehydrated_cfg
    )
    pull_mng.hydrate("rt-env", remote_name="test-ftp")

    assert (envs_path / "rt-env").exists()


# ---------------------------------------------------------------------------
# prune
# ---------------------------------------------------------------------------

_HASH_REF = "aa" * 32
_HASH_ORPHAN = "bb" * 32


@pytest.mark.shpd
def test_prune_removes_orphan_chunks(
    fake_remote_backend: FakeRemoteBackend,
) -> None:
    """prune deletes orphan chunks and retains referenced ones."""
    _seed_prune_backend(
        fake_remote_backend, "my-env", [_HASH_REF], [_HASH_ORPHAN]
    )
    mng = _make_prune_mng(fake_remote_backend)

    mng.prune(remote_name="test-ftp")

    assert RemoteBackend.chunk_path(_HASH_REF) in fake_remote_backend._store
    assert (
        RemoteBackend.chunk_path(_HASH_ORPHAN) not in fake_remote_backend._store
    )


@pytest.mark.shpd
def test_prune_dry_run_removes_nothing(
    fake_remote_backend: FakeRemoteBackend,
) -> None:
    """prune --dry-run leaves all chunks intact."""
    _seed_prune_backend(
        fake_remote_backend, "my-env", [_HASH_REF], [_HASH_ORPHAN]
    )
    mng = _make_prune_mng(fake_remote_backend)

    mng.prune(remote_name="test-ftp", dry_run=True)

    assert RemoteBackend.chunk_path(_HASH_REF) in fake_remote_backend._store
    assert RemoteBackend.chunk_path(_HASH_ORPHAN) in fake_remote_backend._store
