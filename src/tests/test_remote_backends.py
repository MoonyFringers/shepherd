# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

from __future__ import annotations

import ftplib
from unittest.mock import MagicMock, patch

import pytest

from remote import FTPBackend, SFTPBackend

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ROOT = "/shepherd"
_CHUNK_HASH = "ab" + "3f" * 31  # 64-char hex hash, shard "ab"
_CHUNK_PATH = f"chunks/ab/{_CHUNK_HASH}"
_META_PATH = "envs/my-env/latest.json"
_DATA = b"some compressed chunk bytes"


def _make_ftp_backend(mock_ftp: MagicMock, root: str = _ROOT) -> FTPBackend:
    """Construct FTPBackend with a pre-wired mock FTP instance."""
    with patch("remote.ftp_backend.ftplib.FTP", return_value=mock_ftp):
        return FTPBackend("host", root_path=root)


def _make_sftp_backend(
    mock_sftp: MagicMock,
    mock_transport: MagicMock,
    root: str = _ROOT,
) -> SFTPBackend:
    """Construct SFTPBackend with pre-wired mock transport and SFTP client."""
    with (
        patch(
            "remote.sftp_backend.paramiko.Transport",
            return_value=mock_transport,
        ),
        patch(
            "remote.sftp_backend.paramiko.SFTPClient.from_transport",
            return_value=mock_sftp,
        ),
    ):
        return SFTPBackend("host", root_path=root)


# ---------------------------------------------------------------------------
# FTPBackend tests
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_ftp_upload_calls_stor() -> None:
    """upload issues STOR at the correct absolute path."""
    mock_ftp = MagicMock()
    backend = _make_ftp_backend(mock_ftp)
    backend.upload(_CHUNK_PATH, _DATA)
    mock_ftp.storbinary.assert_called_once()
    cmd = mock_ftp.storbinary.call_args[0][0]
    assert cmd == f"STOR {_ROOT}/{_CHUNK_PATH}"


@pytest.mark.remote
def test_ftp_download_returns_data() -> None:
    """download pipes RETR output into a buffer and returns it."""
    mock_ftp = MagicMock()

    def retrbinary_side_effect(cmd: str, callback: object) -> None:
        assert callable(callback)
        callback(_DATA)  # type: ignore[operator]

    mock_ftp.retrbinary.side_effect = retrbinary_side_effect
    backend = _make_ftp_backend(mock_ftp)
    result = backend.download(_META_PATH)
    assert result == _DATA


@pytest.mark.remote
def test_ftp_exists_shard_cache_warms_once() -> None:
    """NLST is called once per shard; subsequent exists() hits the cache."""
    mock_ftp = MagicMock()

    def retrlines_side_effect(cmd: str, callback: object) -> None:
        assert callable(callback)
        if "NLST" in cmd:
            callback(_CHUNK_HASH)  # type: ignore[operator]

    mock_ftp.retrlines.side_effect = retrlines_side_effect
    backend = _make_ftp_backend(mock_ftp)

    assert backend.exists(_CHUNK_PATH) is True
    assert backend.exists(_CHUNK_PATH) is True  # second call
    # NLST was issued only once (warm_shard), not on the second call.
    nlst_calls = [
        c for c in mock_ftp.retrlines.call_args_list if "NLST" in c[0][0]
    ]
    assert len(nlst_calls) == 1


@pytest.mark.remote
def test_ftp_exists_shard_cache_miss() -> None:
    """exists() returns False for a hash not in the NLST result."""
    mock_ftp = MagicMock()
    mock_ftp.retrlines.return_value = None  # NLST yields nothing
    backend = _make_ftp_backend(mock_ftp)
    assert backend.exists(_CHUNK_PATH) is False


@pytest.mark.remote
def test_ftp_exists_non_chunk_uses_size() -> None:
    """Non-chunk paths use SIZE, not NLST."""
    mock_ftp = MagicMock()
    backend = _make_ftp_backend(mock_ftp)
    assert backend.exists(_META_PATH) is True
    mock_ftp.size.assert_called_once_with(f"{_ROOT}/{_META_PATH}")
    mock_ftp.retrlines.assert_not_called()


@pytest.mark.remote
def test_ftp_exists_non_chunk_missing() -> None:
    """SIZE raising error_perm maps to False."""
    mock_ftp = MagicMock()
    mock_ftp.size.side_effect = ftplib.error_perm("550 not found")
    backend = _make_ftp_backend(mock_ftp)
    assert backend.exists(_META_PATH) is False


