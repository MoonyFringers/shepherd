---
status: "accepted"
date: 2026-04-12
decision-makers:
  - '@giubacc'
---

# Remote Storage Deduplication for Shepherd Environments

## Context and Problem Statement

Shepherd environments include the state of backing services (e.g. Postgres
database dumps, Redis snapshots) alongside service definitions. When a user
wants to persist or share an environment they must produce an archive
containing all of this state and upload it to remote storage (FTP server,
S3 bucket, or similar).

The naive approach — one monolithic `.tar.gz` per backup — is wasteful: if
only the database changed between two backups, all unchanged service data
(other DB tables, uploaded files, runtime state) is retransmitted in full.
On a slow uplink or a large database this makes frequent backups impractical.

How do we reduce the data transferred on each backup while keeping the remote
backend fully passive (no server-side agent, no compute)?

## Decision Drivers

- Remote storage is passive: FTP, S3, or any object/file store with
  read/write/list only. No server-side compute can be assumed.
- All deduplication intelligence must live on the client.
- Multiple clients may write to the same remote concurrently without
  corrupting data.
- A client must enumerate available environments and snapshots with minimal
  round-trips.
- New storage transports (S3, Azure Blob, SFTP, …) must be addable as
  plugins without modifying the core.

## Considered Options

- Monolithic `.tar.gz` — one file per snapshot, no dedup.
- rsync delta over the monolithic archive — requires SSH/rsync server-side.
- bsdiff patches over the previous snapshot — no cross-environment sharing;
  requires storing the previous archive to apply the patch.
- Content-defined chunking with a passive chunk store.

## Decision Outcome

Chosen option: **content-defined chunking with a passive chunk store**,
because it is the only approach that satisfies all constraints (passive
backend, client-only logic, cross-environment dedup, and pluggable
transports).

### Algorithm

Instead of uploading a monolithic archive, the client:

1. Produces an **uncompressed `.tar` stream** of the environment directory
   and all associated host-mounted volumes.
2. Splits the stream into variable-length chunks using **FastCDC**
   (content-defined chunking). Chunking is performed on the *uncompressed*
   stream — this is critical for chunk stability across backups;
   recompressing with a different window state would shift all boundaries.
3. Compresses each chunk individually with **Zstd**.
4. Hashes each compressed chunk with **SHA-256** to produce a content
   address.
5. Checks the remote store for which chunk hashes already exist (strategy
   is backend-specific — see below).
6. Uploads only the missing chunks.
7. Writes a **snapshot manifest** (JSON) listing the ordered chunk hashes
   required to reconstruct the archive, plus rich environment metadata.
8. Updates the per-environment `latest.json` pointer and the global
   `index.json` catalogue.

This gives natural deduplication across environments and across time: if
two environments share a common dataset (e.g. the same initial DB seed), or
a new snapshot differs from the previous one only in recently changed rows,
the shared data is stored exactly once.

### Remote Storage Layout

```text
remote-storage/
├── index/
│   └── index.json          # global catalogue — fetch once for discovery
├── envs/
│   └── <env-name>/
│       ├── latest.json     # pointer to most recent snapshot id
│       └── snapshots/
│           ├── <snapshot-id>.json   # manifest: metadata + chunk list
│           └── ...
└── chunks/
    ├── ab/                 # first 2 hex chars = shard subfolder
    │   └── ab3f1c9d...
    └── ...
```

Sharding by 2-character prefix mirrors git's object store and limits any
single FTP directory listing to ≤ 256 entries.

### Key Parameter Decisions

| Parameter | Value | Rationale |
| --- | --- | --- |
| Hash | SHA-256 (`hashlib`) | stdlib, no native build |
| Chunk sizes | min 512 KB / avg 2 MB / max 8 MB | good dedup; tunable |
| Snapshot ID | `{ISO-8601-UTC}-{6-hex-sha256(manifest)}` | readable + safe |
| FTP check | `NLST` shard-listing → in-memory set | avoids O(n) MLST |
| Manifest | `@dataclass` + `json`, `from_dict`/`to_dict` | config.py style |
| Local cache | opt-in LRU, max-bytes, NullLocalChunkCache no-op | 0 overhead |

### sudo-aware tar

DBMS containers often write data under a non-root UID mapped from the host.
When `os.access(path, os.R_OK)` returns `False`, the tar subprocess is
spawned under `sudo tar -cC <path> .`, piped to the chunk engine — mirroring
the existing `_delete_dir_with_sudo` pattern.

### Consistency Model

- Chunks are immutable and content-addressed — concurrent uploads are
  idempotent.
- Manifests are written only after all chunks are confirmed present — a
  partial backup leaves orphan chunks but never a corrupt manifest.
- `index.json` is a best-effort cache; ground truth is always the
  per-environment manifests.
- `latest.json` last-writer-wins — environments are not typically backed up
  from two nodes simultaneously.

### Built-in Transports

Two transports ship with the core:

- **FTP** — using stdlib `ftplib`. Existence checks use the shard-listing
  strategy (one `NLST` per 2-char prefix per session, resolved from an
  in-memory set).
- **SFTP** — using `paramiko`. Provides encrypted transfer and SSH key
  authentication, making it the preferred choice for most real deployments.

Both implement the same `RemoteBackend` ABC and are interchangeable from
the orchestration layer's perspective.

### Backend Extensibility

