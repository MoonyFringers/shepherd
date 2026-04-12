# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Built-in FTP remote storage backend using stdlib ``ftplib``."""

from __future__ import annotations

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
