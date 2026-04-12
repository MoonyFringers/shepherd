# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Optional LRU on-disk chunk cache.

Stores compressed chunk bytes in a flat-file layout that mirrors the remote
chunk store (``<cache_path>/chunks/<2-char-prefix>/<full-hash>``).  LRU
metadata (eviction order and sizes) is kept in a JSON sidecar at
``<cache_path>/meta.json``.

Use :class:`NullLocalChunkCache` when no cache is configured — it is a
drop-in no-op with zero overhead.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LocalChunkCacheProtocol(Protocol):
    """Shared interface for local chunk caches.

    Both :class:`LocalChunkCache` and :class:`NullLocalChunkCache` satisfy
    this protocol, allowing ``RemoteMng`` to accept either without a common
    ABC and without pyright drift between their signatures.
    """

    def contains(self, chunk_hash: str) -> bool: ...

    def get(self, chunk_hash: str) -> bytes | None: ...

    def put(self, chunk_hash: str, data: bytes) -> None: ...


class LocalChunkCache:
    """LRU on-disk cache for compressed chunk bytes.

    Parameters
    ----------
    cache_path:
        Root directory for the cache.
    max_bytes:
        Maximum total size of cached chunks in bytes.  When exceeded, the
        least-recently-used chunks are evicted until the cache fits.
    """

    def __init__(self, cache_path: str, max_bytes: int) -> None:
        raise NotImplementedError  # TODO: Issue 6

    def contains(self, chunk_hash: str) -> bool:
        raise NotImplementedError  # TODO: Issue 6

    def get(self, chunk_hash: str) -> bytes | None:
        """Return compressed chunk bytes, or ``None`` if not cached."""
        raise NotImplementedError  # TODO: Issue 6

    def put(self, chunk_hash: str, data: bytes) -> None:
        """Store compressed chunk bytes; evict LRU entries if over budget."""
        raise NotImplementedError  # TODO: Issue 6


class NullLocalChunkCache:
    """No-op cache used when local caching is disabled."""

    def contains(self, chunk_hash: str) -> bool:  # noqa: ARG002
        return False

    def get(self, chunk_hash: str) -> bytes | None:  # noqa: ARG002
        return None

    def put(self, chunk_hash: str, data: bytes) -> None:  # noqa: ARG002
        pass
