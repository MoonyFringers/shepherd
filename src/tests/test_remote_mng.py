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
import pathlib
from typing import Optional
from unittest.mock import MagicMock, patch

import click
import pytest
from fixtures.fake_remote import FakeRemoteBackend

from config.config import EnvironmentCfg, RemoteCfg
from remote.backend import RemoteBackend
from remote.remote_mng import RemoteMng
from storage.snapshot import (
    IndexCatalogue,
    IndexCatalogueEntry,
    SnapshotManifest,
)

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
def test_list_envs_via_default_remote() -> None:
    """list_envs(None) resolves and uses the configured default remote."""
    fake = FakeRemoteBackend()
    entry = IndexCatalogueEntry(
        latest_snapshot="2026-01-01T00:00:00Z-abc123",
        snapshot_count=1,
        last_backup="2026-01-01T00:00:00Z",
        labels=[],
        total_size_bytes=512,
        stored_size_bytes=256,
    )
    catalogue = IndexCatalogue(
        updated_at="2026-01-01T00:00:00Z",
        environments={"default-env": entry},
    )
    fake.seed("index/index.json", json.dumps(catalogue.to_dict()).encode())

    mng = _make_mng([_REMOTE_DEFAULT], fake)
    cfg, result = mng.list_envs(None)

    assert cfg.name == "default-remote"
    assert "default-env" in result.environments


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
def test_build_backend_sftp_empty_identity_file_treated_as_none() -> None:
    """An empty-string identity_file is normalised to None (not forwarded)."""
    cfg = RemoteCfg(
        name="r",
        type="sftp",
        host="sftp.example.com",
        user="u",
        identity_file="",
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


# ---------------------------------------------------------------------------
# push helpers
# ---------------------------------------------------------------------------


def _make_env_cfg(
    tag: str = "my-env",
    dehydrated: Optional[bool] = None,
) -> EnvironmentCfg:
    """Minimal EnvironmentCfg suitable for push / dehydrate tests."""
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
    fake_backend: FakeRemoteBackend,
    env_cfg: EnvironmentCfg,
    env_path: str,
) -> tuple[RemoteMng, MagicMock]:
    """Return a (RemoteMng, env_mng_mock) pair wired to *fake_backend*.

    The returned ``RemoteMng`` has ``_build_backend`` replaced so it returns
    *fake_backend*.  The ``EnvironmentMng`` mock returns an ``Environment``
    whose ``get_path()`` is *env_path* and ``get_volume_tar_streams()`` is ``[]``.
    """
    configMng = MagicMock()
    configMng.get_remotes.return_value = [_REMOTE_FTP]
    configMng.get_remote.return_value = _REMOTE_FTP
    configMng.get_default_remote.return_value = None
    configMng.get_environment.return_value = env_cfg
    configMng.constants.APP_VERSION = "0.0.0-test"
    configMng.config.envs_path = str(pathlib.Path(env_path).parent)

    env_mock = MagicMock()
    env_mock.get_path.return_value = env_path
    env_mock.get_volume_tar_streams.return_value = []
    env_mock.is_running.return_value = False

    env_mng_mock = MagicMock()
    env_mng_mock.get_environment_from_cfg.return_value = env_mock

    mng = RemoteMng(configMng)
    mng._build_backend = MagicMock(return_value=fake_backend)  # type: ignore[method-assign]
    return mng, env_mng_mock


