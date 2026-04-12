# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""FastCDC-based chunker: splits a byte stream into variable-length chunks,
compresses each with Zstd, and hashes with SHA-256."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import IO, Iterator

import fastcdc
import zstandard


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
        self._min_size = min_size
        self._avg_size = avg_size
        self._max_size = max_size
        self._cctx = zstandard.ZstdCompressor(level=3)

    def chunk_stream(self, stream: IO[bytes]) -> Iterator[ChunkResult]:
        """Yield ChunkResult objects for every chunk in *stream*.

        Buffers ``4 × max_size`` bytes at a time and holds the last FastCDC
        cut of each window as a carry (it may end at the buffer boundary
        rather than a genuine content-defined cut-point).  The carry is
        prepended to the next read.  At EOF the remaining buffer is flushed
        through FastCDC to produce the final chunk(s).

        Parameters
        ----------
        stream:
            An uncompressed, readable byte stream (e.g. a tar stream).
        """
        read_size = self._max_size * 4
        buf = b""

        while True:
            block = stream.read(read_size)
            if not block:
                break
            buf += block
            cuts = list(
                fastcdc.fastcdc(  # type: ignore[reportUnknownMemberType]
                    buf,
                    min_size=self._min_size,
                    avg_size=self._avg_size,
                    max_size=self._max_size,
                    fat=True,
                )
            )
            # Emit all cuts except the last, which may end at the buffer
            # boundary rather than a genuine content-defined cut-point.
            for cut in cuts[:-1]:
                yield self._to_result(cut.data)
            # Carry the last cut's data into the next iteration.
            if cuts:
                buf = buf[cuts[-1].offset :]

        # EOF: flush whatever remains in the buffer.
        if buf:
            for cut in fastcdc.fastcdc(  # type: ignore[reportUnknownMemberType]
                buf,
                min_size=self._min_size,
                avg_size=self._avg_size,
                max_size=self._max_size,
                fat=True,
            ):
                yield self._to_result(cut.data)

    def _to_result(self, raw: bytes) -> ChunkResult:
        compressed = self._cctx.compress(raw)
        digest = hashlib.sha256(compressed).hexdigest()
        return ChunkResult(hash=digest, data=compressed, raw_size=len(raw))
