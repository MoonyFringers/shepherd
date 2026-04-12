# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Dataclasses for snapshot manifests, latest pointers, and the global index.

All models serialise to/from plain JSON via ``from_dict`` / ``to_dict``
helpers, consistent with the ``config.py`` dataclass style.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SnapshotManifest:
    """Full record for a single environment snapshot.

    The ``chunks`` list contains SHA-256 hex digests of the compressed chunk
    bytes, ordered so that concatenating the chunks and decompressing each one
    in turn reconstructs the original uncompressed tar stream.
    """

    snapshot_id: str
    environment: str
    shepherd_version: str
    created_at: str
    chunks: list[str]
    chunk_count: int
    total_size_bytes: int
    stored_size_bytes: int
    compression: str = "zstd"
    chunk_algo: str = "fastcdc"
    avg_chunk_size_kb: int = 2048
    labels: list[str] = field(default_factory=lambda: [])
    db_included: bool = False
    db_engine: str | None = None
    db_version: str | None = None

    @staticmethod
    def build_id(created_at: str, manifest_bytes: bytes) -> str:
        """Return ``{created_at}-{first-6-chars-sha256(manifest_bytes)}``."""
        suffix = hashlib.sha256(manifest_bytes).hexdigest()[:6]
        return f"{created_at}-{suffix}"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SnapshotManifest:
        return cls(
            snapshot_id=d["snapshot_id"],
            environment=d["environment"],
            shepherd_version=d["shepherd_version"],
            created_at=d["created_at"],
            chunks=d["chunks"],
            chunk_count=d["chunk_count"],
            total_size_bytes=d["total_size_bytes"],
            stored_size_bytes=d["stored_size_bytes"],
            compression=d.get("compression", "zstd"),
            chunk_algo=d.get("chunk_algo", "fastcdc"),
            avg_chunk_size_kb=d.get("avg_chunk_size_kb", 2048),
            labels=d.get("labels", []),
            db_included=d.get("db_included", False),
            db_engine=d.get("db_engine"),
            db_version=d.get("db_version"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "environment": self.environment,
            "shepherd_version": self.shepherd_version,
            "created_at": self.created_at,
            "chunks": self.chunks,
            "chunk_count": self.chunk_count,
            "total_size_bytes": self.total_size_bytes,
            "stored_size_bytes": self.stored_size_bytes,
            "compression": self.compression,
            "chunk_algo": self.chunk_algo,
            "avg_chunk_size_kb": self.avg_chunk_size_kb,
            "labels": self.labels,
            "db_included": self.db_included,
            "db_engine": self.db_engine,
            "db_version": self.db_version,
        }


@dataclass
class LatestPointer:
    """Lightweight file that points to the most recent snapshot for an env."""

    snapshot_id: str
    updated_at: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LatestPointer:
        return cls(
            snapshot_id=d["snapshot_id"],
            updated_at=d["updated_at"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "updated_at": self.updated_at,
        }


@dataclass
class IndexCatalogueEntry:
    """Per-environment summary stored inside ``index.json``."""

    latest_snapshot: str
    snapshot_count: int
    last_backup: str
    labels: list[str]
    total_size_bytes: int
    stored_size_bytes: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> IndexCatalogueEntry:
        return cls(
            latest_snapshot=d["latest_snapshot"],
            snapshot_count=d["snapshot_count"],
            last_backup=d["last_backup"],
            labels=d.get("labels", []),
            total_size_bytes=d["total_size_bytes"],
            stored_size_bytes=d["stored_size_bytes"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "latest_snapshot": self.latest_snapshot,
            "snapshot_count": self.snapshot_count,
            "last_backup": self.last_backup,
            "labels": self.labels,
            "total_size_bytes": self.total_size_bytes,
            "stored_size_bytes": self.stored_size_bytes,
        }


@dataclass
class IndexCatalogue:
    """Global catalogue file (``index/index.json``).

    This is a best-effort cache; ground truth is always the per-environment
    manifest files.
    """

    updated_at: str
    environments: dict[str, IndexCatalogueEntry] = field(
        default_factory=lambda: {}
    )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> IndexCatalogue:
        envs = {
            name: IndexCatalogueEntry.from_dict(entry)
            for name, entry in d.get("environments", {}).items()
        }
        return cls(updated_at=d["updated_at"], environments=envs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "updated_at": self.updated_at,
            "environments": {
                name: entry.to_dict()
                for name, entry in self.environments.items()
            },
        }
