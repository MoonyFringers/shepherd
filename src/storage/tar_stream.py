# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Produces an uncompressed tar byte stream from a Shepherd environment,
including host-mounted volumes (with sudo escalation when required)."""

from __future__ import annotations

import os
import subprocess
import tarfile
import threading
from typing import IO, Optional, cast

from util.util import Util


class _CheckedStream:
    """Readable stream that re-raises background-thread errors on close.

    Wraps the read end of the producer pipe.  When the caller closes the
    stream, it joins the background thread and re-raises any exception the
    producer stored — giving a clear root cause instead of a silent EOF.
    ``BrokenPipeError`` (caller closed early) is never stored and therefore
    never re-raised.
    """

    def __init__(
        self,
        r: IO[bytes],
        thread: threading.Thread,
        exc_holder: list[BaseException],
    ) -> None:
        self._r = r
        self._thread = thread
        self._exc_holder = exc_holder
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def read(self, n: int = -1) -> bytes:
        return self._r.read(n)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._r.close()
            self._thread.join()
            if self._exc_holder:
                raise self._exc_holder[0]

    def __enter__(self) -> _CheckedStream:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class TarStreamProducer:
    """Produces an uncompressed tar stream for a Shepherd environment.

    The stream covers:
    - The environment's data directory under the ``env/`` arcname prefix.
    - Each volume supplied as a ``(volume_tag, stream)`` pair, re-injected
      under ``volumes/<tag>/``.

    Volume streams carry the ``volume_tag`` so that the resulting archive is
    self-describing: a restore pass can match each ``volumes/<tag>/`` subtree
    back to the correct ``VolumeCfg`` regardless of order or future additions.
    Callers are responsible for producing the per-volume streams (e.g. via
    ``Environment.get_volume_tar_streams()``).

    Parameters
    ----------
    env_path:
        Absolute path to the environment directory.
    volume_streams:
        Ordered list of ``(volume_tag, uncompressed_tar_stream)`` pairs.
        Each stream must be in tar streaming format (``r|``-readable, entries
        rooted at ``.``).
    """

    def __init__(
        self,
        env_path: str,
        volume_streams: list[tuple[str, IO[bytes]]],
        env_needs_sudo: Optional[bool] = None,
    ) -> None:
        self._env_path = env_path
        self._volume_streams = volume_streams
        self._env_needs_sudo = (
            env_needs_sudo
            if env_needs_sudo is not None
            else not self._is_env_readable()
        )

    def needs_elevated_permissions(self) -> bool:
        """Return True if archiving env_path requires sudo.

        Callers should check this before calling ``stream()`` and ask the user
        for consent before proceeding, since the stream will invoke ``sudo tar``
        to read container-owned subdirectories.
        """
        return self._env_needs_sudo

    def _is_env_readable(self) -> bool:
        return Util.is_tree_readable(self._env_path)

    def _add_env_sudo(self, out_tar: tarfile.TarFile) -> None:
        """Stream env_path via sudo tar; inject entries under env/ arcname."""
        proc = subprocess.Popen(
            ["sudo", "tar", "-cC", self._env_path, "."],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.stdout is None:
            raise RuntimeError("subprocess stdout is None — this is a bug")
        try:
            with tarfile.open(mode="r|", fileobj=proc.stdout) as src_tar:
                for member in src_tar:
                    rel = member.name.lstrip("./")
                    member.name = f"env/{rel}" if rel else "env"
                    fobj = (
                        src_tar.extractfile(member) if member.isreg() else None
                    )
                    out_tar.addfile(member, fobj)
        finally:
            proc.stdout.close()
            stderr_bytes = proc.stderr.read() if proc.stderr else b""
            if proc.stderr:
                proc.stderr.close()
            proc.wait()
        if proc.returncode != 0:
            msg = stderr_bytes.decode(errors="replace").strip()
            raise RuntimeError(
                f"sudo tar failed for {self._env_path} "
                f"(exit {proc.returncode})" + (f": {msg}" if msg else "")
            )

    def stream(self) -> IO[bytes]:
        """Return a readable, uncompressed tar byte stream.

        The stream is produced on a daemon background thread.  Closing the
        returned stream joins the thread; any exception raised by the producer
        (other than ``BrokenPipeError``) is re-raised at that point.
        """
        r_fd, w_fd = os.pipe()
        exc_holder: list[BaseException] = []

        def _produce() -> None:
            try:
                with os.fdopen(w_fd, "wb") as out_file:
                    with tarfile.open(mode="w|", fileobj=out_file) as out_tar:
                        if self._env_needs_sudo:
                            self._add_env_sudo(out_tar)
                        else:
                            out_tar.add(
                                self._env_path,
                                arcname="env",
                                recursive=True,
                            )
                        for tag, vol_stream in self._volume_streams:
                            self._reinject(out_tar, tag, vol_stream)
            except BrokenPipeError:
                pass  # caller closed the read end early
            except BaseException as exc:
                exc_holder.append(exc)

        t = threading.Thread(target=_produce, daemon=True)
        t.start()
        return cast(
            IO[bytes],
            _CheckedStream(os.fdopen(r_fd, "rb"), t, exc_holder),
        )

    def _reinject(
        self,
        out_tar: tarfile.TarFile,
        tag: str,
        vol_stream: IO[bytes],
    ) -> None:
        """Copy entries from *vol_stream* into *out_tar* prefixed by tag."""
        try:
            with tarfile.open(mode="r|", fileobj=vol_stream) as src_tar:
                for member in src_tar:
                    rel = member.name.lstrip("./")
                    member.name = (
                        f"volumes/{tag}/{rel}" if rel else f"volumes/{tag}"
                    )
                    fobj = (
                        src_tar.extractfile(member) if member.isreg() else None
                    )
                    out_tar.addfile(member, fobj)
            vol_stream.close()
        except tarfile.ReadError as exc:
            try:
                vol_stream.close()
            except Exception:
                pass
            raise RuntimeError(
                f"volume stream for '{tag}' is empty or corrupt — "
                "the subprocess producing it likely failed due to "
                "insufficient permissions (check sudo access)"
            ) from exc
