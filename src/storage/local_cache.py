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

import json
import pathlib
import threading
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
        self._max_bytes = max_bytes
        self._lock = threading.Lock()
        self._root = pathlib.Path(cache_path)
        self._meta_path = self._root / "meta.json"
        self._chunks_dir = self._root / "chunks"
        self._chunks_dir.mkdir(parents=True, exist_ok=True)
        # _order: front = LRU, back = MRU
        self._order: list[str] = []
        self._sizes: dict[str, int] = {}
        self._total: int = 0
        self._load_meta()

    # ------------------------------------------------------------------
    # Protocol implementation
    # ------------------------------------------------------------------

    def contains(self, chunk_hash: str) -> bool:
        with self._lock:
            return chunk_hash in self._sizes

    def get(self, chunk_hash: str) -> bytes | None:
        """Return compressed chunk bytes, or ``None`` if not cached."""
        with self._lock:
            if chunk_hash not in self._sizes:
                return None
            data = self._chunk_path(chunk_hash).read_bytes()
            # Promote to MRU.
            self._order.remove(chunk_hash)
            self._order.append(chunk_hash)
            self._save_meta()
            return data

    def put(self, chunk_hash: str, data: bytes) -> None:
        """Store compressed chunk bytes; evict LRU entries if over budget."""
        with self._lock:
            if chunk_hash in self._sizes:
                # Refresh: remove old accounting before re-writing.
                self._total -= self._sizes.pop(chunk_hash)
                self._order.remove(chunk_hash)
            path = self._chunk_path(chunk_hash)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            size = len(data)
            self._sizes[chunk_hash] = size
            self._total += size
            self._order.append(chunk_hash)
            self._evict()
            self._save_meta()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _chunk_path(self, chunk_hash: str) -> pathlib.Path:
        return self._chunks_dir / chunk_hash[:2] / chunk_hash

    def _evict(self) -> None:
        """Remove LRU entries until total_bytes ≤ max_bytes."""
        while self._total > self._max_bytes and self._order:
            lru = self._order.pop(0)
            evicted = self._sizes.pop(lru, 0)
            self._total -= evicted
            self._chunk_path(lru).unlink(missing_ok=True)

    def _load_meta(self) -> None:
        if not self._meta_path.exists():
            return
        with self._meta_path.open() as fh:
            d: dict[str, object] = json.load(fh)
        self._order = list(d.get("order", []))  # type: ignore[arg-type]
        self._sizes = dict(d.get("sizes", {}))  # type: ignore[arg-type]
        self._total = int(d.get("total_bytes", 0))  # type: ignore[arg-type]

    def _save_meta(self) -> None:
        tmp = self._meta_path.with_suffix(".tmp")
        with tmp.open("w") as fh:
            json.dump(
                {
                    "total_bytes": self._total,
                    "order": self._order,
                    "sizes": self._sizes,
                },
                fh,
            )
        tmp.replace(self._meta_path)


class NullLocalChunkCache:
    """No-op cache used when local caching is disabled."""

    def contains(self, chunk_hash: str) -> bool:  # noqa: ARG002
        return False

    def get(self, chunk_hash: str) -> bytes | None:  # noqa: ARG002
        return None

    def put(self, chunk_hash: str, data: bytes) -> None:  # noqa: ARG002
        pass
