# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

from __future__ import annotations

import hashlib
import io
import random

import pytest
import zstandard

from storage import Chunker, ChunkResult

# Use small sizes so tests run quickly without large buffers.
_MIN = 256
_AVG = 1024
_MAX = 4096


def _chunker() -> Chunker:
    return Chunker(min_size=_MIN, avg_size=_AVG, max_size=_MAX)


def _stream(data: bytes) -> io.BytesIO:
    return io.BytesIO(data)


@pytest.mark.storage
def test_chunker_yields_chunk_results() -> None:
    """A non-empty stream produces at least one ChunkResult."""
    data = random.randbytes(8 * _AVG)
    results = list(_chunker().chunk_stream(_stream(data)))
    assert len(results) >= 1
    for r in results:
        assert isinstance(r, ChunkResult)
        assert isinstance(r.hash, str) and len(r.hash) == 64
        assert isinstance(r.data, bytes) and len(r.data) > 0
        assert isinstance(r.raw_size, int) and r.raw_size > 0


@pytest.mark.storage
def test_chunker_sha256_over_compressed() -> None:
    """Hash field is SHA-256 of the compressed (not raw) chunk bytes."""
    data = random.randbytes(4 * _AVG)
    for result in _chunker().chunk_stream(_stream(data)):
        expected = hashlib.sha256(result.data).hexdigest()
        assert result.hash == expected


@pytest.mark.storage
def test_chunker_raw_size_matches() -> None:
    """raw_size equals the length of the decompressed chunk."""
    data = random.randbytes(4 * _AVG)
    dctx = zstandard.ZstdDecompressor()
    for result in _chunker().chunk_stream(_stream(data)):
        raw = dctx.decompress(result.data)
        assert result.raw_size == len(raw)


@pytest.mark.storage
def test_chunker_empty_stream() -> None:
    """An empty stream yields no chunks."""
    results = list(_chunker().chunk_stream(_stream(b"")))
    assert results == []


@pytest.mark.storage
def test_chunker_stream_reconstructs() -> None:
    """Decompressing and concatenating all chunks reproduces the original."""
    data = random.randbytes(12 * _AVG)
    dctx = zstandard.ZstdDecompressor()
    reconstructed = b"".join(
        dctx.decompress(r.data) for r in _chunker().chunk_stream(_stream(data))
    )
    assert reconstructed == data


@pytest.mark.storage
def test_chunker_custom_params() -> None:
    """Chunker accepts custom min/avg/max without errors."""
    data = random.randbytes(3 * 1024 * 1024)
    chunker = Chunker(
        min_size=128 * 1024,
        avg_size=512 * 1024,
        max_size=2 * 1024 * 1024,
    )
    results = list(chunker.chunk_stream(_stream(data)))
    assert len(results) >= 1