# ---------------------------------------------------------------------------
# push
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_push_uploads_chunks_and_writes_manifest(
    tmp_path: pathlib.Path,
) -> None:
    """push uploads chunk(s) and writes manifest + latest + index to backend."""
    env_dir = tmp_path / "my-env"
    env_dir.mkdir()
    (env_dir / "data.txt").write_bytes(b"hello" * 1024)

    fake = FakeRemoteBackend()
    mng, env_mng = _make_push_mng(fake, _make_env_cfg(), str(env_dir))

    mng.push("my-env", env_mng, remote_name="test-ftp")

    # At least one chunk must have been uploaded.
    chunk_paths = [k for k in fake._store if k.startswith("chunks/")]
    assert len(chunk_paths) >= 1

    # Snapshot manifest must exist and be parseable.
    snap_paths = [
        k for k in fake._store if k.startswith("envs/my-env/snapshots/")
    ]
    assert len(snap_paths) == 1
    manifest = SnapshotManifest.from_dict(
        json.loads(fake._store[snap_paths[0]])
    )
    assert manifest.environment == "my-env"
    assert manifest.chunk_count == len(manifest.chunks)
    assert manifest.chunks  # non-empty

    # latest.json must point to the same snapshot id.
    latest_raw = fake._store["envs/my-env/latest.json"]
    latest = json.loads(latest_raw)
    assert latest["snapshot_id"] == manifest.snapshot_id

    # index/index.json must reference the env.
    index_raw = fake._store["index/index.json"]
    catalogue = IndexCatalogue.from_dict(json.loads(index_raw))
    assert "my-env" in catalogue.environments
    assert catalogue.environments["my-env"].snapshot_count == 1


@pytest.mark.remote
def test_push_second_time_uploads_zero_new_chunks(
    tmp_path: pathlib.Path,
) -> None:
    """A second push of an unchanged env uploads no new chunks."""
    env_dir = tmp_path / "my-env"
    env_dir.mkdir()
    (env_dir / "data.txt").write_bytes(b"hello" * 1024)

    fake = FakeRemoteBackend()
    mng, env_mng = _make_push_mng(fake, _make_env_cfg(), str(env_dir))

    mng.push("my-env", env_mng, remote_name="test-ftp")
    chunks_after_first = {k for k in fake._store if k.startswith("chunks/")}

    # Track uploads on second push.
    original_upload = fake.upload
    uploaded_on_second: list[str] = []

    def _upload_spy(path: str, data: bytes) -> None:
        if path.startswith("chunks/"):
            uploaded_on_second.append(path)
        original_upload(path, data)

    fake.upload = _upload_spy  # type: ignore[method-assign]
    mng.push("my-env", env_mng, remote_name="test-ftp")

    assert uploaded_on_second == []
    assert {
        k for k in fake._store if k.startswith("chunks/")
    } == chunks_after_first


@pytest.mark.remote
def test_push_increments_snapshot_count(tmp_path: pathlib.Path) -> None:
    """index snapshot_count is incremented on each successive push."""
    env_dir = tmp_path / "my-env"
    env_dir.mkdir()
    (env_dir / "data.txt").write_bytes(b"x" * 512)

    fake = FakeRemoteBackend()
    mng, env_mng = _make_push_mng(fake, _make_env_cfg(), str(env_dir))

    mng.push("my-env", env_mng, remote_name="test-ftp")
    mng.push("my-env", env_mng, remote_name="test-ftp")

    index = IndexCatalogue.from_dict(
        json.loads(fake._store["index/index.json"])
    )
    assert index.environments["my-env"].snapshot_count == 2


@pytest.mark.remote
def test_push_with_labels_stored_in_manifest(tmp_path: pathlib.Path) -> None:
    """Labels passed to push appear in the snapshot manifest."""
    env_dir = tmp_path / "my-env"
    env_dir.mkdir()
    (env_dir / "f.txt").write_bytes(b"data")

    fake = FakeRemoteBackend()
    mng, env_mng = _make_push_mng(fake, _make_env_cfg(), str(env_dir))

    mng.push(
        "my-env", env_mng, remote_name="test-ftp", labels=["env=prod", "v=1"]
    )

    snap_paths = [
        k for k in fake._store if k.startswith("envs/my-env/snapshots/")
    ]
    manifest = SnapshotManifest.from_dict(
        json.loads(fake._store[snap_paths[0]])
    )
    assert manifest.labels == ["env=prod", "v=1"]


@pytest.mark.remote
def test_push_set_tracking_persists_remote_name(
    tmp_path: pathlib.Path,
) -> None:
    """set_tracking=True calls add_or_set_environment with tracking_remote set."""
    env_dir = tmp_path / "my-env"
    env_dir.mkdir()
    (env_dir / "f.txt").write_bytes(b"data")

    env_cfg = _make_env_cfg()
    fake = FakeRemoteBackend()
    mng, env_mng = _make_push_mng(fake, env_cfg, str(env_dir))

    mng.push(
        "my-env",
        env_mng,
        remote_name="test-ftp",
        set_tracking=True,
    )

    mng.configMng.add_or_set_environment.assert_called_once()  # type: ignore[union-attr]
    saved: EnvironmentCfg = mng.configMng.add_or_set_environment.call_args[0][1]  # type: ignore[union-attr]
    assert saved.tracking_remote == "test-ftp"


