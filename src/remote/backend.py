# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Abstract base class for remote storage backends.

This ABC is also exported from the public plugin API (``src/plugin/api.py``)
so that external plugins can contribute new backend implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class RemoteBackend(ABC):
    """Contract that every remote storage transport must satisfy.

    Implementations are responsible for a single concern: moving bytes between
    the local machine and a remote store identified by opaque path strings.
    All higher-level logic (chunking, manifests, dedup) lives in
    :class:`~remote.remote_mng.RemoteMng`.

    Implementations should be used as context managers so that connections are
    closed deterministically::

        with backend:
            backend.upload("chunks/ab/ab3f...", data)
    """

    # ------------------------------------------------------------------
    # Path helpers (convenience, not abstract — backends may override)
    # ------------------------------------------------------------------

    @staticmethod
    def chunk_path(chunk_hash: str) -> str:
        """Return the remote path for *chunk_hash*.

        Example: ``ab3f1c9d...`` → ``chunks/ab/ab3f1c9d...``
        """
        return f"chunks/{chunk_hash[:2]}/{chunk_hash}"

    @staticmethod
    def chunk_tmp_path(chunk_hash: str) -> str:
        """Return the in-flight temp path for *chunk_hash* during upload.

        Example: ``ab3f1c9d...`` → ``chunks/ab/ab3f1c9d....tmp``
        """
        return f"chunks/{chunk_hash[:2]}/{chunk_hash}.tmp"

    @staticmethod
    def snapshots_prefix(env_name: str) -> str:
        """Return the remote path prefix for all snapshots of *env_name*.

        Example: ``"my-env"`` → ``"envs/my-env/snapshots"``
        """
        return f"envs/{env_name}/snapshots"

    @staticmethod
    def snapshot_path(env_name: str, snapshot_id: str) -> str:
        """Return the remote path for a snapshot manifest."""
        return f"envs/{env_name}/snapshots/{snapshot_id}.json"

    @staticmethod
    def latest_path(env_name: str) -> str:
        """Return the remote path for an environment's latest pointer."""
        return f"envs/{env_name}/latest.json"

    @staticmethod
    def index_path() -> str:
        """Return the remote path for the global index."""
        return "index/index.json"

    # ------------------------------------------------------------------
    # Abstract transport operations
    # ------------------------------------------------------------------

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Return ``True`` if *path* exists on the remote."""

    @abstractmethod
    def upload(self, path: str, data: bytes) -> None:
        """Write *data* to *path* on the remote, creating parents as needed."""

    @abstractmethod
    def download(self, path: str) -> bytes:
        """Return the full contents of *path* from the remote."""

    @abstractmethod
    def list_prefix(self, prefix: str) -> list[str]:
        """Return the leaf names of all objects under *prefix*.

        Example: ``list_prefix("chunks/ab")`` might return
        ``["ab3f1c9d...", "ab7e2a11..."]``.
        """

    @abstractmethod
    def delete(self, path: str) -> None:
        """Delete *path* from the remote."""

    @abstractmethod
    def rename(self, src_path: str, dst_path: str) -> None:
        """Atomically rename *src_path* to *dst_path* on the remote.

        Both paths are always in the same shard directory.  Implementations
        map to ``RNFR``/``RNTO`` (FTP) or ``sftp.rename()`` (SFTP).
        """

    @abstractmethod
    def close(self) -> None:
        """Release any underlying connections or resources."""

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> RemoteBackend:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