`RemoteBackend` is an abstract base class exposed in the public plugin API
alongside `EnvironmentFactory` and `ServiceFactory`. A plugin contributes
additional transports by implementing `ShepherdPlugin.get_remote_backends()`
returning `PluginRemoteBackendSpec(type_id, factory)`.
`RemoteMng._build_backend()` checks core built-ins first (FTP, SFTP), then
delegates to the plugin registry — the same dispatch pattern used by env/svc
factories.

S3, Azure Blob, and other transports follow as standalone plugin packages.
See [Plugin-Contributed Remote Backends](../plugins.md#plugin-contributed-remote-backends)
for the full authoring guide including the `RemoteBackend` contract, a
worked S3 example, and remote config YAML conventions.

### Remote Configuration and CLI

See [docs/remote.md](../remote.md) for the full configuration reference,
built-in transport details, and worked CLI examples.

Remotes are persisted in the main Shepherd config (`~/.shpd.conf`) under a
top-level `remotes` list. Each entry has a `name`, a `type` (`ftp` or `sftp`
for built-ins, or a plugin-registered type id), type-specific connection
fields, and optional chunk tuning and local cache settings.

Remotes are managed via `shepctl remote`:

```sh
# Register an FTP remote
shepctl remote add prod-backup --ftp \
    --host storage.example.com \
    --user backup \
    --password "${BACKUP_PWD}" \
    --root-path /shepherd \
    --set-default

# Register an SFTP remote (key-based auth)
shepctl remote add dev-backup --sftp \
    --host dev.example.com \
    --user deploy \
    --identity-file ~/.ssh/id_ed25519 \
    --root-path /backups/shepherd

# List registered remotes
shepctl remote list

# Inspect snapshots available for an environment on a remote
shepctl remote get myenv [--remote=prod-backup]

# Remove orphan chunks from a remote
shepctl remote prune [--remote=prod-backup] [--dry-run]

# Unregister a remote (does not delete remote data)
shepctl remote delete prod-backup
```

Environment operations that interact with a remote:

```sh
# Push a new snapshot
# (uses tracking remote or default if --remote omitted)
shepctl env push [env-tag] \
    [--remote=<name>] [--set-tracking-remote] [--labels=...]

# First-time download — env not yet registered locally
shepctl env pull [env-tag] [--remote=<name>] [--snapshot-id=<id>]

# Restore data for an already-registered dehydrated env
shepctl env hydrate [env-tag] [--remote=<name>] [--snapshot-id=<id>]

# Strip local data, keep config entry
shepctl env dehydrate [env-tag]
```

`--password` and `--identity-file` values that contain `${VAR}` are stored
verbatim and resolved at runtime via the existing `Resolvable` mechanism, so
credentials are never hard-coded in the config file.

### pull vs hydrate State Machine

```text
[remote snapshot]
      │
      │  env pull    (env unknown locally → creates config entry + data)
      ▼
[local env, hydrated] ──── env dehydrate ────► [local env, dehydrated]
      ▲                                                  │
      └──────────────── env hydrate ─────────────────────┘
```

- `env push` — create a new remote snapshot from the local env.
- `env pull` — first-time download; env not yet registered locally.
- `env hydrate` — restore data for an already-registered dehydrated env.
- `env dehydrate` — strip local data, keep config entry.

### Consequences

- Good, because only changed data is transferred; dedup is automatic across
  environments and across time for env-specific data (DB state, mounted
  volumes, runtime files).
- Good, because the passive-backend constraint is fully respected.
- Good, because new transports can be added as plugins without touching
  the core.
- Good, because orphan chunks can be reclaimed with a `prune` command.
- Neutral, because chunk metadata (manifests, index) adds a small overhead
  per snapshot vs. a single file upload.
- Bad, because the implementation introduces three new runtime dependencies
  (`fastcdc`, `zstandard`, `paramiko`).

### Confirmation

The implementation is aligned with this ADR when:

- `shepctl env push` transfers fewer bytes on a second push of the same
  environment.
- `shepctl env pull` creates a local env entry from a remote snapshot.
- `shepctl env dehydrate` + `shepctl env hydrate` round-trip without data
  loss.
- `shepctl remote prune` removes orphan chunks and retains all referenced
  ones.
- A plugin contributing a `PluginRemoteBackendSpec` is picked up by
  `RemoteMng` without core modifications.
- Automated tests cover the push/pull/hydrate/dehydrate/prune flows using a
  `FakeRemoteBackend` and an FTP/SFTP integration fixture.

## Pros and Cons of the Options

### Content-Defined Chunking (chosen)

- Good, because dedup is cross-environment and cross-time with no extra
  metadata.
- Good, because the passive backend constraint is satisfied.
- Good, because chunk uploads are individually retryable.
- Neutral, because manifest management adds a small protocol layer.

### Monolithic `.tar.gz`

- Good, because it is trivially simple to implement.
- Bad, because the entire archive is retransmitted on every backup.
- Bad, because it does not scale to large environments on slow links.

### rsync Delta

- Good, because deltas can be very small.
- Bad, because it requires an rsync or SSH server — violates the
  passive-backend constraint.

### bsdiff Patches

- Bad, because there is no cross-environment sharing.
- Bad, because restoring requires the previous archive to apply the patch.
- Bad, because patch metadata can be large for random-access storage
  patterns.