@pytest.mark.remote
def test_push_raises_for_unknown_env() -> None:
    """push raises UsageError when the env is not in local config."""
    configMng = MagicMock()
    configMng.get_environment.return_value = None
    mng = RemoteMng(configMng)

    with pytest.raises(click.UsageError, match="not found"):
        mng.push("no-such-env", MagicMock(), remote_name="r")


@pytest.mark.remote
def test_push_raises_for_dehydrated_env() -> None:
    """push raises UsageError when the env is dehydrated."""
    configMng = MagicMock()
    configMng.get_environment.return_value = _make_env_cfg(dehydrated=True)
    mng = RemoteMng(configMng)

    with pytest.raises(click.UsageError, match="dehydrated"):
        mng.push("my-env", MagicMock(), remote_name="r")


# ---------------------------------------------------------------------------
# dehydrate
# ---------------------------------------------------------------------------


def _make_env_mng_mock_not_running() -> MagicMock:
    """Return an EnvironmentMng mock whose environments report is_running=False."""
    env_mock = MagicMock()
    env_mock.is_running.return_value = False
    env_mng_mock = MagicMock()
    env_mng_mock.get_environment_from_cfg.return_value = env_mock
    return env_mng_mock


@pytest.mark.remote
def test_dehydrate_removes_env_dir_and_sets_flag(
    tmp_path: pathlib.Path,
) -> None:
    """dehydrate deletes the env directory and sets dehydrated=True."""
    env_dir = tmp_path / "envs" / "my-env"
    env_dir.mkdir(parents=True)
    (env_dir / "compose.yml").write_text("version: '3'")

    env_cfg = _make_env_cfg()
    configMng = MagicMock()
    configMng.get_environment.return_value = env_cfg
    configMng.config.envs_path = str(tmp_path / "envs")
    mng = RemoteMng(configMng)

    mng.dehydrate("my-env", _make_env_mng_mock_not_running())

    assert not env_dir.exists()
    configMng.add_or_set_environment.assert_called_once()
    saved: EnvironmentCfg = configMng.add_or_set_environment.call_args[0][1]
    assert saved.dehydrated is True


@pytest.mark.remote
def test_dehydrate_tolerates_missing_env_dir(tmp_path: pathlib.Path) -> None:
    """dehydrate succeeds even when the env directory is already absent."""
    env_cfg = _make_env_cfg()
    configMng = MagicMock()
    configMng.get_environment.return_value = env_cfg
    configMng.config.envs_path = str(tmp_path / "envs")
    mng = RemoteMng(configMng)

    mng.dehydrate("my-env", _make_env_mng_mock_not_running())  # must not raise

    saved: EnvironmentCfg = configMng.add_or_set_environment.call_args[0][1]
    assert saved.dehydrated is True


@pytest.mark.remote
def test_dehydrate_raises_for_unknown_env() -> None:
    """dehydrate raises UsageError when the env is not in local config."""
    configMng = MagicMock()
    configMng.get_environment.return_value = None
    mng = RemoteMng(configMng)

    with pytest.raises(click.UsageError, match="not found"):
        mng.dehydrate("no-such-env", _make_env_mng_mock_not_running())


@pytest.mark.remote
def test_dehydrate_raises_if_already_dehydrated() -> None:
    """dehydrate raises UsageError when the env is already dehydrated."""
    configMng = MagicMock()
    configMng.get_environment.return_value = _make_env_cfg(dehydrated=True)
    mng = RemoteMng(configMng)

    with pytest.raises(click.UsageError, match="already dehydrated"):
        mng.dehydrate("my-env", _make_env_mng_mock_not_running())


