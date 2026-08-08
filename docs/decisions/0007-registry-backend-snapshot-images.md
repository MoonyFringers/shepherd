---
status: "accepted"
date: 2026-08-08
decision-makers:
  - '@giubacc'
---

# Registry Backend: Bare Chunk Blobs + Per-Snapshot OCI Images

Supersedes: ADR-0006 (registry-transport section only). ADR-0006's
chunking algorithm and FTP/SFTP transports remain fully accepted and
are unaffected by this ADR — ADRs are immutable records, so ADR-0006's
body is not edited; only its `status` frontmatter now points here.

## Context and Problem Statement

ADR-0006 added an OCI registry transport that maps every path the
`RemoteBackend` contract stores — every chunk, every snapshot
manifest, `latest.json`, `index.json` — onto its own single-layer OCI
artifact, tagged with a translated form of the path. This satisfies
the contract, but wastes what makes a registry different from a plain
KV store: one environment push produces thousands of tiny fake
"images" (one manifest + one tag per chunk), none of which is a real,
inspectable artifact, and none of which benefits from the registry's
own image/layer model beyond blob-level content addressing that
FTP/SFTP-style dedup already provided by construction.

How do we keep the chunk-level dedup that makes repeated backups cheap
(ADR-0006) while producing a registry-native artifact that is actually
meaningful to registry tooling — pullable, inspectable, and subject to
the registry's own layer/image conventions — instead of a pile of
disposable per-chunk tags?

## Decision Drivers

- Minimize wasted manifest/tag churn: one manifest+tag write per chunk
  does not scale and adds no value over a bare blob.
- Produce a real multi-layer OCI image per snapshot, so
  `docker pull`/`crane manifest`/registry UIs show something
  meaningful, not thousands of disposable one-layer tags.
- Preserve the existing dedup granularity: unchanged data between two
  pushes must not be retransmitted, same as ADR-0006's guarantee for
  FTP/SFTP.
- Zero changes to `RemoteMng`, the `RemoteBackend` ABC, or the
  FTP/SFTP backends — this is a `RegistryBackend`-only change.
- OCI registries expose no blob-listing API, only a per-repository
  tag list — removing per-chunk tags removes the only mechanism
  `list_prefix("chunks/<shard>")` had to enumerate chunks, and
  `RemoteMng`'s push-time dedup check and `prune`'s orphan scan both
  depend on it with no fallback.

## Considered Options

- Keep per-chunk tagging (status quo from ADR-0006) — rejected; this
  ADR exists because that design is the problem being solved.
- Push one single-layer image per environment, whole tar as one blob —
  rejected; dedup would only fire when two environments are
  byte-identical as a whole, regressing ADR-0006's core guarantee that
  only changed data is retransmitted.
- Bare content-addressed chunk blobs (no tag) + one multi-layer OCI
  image per snapshot (layers = chunk blobs, in order) + a per-shard
  index object to replace tag-list-based chunk enumeration — chosen.
- Bare chunk blobs with no enumeration support at all, relying on a
  per-chunk `exists()` instead of batched `list_prefix` — rejected;
  would require changing `RemoteMng`'s push loop (out of scope) and is
  far chattier than a shard-index read.

## Decision Outcome

Chosen option: **bare chunk blobs + per-snapshot OCI image + per-shard
index**, because it eliminates per-chunk tag overhead, produces a real
pullable artifact per snapshot, and requires no changes outside
`RegistryBackend`.

### Chunk objects become bare blobs

A chunk's path (`chunks/<shard>/<hash>`) already embeds its SHA-256
hash, which *is* its OCI blob digest — this invariant holds for every
real chunk path, since `RemoteMng`/`Chunker` always compute the path
from the actual content hash before calling `upload`. `exists()` and
`download()` for chunk paths resolve the digest straight from the
path, with no manifest lookup. `upload()` for a chunk path stops after
the blob PUT — no manifest, no tag. `delete()` issues a direct blob
`DELETE`. `rename()` becomes a no-op on the blob itself (the tmp and
final paths share the same hash/digest, so there is nothing to move) —
a significant simplification and performance win over the previous
download+upload+delete dance.

### Per-shard chunk index

Since chunks are no longer tagged, `list_prefix("chunks/<shard>")` can
no longer use the tag-list endpoint. A small JSON blob per shard,
`chunks/<shard>/.index.json`, stored through the ordinary
tagged-artifact path (it isn't chunk-shaped, so no special-casing is
needed there), tracks which chunk hashes exist in that shard.
`RegistryBackend` buffers adds/removes in memory as chunks are
confirmed (`rename()`, or `upload()` directly to a non-`.tmp` chunk
path) or removed (`delete()`), and flushes once per touched shard in
`close()` — the one lifecycle hook `RemoteMng` always invokes via
`with backend:` for every push/pull/hydrate/prune operation. This
turns O(new chunks) index writes into O(touched shards).

### Per-snapshot OCI image

