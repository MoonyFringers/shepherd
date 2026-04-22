# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Built-in FTP remote storage backend using stdlib ``ftplib``."""

from __future__ import annotations

import ftplib
import io
import posixpath

from .backend import RemoteBackend


class FTPBackend(RemoteBackend):
    """FTP remote backend.

    Existence checks use the shard-listing strategy: at the start of a backup
    session, each needed 2-character prefix directory is listed once via
    ``NLST``, building an in-memory ``set[str]`` of known chunk hashes.
    Subsequent ``exists()`` calls for chunks in the same shard are resolved
    from the in-memory cache without additional round-trips.

    Parameters
    ----------
    host:
        FTP server hostname.
    port:
        FTP server port (default 21).
    user:
        FTP username.
    password:
        FTP password (supports ``${VAR}`` resolved before construction).
    root_path:
        Remote root directory under which the chunk store layout lives.
    """

    def __init__(
        self,
        host: str,
        port: int = 21,
        user: str = "",
        password: str = "",
        root_path: str = "/",
    ) -> None:
        self._root = root_path.rstrip("/")
        # Shard cache: shard prefix → set of known chunk hashes.
        self._shard_cache: dict[str, set[str]] = {}
        self._ftp = ftplib.FTP()
        self._ftp.connect(host, port)
        self._ftp.login(user, password)
        self._ftp.set_pasv(True)

    # ------------------------------------------------------------------
    # RemoteBackend implementation
    # ------------------------------------------------------------------

    def exists(self, path: str) -> bool:
        parts = path.split("/")
        if len(parts) == 3 and parts[0] == "chunks":
            shard = parts[1]
            if shard not in self._shard_cache:
                self._warm_shard(shard)
            return parts[2] in self._shard_cache.get(shard, set())
        try:
            self._ftp.size(self._abs(path))
            return True
        except ftplib.error_perm:
            return False

    def upload(self, path: str, data: bytes) -> None:
        abs_path = self._abs(path)
        self._mkdirs(posixpath.dirname(abs_path))
        self._ftp.storbinary(f"STOR {abs_path}", io.BytesIO(data))
        # Keep shard cache consistent after a new chunk is written.
        # When uploading via the write-then-rename pattern the caller first
        # uploads to a .tmp path (added here) and then calls rename(), which
        # swaps the .tmp entry for the final hash.  The end state is correct
        # as long as both calls are made in sequence on the same instance.
        parts = path.split("/")
        if len(parts) == 3 and parts[0] == "chunks":
            shard = parts[1]
            if shard in self._shard_cache:
                self._shard_cache[shard].add(parts[2])

    def download(self, path: str) -> bytes:
        buf = io.BytesIO()
        self._ftp.retrbinary(f"RETR {self._abs(path)}", buf.write)
        return buf.getvalue()

    def list_prefix(self, prefix: str) -> list[str]:
        names: list[str] = []
        try:
            self._ftp.retrlines(f"NLST {self._abs(prefix)}", names.append)
        except ftplib.error_perm:
            pass
        return [posixpath.basename(n) for n in names]

    def delete(self, path: str) -> None:
        # Note: the shard cache is NOT updated here.  Deletion happens during
        # pruning, which uses a separate backend instance from the dedup-check
        # path, so stale cache entries are never observed in practice.
        try:
            self._ftp.delete(self._abs(path))
        except ftplib.error_perm:
            pass

    def rename(self, src_path: str, dst_path: str) -> None:
        self._ftp.rename(self._abs(src_path), self._abs(dst_path))
        src_parts = src_path.split("/")
        dst_parts = dst_path.split("/")
        if (
            len(src_parts) == 3
            and src_parts[0] == "chunks"
            and len(dst_parts) == 3
            and dst_parts[0] == "chunks"
        ):
            shard = dst_parts[1]
            if shard in self._shard_cache:
                self._shard_cache[shard].discard(src_parts[2])
                self._shard_cache[shard].add(dst_parts[2])

    def close(self) -> None:
        try:
            self._ftp.quit()
        except Exception:
            self._ftp.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _abs(self, path: str) -> str:
        return f"{self._root}/{path}" if self._root else path

    def _mkdirs(self, abs_dir: str) -> None:
        """Create all components of *abs_dir*, ignoring existing dirs."""
        current = ""
        for part in abs_dir.lstrip("/").split("/"):
            current = f"{current}/{part}"
            try:
                self._ftp.mkd(current)
            except ftplib.error_perm:
                pass

    def _warm_shard(self, shard: str) -> None:
        """Populate the shard cache for *shard* with a single NLST call."""
        names: list[str] = []
        try:
            self._ftp.retrlines(
                f"NLST {self._abs(f'chunks/{shard}')}", names.append
            )
        except ftplib.error_perm:
            pass
        self._shard_cache[shard] = {
            posixpath.basename(n)
            for n in names
            if not posixpath.basename(n).endswith(".tmp")
        }
