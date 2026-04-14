# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Orchestrates all remote storage operations: push, pull, hydrate, dehydrate,
prune, and remote/env listing."""

from __future__ import annotations

import datetime
import json
from copy import deepcopy
from typing import Optional

import click

from config import ConfigMng
from config.config import RemoteCfg
from storage.snapshot import IndexCatalogue, SnapshotManifest
from util import Util

from .backend import RemoteBackend
from .ftp_backend import FTPBackend
from .sftp_backend import SFTPBackend


def _fmt_bytes(n: int) -> str:
    """Return a human-readable byte count (e.g. ``1.2 MiB``)."""
    for unit, threshold in (
        ("GiB", 1 << 30),
        ("MiB", 1 << 20),
        ("KiB", 1 << 10),
    ):
        if n >= threshold:
            return f"{n / threshold:.1f} {unit}"
    return f"{n} B"


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

    def __init__(self, configMng: ConfigMng) -> None:
        self.configMng = configMng

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_remote(self, name: Optional[str]) -> RemoteCfg:
        """Return the named remote, the default, or raise
        :exc:`click.UsageError`.

        :param name: Remote name, or ``None`` to fall back to the default.
        :raises click.UsageError: If the remote cannot be found or no default
            is configured.
        """
        if name:
            cfg = self.configMng.get_remote(name)
            if cfg is None:
                raise click.UsageError(f"Remote '{name}' is not configured.")
            return cfg
        cfg = self.configMng.get_default_remote()
        if cfg is not None:
            return cfg
        remotes = self.configMng.get_remotes()
        if not remotes:
            raise click.UsageError(
                "No remotes configured. Use 'shepctl remote add' first."
            )
        raise click.UsageError(
            "No default remote set and --remote not specified. "
            "Use --remote=<name> or mark one as default with --set-default."
        )

    def _build_backend(self, cfg: RemoteCfg) -> RemoteBackend:
        """Instantiate the transport backend described by *cfg*.

        Resolves ``${VAR}`` placeholders in connection fields before passing
        them to the backend constructor.

        :raises NotImplementedError: For plugin-registered backend types
            (not yet supported in this release).
        :raises click.UsageError: For unknown built-in type strings.
        """
        cfg = deepcopy(cfg)
        cfg.set_resolved()
        host: str = cfg.host or ""
        port: Optional[int] = cfg.port
        user: str = cfg.user or ""
        root_path: str = cfg.root_path or "/"

        if cfg.type == "ftp":
            return FTPBackend(
                host=host,
                port=port if port is not None else 21,
                user=user,
                password=cfg.password or "",
                root_path=root_path,
            )

        if cfg.type == "sftp":
            return SFTPBackend(
                host=host,
                port=port if port is not None else 22,
                user=user,
                password=cfg.password if cfg.password else None,
                identity_file=cfg.identity_file if cfg.identity_file else None,
                root_path=root_path,
            )

        raise click.UsageError(
            f"Unknown remote type '{cfg.type}'. "
            "Built-in types are 'ftp' and 'sftp'. "
            "Plugin-registered backends are not yet supported."
        )

    # ------------------------------------------------------------------
    # Data-returning methods (used by display_* and tests)
    # ------------------------------------------------------------------

    def list_envs(
        self, remote_name: Optional[str] = None
    ) -> tuple[RemoteCfg, IndexCatalogue]:
        """Fetch the global index from *remote_name* and return it.

        Returns an empty :class:`~storage.snapshot.IndexCatalogue` when the
        remote has no index yet (first use).

        :param remote_name: Name of the remote to query, or ``None`` to use the
            default.
        :returns: A ``(RemoteCfg, IndexCatalogue)`` pair.
        """
        remote_cfg = self._resolve_remote(remote_name)
        with self._build_backend(remote_cfg) as backend:
            index_path = backend.index_path()
            if not backend.exists(index_path):
                now = (
                    datetime.datetime.now(datetime.timezone.utc)
                    .isoformat(timespec="seconds")
                    .replace("+00:00", "Z")
                )
                return remote_cfg, IndexCatalogue(updated_at=now)
            raw = backend.download(index_path)
            catalogue = IndexCatalogue.from_dict(json.loads(raw))
        return remote_cfg, catalogue

    def list_snapshots(
        self, env_name: str, remote_name: Optional[str] = None
    ) -> tuple[RemoteCfg, list[SnapshotManifest]]:
        """Fetch all snapshot manifests for *env_name* from *remote_name*.

        :param env_name: Name of the environment to query.
        :param remote_name: Name of the remote to query, or ``None`` to use the
            default.
        :returns: A ``(RemoteCfg, list[SnapshotManifest])`` pair sorted
            newest-first by ``created_at``.
        """
        remote_cfg = self._resolve_remote(remote_name)
        with self._build_backend(remote_cfg) as backend:
            prefix = RemoteBackend.snapshots_prefix(env_name)
            names = backend.list_prefix(prefix)
            manifests: list[SnapshotManifest] = []
            for name in names:
                if not name.endswith(".json"):
                    continue
                raw = backend.download(f"{prefix}/{name}")
                manifests.append(SnapshotManifest.from_dict(json.loads(raw)))
        manifests.sort(key=lambda m: m.created_at, reverse=True)
        return remote_cfg, manifests

    # ------------------------------------------------------------------
    # Display methods (called by CLI commands)
    # ------------------------------------------------------------------

    def display_registered(self) -> None:
        """Render a table of registered remotes from the local config."""
        remotes = self.configMng.get_remotes()
        if not remotes:
            Util.print("No remotes configured.")
            return
        rows = [
            [
                r.name,
                r.type,
                r.host or "",
                "*" if r.is_default() else "",
            ]
            for r in remotes
        ]
        Util.render_table(
            "Remotes",
            [
                {"header": "Name", "style": "cyan"},
                {"header": "Type"},
                {"header": "Host"},
                {"header": "Default"},
            ],
            rows,
        )

    def display_envs(self, remote_name: Optional[str] = None) -> None:
        """Render a table of environments available on *remote_name*."""
        remote_cfg, catalogue = self.list_envs(remote_name)
        if not catalogue.environments:
            Util.print(f"No environments found on remote '{remote_cfg.name}'.")
            return
        rows = [
            [
                env_name,
                entry.latest_snapshot,
                str(entry.snapshot_count),
                entry.last_backup,
                _fmt_bytes(entry.total_size_bytes),
                _fmt_bytes(entry.stored_size_bytes),
            ]
            for env_name, entry in sorted(catalogue.environments.items())
        ]
        Util.render_table(
            f"Environments on '{remote_cfg.name}'",
            [
                {"header": "Env", "style": "cyan"},
                {"header": "Latest Snapshot"},
                {"header": "Snapshots"},
                {"header": "Last Backup"},
                {"header": "Total Size"},
                {"header": "Stored Size"},
            ],
            rows,
        )

    def display_snapshots(
        self, env_name: str, remote_name: Optional[str] = None
    ) -> None:
        """Render a table of snapshots for *env_name* on *remote_name*."""
        remote_cfg, manifests = self.list_snapshots(env_name, remote_name)
        if not manifests:
            Util.print(
                f"No snapshots found for '{env_name}' "
                f"on remote '{remote_cfg.name}'."
            )
            return
        rows = [
            [
                m.snapshot_id,
                m.created_at,
                str(m.chunk_count),
                _fmt_bytes(m.total_size_bytes),
                _fmt_bytes(m.stored_size_bytes),
                ", ".join(m.labels) if m.labels else "",
            ]
            for m in manifests
        ]
        Util.render_table(
            f"Snapshots for '{env_name}' on '{remote_cfg.name}'",
            [
                {"header": "Snapshot ID", "style": "cyan"},
                {"header": "Created At"},
                {"header": "Chunks"},
                {"header": "Total Size"},
                {"header": "Stored Size"},
                {"header": "Labels"},
            ],
            rows,
        )
