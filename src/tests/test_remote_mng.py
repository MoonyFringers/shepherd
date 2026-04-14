# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Unit tests for :class:`~remote.remote_mng.RemoteMng`.

All tests use :class:`FakeRemoteBackend` — an in-memory implementation of
:class:`~remote.backend.RemoteBackend` — to exercise the orchestration logic
without touching a real FTP or SFTP server.
"""

from __future__ import annotations

import json
from typing import Optional
from unittest.mock import MagicMock, patch

import click
import pytest

from config.config import RemoteCfg
from remote.backend import RemoteBackend
from remote.remote_mng import RemoteMng
from storage.snapshot import (
    IndexCatalogue,
    IndexCatalogueEntry,
    SnapshotManifest,
)

# ---------------------------------------------------------------------------
# FakeRemoteBackend
# ---------------------------------------------------------------------------


class FakeRemoteBackend(RemoteBackend):
    """In-memory :class:`~remote.backend.RemoteBackend` for testing.

    Stores all data in a plain ``dict[str, bytes]``.  Can be pre-seeded via
    :meth:`seed` before the test calls into ``RemoteMng``.
    """

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    def seed(self, path: str, data: bytes) -> None:
        """Pre-populate *path* with *data* (test helper)."""
        self._store[path] = data

    # RemoteBackend contract

    def exists(self, path: str) -> bool:
        return path in self._store

    def upload(self, path: str, data: bytes) -> None:
        self._store[path] = data

    def download(self, path: str) -> bytes:
        if path not in self._store:
            raise FileNotFoundError(f"FakeRemoteBackend: no such path: {path}")
        return self._store[path]

    def list_prefix(self, prefix: str) -> list[str]:
        """Return leaf names of all paths that start with *prefix/*."""
        results: list[str] = []
        search = prefix.rstrip("/") + "/"
        for key in self._store:
            if key.startswith(search):
                leaf = key[len(search) :]
                # only one level deep (no nested slashes)
                if "/" not in leaf:
                    results.append(leaf)
        return results

    def delete(self, path: str) -> None:
        self._store.pop(path, None)

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REMOTE_FTP = RemoteCfg(
    name="test-ftp",
    type="ftp",
    host="localhost",
    user="u",
    password="p",
    root_path="/shpd",
)
_REMOTE_SFTP = RemoteCfg(
    name="test-sftp",
    type="sftp",
    host="localhost",
    user="u",
    root_path="/shpd",
)
_REMOTE_DEFAULT = RemoteCfg(
    name="default-remote",
    type="ftp",
    host="localhost",
    user="u",
    password="p",
    root_path="/shpd",
    default="true",
)


def _make_mng(
    remotes: list[RemoteCfg],
    fake_backend: FakeRemoteBackend,
) -> RemoteMng:
    """Build a :class:`RemoteMng` wired to *fake_backend*.

    The ``_build_backend`` method is replaced via ``MagicMock`` so that the
    test can inject ``fake_backend`` regardless of the ``RemoteCfg.type``.
    """
    configMng = MagicMock()
    configMng.get_remotes.return_value = remotes
    configMng.get_remote.side_effect = lambda name: next(
        (r for r in remotes if r.name == name), None
    )
    configMng.get_default_remote.return_value = next(
        (r for r in remotes if r.is_default()), None
    )

    mng = RemoteMng(configMng)
    mng._build_backend = MagicMock(return_value=fake_backend)  # type: ignore[method-assign]
    return mng


def _make_manifest(
    snapshot_id: str,
    env: str = "my-env",
    created_at: str = "2026-01-01T00:00:00Z",
) -> SnapshotManifest:
    return SnapshotManifest(
        snapshot_id=snapshot_id,
        environment=env,
        shepherd_version="0.1.0",
        created_at=created_at,
        chunks=["ab" * 32],
        chunk_count=1,
        total_size_bytes=1024,
        stored_size_bytes=512,
    )


# ---------------------------------------------------------------------------
# list_envs
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_list_envs_no_index() -> None:
    """When the remote has no index.json the returned catalogue is empty."""
    fake = FakeRemoteBackend()
    mng = _make_mng([_REMOTE_FTP], fake)

    _, catalogue = mng.list_envs("test-ftp")

    assert isinstance(catalogue, IndexCatalogue)
    assert catalogue.environments == {}


@pytest.mark.remote
def test_list_envs_with_index() -> None:
    """A seeded index.json is parsed and returned correctly."""
    fake = FakeRemoteBackend()
    entry = IndexCatalogueEntry(
        latest_snapshot="2026-01-01T00:00:00Z-abc123",
        snapshot_count=3,
        last_backup="2026-01-01T00:00:00Z",
        labels=["prod"],
        total_size_bytes=1_000_000,
        stored_size_bytes=600_000,
    )
    catalogue = IndexCatalogue(
        updated_at="2026-01-01T00:00:00Z",
        environments={"my-env": entry},
    )
    fake.seed("index/index.json", json.dumps(catalogue.to_dict()).encode())

    mng = _make_mng([_REMOTE_FTP], fake)
    _, result = mng.list_envs("test-ftp")

    assert "my-env" in result.environments
    assert result.environments["my-env"].snapshot_count == 3
    assert result.environments["my-env"].labels == ["prod"]


# ---------------------------------------------------------------------------
# list_snapshots
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_list_snapshots_empty() -> None:
    """When no snapshot manifests exist the returned list is empty."""
    fake = FakeRemoteBackend()
    mng = _make_mng([_REMOTE_FTP], fake)

    _, manifests = mng.list_snapshots("my-env", "test-ftp")

    assert manifests == []


@pytest.mark.remote
def test_list_snapshots_sorted_newest_first() -> None:
    """Snapshot manifests are returned sorted newest-first by created_at."""
    fake = FakeRemoteBackend()
    for ts, sid in [
        ("2026-01-01T00:00:00Z", "snap-a"),
        ("2026-03-01T00:00:00Z", "snap-c"),
        ("2026-02-01T00:00:00Z", "snap-b"),
    ]:
        m = _make_manifest(sid, created_at=ts)
        path = f"envs/my-env/snapshots/{sid}.json"
        fake.seed(path, json.dumps(m.to_dict()).encode())

    mng = _make_mng([_REMOTE_FTP], fake)
    _, manifests = mng.list_snapshots("my-env", "test-ftp")

    assert len(manifests) == 3
    assert [m.snapshot_id for m in manifests] == ["snap-c", "snap-b", "snap-a"]


@pytest.mark.remote
def test_list_snapshots_ignores_non_json_entries() -> None:
    """Non-JSON entries returned by list_prefix are silently skipped."""
    fake = FakeRemoteBackend()
    m = _make_manifest("snap-a")
    fake.seed(
        "envs/my-env/snapshots/snap-a.json",
        json.dumps(m.to_dict()).encode(),
    )
    fake.seed("envs/my-env/snapshots/README", b"ignore me")

    mng = _make_mng([_REMOTE_FTP], fake)
    _, manifests = mng.list_snapshots("my-env", "test-ftp")

    assert len(manifests) == 1
    assert manifests[0].snapshot_id == "snap-a"


# ---------------------------------------------------------------------------
# _resolve_remote
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_resolve_remote_by_name() -> None:
    """_resolve_remote returns the named remote when it exists."""
    mng = _make_mng([_REMOTE_FTP, _REMOTE_SFTP], FakeRemoteBackend())
    result = mng._resolve_remote("test-sftp")
    assert result.name == "test-sftp"


@pytest.mark.remote
def test_resolve_remote_default() -> None:
    """_resolve_remote falls back to the default remote when name is None."""
    mng = _make_mng([_REMOTE_FTP, _REMOTE_DEFAULT], FakeRemoteBackend())
    result = mng._resolve_remote(None)
    assert result.name == "default-remote"


@pytest.mark.remote
def test_resolve_remote_raises_when_no_remotes() -> None:
    """_resolve_remote raises UsageError when no remotes are configured."""
    mng = _make_mng([], FakeRemoteBackend())
    with pytest.raises(click.UsageError, match="No remotes configured"):
        mng._resolve_remote(None)


@pytest.mark.remote
def test_resolve_remote_raises_when_no_default() -> None:
    """_resolve_remote raises UsageError when remotes exist but none is default."""
    mng = _make_mng([_REMOTE_FTP], FakeRemoteBackend())
    with pytest.raises(click.UsageError, match="No default remote"):
        mng._resolve_remote(None)


@pytest.mark.remote
def test_resolve_remote_raises_when_name_unknown() -> None:
    """_resolve_remote raises UsageError for an unknown remote name."""
    mng = _make_mng([_REMOTE_FTP], FakeRemoteBackend())
    with pytest.raises(click.UsageError, match="not configured"):
        mng._resolve_remote("does-not-exist")


# ---------------------------------------------------------------------------
# _build_backend
# ---------------------------------------------------------------------------


def _mng() -> RemoteMng:
    """Return a bare RemoteMng with a no-op configMng."""
    return RemoteMng(MagicMock())


@pytest.mark.remote
def test_build_backend_ftp_default_port() -> None:
    """FTP backend receives port 21 when none is specified."""
    cfg = RemoteCfg(
        name="r",
        type="ftp",
        host="ftp.example.com",
        user="u",
        password="p",
        root_path="/shpd",
    )
    with patch("remote.remote_mng.FTPBackend") as MockFTP:
        _mng()._build_backend(cfg)
    MockFTP.assert_called_once_with(
        host="ftp.example.com",
        port=21,
        user="u",
        password="p",
        root_path="/shpd",
    )


@pytest.mark.remote
def test_build_backend_ftp_explicit_port() -> None:
    """FTP backend forwards an explicit port unchanged."""
    cfg = RemoteCfg(
        name="r",
        type="ftp",
        host="ftp.example.com",
        port=2121,
        user="u",
        password="p",
        root_path="/shpd",
    )
    with patch("remote.remote_mng.FTPBackend") as MockFTP:
        _mng()._build_backend(cfg)
    MockFTP.assert_called_once_with(
        host="ftp.example.com",
        port=2121,
        user="u",
        password="p",
        root_path="/shpd",
    )


@pytest.mark.remote
def test_build_backend_sftp_default_port() -> None:
    """SFTP backend receives port 22 when none is specified."""
    cfg = RemoteCfg(
        name="r",
        type="sftp",
        host="sftp.example.com",
        user="u",
        root_path="/shpd",
    )
    with patch("remote.remote_mng.SFTPBackend") as MockSFTP:
        _mng()._build_backend(cfg)
    MockSFTP.assert_called_once_with(
        host="sftp.example.com",
        port=22,
        user="u",
        password=None,
        identity_file=None,
        root_path="/shpd",
    )


@pytest.mark.remote
def test_build_backend_sftp_with_identity_file() -> None:
    """SFTP backend forwards identity_file when provided."""
    cfg = RemoteCfg(
        name="r",
        type="sftp",
        host="sftp.example.com",
        port=2222,
        user="u",
        identity_file="/home/u/.ssh/id_ed25519",
        root_path="/shpd",
    )
    with patch("remote.remote_mng.SFTPBackend") as MockSFTP:
        _mng()._build_backend(cfg)
    MockSFTP.assert_called_once_with(
        host="sftp.example.com",
        port=2222,
        user="u",
        password=None,
        identity_file="/home/u/.ssh/id_ed25519",
        root_path="/shpd",
    )


@pytest.mark.remote
def test_build_backend_unknown_type_raises() -> None:
    """An unrecognised type string raises click.UsageError."""
    cfg = RemoteCfg(
        name="r",
        type="s3",
        host="s3.example.com",
        user="u",
        root_path="/shpd",
    )
    with pytest.raises(click.UsageError, match="Unknown remote type"):
        _mng()._build_backend(cfg)


@pytest.mark.remote
def test_build_backend_does_not_mutate_original_cfg() -> None:
    """_build_backend must not modify the RemoteCfg it receives."""
    cfg = RemoteCfg(
        name="r",
        type="ftp",
        host="ftp.example.com",
        user="u",
        password="p",
        root_path="/shpd",
    )
    resolved_before = cfg.is_resolved()
    with patch("remote.remote_mng.FTPBackend"):
        _mng()._build_backend(cfg)
    assert cfg.is_resolved() == resolved_before
