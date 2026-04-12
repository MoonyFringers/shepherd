# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

from __future__ import annotations

import json
import re

import pytest

from storage import (
    IndexCatalogue,
    IndexCatalogueEntry,
    LatestPointer,
    SnapshotManifest,
)


def _manifest() -> SnapshotManifest:
    return SnapshotManifest(
        snapshot_id="2025-01-01T00:00:00-abc123",
        environment="my-env",
        shepherd_version="1.0.0",
        created_at="2025-01-01T00:00:00",
        chunks=["aabbcc", "ddeeff"],
        chunk_count=2,
        total_size_bytes=1024,
        stored_size_bytes=512,
    )


@pytest.mark.storage
def test_snapshot_manifest_round_trip() -> None:
    """to_dict → from_dict reproduces an identical object."""
    original = _manifest()
    restored = SnapshotManifest.from_dict(original.to_dict())
    assert restored == original


@pytest.mark.storage
def test_snapshot_manifest_build_id_format() -> None:
    """build_id returns '{created_at}-{6 lowercase hex chars}'."""
    payload = b'{"snapshot": "data"}'
    result = SnapshotManifest.build_id("2025-06-01T12:00:00", payload)
    assert re.match(r"^2025-06-01T12:00:00-[0-9a-f]{6}$", result)


@pytest.mark.storage
def test_snapshot_manifest_build_id_deterministic() -> None:
    """Same inputs always produce the same build_id."""
    ts = "2025-01-01T00:00:00"
    payload = json.dumps({"x": 1}).encode()
    assert SnapshotManifest.build_id(ts, payload) == SnapshotManifest.build_id(
        ts, payload
    )


@pytest.mark.storage
def test_latest_pointer_round_trip() -> None:
    ptr = LatestPointer(
        snapshot_id="2025-01-01T00:00:00-abc123",
        updated_at="2025-01-01T00:00:00",
    )
    assert LatestPointer.from_dict(ptr.to_dict()) == ptr


@pytest.mark.storage
def test_index_catalogue_entry_round_trip() -> None:
    entry = IndexCatalogueEntry(
        latest_snapshot="2025-01-01T00:00:00-abc123",
        snapshot_count=3,
        last_backup="2025-01-01T00:00:00",
        labels=["prod"],
        total_size_bytes=2048,
        stored_size_bytes=1024,
    )
    assert IndexCatalogueEntry.from_dict(entry.to_dict()) == entry


@pytest.mark.storage
def test_index_catalogue_round_trip() -> None:
    """Nested IndexCatalogueEntry objects survive a round-trip."""
    catalogue = IndexCatalogue(
        updated_at="2025-01-01T00:00:00",
        environments={
            "env-a": IndexCatalogueEntry(
                latest_snapshot="snap-1",
                snapshot_count=1,
                last_backup="2025-01-01T00:00:00",
                labels=[],
                total_size_bytes=100,
                stored_size_bytes=50,
            )
        },
    )
    restored = IndexCatalogue.from_dict(catalogue.to_dict())
    assert restored == catalogue
    assert isinstance(restored.environments["env-a"], IndexCatalogueEntry)


@pytest.mark.storage
def test_from_dict_tolerates_missing_optional_fields() -> None:
    """from_dict fills in defaults for optional manifest fields."""
    minimal = {
        "snapshot_id": "snap-1",
        "environment": "env",
        "shepherd_version": "1.0.0",
        "created_at": "2025-01-01T00:00:00",
        "chunks": [],
        "chunk_count": 0,
        "total_size_bytes": 0,
        "stored_size_bytes": 0,
    }
    m = SnapshotManifest.from_dict(minimal)
    assert m.compression == "zstd"
    assert m.chunk_algo == "fastcdc"
    assert m.avg_chunk_size_kb == 2048
    assert m.labels == []
