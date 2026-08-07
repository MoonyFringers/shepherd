# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Built-in OCI registry remote storage backend.

Maps the passive key/value ``RemoteBackend`` contract onto an OCI
container registry's native content-addressed blob store (the same
protocol ``docker push``/``docker pull`` use).

Chunk objects (``chunks/<shard>/<hash>``) are stored as **bare blobs**:
the path already embeds the chunk's SHA-256 hash, which *is* its OCI
blob digest, so no manifest or tag is created per chunk. Because OCI
registries expose no blob-listing API, a small per-shard index object
(``chunks/<shard>/.index.json``) is maintained to support
``list_prefix`` (used by push-time dedup checks and ``prune``).

Every other path (snapshot manifests, ``latest.json``, ``index.json``,
the per-shard index itself) keeps the original model: a small
single-layer OCI artifact tagged with a translated form of the path.

Additionally, whenever a snapshot manifest is written
(``envs/<env>/snapshots/<id>.json``), this backend assembles and pushes
one real multi-layer OCI image for that snapshot — layers are the
snapshot's chunk blobs, in order — under an immutable per-snapshot tag
and a mutable per-environment ``:latest``-style tag. This is a genuine
``docker pull``/``crane manifest``-able artifact (registry-native
dedup applies to its layers directly) but is not runnable: layers are
opaque zstd-compressed FastCDC chunks, not real tar diffs, so
``docker run``/``docker save`` would not produce a coherent
filesystem. It exists for registry-native storage/dedup visibility and
interoperability, not execution. See ADR-0007.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Optional, cast

import requests

from storage.snapshot import SnapshotManifest

from .backend import RemoteBackend

_EMPTY_CONFIG_BYTES = b"{}"
_EMPTY_CONFIG_DIGEST = (
    f"sha256:{hashlib.sha256(_EMPTY_CONFIG_BYTES).hexdigest()}"
)
_CONFIG_MEDIA_TYPE = "application/vnd.shepherd.remote.config.v1+json"
_LAYER_MEDIA_TYPE = "application/vnd.shepherd.remote.object.v1"
_MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"

_CHUNK_PATH_RE = re.compile(r"^chunks/[0-9a-f]{2}/([0-9a-f]{64})(?:\.tmp)?$")
_CHUNK_SHARD_RE = re.compile(r"^chunks/([0-9a-f]{2})$")
_SNAPSHOT_MANIFEST_RE = re.compile(r"^envs/[^/]+/snapshots/[^/]+\.json$")

_INDEX_WRITE_ATTEMPTS = 5


def _chunk_digest_from_path(path: str) -> Optional[str]:
    """Return the ``sha256:<hash>`` blob digest encoded in *path*.

    Chunk paths embed their own content hash (see
    :meth:`RemoteBackend.chunk_path`), so the digest never requires a
    manifest lookup. Returns ``None`` for non-chunk paths.
    """
    m = _CHUNK_PATH_RE.match(path)
    return f"sha256:{m.group(1)}" if m else None


def _chunk_shard_from_prefix(prefix: str) -> Optional[str]:
    """Return the 2-hex shard if *prefix* is a chunk-shard prefix."""
    m = _CHUNK_SHARD_RE.match(prefix)
    return m.group(1) if m else None


def _path_to_tag(path: str) -> str:
    """Translate a backend path into a valid OCI tag.

    OCI tag names are restricted to ``[A-Za-z0-9_][A-Za-z0-9._-]*``. Every
    path this backend stores uses ``/`` as a directory separator
    (mirroring the FTP/SFTP layout) and snapshot ids embed an ISO-8601
    UTC timestamp containing ``:`` (see ``SnapshotManifest.build_id`` in
    ``storage/snapshot.py``) — both characters are illegal in a tag.
    Both are replaced with ``_``. This is a one-way mapping (not required
    to round-trip: tags are looked up by exact translated string, never
    parsed back into a path), so a real ``_`` in a path and an escaped
    ``/`` or ``:`` are indistinguishable, which is harmless here.
    """
    return path.replace("/", "_").replace(":", "_")