@pytest.mark.remote
def test_ftp_list_prefix_returns_basenames() -> None:
    """list_prefix strips directory components returned by some FTP servers."""
    mock_ftp = MagicMock()

    def retrlines_side_effect(cmd: str, callback: object) -> None:
        assert callable(callback)
        # Simulate an FTP server that returns full paths in NLST.
        for name in [f"{_ROOT}/chunks/ab/hash1", f"{_ROOT}/chunks/ab/hash2"]:
            callback(name)  # type: ignore[operator]

    mock_ftp.retrlines.side_effect = retrlines_side_effect
    backend = _make_ftp_backend(mock_ftp)
    result = backend.list_prefix("chunks/ab")
    assert result == ["hash1", "hash2"]


@pytest.mark.remote
def test_ftp_list_prefix_empty_on_error() -> None:
    """error_perm from NLST (missing dir) returns an empty list."""
    mock_ftp = MagicMock()
    mock_ftp.retrlines.side_effect = ftplib.error_perm("550 no such dir")
    backend = _make_ftp_backend(mock_ftp)
    assert backend.list_prefix("chunks/zz") == []


@pytest.mark.remote
def test_ftp_delete_ignores_missing() -> None:
    """error_perm from DELETE does not propagate."""
    mock_ftp = MagicMock()
    mock_ftp.delete.side_effect = ftplib.error_perm("550 not found")
    backend = _make_ftp_backend(mock_ftp)
    backend.delete(_CHUNK_PATH)  # must not raise


@pytest.mark.remote
def test_ftp_close_calls_quit() -> None:
    """close() calls quit() on the FTP connection."""
    mock_ftp = MagicMock()
    backend = _make_ftp_backend(mock_ftp)
    backend.close()
    mock_ftp.quit.assert_called_once()


# ---------------------------------------------------------------------------
# SFTPBackend tests
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_sftp_upload_creates_parents() -> None:
    """upload calls mkdir for each path component, then opens for writing."""
    mock_sftp = MagicMock()
    mock_transport = MagicMock()
    backend = _make_sftp_backend(mock_sftp, mock_transport)
    backend.upload(_CHUNK_PATH, _DATA)
    # open("wb") must have been called with the correct absolute path.
    mock_sftp.open.assert_called_once_with(f"{_ROOT}/{_CHUNK_PATH}", "wb")
    # mkdir must have been called at least once (for intermediate dirs).
    assert mock_sftp.mkdir.call_count >= 1


@pytest.mark.remote
def test_sftp_download_returns_data() -> None:
    """download opens "rb", reads, and returns bytes."""
    mock_sftp = MagicMock()
    mock_transport = MagicMock()
    mock_file = MagicMock()
    mock_file.read.return_value = _DATA
    mock_sftp.open.return_value.__enter__ = MagicMock(return_value=mock_file)
    mock_sftp.open.return_value.__exit__ = MagicMock(return_value=False)
    backend = _make_sftp_backend(mock_sftp, mock_transport)
    result = backend.download(_META_PATH)
    assert result == _DATA
    mock_sftp.open.assert_called_once_with(f"{_ROOT}/{_META_PATH}", "rb")


@pytest.mark.remote
def test_sftp_exists_true() -> None:
    """exists() returns True when stat() succeeds."""
    mock_sftp = MagicMock()
    mock_transport = MagicMock()
    backend = _make_sftp_backend(mock_sftp, mock_transport)
    assert backend.exists(_META_PATH) is True
    mock_sftp.stat.assert_called_once_with(f"{_ROOT}/{_META_PATH}")


@pytest.mark.remote
def test_sftp_exists_false_on_missing() -> None:
    """exists() returns False when stat() raises FileNotFoundError."""
    mock_sftp = MagicMock()
    mock_transport = MagicMock()
    mock_sftp.stat.side_effect = FileNotFoundError
    backend = _make_sftp_backend(mock_sftp, mock_transport)
    assert backend.exists(_META_PATH) is False


@pytest.mark.remote
def test_sftp_list_prefix_returns_names() -> None:
    """list_prefix returns the listdir result directly."""
    mock_sftp = MagicMock()
    mock_transport = MagicMock()
    mock_sftp.listdir.return_value = ["hash1", "hash2"]
    backend = _make_sftp_backend(mock_sftp, mock_transport)
    assert backend.list_prefix("chunks/ab") == ["hash1", "hash2"]
    mock_sftp.listdir.assert_called_once_with(f"{_ROOT}/chunks/ab")


@pytest.mark.remote
def test_sftp_list_prefix_empty_on_missing() -> None:
    """FileNotFoundError from listdir (missing dir) returns []."""
    mock_sftp = MagicMock()
    mock_transport = MagicMock()
    mock_sftp.listdir.side_effect = FileNotFoundError
    backend = _make_sftp_backend(mock_sftp, mock_transport)
    assert backend.list_prefix("chunks/zz") == []


