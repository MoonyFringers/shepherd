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
import os
import shutil
import subprocess
import tarfile
import threading
from copy import deepcopy
from typing import TYPE_CHECKING, Optional

import click
import zstandard

from config import ConfigMng
from config.config import EnvironmentCfg, RemoteCfg
from storage.chunker import Chunker
from storage.local_cache import LocalChunkCache, NullLocalChunkCache
from storage.snapshot import (
    IndexCatalogue,
    IndexCatalogueEntry,
    LatestPointer,
    SnapshotManifest,
)
from storage.tar_stream import TarStreamProducer
from util import Util

from .backend import RemoteBackend
from .ftp_backend import FTPBackend
from .sftp_backend import SFTPBackend

if TYPE_CHECKING:
    from environment.environment import Environment, EnvironmentMng
    from plugin.runtime import PluginRuntimeMng


def _utcnow() -> str:
    """Return the current UTC time as an ISO-8601 string ending in ``Z``."""
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


class RemoteMng:
    """Coordinates the full remote backup and restore workflow.

    Responsibilities:
    - Build the appropriate :class:`~remote.backend.RemoteBackend` (core
      built-in FTP, or a plugin-registered backend) from a ``RemoteCfg``.
    - Drive the push algorithm: tar stream → chunk → dedup check →
      upload missing chunks → write manifest → update ``latest.json``
      / ``index.json``.
    - Drive pull (first-time download, creates local env entry) and hydrate
      (restore data for an already-registered dehydrated env).
    - Dehydrate: strip local data while keeping the env registered in config.
    - List remote envs and snapshots.
    - Prune orphan chunks.
    """

    def __init__(self, configMng: ConfigMng) -> None:
        self.configMng = configMng
        self._plugin_runtime: Optional[PluginRuntimeMng] = None

    def attach_plugin_runtime(
        self, plugin_runtime: Optional[PluginRuntimeMng]
    ) -> None:
        self._plugin_runtime = plugin_runtime

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
        them to the backend constructor.  After the built-in ``ftp`` /
        ``sftp`` checks the method falls through to the plugin registry;
        plugins receive the resolved ``cfg`` and may read type-specific
        parameters from ``cfg.properties``.

        :raises click.UsageError: For unknown type strings with no matching
            plugin backend.
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

        if self._plugin_runtime is not None:
            backend = self._plugin_runtime.build_remote_backend(cfg.type, cfg)
            if backend is not None:
                return backend
        raise click.UsageError(
            f"Unknown remote type '{cfg.type}'. "
            "Built-in types are 'ftp' and 'sftp'. "
            "Use a plugin to add additional transport backends."
        )

    def _update_index(
        self,
        backend: RemoteBackend,
        env_name: str,
        snapshot_id: str,
        now: str,
        labels: list[str],
        total_size_bytes: int,
        stored_size_bytes: int,
    ) -> None:
        """Fetch, update, and re-upload ``index/index.json``."""
        index_path = RemoteBackend.index_path()
        if backend.exists(index_path):
            catalogue = IndexCatalogue.from_dict(
                json.loads(backend.download(index_path))
            )
        else:
            catalogue = IndexCatalogue(updated_at=now)

        existing = catalogue.environments.get(env_name)
        catalogue.environments[env_name] = IndexCatalogueEntry(
            latest_snapshot=snapshot_id,
            snapshot_count=(existing.snapshot_count + 1 if existing else 1),
            last_backup=now,
            labels=labels,
            total_size_bytes=total_size_bytes,
            stored_size_bytes=stored_size_bytes,
        )
        catalogue.updated_at = now
        backend.upload(
            index_path,
            json.dumps(catalogue.to_dict(), indent=2).encode(),
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
                return remote_cfg, IndexCatalogue(updated_at=_utcnow())
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
    # Push / dehydrate
    # ------------------------------------------------------------------

    def _stop_if_running(
        self, env: Environment, environment_mng: EnvironmentMng
    ) -> None:
        """Prompt the user to stop *env* if any of its services are running.

        Uses :meth:`~environment.environment.Environment.is_running` (which
        queries the concrete backend) rather than the config's
        ``rendered_config`` field, so stale state is never a false positive.

        :raises click.Abort: If the user declines to stop.
        """
        if not env.is_running():
            return
        if not Util.confirm(
            f"Environment '{env.envCfg.tag}' has running services. "
            "Stop it now to proceed?"
        ):
            raise click.Abort()
        environment_mng.stop_env(env.envCfg)

    def push(
        self,
        env_name: str,
        environment_mng: EnvironmentMng,
        remote_name: Optional[str] = None,
        set_tracking: bool = False,
        labels: Optional[list[str]] = None,
    ) -> None:
        """Create a new remote snapshot for *env_name*.

        Streams the environment directory and all host-mounted volumes through
        the FastCDC chunker, uploads only the chunks that are not already
        present on the remote, then writes the snapshot manifest, updates
        ``latest.json``, and refreshes ``index/index.json``.

        :param env_name: Tag of the local environment to push.
        :param environment_mng: Provides access to the concrete
            :class:`~environment.environment.Environment` for streaming and
            for stopping the env if it is currently running.
        :param remote_name: Remote to push to, or ``None`` for the default.
        :param set_tracking: When ``True``, persist *remote_name* as the
            env's ``tracking_remote`` in the local config.
        :param labels: Optional list of ``key=value`` label strings to attach
            to the snapshot manifest.
        :raises click.UsageError: If the env is unknown or dehydrated.
        :raises click.Abort: If the env is running and the user declines to
            stop it.
        """
        env_cfg = self.configMng.get_environment(env_name)
        if env_cfg is None:
            raise click.UsageError(
                f"Environment '{env_name}' not found in local config."
            )
        if env_cfg.dehydrated:
            raise click.UsageError(
                f"Environment '{env_name}' is dehydrated; "
                "restore local data with 'env hydrate' before pushing."
            )

        remote_cfg = self._resolve_remote(remote_name)
        env: Environment = environment_mng.get_environment_from_cfg(env_cfg)
        self._stop_if_running(env, environment_mng)

        producer = TarStreamProducer(
            env_path=env.get_path(),
            volume_streams=env.get_volume_tar_streams(),
        )
        chunker = Chunker(
            min_size=remote_cfg.chunk.min_size_kb * 1024,
            avg_size=remote_cfg.chunk.avg_size_kb * 1024,
            max_size=remote_cfg.chunk.max_size_kb * 1024,
        )

        chunk_hashes: list[str] = []
        total_raw = 0
        total_stored = 0
        uploaded = 0

        with self._build_backend(remote_cfg) as backend:
            # Stream the tar through the chunker in a single pass.
            #
            # Shard listings are fetched lazily the first time a chunk whose
            # shard has not been seen yet arrives.  This preserves the same
            # O(unique_shards) list_prefix RPC count as the previous
            # batch-then-upload approach while eliminating the need to hold
            # every ChunkResult (and its compressed data bytes) in memory
            # simultaneously.  ChunkResult.data is uploaded — or discarded —
            # immediately and never accumulated in a list.
            #
            # list_prefix calls are interleaved with chunk production: if a
            # call blocks, the TarStreamProducer background thread fills the
            # OS pipe buffer and then blocks on write — natural backpressure
            # with no deadlock risk.
            shard_cache: dict[str, set[str]] = {}
            with producer.stream() as stream:
                for chunk in chunker.chunk_stream(stream):
                    shard = chunk.hash[:2]
                    if shard not in shard_cache:
                        shard_cache[shard] = set(
                            backend.list_prefix(f"chunks/{shard}")
                        )
                    chunk_hashes.append(chunk.hash)
                    total_raw += chunk.raw_size
                    total_stored += len(chunk.data)
                    if chunk.hash not in shard_cache[shard]:
                        backend.upload(
                            RemoteBackend.chunk_path(chunk.hash), chunk.data
                        )
                        uploaded += 1

            now = _utcnow()

            # Build manifest (two-pass: need bytes to derive the snapshot id).
            manifest = SnapshotManifest(
                snapshot_id="",  # filled in below
                environment=env_name,
                shepherd_version=self.configMng.constants.APP_VERSION,
                created_at=now,
                chunks=chunk_hashes,
                chunk_count=len(chunk_hashes),
                total_size_bytes=total_raw,
                stored_size_bytes=total_stored,
                labels=list(labels or []),
            )
            manifest_bytes = json.dumps(manifest.to_dict(), indent=2).encode()
            snapshot_id = SnapshotManifest.build_id(now, manifest_bytes)
            manifest.snapshot_id = snapshot_id
            manifest_bytes = json.dumps(manifest.to_dict(), indent=2).encode()

            backend.upload(
                RemoteBackend.snapshot_path(env_name, snapshot_id),
                manifest_bytes,
            )

            pointer = LatestPointer(snapshot_id=snapshot_id, updated_at=now)
            backend.upload(
                RemoteBackend.latest_path(env_name),
                json.dumps(pointer.to_dict()).encode(),
            )

            self._update_index(
                backend,
                env_name,
                snapshot_id,
                now,
                list(labels or []),
                total_raw,
                total_stored,
            )

        if set_tracking:
            env_cfg.tracking_remote = remote_cfg.name
            self.configMng.add_or_set_environment(env_name, env_cfg)

        skipped = len(chunk_hashes) - uploaded
        Util.print(
            f"Pushed '{env_name}' → '{remote_cfg.name}' "
            f"[{snapshot_id}]: "
            f"{uploaded} chunk(s) uploaded, "
            f"{skipped} already present, "
            f"{Util.fmt_bytes(total_stored)} stored."
        )

    def dehydrate(self, env_name: str, environment_mng: EnvironmentMng) -> None:
        """Strip local data for *env_name* while preserving its config entry.

        Removes the environment directory and any bind-mount volume device
        paths declared in the config.  Named Docker volumes are not removed
        (they are managed by the Docker daemon).  After deletion the env's
        ``dehydrated`` flag is set to ``True`` and the config is persisted.

        :param env_name: Tag of the local environment to dehydrate.
        :param environment_mng: Used to check and stop the env if running.
        :raises click.UsageError: If the env is unknown or already dehydrated.
        :raises click.Abort: If the env is running and the user declines to
            stop it.
        """
        env_cfg = self.configMng.get_environment(env_name)
        if env_cfg is None:
            raise click.UsageError(
                f"Environment '{env_name}' not found in local config."
            )
        if env_cfg.dehydrated:
            raise click.UsageError(
                f"Environment '{env_name}' is already dehydrated."
            )

        env: Environment = environment_mng.get_environment_from_cfg(env_cfg)
        self._stop_if_running(env, environment_mng)

        env_dir = os.path.join(self.configMng.config.envs_path, env_name)
        self._delete_dir(env_dir)

        # Also delete bind-mount device paths declared in VolumeCfg.
        for vol in env_cfg.volumes or []:
            if (
                vol.driver == "local"
                and vol.driver_opts
                and vol.driver_opts.get("type") == "none"
                and vol.driver_opts.get("o") == "bind"
            ):
                device = vol.driver_opts.get("device", "")
                if device:
                    self._delete_dir(device)

        env_cfg.dehydrated = True
        self.configMng.add_or_set_environment(env_name, env_cfg)
        Util.print(f"Dehydrated '{env_name}': local data removed.")

    # ------------------------------------------------------------------
    # Pull / hydrate
    # ------------------------------------------------------------------

    def _build_cache(
        self, cfg: RemoteCfg
    ) -> LocalChunkCache | NullLocalChunkCache:
        """Return the configured local chunk cache, or a no-op cache."""
        if cfg.local_cache and cfg.local_cache.path:
            return LocalChunkCache(
                cache_path=cfg.local_cache.path,
                max_bytes=cfg.local_cache.max_size_gb * (1 << 30),
            )
        return NullLocalChunkCache()

    def _resolve_manifest(
        self,
        backend: RemoteBackend,
        env_name: str,
        snapshot_id: Optional[str],
    ) -> SnapshotManifest:
        """Download and return the snapshot manifest for *env_name*.

        If *snapshot_id* is ``None``, the manifest is resolved via
        ``latest.json``.

        :raises click.UsageError: If ``latest.json`` or the manifest file is
            absent on the remote.
        """
        if snapshot_id is None:
            latest_path = RemoteBackend.latest_path(env_name)
            if not backend.exists(latest_path):
                raise click.UsageError(
                    f"No snapshots found for '{env_name}' on the remote."
                )
            pointer = LatestPointer.from_dict(
                json.loads(backend.download(latest_path))
            )
            snapshot_id = pointer.snapshot_id

        manifest_path = RemoteBackend.snapshot_path(env_name, snapshot_id)
        if not backend.exists(manifest_path):
            raise click.UsageError(
                f"Snapshot '{snapshot_id}' not found for '{env_name}'."
            )
        return SnapshotManifest.from_dict(
            json.loads(backend.download(manifest_path))
        )

    def _restore_chunks(
        self,
        backend: RemoteBackend,
        manifest: SnapshotManifest,
        dest_dir: str,
        cache: LocalChunkCache | NullLocalChunkCache,
    ) -> tuple[int, int]:
        """Download, decompress, and untar all chunks into *dest_dir*.

        Uses an OS pipe to connect a producer thread (download → decompress →
        write) to the tarfile reader on the main thread.  This keeps peak RSS
        bounded to roughly one decompressed chunk at a time (~1 MB avg) instead
        of materialising the entire uncompressed archive in an ``io.BytesIO``
        buffer.  ``tarfile.open`` must use streaming mode (``"r|"``) because
        the read end of a pipe does not support seeking.

        Thread-safety note: ``counters`` and ``exc_holder`` are written
        exclusively by ``_feed()`` and read by the main thread only after
        ``t.join()``, so no lock is required — the join provides the
        necessary happens-before guarantee.

        :returns: A ``(downloaded, from_cache)`` tuple counting chunks.
        """
        r_fd, w_fd = os.pipe()
        exc_holder: list[BaseException] = []
        counters = [0, 0]  # [downloaded, from_cache]

        def _feed() -> None:
            dctx = zstandard.ZstdDecompressor()
            try:
                with os.fdopen(w_fd, "wb") as wf:
                    for chunk_hash in manifest.chunks:
                        if (cached := cache.get(chunk_hash)) is not None:
                            compressed = cached
                            counters[1] += 1
                        else:
                            compressed = backend.download(
                                RemoteBackend.chunk_path(chunk_hash)
                            )
                            cache.put(chunk_hash, compressed)
                            counters[0] += 1
                        wf.write(dctx.decompress(compressed))
            except BrokenPipeError:
                # The read end was closed early (e.g. tarfile raised an error
                # on the main thread).  The exception will surface via
                # exc_holder on the main thread instead.
                pass
            except BaseException as exc:
                exc_holder.append(exc)

        t = threading.Thread(target=_feed, daemon=True)
        t.start()
        os.makedirs(dest_dir, exist_ok=True)
        try:
            with os.fdopen(r_fd, "rb") as rf:
                with tarfile.open(fileobj=rf, mode="r|") as tf:
                    tf.extractall(path=dest_dir, filter="data")
        finally:
            t.join()
            if exc_holder:
                raise exc_holder[0]

        return counters[0], counters[1]

    def pull(
        self,
        env_name: str,
        remote_name: Optional[str] = None,
        snapshot_id: Optional[str] = None,
    ) -> None:
        """Create a local environment entry from a remote snapshot.

        Downloads all chunks for *env_name* (or the specific *snapshot_id*),
        reconstructs the tar stream, and untars into the local envs directory.
        A new :class:`~config.config.EnvironmentCfg` entry is created in the
        local config with ``tracking_remote`` set and ``dehydrated = False``.

        :param env_name: Tag of the environment to restore.
        :param remote_name: Remote to pull from, or ``None`` for the default.
        :param snapshot_id: Specific snapshot to restore, or ``None`` for the
            latest.
        :raises click.UsageError: If the env is already registered locally.
        """
        if self.configMng.get_environment(env_name) is not None:
            raise click.UsageError(
                f"Environment '{env_name}' is already registered locally. "
                "Use 'env hydrate' to restore its data."
            )

        remote_cfg = self._resolve_remote(remote_name)
        cache = self._build_cache(remote_cfg)
        dest_dir = os.path.join(self.configMng.config.envs_path, env_name)

        with self._build_backend(remote_cfg) as backend:
            manifest = self._resolve_manifest(backend, env_name, snapshot_id)
            downloaded, from_cache = self._restore_chunks(
                backend, manifest, dest_dir, cache
            )

        env_cfg = EnvironmentCfg(
            tag=env_name,
            template="",
            factory="",
            services=None,
            probes=None,
            networks=None,
            volumes=None,
            tracking_remote=remote_cfg.name,
            dehydrated=False,
        )
        self.configMng.add_or_set_environment(env_name, env_cfg)

        Util.print(
            f"Pulled '{env_name}' ← '{remote_cfg.name}' "
            f"[{manifest.snapshot_id}]: "
            f"{downloaded} chunk(s) downloaded, "
            f"{from_cache} from cache, "
            f"{Util.fmt_bytes(manifest.stored_size_bytes)} stored."
        )

    def hydrate(
        self,
        env_name: str,
        remote_name: Optional[str] = None,
        snapshot_id: Optional[str] = None,
    ) -> None:
        """Restore local data for a dehydrated environment.

        Same chunk-download and untar logic as :meth:`pull`, but the env must
        already exist in config with ``dehydrated = True``.  After restoration,
        ``dehydrated`` is cleared to ``False`` and the config is persisted.

        :param env_name: Tag of the dehydrated environment to restore.
        :param remote_name: Remote to pull from, or ``None`` for the default.
        :param snapshot_id: Specific snapshot to restore, or ``None`` for the
            latest.
        :raises click.UsageError: If the env is unknown or not dehydrated.
        """
        env_cfg = self.configMng.get_environment(env_name)
        if env_cfg is None:
            raise click.UsageError(
                f"Environment '{env_name}' not found in local config."
            )
        if not env_cfg.dehydrated:
            raise click.UsageError(
                f"Environment '{env_name}' is not dehydrated."
            )

        remote_cfg = self._resolve_remote(remote_name)
        cache = self._build_cache(remote_cfg)
        dest_dir = os.path.join(self.configMng.config.envs_path, env_name)

        with self._build_backend(remote_cfg) as backend:
            manifest = self._resolve_manifest(backend, env_name, snapshot_id)
            downloaded, from_cache = self._restore_chunks(
                backend, manifest, dest_dir, cache
            )

        env_cfg.dehydrated = False
        self.configMng.add_or_set_environment(env_name, env_cfg)

        Util.print(
            f"Hydrated '{env_name}' ← '{remote_cfg.name}' "
            f"[{manifest.snapshot_id}]: "
            f"{downloaded} chunk(s) downloaded, "
            f"{from_cache} from cache, "
            f"{Util.fmt_bytes(manifest.stored_size_bytes)} stored."
        )

    # ------------------------------------------------------------------
    # Prune
    # ------------------------------------------------------------------

    def prune(
        self,
        remote_name: Optional[str] = None,
        dry_run: bool = False,
    ) -> None:
        """Delete orphan chunks on *remote_name*.

        A chunk is considered orphaned when no snapshot manifest for any
        environment references it.  Env names are discovered from
        ``index/index.json``; chunks are enumerated by iterating all 256
        two-character hex shards under ``chunks/``.

        :param remote_name: Remote to prune, or ``None`` for the default.
        :param dry_run: When ``True``, report orphans but do not delete them.
        """
        remote_cfg = self._resolve_remote(remote_name)

        with self._build_backend(remote_cfg) as backend:
            # Collect env names from the global index.
            index_path = RemoteBackend.index_path()
            if backend.exists(index_path):
                catalogue = IndexCatalogue.from_dict(
                    json.loads(backend.download(index_path))
                )
                env_names = list(catalogue.environments.keys())
            else:
                env_names = []

            # Collect all chunk hashes referenced by any snapshot.
            referenced: set[str] = set()
            for env_name in env_names:
                prefix = RemoteBackend.snapshots_prefix(env_name)
                for name in backend.list_prefix(prefix):
                    if not name.endswith(".json"):
                        continue
                    raw = backend.download(f"{prefix}/{name}")
                    manifest = SnapshotManifest.from_dict(json.loads(raw))
                    referenced.update(manifest.chunks)

            # Enumerate every stored chunk across all 256 hex shards.
            orphans: list[str] = []
            total = 0
            for shard in (f"{i:02x}" for i in range(256)):
                for chunk_hash in backend.list_prefix(f"chunks/{shard}"):
                    total += 1
                    if chunk_hash not in referenced:
                        orphans.append(chunk_hash)

            # Delete (or dry-run report) orphaned chunks.
            if not dry_run:
                for chunk_hash in orphans:
                    backend.delete(RemoteBackend.chunk_path(chunk_hash))

        action = "would be deleted" if dry_run else "deleted"
        Util.print(
            f"Prune '{remote_cfg.name}': "
            f"{total} chunk(s) scanned, "
            f"{len(orphans)} orphan(s) {action}."
        )

    def _delete_dir(self, path: str) -> None:
        """Delete *path* recursively; retry under sudo on PermissionError."""
        try:
            shutil.rmtree(path)
        except FileNotFoundError:
            pass  # already absent — treat as success
        except PermissionError:
            if os.name != "posix" or not shutil.which("sudo"):
                raise
            uid = os.getuid()
            gid = os.getgid()
            subprocess.run(
                ["sudo", "chown", "-R", f"{uid}:{gid}", path],
                check=True,
            )
            shutil.rmtree(path)

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
                Util.fmt_bytes(entry.total_size_bytes),
                Util.fmt_bytes(entry.stored_size_bytes),
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
                Util.fmt_bytes(m.total_size_bytes),
                Util.fmt_bytes(m.stored_size_bytes),
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
