# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

from __future__ import annotations

import pathlib

import pytest

from storage import (
    LocalChunkCache,
    LocalChunkCacheProtocol,
    NullLocalChunkCache,
)

_HASH_A = "a" * 64
_HASH_B = "b" * 64
_HASH_C = "c" * 64
_DATA_A = b"chunk-a-data"
_DATA_B = b"chunk-b-data"
_DATA_C = b"chunk-c-data"


@pytest.mark.storage
def test_cache_put_and_get(tmp_path: pathlib.Path) -> None:
    """put then get returns the same bytes."""
    cache = LocalChunkCache(str(tmp_path), max_bytes=1024 * 1024)
    cache.put(_HASH_A, _DATA_A)
    assert cache.get(_HASH_A) == _DATA_A


@pytest.mark.storage
def test_cache_contains(tmp_path: pathlib.Path) -> None:
    """contains returns True after put, False for absent hash."""
    cache = LocalChunkCache(str(tmp_path), max_bytes=1024 * 1024)
    assert not cache.contains(_HASH_A)
    cache.put(_HASH_A, _DATA_A)
    assert cache.contains(_HASH_A)
    assert not cache.contains(_HASH_B)


@pytest.mark.storage
def test_cache_get_missing(tmp_path: pathlib.Path) -> None:
    """get of an absent hash returns None."""
    cache = LocalChunkCache(str(tmp_path), max_bytes=1024 * 1024)
    assert cache.get(_HASH_A) is None


@pytest.mark.storage
def test_cache_evicts_lru(tmp_path: pathlib.Path) -> None:
    """Inserting past the budget evicts the least-recently-used entry."""
    # budget: fits exactly two 12-byte chunks
    cache = LocalChunkCache(str(tmp_path), max_bytes=len(_DATA_A) * 2)
    cache.put(_HASH_A, _DATA_A)
    cache.put(_HASH_B, _DATA_B)
    # Adding a third entry must evict the LRU (_HASH_A).
    cache.put(_HASH_C, _DATA_C)
    assert not cache.contains(_HASH_A)
    assert cache.contains(_HASH_B)
    assert cache.contains(_HASH_C)


@pytest.mark.storage
def test_cache_lru_order_updated_on_get(
    tmp_path: pathlib.Path,
) -> None:
    """A get call promotes the entry to MRU, changing eviction order."""
    cache = LocalChunkCache(str(tmp_path), max_bytes=len(_DATA_A) * 2)
    cache.put(_HASH_A, _DATA_A)
    cache.put(_HASH_B, _DATA_B)
    # Access _HASH_A so it becomes MRU; _HASH_B is now LRU.
    cache.get(_HASH_A)
    cache.put(_HASH_C, _DATA_C)
    assert cache.contains(_HASH_A)
    assert not cache.contains(_HASH_B)
    assert cache.contains(_HASH_C)


@pytest.mark.storage
def test_cache_persists_across_instances(
    tmp_path: pathlib.Path,
) -> None:
    """Data and LRU metadata survive across separate LocalChunkCache instances."""
    cache1 = LocalChunkCache(str(tmp_path), max_bytes=1024 * 1024)
    cache1.put(_HASH_A, _DATA_A)
    cache1.put(_HASH_B, _DATA_B)

    cache2 = LocalChunkCache(str(tmp_path), max_bytes=1024 * 1024)
    assert cache2.get(_HASH_A) == _DATA_A
    assert cache2.get(_HASH_B) == _DATA_B


@pytest.mark.storage
def test_null_cache_always_misses() -> None:
    """NullLocalChunkCache always returns False/None and accepts put silently."""
    null = NullLocalChunkCache()
    null.put(_HASH_A, _DATA_A)
    assert not null.contains(_HASH_A)
    assert null.get(_HASH_A) is None


@pytest.mark.storage
def test_protocol_satisfied(tmp_path: pathlib.Path) -> None:
    """Both implementations satisfy LocalChunkCacheProtocol."""
    assert isinstance(NullLocalChunkCache(), LocalChunkCacheProtocol)
    assert isinstance(
        LocalChunkCache(str(tmp_path), max_bytes=1024),
        LocalChunkCacheProtocol,
    )