@pytest.mark.remote
def test_sftp_delete_ignores_missing() -> None:
    """FileNotFoundError from remove does not propagate."""
    mock_sftp = MagicMock()
    mock_transport = MagicMock()
    mock_sftp.remove.side_effect = FileNotFoundError
    backend = _make_sftp_backend(mock_sftp, mock_transport)
    backend.delete(_CHUNK_PATH)  # must not raise


@pytest.mark.remote
def test_sftp_close_closes_transport() -> None:
    """transport.close() is always called, even if sftp.close() raises."""
    mock_sftp = MagicMock()
    mock_transport = MagicMock()
    mock_sftp.close.side_effect = RuntimeError("channel broken")
    backend = _make_sftp_backend(mock_sftp, mock_transport)
    with pytest.raises(RuntimeError):
        backend.close()
    mock_transport.close.assert_called_once()


# ---------------------------------------------------------------------------
# chunk_tmp_path helper
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_chunk_tmp_path_format() -> None:
    """chunk_tmp_path returns {shard}/{hash}.tmp, differing from chunk_path by .tmp."""
    from remote.backend import RemoteBackend

    h = _CHUNK_HASH
    assert RemoteBackend.chunk_tmp_path(h) == f"chunks/ab/{h}.tmp"
    assert (
        RemoteBackend.chunk_tmp_path(h) == RemoteBackend.chunk_path(h) + ".tmp"
    )


# ---------------------------------------------------------------------------
# FTPBackend — rename
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_ftp_rename_calls_ftp_rename() -> None:
    """rename issues ftp.rename() at the correct absolute paths."""
    mock_ftp = MagicMock()
    backend = _make_ftp_backend(mock_ftp)
    src = f"chunks/ab/{_CHUNK_HASH}.tmp"
    dst = _CHUNK_PATH
    backend.rename(src, dst)
    mock_ftp.rename.assert_called_once_with(f"{_ROOT}/{src}", f"{_ROOT}/{dst}")


@pytest.mark.remote
def test_ftp_rename_updates_shard_cache() -> None:
    """rename removes the .tmp name and inserts the final name in the shard cache."""
    mock_ftp = MagicMock()

    def retrlines_side_effect(cmd: str, callback: object) -> None:
        if "NLST" in cmd:
            callback(f"{_CHUNK_HASH}.tmp")  # type: ignore[operator]

    mock_ftp.retrlines.side_effect = retrlines_side_effect
    backend = _make_ftp_backend(mock_ftp)

    # Warm the shard cache.
    backend.exists(f"chunks/ab/{_CHUNK_HASH}.tmp")

    backend.rename(f"chunks/ab/{_CHUNK_HASH}.tmp", _CHUNK_PATH)

    shard = backend._shard_cache.get("ab", set())
    assert f"{_CHUNK_HASH}.tmp" not in shard
    assert _CHUNK_HASH in shard


@pytest.mark.remote
def test_ftp_rename_cold_cache_does_not_raise() -> None:
    """rename succeeds and leaves the cache untouched when the shard is not warmed."""
    mock_ftp = MagicMock()
    backend = _make_ftp_backend(mock_ftp)

    # Shard "ab" is deliberately NOT warmed before the rename.
    assert "ab" not in backend._shard_cache

    backend.rename(f"chunks/ab/{_CHUNK_HASH}.tmp", _CHUNK_PATH)

    mock_ftp.rename.assert_called_once()
    # Cache must remain absent — not populated with stale data.
    assert "ab" not in backend._shard_cache


@pytest.mark.remote
def test_ftp_warm_shard_excludes_tmp_files() -> None:
    """_warm_shard must not add .tmp file names to the shard cache."""
    mock_ftp = MagicMock()
    tmp_name = f"{_CHUNK_HASH}.tmp"

    def retrlines_side_effect(cmd: str, callback: object) -> None:
        if "NLST" in cmd:
            callback(tmp_name)  # type: ignore[operator]
            callback(_CHUNK_HASH)  # type: ignore[operator]

    mock_ftp.retrlines.side_effect = retrlines_side_effect
    backend = _make_ftp_backend(mock_ftp)

    # Trigger shard warming.
    backend.exists(_CHUNK_PATH)

    shard = backend._shard_cache.get("ab", set())
    assert tmp_name not in shard
    assert _CHUNK_HASH in shard


# ---------------------------------------------------------------------------
# SFTPBackend — rename
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_sftp_rename_calls_sftp_rename() -> None:
    """rename delegates to sftp.rename() at the correct absolute paths."""
    mock_sftp = MagicMock()
    mock_transport = MagicMock()
    backend = _make_sftp_backend(mock_sftp, mock_transport)
    src = f"chunks/ab/{_CHUNK_HASH}.tmp"
    dst = _CHUNK_PATH
    backend.rename(src, dst)
    mock_sftp.rename.assert_called_once_with(f"{_ROOT}/{src}", f"{_ROOT}/{dst}")
