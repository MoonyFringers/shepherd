# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Built-in SFTP remote storage backend using paramiko."""

from __future__ import annotations

import posixpath

import paramiko

from .backend import RemoteBackend


def _load_pkey(path: str) -> paramiko.PKey:
    """Load a private key from *path*, auto-detecting the key type.

    Uses ``paramiko.PKey.from_path`` (available since paramiko 3.2), which
    transparently handles Ed25519, ECDSA, and RSA keys.
    """
    return paramiko.PKey.from_path(path)  # type: ignore[return-value]


class SFTPBackend(RemoteBackend):
    """SFTP remote backend.

    Provides encrypted transfer and SSH key or password authentication,
    making it the preferred built-in transport for most real deployments.

    Parameters
    ----------
    host:
        SFTP server hostname.
    port:
        SFTP server port (default 22).
    user:
        SSH username.
    password:
        SSH password (optional; supports ``${VAR}`` resolved before
        construction). Mutually exclusive with ``identity_file``.
    identity_file:
        Path to a private key file (optional; supports ``${VAR}``).
        Takes precedence over ``password`` when both are supplied.
    root_path:
        Remote root directory under which the chunk store layout lives.
    """

    def __init__(
        self,
        host: str,
        port: int = 22,
        user: str = "",
        password: str | None = None,
        identity_file: str | None = None,
        root_path: str = "/",
    ) -> None:
        self._root = root_path.rstrip("/")
        self._transport = paramiko.Transport((host, port))
        if identity_file:
            self._transport.connect(
                username=user, pkey=_load_pkey(identity_file)
            )
        else:
            self._transport.connect(username=user, password=password)
        sftp = paramiko.SFTPClient.from_transport(self._transport)
        if sftp is None:
            raise RuntimeError("Failed to open SFTP channel")
        self._sftp = sftp

    # ------------------------------------------------------------------
    # RemoteBackend implementation
    # ------------------------------------------------------------------

    def exists(self, path: str) -> bool:
        try:
            self._sftp.stat(self._abs(path))
            return True
        except FileNotFoundError:
            return False

    def upload(self, path: str, data: bytes) -> None:
        abs_path = self._abs(path)
        self._mkdirs(posixpath.dirname(abs_path))
        with self._sftp.open(abs_path, "wb") as f:
            f.write(data)

    def download(self, path: str) -> bytes:
        with self._sftp.open(self._abs(path), "rb") as f:
            return bytes(f.read())

    def list_prefix(self, prefix: str) -> list[str]:
        try:
            return self._sftp.listdir(self._abs(prefix))
        except FileNotFoundError:
            return []

    def delete(self, path: str) -> None:
        try:
            self._sftp.remove(self._abs(path))
        except FileNotFoundError:
            pass

    def rename(self, src_path: str, dst_path: str) -> None:
        # Errors propagate intentionally: a failed rename must abort the push
        # rather than leave a .tmp file silently treated as a valid chunk.
        self._sftp.rename(self._abs(src_path), self._abs(dst_path))

    def close(self) -> None:
        try:
            self._sftp.close()
        finally:
            self._transport.close()

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
                self._sftp.mkdir(current)
            except OSError:
                pass