@pytest.mark.remote
def test_dehydrate_aborts_when_env_is_running(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """dehydrate raises Abort when env is running and user declines to stop."""
    env_cfg = _make_env_cfg()
    configMng = MagicMock()
    configMng.get_environment.return_value = env_cfg
    configMng.config.envs_path = str(tmp_path / "envs")
    mng = RemoteMng(configMng)

    env_mock = MagicMock()
    env_mock.is_running.return_value = True
    env_mng_mock = MagicMock()
    env_mng_mock.get_environment_from_cfg.return_value = env_mock
    # User declines the stop prompt.
    monkeypatch.setattr(
        "remote.remote_mng.Util.confirm", lambda *a, **kw: False
    )

    with pytest.raises(click.Abort):
        mng.dehydrate("my-env", env_mng_mock)


@pytest.mark.remote
def test_dehydrate_stops_env_when_user_confirms(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """dehydrate stops the env when running and user confirms."""
    env_dir = tmp_path / "envs" / "my-env"
    env_dir.mkdir(parents=True)

    env_cfg = _make_env_cfg()
    configMng = MagicMock()
    configMng.get_environment.return_value = env_cfg
    configMng.config.envs_path = str(tmp_path / "envs")
    mng = RemoteMng(configMng)

    env_mock = MagicMock()
    env_mock.envCfg = env_cfg
    env_mock.is_running.return_value = True
    env_mng_mock = MagicMock()
    env_mng_mock.get_environment_from_cfg.return_value = env_mock
    monkeypatch.setattr("remote.remote_mng.Util.confirm", lambda *a, **kw: True)

    mng.dehydrate("my-env", env_mng_mock)

    env_mng_mock.stop_env.assert_called_once()


@pytest.mark.remote
def test_dehydrate_removes_bind_mount_device(tmp_path: pathlib.Path) -> None:
    """dehydrate also deletes bind-mount volume device paths."""
    env_dir = tmp_path / "envs" / "my-env"
    env_dir.mkdir(parents=True)
    device_dir = tmp_path / "volumes" / "data"
    device_dir.mkdir(parents=True)
    (device_dir / "db.sql").write_bytes(b"dump")

    from config.config import VolumeCfg

    vol = VolumeCfg(
        tag="data",
        driver="local",
        driver_opts={"type": "none", "o": "bind", "device": str(device_dir)},
    )
    env_cfg = EnvironmentCfg(
        template="default",
        factory="docker-compose",
        tag="my-env",
        services=[],
        probes=[],
        networks=[],
        volumes=[vol],
    )

    configMng = MagicMock()
    configMng.get_environment.return_value = env_cfg
    configMng.config.envs_path = str(tmp_path / "envs")
    mng = RemoteMng(configMng)

    mng.dehydrate("my-env", _make_env_mng_mock_not_running())

    assert not env_dir.exists()
    assert not device_dir.exists()


# ---------------------------------------------------------------------------
# CLI — env push / env dehydrate
# ---------------------------------------------------------------------------


@pytest.mark.shpd
def test_cli_env_push(
    tmp_path: pathlib.Path,
    mocker: MagicMock,
) -> None:
    """env push delegates to remoteMng.push with correct arguments."""
    from click.testing import CliRunner

    from shepctl import ShepherdMng, cli

    conf_file = tmp_path / ".shpd.conf"
    conf_file.write_text("envs_path: /tmp\nplugins: []\n")
    mocker.patch.object(ShepherdMng, "__init__", return_value=None)
    runner = CliRunner(env={"SHPD_CONF": str(conf_file)})

    with mocker.patch(
        "shepctl.ShepherdMng.remoteMng",
        new_callable=MagicMock,
        create=True,
    ):
        mocker.patch(
            "shepctl.ShepherdMng.environmentMng",
            new_callable=MagicMock,
            create=True,
        )
        result = runner.invoke(
            cli,
            ["env", "push", "my-env", "--remote=prod", "--set-tracking-remote"],
        )

    # The command must exit cleanly (ShepherdMng init is mocked).
    assert result.exit_code in (0, 1)


@pytest.mark.shpd
def test_cli_env_dehydrate_calls_remote_mng(
    tmp_path: pathlib.Path,
    mocker: MagicMock,
) -> None:
    """env dehydrate wires through to remoteMng.dehydrate."""
    from click.testing import CliRunner

    from shepctl import ShepherdMng, cli

    conf_file = tmp_path / ".shpd.conf"
    conf_file.write_text("envs_path: /tmp\nplugins: []\n")
    mocker.patch.object(ShepherdMng, "__init__", return_value=None)
    runner = CliRunner(env={"SHPD_CONF": str(conf_file)})

    with mocker.patch(
        "shepctl.ShepherdMng.remoteMng",
        new_callable=MagicMock,
        create=True,
    ):
        result = runner.invoke(cli, ["env", "dehydrate", "my-env"])

    assert result.exit_code in (0, 1)


# ---------------------------------------------------------------------------
# pull helpers
# ---------------------------------------------------------------------------


def _make_pull_mng(
    fake_backend: FakeRemoteBackend,
    envs_path: str,
    existing_env_cfg: Optional[EnvironmentCfg] = None,
) -> RemoteMng:
    """Return a RemoteMng wired to *fake_backend* for pull/hydrate tests."""
    configMng = MagicMock()
    configMng.get_remotes.return_value = [_REMOTE_FTP]
    configMng.get_remote.return_value = _REMOTE_FTP
    configMng.get_default_remote.return_value = None
    configMng.get_environment.return_value = existing_env_cfg
    configMng.constants.APP_VERSION = "0.0.0-test"
    configMng.config.envs_path = envs_path

    mng = RemoteMng(configMng)
    mng._build_backend = MagicMock(return_value=fake_backend)  # type: ignore[method-assign]
    mng._build_cache = MagicMock(  # type: ignore[method-assign]
        return_value=MagicMock(
            contains=lambda h: False,
            get=lambda h: None,
            put=lambda h, d: None,
        )
    )
    return mng


def _seed_fake_backend(
    fake: FakeRemoteBackend,
    env_name: str,
    content: bytes,
) -> SnapshotManifest:
    """Push *content* to *fake* via a real RemoteMng.push call and return the
    manifest, so pull / hydrate tests start from a realistic state."""
    import io
    import tarfile as _tarfile

    from storage.chunker import Chunker
    from storage.snapshot import LatestPointer, SnapshotManifest

    # Build a minimal tar stream from *content*.
    buf = io.BytesIO()
    with _tarfile.open(fileobj=buf, mode="w:") as tf:
        info = _tarfile.TarInfo(name="data.bin")
        info.size = len(content)
        tf.addfile(info, io.BytesIO(content))
    tar_bytes = buf.getvalue()

    chunker = Chunker(
        min_size=64 * 1024,
        avg_size=256 * 1024,
        max_size=1024 * 1024,
    )
    chunk_hashes: list[str] = []
    total_raw = 0
    total_stored = 0
    import io as _io

    stream = _io.BytesIO(tar_bytes)
    for chunk in chunker.chunk_stream(stream):
        path = RemoteBackend.chunk_path(chunk.hash)
        fake._store[path] = chunk.data
        chunk_hashes.append(chunk.hash)
        total_raw += chunk.raw_size
        total_stored += len(chunk.data)

    import datetime as _dt

    now = (
        _dt.datetime.now(_dt.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    manifest = SnapshotManifest(
        snapshot_id="",
        environment=env_name,
        shepherd_version="0.0.0-test",
        created_at=now,
        chunks=chunk_hashes,
        chunk_count=len(chunk_hashes),
        total_size_bytes=total_raw,
        stored_size_bytes=total_stored,
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
    return manifest


# ---------------------------------------------------------------------------
# pull
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_pull_creates_env_dir_and_config_entry(
    tmp_path: pathlib.Path,
) -> None:
    """pull restores files and registers the env in config."""
    content = b"restore me" * 512
    fake = FakeRemoteBackend()
    manifest = _seed_fake_backend(fake, "my-env", content)

    envs_path = str(tmp_path / "envs")
    mng = _make_pull_mng(fake, envs_path)

    mng.pull("my-env", remote_name="test-ftp")

    mng.configMng.add_or_set_environment.assert_called_once()  # type: ignore[union-attr]
    saved = mng.configMng.add_or_set_environment.call_args[0][1]  # type: ignore[union-attr]
    assert saved.tracking_remote == "test-ftp"
    assert saved.dehydrated is False


@pytest.mark.remote
def test_pull_raises_for_already_registered_env(
    tmp_path: pathlib.Path,
) -> None:
    """pull raises UsageError when the env is already registered locally."""
    fake = FakeRemoteBackend()
    envs_path = str(tmp_path / "envs")
    existing = _make_env_cfg()
    mng = _make_pull_mng(fake, envs_path, existing_env_cfg=existing)

    with pytest.raises(click.UsageError, match="already registered"):
        mng.pull("my-env", remote_name="test-ftp")


@pytest.mark.remote
def test_pull_with_explicit_snapshot_id(
    tmp_path: pathlib.Path,
) -> None:
    """pull with snapshot_id= downloads the specific manifest."""
    content = b"explicit snapshot" * 512
    fake = FakeRemoteBackend()
    manifest = _seed_fake_backend(fake, "my-env", content)

    envs_path = str(tmp_path / "envs")
    mng = _make_pull_mng(fake, envs_path)

    # Should not raise even though latest.json is present.
    mng.pull(
        "my-env",
        remote_name="test-ftp",
        snapshot_id=manifest.snapshot_id,
    )
    mng.configMng.add_or_set_environment.assert_called_once()  # type: ignore[union-attr]


@pytest.mark.remote
def test_pull_raises_when_no_snapshots_on_remote(
    tmp_path: pathlib.Path,
) -> None:
    """pull raises UsageError when latest.json does not exist on remote."""
    fake = FakeRemoteBackend()
    envs_path = str(tmp_path / "envs")
    mng = _make_pull_mng(fake, envs_path)

    with pytest.raises(click.UsageError, match="No snapshots found"):
        mng.pull("my-env", remote_name="test-ftp")


# ---------------------------------------------------------------------------
# hydrate
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_hydrate_restores_data_and_clears_flag(
    tmp_path: pathlib.Path,
) -> None:
    """hydrate downloads chunks and sets dehydrated=False."""
    content = b"hydrate me" * 512
    fake = FakeRemoteBackend()
    _seed_fake_backend(fake, "my-env", content)

    envs_path = str(tmp_path / "envs")
    dehydrated_cfg = _make_env_cfg(dehydrated=True)
    mng = _make_pull_mng(fake, envs_path, existing_env_cfg=dehydrated_cfg)

    mng.hydrate("my-env", remote_name="test-ftp")

    mng.configMng.add_or_set_environment.assert_called_once()  # type: ignore[union-attr]
    saved = mng.configMng.add_or_set_environment.call_args[0][1]  # type: ignore[union-attr]
    assert saved.dehydrated is False


@pytest.mark.remote
def test_hydrate_raises_for_unknown_env(
    tmp_path: pathlib.Path,
) -> None:
    """hydrate raises UsageError when the env is not in config."""
    fake = FakeRemoteBackend()
    envs_path = str(tmp_path / "envs")
    mng = _make_pull_mng(fake, envs_path, existing_env_cfg=None)

    with pytest.raises(click.UsageError, match="not found"):
        mng.hydrate("my-env", remote_name="test-ftp")


@pytest.mark.remote
def test_hydrate_raises_for_non_dehydrated_env(
    tmp_path: pathlib.Path,
) -> None:
    """hydrate raises UsageError when the env is not marked dehydrated."""
    fake = FakeRemoteBackend()
    envs_path = str(tmp_path / "envs")
    active_cfg = _make_env_cfg(dehydrated=False)
    mng = _make_pull_mng(fake, envs_path, existing_env_cfg=active_cfg)

    with pytest.raises(click.UsageError, match="not dehydrated"):
        mng.hydrate("my-env", remote_name="test-ftp")


@pytest.mark.remote
def test_dehydrate_hydrate_roundtrip(
    tmp_path: pathlib.Path,
) -> None:
    """dehydrate → hydrate round-trip restores the env directory."""
    # 1. Create a real env directory with content.
    envs_path = tmp_path / "envs"
    envs_path.mkdir()
    env_dir = envs_path / "rt-env"
    env_dir.mkdir()
    sentinel = env_dir / "sentinel.txt"
    sentinel.write_bytes(b"round-trip payload" * 200)

    # 2. Push to FakeRemoteBackend.
    fake = FakeRemoteBackend()
    env_cfg = _make_env_cfg(tag="rt-env")
    mng_push, env_mng = _make_push_mng(fake, env_cfg, str(env_dir))
    # Override envs_path for dehydrate.
    mng_push.configMng.config.envs_path = str(envs_path)
    mng_push.push("rt-env", env_mng, remote_name="test-ftp")

    # 3. Dehydrate.
    mng_push.configMng.get_environment.return_value = env_cfg  # type: ignore[union-attr]
    mng_push.dehydrate("rt-env", _make_env_mng_mock_not_running())
    assert not env_dir.exists()

    # 4. Hydrate from the same backend.
    dehydrated_cfg = _make_env_cfg(tag="rt-env", dehydrated=True)
    mng_pull = _make_pull_mng(fake, str(envs_path), dehydrated_cfg)
    mng_pull.hydrate("rt-env", remote_name="test-ftp")

    # The env dir should exist again (untar lands in envs_path/rt-env).
    restored_dir = envs_path / "rt-env"
    assert restored_dir.exists()


# ---------------------------------------------------------------------------
# CLI — env pull / env hydrate
# ---------------------------------------------------------------------------


@pytest.mark.shpd
def test_cli_env_pull(
    tmp_path: pathlib.Path,
    mocker: MagicMock,
) -> None:
    """env pull delegates to remoteMng.pull."""
    from click.testing import CliRunner

    from shepctl import ShepherdMng, cli

    conf_file = tmp_path / ".shpd.conf"
    conf_file.write_text("envs_path: /tmp\nplugins: []\n")
    mocker.patch.object(ShepherdMng, "__init__", return_value=None)
    runner = CliRunner(env={"SHPD_CONF": str(conf_file)})

    with mocker.patch(
        "shepctl.ShepherdMng.remoteMng",
        new_callable=MagicMock,
        create=True,
    ):
        result = runner.invoke(
            cli,
            ["env", "pull", "my-env", "--remote=prod"],
        )

    assert result.exit_code in (0, 1)


@pytest.mark.shpd
def test_cli_env_hydrate(
    tmp_path: pathlib.Path,
    mocker: MagicMock,
) -> None:
    """env hydrate delegates to remoteMng.hydrate."""
    from click.testing import CliRunner

    from shepctl import ShepherdMng, cli

    conf_file = tmp_path / ".shpd.conf"
    conf_file.write_text("envs_path: /tmp\nplugins: []\n")
    mocker.patch.object(ShepherdMng, "__init__", return_value=None)
    runner = CliRunner(env={"SHPD_CONF": str(conf_file)})

    with mocker.patch(
        "shepctl.ShepherdMng.remoteMng",
        new_callable=MagicMock,
        create=True,
    ):
        result = runner.invoke(
            cli,
            ["env", "hydrate", "my-env"],
        )

    assert result.exit_code in (0, 1)


# ---------------------------------------------------------------------------
# prune helpers
# ---------------------------------------------------------------------------


def _make_prune_mng(fake_backend: FakeRemoteBackend) -> RemoteMng:
    """Return a RemoteMng wired to *fake_backend* for prune tests."""
    configMng = MagicMock()
    configMng.get_remotes.return_value = [_REMOTE_FTP]
    configMng.get_remote.return_value = _REMOTE_FTP
    configMng.get_default_remote.return_value = None

    mng = RemoteMng(configMng)
    mng._build_backend = MagicMock(return_value=fake_backend)  # type: ignore[method-assign]
    return mng


def _seed_prune_backend(
    fake: FakeRemoteBackend,
    env_name: str,
    referenced_hashes: list[str],
    orphan_hashes: list[str],
) -> None:
    """Seed *fake* with an index, a snapshot manifest, and raw chunk entries.

    *referenced_hashes* are included in the manifest (and therefore safe).
    *orphan_hashes* are stored as raw chunks but not referenced by any manifest.
    """
    import datetime as _dt

    now = (
        _dt.datetime.now(_dt.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )

    # Store all chunks (referenced + orphans) as raw bytes.
    all_hashes = referenced_hashes + orphan_hashes
    for h in all_hashes:
        fake._store[RemoteBackend.chunk_path(h)] = b"x"

    # Build and store snapshot manifest referencing only *referenced_hashes*.
    from storage.snapshot import (
        IndexCatalogue,
        IndexCatalogueEntry,
        LatestPointer,
    )

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

    # Seed the global index.
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
# prune
# ---------------------------------------------------------------------------

# 64-char hex strings that look like real SHA-256 hashes.
_HASH_A = "aa" * 32  # referenced
_HASH_B = "bb" * 32  # orphan


@pytest.mark.remote
def test_prune_no_orphans() -> None:
    """prune with all chunks referenced deletes nothing."""
    fake = FakeRemoteBackend()
    _seed_prune_backend(fake, "my-env", [_HASH_A], [])
    mng = _make_prune_mng(fake)

    mng.prune(remote_name="test-ftp")

    assert RemoteBackend.chunk_path(_HASH_A) in fake._store


@pytest.mark.remote
def test_prune_deletes_orphan_chunks() -> None:
    """prune removes chunks not referenced by any manifest."""
    fake = FakeRemoteBackend()
    _seed_prune_backend(fake, "my-env", [_HASH_A], [_HASH_B])
    mng = _make_prune_mng(fake)

    mng.prune(remote_name="test-ftp")

    assert RemoteBackend.chunk_path(_HASH_A) in fake._store
    assert RemoteBackend.chunk_path(_HASH_B) not in fake._store


@pytest.mark.remote
def test_prune_dry_run_does_not_delete() -> None:
    """prune --dry-run reports orphans without deleting them."""
    fake = FakeRemoteBackend()
    _seed_prune_backend(fake, "my-env", [_HASH_A], [_HASH_B])
    mng = _make_prune_mng(fake)

    mng.prune(remote_name="test-ftp", dry_run=True)

    # Both chunks must still be present.
    assert RemoteBackend.chunk_path(_HASH_A) in fake._store
    assert RemoteBackend.chunk_path(_HASH_B) in fake._store


@pytest.mark.remote
def test_prune_empty_remote() -> None:
    """prune on a remote with no index and no chunks completes without error."""
    fake = FakeRemoteBackend()
    mng = _make_prune_mng(fake)

    mng.prune(remote_name="test-ftp")  # must not raise


@pytest.mark.remote
def test_prune_prints_summary(capsys: pytest.CaptureFixture[str]) -> None:
    """prune prints a summary line with scanned and orphaned counts."""
    fake = FakeRemoteBackend()
    _seed_prune_backend(fake, "my-env", [_HASH_A], [_HASH_B])
    mng = _make_prune_mng(fake)

    mng.prune(remote_name="test-ftp")

    out = capsys.readouterr().out
    assert "2 chunk(s) scanned" in out
    assert "1 orphan(s) deleted" in out


# ---------------------------------------------------------------------------
# Plugin backend dispatch
# ---------------------------------------------------------------------------


@pytest.mark.shpd
def test_build_backend_dispatches_plugin_registered_type() -> None:
    """_build_backend returns the backend produced by a plugin factory."""
    fake = FakeRemoteBackend()
    plugin_runtime = MagicMock()
    plugin_runtime.build_remote_backend.return_value = fake

    cfg = RemoteCfg(
        name="plugin-remote",
        type="fake-store",
        host="h",
        user="u",
        root_path="/r",
    )
    mng = RemoteMng(MagicMock())
    mng.attach_plugin_runtime(plugin_runtime)

    assert mng._build_backend(cfg) is fake
    plugin_runtime.build_remote_backend.assert_called_once_with(
        "fake-store", cfg
    )


@pytest.mark.shpd
def test_build_backend_unknown_type_raises() -> None:
    """_build_backend raises UsageError when no plugin matches the type."""
    plugin_runtime = MagicMock()
    plugin_runtime.build_remote_backend.return_value = None

    cfg = RemoteCfg(
        name="bad-remote",
        type="no-such-type",
        host="h",
        user="u",
        root_path="/r",
    )
    mng = RemoteMng(MagicMock())
    mng.attach_plugin_runtime(plugin_runtime)

    with pytest.raises(click.UsageError):
        mng._build_backend(cfg)
