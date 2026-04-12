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
import tarfile
import threading
from typing import IO


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
        Absolute path to the environment directory.  This path must be
        readable by the current process.
    volume_streams:
        Ordered list of ``(volume_tag, uncompressed_tar_stream)`` pairs.
        Each stream must be in tar streaming format (``r|``-readable, entries
        rooted at ``.``).
    """

    def __init__(
        self,
        env_path: str,
        volume_streams: list[tuple[str, IO[bytes]]],
    ) -> None:
        self._env_path = env_path
        self._volume_streams = volume_streams

    def stream(self) -> IO[bytes]:
        """Return a readable, uncompressed tar byte stream.

        The stream is produced on a daemon background thread.  The caller is
        responsible for closing the returned file object when done.
        """
        r_fd, w_fd = os.pipe()

        def _produce() -> None:
            try:
                with os.fdopen(w_fd, "wb") as out_file:
                    with tarfile.open(mode="w|", fileobj=out_file) as out_tar:
                        out_tar.add(
                            self._env_path, arcname="env", recursive=True
                        )
                        for tag, vol_stream in self._volume_streams:
                            self._reinject(out_tar, tag, vol_stream)
            except BrokenPipeError:
                pass  # caller closed the read end early

        t = threading.Thread(target=_produce, daemon=True)
        t.start()
        return os.fdopen(r_fd, "rb")

    def _reinject(
        self,
        out_tar: tarfile.TarFile,
        tag: str,
        vol_stream: IO[bytes],
    ) -> None:
        """Copy entries from *vol_stream* into *out_tar* prefixed by tag."""
        with tarfile.open(mode="r|", fileobj=vol_stream) as src_tar:
            for member in src_tar:
                rel = member.name.lstrip("./")
                member.name = (
                    f"volumes/{tag}/{rel}" if rel else f"volumes/{tag}"
                )
                fobj = src_tar.extractfile(member) if member.isreg() else None
                out_tar.addfile(member, fobj)
