# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Built-in SFTP remote storage backend using paramiko."""

from __future__ import annotations

from .backend import RemoteBackend


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
        raise NotImplementedError  # TODO: Issue 7

    # RemoteBackend implementation

    def exists(self, path: str) -> bool:
        raise NotImplementedError  # TODO: Issue 7

    def upload(self, path: str, data: bytes) -> None:
        raise NotImplementedError  # TODO: Issue 7

    def download(self, path: str) -> bytes:
        raise NotImplementedError  # TODO: Issue 7

    def list_prefix(self, prefix: str) -> list[str]:
        raise NotImplementedError  # TODO: Issue 7

    def delete(self, path: str) -> None:
        raise NotImplementedError  # TODO: Issue 7

    def close(self) -> None:
        raise NotImplementedError  # TODO: Issue 7
