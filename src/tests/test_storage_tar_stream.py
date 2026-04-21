# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

from __future__ import annotations

import io
import tarfile
from pathlib import Path
from typing import IO

import pytest

from storage import TarStreamProducer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tar_stream(files: dict[str, bytes]) -> IO[bytes]:
    """Build an in-memory tar stream with the given ``{name: content}`` map."""
    buf = io.BytesIO()
    with tarfile.open(mode="w|", fileobj=buf) as t:
        for name, content in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            t.addfile(info, io.BytesIO(content))
    buf.seek(0)
    return buf


def _list_tar_names(stream: IO[bytes]) -> list[str]:
    with tarfile.open(mode="r|", fileobj=stream) as t:
        return [m.name for m in t]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.storage
def test_stream_env_only(tmp_path: Path) -> None:
    """Output tar contains env/ entries when no volumes are provided."""
    env_dir = tmp_path / "myenv"
    env_dir.mkdir()
    (env_dir / "docker-compose.yml").write_text("version: '3'")

    producer = TarStreamProducer(str(env_dir), [])
    names = _list_tar_names(producer.stream())

    assert any(n.startswith("env") for n in names)
    assert not any(n.startswith("volumes/") for n in names)


@pytest.mark.storage
def test_stream_with_volumes(tmp_path: Path) -> None:
    """Volume streams are re-injected under volumes/<tag>/."""
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    (env_dir / "meta.yml").write_text("tag: test")

    vol_a = _make_tar_stream({"./data.bin": b"aaa"})
    vol_b = _make_tar_stream({"./rows.csv": b"1,2,3"})

    producer = TarStreamProducer(
        str(env_dir),
        [("db_data", vol_a), ("uploads", vol_b)],
    )
    names = _list_tar_names(producer.stream())

    assert any(n.startswith("env") for n in names)
    assert any(n.startswith("volumes/db_data") for n in names)
    assert any(n.startswith("volumes/uploads") for n in names)


@pytest.mark.storage
def test_stream_env_and_volume_arcnames(tmp_path: Path) -> None:
    """Arcname prefixes are exactly env/ and volumes/<tag>/ — not index-based."""
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    (env_dir / "cfg.yml").write_text("x: 1")

    vol = _make_tar_stream({"./file.txt": b"hello"})
    producer = TarStreamProducer(str(env_dir), [("my_vol", vol)])
    names = _list_tar_names(producer.stream())

    # Exact prefix check
    assert all(
        n.startswith("env") or n.startswith("volumes/my_vol") for n in names
    )
    # No numeric index in any name
    assert not any(n.startswith("volumes/0") for n in names)


@pytest.mark.storage
def test_needs_elevated_permissions_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """needs_elevated_permissions() reflects the eager check done in __init__."""
    import os as _os

    env_dir = tmp_path / "env"
    env_dir.mkdir()

    real_walk = _os.walk

    def _patched_walk(path: str, onerror=None, **kwargs):  # type: ignore[override]
        yield from real_walk(path, **kwargs)
        if onerror is not None:
            onerror(PermissionError(13, "Permission denied", str(path)))

    monkeypatch.setattr("util.util.os.walk", _patched_walk)
    monkeypatch.setattr("util.util.shutil.which", lambda _: "/usr/bin/sudo")

    producer = TarStreamProducer(str(env_dir), [])
    assert producer.needs_elevated_permissions() is True


class _FakeProc:
    """Minimal subprocess.Popen stand-in for _add_env_sudo tests."""

    def __init__(self, stream: io.BytesIO, returncode: int = 0) -> None:
        self.stdout = stream
        self.stderr = io.BytesIO(b"")
        self.returncode = returncode

    def wait(self) -> int:
        return self.returncode


@pytest.mark.storage
def test_stream_env_sudo_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Falls back to sudo tar and emits env/ entries when env is not readable."""
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    (env_dir / "cfg.yml").write_text("x: 1")

    sudo_stream = _make_tar_stream({"./cfg.yml": b"x: 1"})

    popen_calls: list[list[str]] = []

    def _fake_popen(cmd: list[str], **kwargs):  # type: ignore[override]
        popen_calls.append(cmd)
        return _FakeProc(sudo_stream)

    monkeypatch.setattr("storage.tar_stream.subprocess.Popen", _fake_popen)
    monkeypatch.setattr(
        TarStreamProducer, "_is_env_readable", lambda self: False
    )

    producer = TarStreamProducer(str(env_dir), [])
    names = _list_tar_names(producer.stream())

    assert any(n.startswith("env") for n in names)
    assert len(popen_calls) == 1
    assert popen_calls[0][:3] == ["sudo", "tar", "-cC"]
    assert popen_calls[0][3] == str(env_dir)


@pytest.mark.storage
def test_reinject_empty_stream_raises_runtime_error(
    tmp_path: Path,
) -> None:
    """_reinject raises RuntimeError with a readable message on empty volume stream."""
    env_dir = tmp_path / "env"
    env_dir.mkdir()

    empty_stream = io.BytesIO(b"")

    producer = TarStreamProducer(str(env_dir), [("db_data", empty_stream)])
    with pytest.raises(RuntimeError, match="db_data"):
        with producer.stream() as s:
            s.read()
