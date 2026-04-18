# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Shared FakeRemoteBackend fixture for the test suite."""

from __future__ import annotations

import pytest

from remote.backend import RemoteBackend


class FakeRemoteBackend(RemoteBackend):
    """In-memory :class:`~remote.backend.RemoteBackend` for testing.

    Stores all data in a plain ``dict[str, bytes]``.  Can be pre-seeded via
    :meth:`seed` before the test calls into ``RemoteMng``.
    """

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    def seed(self, path: str, data: bytes) -> None:
        """Pre-populate *path* with *data* (test helper)."""
        self._store[path] = data

    # RemoteBackend contract

    def exists(self, path: str) -> bool:
        return path in self._store

    def upload(self, path: str, data: bytes) -> None:
        self._store[path] = data

    def download(self, path: str) -> bytes:
        if path not in self._store:
            raise FileNotFoundError(f"FakeRemoteBackend: no such path: {path}")
        return self._store[path]

    def list_prefix(self, prefix: str) -> list[str]:
        """Return leaf names of all paths that start with *prefix/*."""
        results: list[str] = []
        search = prefix.rstrip("/") + "/"
        for key in self._store:
            if key.startswith(search):
                leaf = key[len(search) :]
                # only one level deep (no nested slashes)
                if "/" not in leaf:
                    results.append(leaf)
        return results

    def delete(self, path: str) -> None:
        self._store.pop(path, None)

    def close(self) -> None:
        pass


@pytest.fixture
def fake_remote_backend() -> FakeRemoteBackend:
    """Fresh in-memory remote backend for each test."""
    return FakeRemoteBackend()
