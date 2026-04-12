# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""FastCDC-based chunker: splits a byte stream into variable-length chunks,
compresses each with Zstd, and hashes with SHA-256."""

from __future__ import annotations

from dataclasses import dataclass
from typing import IO, Iterator


@dataclass
class ChunkResult:
    """A single content-defined chunk ready for upload."""

    hash: str
    """SHA-256 hex digest of the *compressed* chunk bytes."""

    data: bytes
    """Compressed (Zstd) chunk bytes."""

    raw_size: int
    """Size of the uncompressed chunk in bytes."""


class Chunker:
    """Splits a raw byte stream into content-defined chunks.

    Each chunk is:
    1. Bounded by FastCDC cut-points on the *uncompressed* stream.
    2. Compressed individually with Zstd.
    3. Identified by the SHA-256 of the compressed bytes.

    Parameters
    ----------
    min_size:
        Minimum chunk size in bytes (default 512 KB).
    avg_size:
        Average (target) chunk size in bytes (default 2 MB).
    max_size:
        Maximum chunk size in bytes (default 8 MB).
    """

    def __init__(
        self,
        min_size: int = 512 * 1024,
        avg_size: int = 2 * 1024 * 1024,
        max_size: int = 8 * 1024 * 1024,
    ) -> None:
        raise NotImplementedError  # TODO: Issue 5

    def chunk_stream(self, stream: IO[bytes]) -> Iterator[ChunkResult]:
        """Yield ChunkResult objects for every chunk in *stream*.

        Parameters
        ----------
        stream:
            An uncompressed, readable byte stream (e.g. a tar stream).
        """
        raise NotImplementedError  # TODO: Issue 5
