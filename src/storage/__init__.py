# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Local storage engine: chunking, tar, snapshot models, and chunk cache."""

from .chunker import Chunker, ChunkResult
from .local_cache import (
    LocalChunkCache,
    LocalChunkCacheProtocol,
    NullLocalChunkCache,
)
from .snapshot import (
    IndexCatalogue,
    IndexCatalogueEntry,
    LatestPointer,
    SnapshotManifest,
)
from .tar_stream import TarStreamProducer

__all__ = [
    "ChunkResult",
    "Chunker",
    "IndexCatalogue",
    "IndexCatalogueEntry",
    "LatestPointer",
    "LocalChunkCache",
    "LocalChunkCacheProtocol",
    "NullLocalChunkCache",
    "SnapshotManifest",
    "TarStreamProducer",
]
