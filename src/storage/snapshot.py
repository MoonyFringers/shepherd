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
        raise NotImplementedError  # TODO: Issue 5

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SnapshotManifest:
        raise NotImplementedError  # TODO: Issue 5

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError  # TODO: Issue 5


@dataclass
class LatestPointer:
    """Lightweight file that points to the most recent snapshot for an env."""

    snapshot_id: str
    updated_at: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LatestPointer:
        raise NotImplementedError  # TODO: Issue 5

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError  # TODO: Issue 5


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
        raise NotImplementedError  # TODO: Issue 5

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError  # TODO: Issue 5


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
        raise NotImplementedError  # TODO: Issue 5

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError  # TODO: Issue 5
