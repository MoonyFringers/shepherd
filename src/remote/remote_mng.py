# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Orchestrates all remote storage operations: push, pull, hydrate, dehydrate,
prune, and remote/env listing."""

from __future__ import annotations


class RemoteMng:
    """Coordinates the full remote backup and restore workflow.

    Responsibilities:
    - Build the appropriate :class:`~remote.backend.RemoteBackend` (core
      built-in FTP, or a plugin-registered backend) from a ``RemoteCfg``.
    - Drive the push algorithm: tar stream → chunk → dedup check → upload
      missing chunks → write manifest → update ``latest.json`` / ``index.json``.
    - Drive pull (first-time download, creates local env entry) and hydrate
      (restore data for an already-registered dehydrated env).
    - Dehydrate: strip local data while keeping the env registered in config.
    - List remote envs and snapshots.
    - Prune orphan chunks.
    """

    def __init__(self) -> None:
        raise NotImplementedError  # TODO: Issues 8–10