class RegistryBackend(RemoteBackend):
    """OCI registry remote backend.

    Chunk objects are bare, untagged blobs: a chunk's SHA-256 hash
    (already computed by :class:`~storage.chunker.Chunker` over the
    compressed bytes) *is* its OCI blob digest and is encoded directly
    in its path, so ``exists()``/``download()`` for chunk paths resolve
    the digest without any manifest lookup, and ``upload()`` stops
    after the blob PUT — no per-chunk manifest or tag is created.

    All other objects (snapshot manifests, pointers, the global index,
    and the per-shard chunk index described below) keep the original
    model: a small single-layer OCI artifact tagged with a translated
    form of its backend path (see :func:`_path_to_tag`).

    ``list_prefix`` has no direct OCI equivalent (registries have no
    blob- or tag-listing API beyond the repository's flat tag list).
    For non-chunk prefixes it is implemented via the tag-list endpoint
    (``GET /v2/<repo>/tags/list``), filtered by the translated prefix —
    this keeps ``shepctl remote get`` (snapshot enumeration) working
    exactly as it does against FTP/SFTP. For a chunk-shard prefix
    (``chunks/<shard>``) it instead reads a small per-shard index blob
    (``chunks/<shard>/.index.json``, itself stored via the ordinary
    tagged-artifact path since it isn't chunk-shaped), which this
    backend keeps in sync as chunks are confirmed (``rename()``) or
    removed (``delete()``). Index updates are buffered in memory and
    flushed once per touched shard in :meth:`close`, so a push that
    touches many chunks in the same shard costs one index write, not
    one per chunk. The flush uses an optimistic-concurrency recheck
    (see :meth:`_write_shard_index`) to avoid silently undoing a
    concurrent session's update to the same shard — the OCI
    distribution spec has no atomic compare-and-swap for tags, so this
    narrows but does not fully eliminate that race.

    Writing a snapshot manifest (``envs/<env>/snapshots/<id>.json``)
    additionally assembles a real multi-layer OCI image for that
    snapshot (layers = the manifest's chunk blobs, in order) under an
    immutable per-snapshot tag and a mutable per-environment ``latest``
    tag. See the module docstring and ADR-0007.

    Parameters
    ----------
    host:
        Registry host, optionally including a port (e.g.
        ``registry.example.com:5000``).
    user:
        Registry username (optional; used for Basic auth and to resolve
        Bearer token challenges).
    password:
        Registry password or access token (optional; supports
        ``${VAR}`` resolved before construction).
    root_path:
        Repository name (OCI ``<name>`` path component) under which all
        objects for this remote are stored, e.g. ``myorg/shepherd``.
    insecure:
        When ``True``, connect over plain HTTP instead of HTTPS (for
        local/test registries such as ``registry:2`` without TLS).
    """

    def __init__(
        self,
        host: str,
        user: str = "",
        password: str = "",
        root_path: str = "shepherd",
        insecure: bool = False,
    ) -> None:
        self._repo = root_path.strip("/") or "shepherd"
        scheme = "http" if insecure else "https"
        self._base = f"{scheme}://{host}/v2/{self._repo}"
        self._user = user
        self._password = password
        self._session = requests.Session()
        # Cache of Bearer tokens keyed by the (realm, service, scope)
        # challenge tuple, so repeated requests against the same scope
        # do not each re-authenticate.
        self._token_cache: dict[tuple[str, str, str], str] = {}
        # Sizes of blobs uploaded (or confirmed present) this session,
        # so assembling a snapshot image doesn't re-HEAD a blob this
        # same push just wrote.
        self._known_blob_sizes: dict[str, int] = {}
        # Per-shard chunk-hash adds/removes not yet flushed to the
        # shard's .index.json (see _flush_shard_indexes / close()).
        self._pending_index_adds: dict[str, set[str]] = {}
        self._pending_index_removes: dict[str, set[str]] = {}

    # ------------------------------------------------------------------
    # RemoteBackend implementation
    # ------------------------------------------------------------------

    def exists(self, path: str) -> bool:
        digest = _chunk_digest_from_path(path) or self._resolve_digest(path)
        if digest is None:
            return False
        resp = self._request("HEAD", f"/blobs/{digest}")
        return resp.status_code == 200

    def upload(self, path: str, data: bytes) -> None:
        digest = f"sha256:{hashlib.sha256(data).hexdigest()}"
        if not self._blob_exists(digest):
            self._upload_blob(data, digest)
        self._known_blob_sizes[digest] = len(data)

        if _chunk_digest_from_path(path) is not None:
            # Bare content-addressed blob only — no manifest, no tag.
            if not path.endswith(".tmp"):
                # Final chunk path (not a staging .tmp path, so no
                # rename() will follow to confirm it) — index it as
                # enumerable immediately.
                shard, chunk_hash = self._shard_and_hash(path)
                self._pending_index_adds.setdefault(shard, set()).add(
                    chunk_hash
                )
                self._pending_index_removes.get(shard, set()).discard(
                    chunk_hash
                )
            return

        if not self._blob_exists(_EMPTY_CONFIG_DIGEST):
            self._upload_blob(_EMPTY_CONFIG_BYTES, _EMPTY_CONFIG_DIGEST)
        tag = _path_to_tag(path)
        self._put_manifest(
            tag,
            json.dumps(self._build_manifest(digest, len(data), tag)).encode(),
        )

        if _SNAPSHOT_MANIFEST_RE.match(path):
            self._push_snapshot_image(data)

    def download(self, path: str) -> bytes:
        digest = _chunk_digest_from_path(path) or self._resolve_digest(path)
        if digest is None:
            raise FileNotFoundError(path)
        resp = self._request("GET", f"/blobs/{digest}")
        resp.raise_for_status()
        return resp.content

    def list_prefix(self, prefix: str) -> list[str]:
        shard = _chunk_shard_from_prefix(prefix)
        if shard is not None:
            return self._effective_shard_index(shard)
        tag_prefix = _path_to_tag(prefix)
        if tag_prefix and not tag_prefix.endswith("_"):
            tag_prefix = f"{tag_prefix}_"
        names: list[str] = []
        url: Optional[str] = f"{self._base}/tags/list?n=1000"
        while url is not None:
            resp = self._request_absolute("GET", url)
            if resp.status_code == 404:
                break
            resp.raise_for_status()
            body: dict[str, Any] = resp.json()
            tags = cast("list[str]", body.get("tags") or [])
            for tag in tags:
                if tag.startswith(tag_prefix):
                    names.append(tag[len(tag_prefix) :])
            url = self._next_page_url(resp)
        return names

    def delete(self, path: str) -> None:
        chunk_digest = _chunk_digest_from_path(path)
        if chunk_digest is not None:
            resp = self._request("DELETE", f"/blobs/{chunk_digest}")
            if resp.status_code not in (200, 202, 404, 405):
                resp.raise_for_status()
            shard, chunk_hash = self._shard_and_hash(path)
            self._pending_index_removes.setdefault(shard, set()).add(chunk_hash)
            self._pending_index_adds.get(shard, set()).discard(chunk_hash)
            return

        tag = _path_to_tag(path)
        digest = self._manifest_digest(tag)
        if digest is None:
            return
        resp = self._request("DELETE", f"/manifests/{digest}")
        # Many registries (notably Docker Hub) disable manifest/blob
        # deletion entirely without a separate GC pass. Mirror the
        # FTP/SFTP backends' "best effort, ignore missing" stance for
        # anything short of an unexpected server error.
        if resp.status_code not in (200, 202, 404, 405):
            resp.raise_for_status()

    def rename(self, src_path: str, dst_path: str) -> None:
        if _chunk_digest_from_path(src_path) is not None:
            # Content-addressed: upload(tmp_path, data) already wrote
            # the blob at its permanent digest (tmp and final paths
            # share the same hash) — there is nothing to move. Record
            # the chunk as confirmed/enumerable in its shard index.
            shard, chunk_hash = self._shard_and_hash(dst_path)
            self._pending_index_adds.setdefault(shard, set()).add(chunk_hash)
            self._pending_index_removes.get(shard, set()).discard(chunk_hash)
            return

        # Every other stored path (pointer/manifest) is tagged
        # individually (see _path_to_tag), so upload(tmp_path, ...)
        # leaves the content reachable only under the .tmp tag — the
        # underlying blob upload is atomic, but the *tag* pointing at it
        # still needs to move. Re-tag by re-pushing the manifest under
        # the destination tag (registry tag writes are atomic), then
        # remove the source tag.
        if self._resolve_digest(src_path) is None:
            return
        data = self.download(src_path)
        self.upload(dst_path, data)
        self.delete(src_path)

    def close(self) -> None:
        self._flush_shard_indexes()
        self._session.close()

    # ------------------------------------------------------------------
    # Chunk-path helpers
    # ------------------------------------------------------------------

    def _shard_and_hash(self, chunk_path: str) -> tuple[str, str]:
        m = _CHUNK_PATH_RE.match(chunk_path)
        assert m is not None, chunk_path
        return chunk_path.split("/")[1], m.group(1)

    # ------------------------------------------------------------------
    # Per-shard chunk index (list_prefix / prune enumeration)
    # ------------------------------------------------------------------

    def _shard_index_path(self, shard: str) -> str:
        return f"chunks/{shard}/.index.json"

    def _read_persisted_shard_index(self, shard: str) -> list[str]:
        path = self._shard_index_path(shard)
        digest = self._resolve_digest(path)
        if digest is None:
            return []
        resp = self._request("GET", f"/blobs/{digest}")
        resp.raise_for_status()
        return cast("list[str]", json.loads(resp.content))

    def _effective_shard_index(self, shard: str) -> list[str]:
        current = set(self._read_persisted_shard_index(shard))
        current |= self._pending_index_adds.get(shard, set())
        current -= self._pending_index_removes.get(shard, set())
        return sorted(current)

    def _upload_index_blob(self, entries: list[str]) -> tuple[str, bytes]:
        data = json.dumps(entries).encode()
        digest = f"sha256:{hashlib.sha256(data).hexdigest()}"
        if not self._blob_exists(digest):
            self._upload_blob(data, digest)
        if not self._blob_exists(_EMPTY_CONFIG_DIGEST):
            self._upload_blob(_EMPTY_CONFIG_BYTES, _EMPTY_CONFIG_DIGEST)
        return digest, data

    def _write_shard_index(self, shard: str) -> None:
        """Write *shard*'s merged index, retrying under contention.

        The OCI distribution spec has no atomic compare-and-swap for
        manifest tags, so a plain read-merge-write here can silently
        undo a concurrent session's update to the same shard (e.g. this
        push's flush racing a concurrent ``prune()`` that just deleted a
        chunk from this shard). Immediately before writing, re-check
        that the index tag hasn't moved since we read it; if it has,
        retry with a fresh read/merge instead of blindly overwriting the
        concurrent change. This narrows the race to the single HTTP
        round trip between that recheck and the write, rather than the
        whole read-merge-write sequence — not a full fix (no CAS
        primitive is available to close it entirely), but a large
        reduction in the window during which a lost update can occur.
        """
        tag = _path_to_tag(self._shard_index_path(shard))
        for _ in range(_INDEX_WRITE_ATTEMPTS - 1):
            base_digest = self._manifest_digest(tag)
            entries = self._effective_shard_index(shard)
            digest, data = self._upload_index_blob(entries)
            if self._manifest_digest(tag) != base_digest:
                continue  # raced by a concurrent writer — retry
            self._put_manifest(
                tag,
                json.dumps(
                    self._build_manifest(digest, len(data), tag)
                ).encode(),
            )
            return
        # Retry budget exhausted under heavy contention: write once more,
        # unconditionally, rather than silently dropping this session's
        # update. This risks the same class of lost update the loop
        # above was narrowing, not a new one — a later flush from any
        # session reconciles further changes.
        entries = self._effective_shard_index(shard)
        digest, data = self._upload_index_blob(entries)
        self._put_manifest(
            tag,
            json.dumps(self._build_manifest(digest, len(data), tag)).encode(),
        )

    def _flush_shard_indexes(self) -> None:
        shards = set(self._pending_index_adds) | set(
            self._pending_index_removes
        )
        for shard in shards:
            self._write_shard_index(shard)
        self._pending_index_adds.clear()
        self._pending_index_removes.clear()

    # ------------------------------------------------------------------
    # Per-snapshot OCI image
    # ------------------------------------------------------------------

    def _snapshot_image_tag(self, env_name: str, snapshot_id: str) -> str:
        return _path_to_tag(f"images/{env_name}/{snapshot_id}")

    def _snapshot_latest_image_tag(self, env_name: str) -> str:
        return _path_to_tag(f"images/{env_name}/latest")

    def _blob_size(self, digest: str) -> int:
        if digest in self._known_blob_sizes:
            return self._known_blob_sizes[digest]
        resp = self._request("HEAD", f"/blobs/{digest}")
        resp.raise_for_status()
        size = int(resp.headers.get("Content-Length", "0"))
        self._known_blob_sizes[digest] = size
        return size

    def _push_snapshot_image(self, manifest_data: bytes) -> None:
        """Assemble and push the multi-layer OCI image for a snapshot.

        Called from :meth:`upload` right after a snapshot manifest
        (``envs/<env>/snapshots/<id>.json``) is written. Layers are the
        snapshot's chunk blobs, in the same order as
        ``SnapshotManifest.chunks`` — all already pushed as bare blobs
        by earlier ``upload()`` calls in the same push.
        """
        snapshot = SnapshotManifest.from_dict(json.loads(manifest_data))
        layers: list[dict[str, Any]] = []
        for chunk_hash in snapshot.chunks:
            digest = f"sha256:{chunk_hash}"
            layers.append(
                {
                    "mediaType": _LAYER_MEDIA_TYPE,
                    "digest": digest,
                    "size": self._blob_size(digest),
                }
            )
        image_manifest = self._build_snapshot_image_manifest(layers)
        manifest_bytes = json.dumps(image_manifest).encode()
        self._put_manifest(
            self._snapshot_image_tag(
                snapshot.environment, snapshot.snapshot_id
            ),
            manifest_bytes,
        )
        self._put_manifest(
            self._snapshot_latest_image_tag(snapshot.environment),
            manifest_bytes,
        )

    def _build_snapshot_image_manifest(
        self, layers: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {
            "schemaVersion": 2,
            "mediaType": _MANIFEST_MEDIA_TYPE,
            "config": {
                "mediaType": _CONFIG_MEDIA_TYPE,
                "digest": _EMPTY_CONFIG_DIGEST,
                "size": len(_EMPTY_CONFIG_BYTES),
            },
            "layers": layers,
        }

    # ------------------------------------------------------------------
    # OCI manifest helpers
    # ------------------------------------------------------------------

    def _put_manifest(self, tag: str, manifest_bytes: bytes) -> None:
        resp = self._request(
            "PUT",
            f"/manifests/{tag}",
            data=manifest_bytes,
            headers={"Content-Type": _MANIFEST_MEDIA_TYPE},
        )
        resp.raise_for_status()

    def _build_manifest(
        self, digest: str, size: int, tag: str
    ) -> dict[str, Any]:
        # The manifest embeds its own tag as an annotation so that two
        # tags pointing at byte-identical content (e.g. the .tmp and
        # final tags for the same chunk during push, or two distinct
        # chunks that happen to compress to the same bytes) never
        # collide on the same manifest digest. Digest-based delete
        # (DELETE /manifests/<digest>) removes every tag pointing at
        # that digest, not just one — a collision here would let
        # deleting one tag silently take a second, unrelated tag with
        # it. See delete()/rename() for the corresponding safety notes.
        return {
            "schemaVersion": 2,
            "mediaType": _MANIFEST_MEDIA_TYPE,
            "config": {
                "mediaType": _CONFIG_MEDIA_TYPE,
                "digest": _EMPTY_CONFIG_DIGEST,
                "size": len(_EMPTY_CONFIG_BYTES),
            },
            "layers": [
                {
                    "mediaType": _LAYER_MEDIA_TYPE,
                    "digest": digest,
                    "size": size,
                }
            ],
            "annotations": {"com.moonyfringers.shepherd.tag": tag},
        }

    def _resolve_digest(self, path: str) -> Optional[str]:
        """Return the blob digest referenced by *path*'s tag manifest."""
        tag = _path_to_tag(path)
        resp = self._request(
            "GET",
            f"/manifests/{tag}",
            headers={"Accept": _MANIFEST_MEDIA_TYPE},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        manifest: dict[str, Any] = resp.json()
        layers = cast("list[dict[str, Any]]", manifest.get("layers") or [])
        if not layers:
            return None
        return cast(str, layers[0]["digest"])

    def _manifest_digest(self, tag: str) -> Optional[str]:
        """Return the manifest's own digest (for delete-by-digest)."""
        resp = self._request(
            "GET",
            f"/manifests/{tag}",
            headers={"Accept": _MANIFEST_MEDIA_TYPE},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.headers.get("Docker-Content-Digest")

    def _blob_exists(self, digest: str) -> bool:
        resp = self._request("HEAD", f"/blobs/{digest}")
        return resp.status_code == 200

    def _upload_blob(self, data: bytes, digest: str) -> None:
        # Single monolithic PUT: initiate the upload session, then push
        # the entire blob in one request with the digest attached.
        # Chunk sizes here (avg 2 MB, max 8 MB) are comfortably within
        # what registries accept as a single PUT.
        start = self._request("POST", "/blobs/uploads/")
        start.raise_for_status()
        location = start.headers["Location"]
        put_url = self._with_query(location, {"digest": digest})
        resp = self._request_absolute(
            "PUT",
            put_url,
            data=data,
            headers={"Content-Type": "application/octet-stream"},
        )
        resp.raise_for_status()

    def _with_query(self, url: str, params: dict[str, str]) -> str:
        sep = "&" if "?" in url else "?"
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{url}{sep}{query}"

    def _next_page_url(self, resp: requests.Response) -> Optional[str]:
        link = resp.links.get("next")
        if link is None:
            return None
        href = link.get("url")
        if href is None:
            return None
        if href.startswith("http"):
            return href
        # Relative Link header (e.g. "/v2/<repo>/tags/list?...").
        base = self._base.split("/v2/", 1)[0]
        return f"{base}{href}"

    # ------------------------------------------------------------------
    # HTTP + auth
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        data: Optional[bytes] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> requests.Response:
        return self._request_absolute(
            method, f"{self._base}{path}", data=data, headers=headers
        )

    def _request_absolute(
        self,
        method: str,
        url: str,
        data: Optional[bytes] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> requests.Response:
        resp = self._session.request(method, url, data=data, headers=headers)
        if resp.status_code == 401:
            token = self._authenticate(resp)
            if token is not None:
                auth_headers = dict(headers or {})
                auth_headers["Authorization"] = f"Bearer {token}"
                resp = self._session.request(
                    method, url, data=data, headers=auth_headers
                )
        return resp

    def _authenticate(self, challenge: requests.Response) -> Optional[str]:
        """Resolve a ``WWW-Authenticate: Bearer`` challenge into a token.

        Implements the standard Docker Registry v2 token auth flow: the
        registry's 401 response names a token *realm*, *service*, and
        *scope*; the client fetches a short-lived Bearer token from the
        realm (optionally using Basic auth credentials) and retries the
        original request with it attached.
        """
        header = challenge.headers.get("WWW-Authenticate", "")
        if not header.lower().startswith("bearer "):
            return None
        params = self._parse_bearer_challenge(header)
        realm = params.get("realm")
        if realm is None:
            return None
        service = params.get("service", "")
        scope = params.get("scope", "")
        cache_key = (realm, service, scope)
        if cache_key in self._token_cache:
            return self._token_cache[cache_key]

        query: dict[str, str] = {}
        if service:
            query["service"] = service
        if scope:
            query["scope"] = scope
        auth = (self._user, self._password) if self._user else None
        resp = self._session.get(realm, params=query, auth=auth)
        resp.raise_for_status()
        body: dict[str, Any] = resp.json()
        token = body.get("token") or body.get("access_token")
        if token is None:
            return None
        self._token_cache[cache_key] = token
        return token

    @staticmethod
    def _parse_bearer_challenge(header: str) -> dict[str, str]:
        """Parse a ``Bearer realm="...",service="...",scope="..."`` header."""
        raw = header[len("Bearer ") :]
        params: dict[str, str] = {}
        for part in raw.split(","):
            if "=" not in part:
                continue
            key, _, value = part.strip().partition("=")
            params[key.strip()] = value.strip().strip('"')
        return params