Writing a snapshot manifest (`envs/<env>/snapshots/<id>.json`)
additionally assembles one real multi-layer OCI image: layers are the
manifest's chunk blobs, in the same order as `SnapshotManifest.chunks`,
each already present as a bare blob from earlier in the same push.
This image is pushed under two tags: an immutable per-snapshot tag
(`images/<env>/<snapshot_id>`, translated) and a mutable
per-environment tag (`images/<env>/latest`, translated) repointed on
every push — mirroring `latest.json`'s role, so
`docker pull <repo>:<env>-latest`-style access just works. The
synthetic `images/` path namespace cannot collide with any real KV
path.

The image is a genuine `docker pull`/`crane manifest`-able artifact —
registry-native layer dedup applies to it directly — but it is **not
runnable**: layers are opaque zstd-compressed FastCDC chunks, not real
tar diffs, so `docker run`/`docker save` would not produce a coherent
filesystem. It exists for registry-native storage/dedup visibility and
interoperability, not execution.

The existing per-snapshot manifest JSON object
(`envs/<env>/snapshots/<id>.json`) is unchanged and continues to serve
as the cheap metadata sidecar for `shepctl remote get`/listing,
without ever touching the big image.

### Consequences

- Good, because per-push manifest/tag writes drop from O(chunks) to
  O(touched shards) + O(1) image assembly — the dominant waste in the
  previous design is gone.
- Good, because each snapshot now has a real, inspectable,
  `docker pull`-able artifact instead of thousands of disposable tags.
- Good, because `rename()` for chunks becomes a no-op instead of a
  download+upload+delete round trip, and `delete()` for chunks becomes
  a direct blob delete instead of a manifest-digest lookup first.
- Good, because `RemoteMng`, the `RemoteBackend` ABC, and FTP/SFTP are
  completely untouched.
- Neutral, because assembling a snapshot's image costs one `HEAD` per
  chunk that was a dedup hit this push (to learn its size for the
  layer descriptor) — bounded, one-time cost at manifest-upload time.
- Neutral, because a crash between uploading new chunks and `close()`
  flushing the shard index leaves those chunks temporarily invisible
  to `list_prefix`/`prune` within a *single* session. This is
  self-healing (a later push re-PUTs an idempotent, already-present
  digest) and non-corrupting for that single-session-crash scenario.
- Bad, because the OCI distribution spec has no atomic compare-and-swap
  for manifest tags, so the shard-index flush (`_write_shard_index`) is
  fundamentally a read-merge-write against shared state. Two backend
  sessions racing on the *same shard* — e.g. a `push()`'s flush and a
  concurrent `prune()`'s deletion — can still interleave in a way that
  resurrects an already-deleted hash if both land within the same
  narrow window. `_write_shard_index` mitigates this with an
  optimistic-concurrency recheck immediately before the write (retried
  up to `_INDEX_WRITE_ATTEMPTS`), which shrinks the race from the whole
  read-merge-write sequence down to a single HTTP round trip, but does
  not eliminate it — this is a real, if narrow, gap in the "multiple
  clients may write concurrently without corrupting data" driver from
  ADR-0006, specific to the shard-index mechanism this ADR introduces
  (FTP/SFTP and the chunk/manifest objects themselves have no
  equivalent derived-state race).
- Bad, because the per-shard `.index.json` is one more piece of
  derived state that must stay consistent with actual blob presence;
  consistency is maintained solely by `delete()`/`rename()`/`upload()`
  on chunk paths, so any future code path that writes/removes chunk
  blobs without going through those methods would need to keep it in
  sync too.
- Bad (forward-looking gap), because `RemoteMng` has no
  snapshot-deletion feature today — `prune()` only removes orphan
  chunks, snapshot manifests are kept forever — so nothing currently
  deletes a per-snapshot image tag or repoints `:latest` when a
  snapshot is forgotten. A future `shepctl remote forget <snapshot>`
  (or similar) would need to also delete the per-snapshot image tag
  and, if that snapshot was newest, repoint (or remove) the `:latest`
  tag. Not implemented as part of this change.

### Confirmation

- `shepctl env push` twice in a row against a registry remote uploads
  zero new chunks on the second push (same guarantee as ADR-0006).
- A push's per-snapshot image tag (`GET /v2/<repo>/manifests/<tag>`,
  or `crane manifest`/`docker pull`) returns a valid OCI manifest with
  one layer per chunk, in the same order as the snapshot manifest's
  `chunks` list.
- `shepctl remote prune` against the registry backend removes orphan
  chunk blobs and leaves referenced ones and their shard indexes
  consistent.
- `shepctl env pull`/`hydrate`/`dehydrate` round-trip against the
  registry backend without data loss, unchanged from before this ADR.
- Unit tests (`src/tests/test_remote_registry_backend.py`) and the
  Docker-backed integration suite
  (`src/tests/integration/test_ftp_sftp_backends.py`, `registry`
  parametrization) cover the above.

## More Information

Full transport-specific reference: [docs/remote.md](../remote.md#registry-oci).
