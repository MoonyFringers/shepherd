# Remote Storage

Shepherd can push environment snapshots to a remote storage server and pull
them back on other machines. Data is transferred as a content-deduplicated
chunk store — only data that changed since the last push is uploaded. See
[ADR-0006](decisions/0006-remote-storage-deduplication.md) for the design
rationale and data model details.

## Remote Storage Layout

Every remote stores its data under a single root directory chosen at
registration time (`--root-path` / `root_path`). The layout inside that
root is fixed:

```text
<root_path>/
├── index/
│   └── index.json          # global catalogue — fetch once for discovery
├── envs/
│   └── <env-name>/
│       ├── latest.json     # pointer to the most recent snapshot
│       └── snapshots/
│           └── <snapshot-id>.json   # manifest: metadata + chunk list
└── chunks/
    ├── ab/                 # first 2 hex chars of the chunk hash
    │   └── ab3f1c9d...     # individual Zstd-compressed chunk
    └── ...
```

Sharding by two-character prefix mirrors git's object store layout and keeps
any single directory listing to ≤ 256 entries — important for FTP servers
that degrade with large flat directories.

Shepherd creates all directories automatically on first write. The root path
itself must exist on the server before the first push.

## Remote Management Commands

### Register a remote

```sh
# FTP remote
shepctl remote add prod-ftp --ftp \
    --host storage.example.com \
    --user backup \
    --password "${BACKUP_PWD}" \
    --root-path /shepherd \
    --set-default

# SFTP remote — key-based auth (recommended)
shepctl remote add prod-sftp --sftp \
    --host storage.example.com \
    --user deploy \
    --identity-file ~/.ssh/id_ed25519 \
    --root-path /backups/shepherd \
    --set-default

# SFTP remote — password auth
shepctl remote add dev-sftp --sftp \
    --host dev.example.com \
    --user ci \
    --password "${CI_SFTP_PWD}" \
    --root-path /ci/shepherd
```

Other remote management commands:

```sh
# List all registered remotes
shepctl remote list

# Inspect snapshots available for an env on a remote
shepctl remote get <env-tag> [--remote=<name>]

# Remove orphan chunks (chunks not referenced by any manifest)
shepctl remote prune [--remote=<name>] [--dry-run]

# Unregister a remote (does not delete data on the server)
shepctl remote delete <name>
```

### Environment data commands

```sh
# Create a new remote snapshot from the local env
shepctl env push [env-tag] [--remote=<name>] \
    [--set-tracking-remote] [--labels=k=v ...]

# First-time download — env not yet registered locally
shepctl env pull [env-tag] [--remote=<name>] [--snapshot-id=<id>]

# Restore data for an already-registered dehydrated env
shepctl env hydrate [env-tag] [--remote=<name>] [--snapshot-id=<id>]

# Strip local data, keep config entry (inverse of hydrate)
shepctl env dehydrate [env-tag]
```

State transitions:

```text
[remote snapshot]
      │
      │  env pull    (env unknown locally → creates config + data)
      ▼
[local, hydrated] ──── env dehydrate ────► [local, dehydrated]
      ▲                                             │
      └──────────── env hydrate ────────────────────┘
```

## Built-in Transports

### FTP

Use FTP on trusted private networks (local NAS, VPN-protected servers) where
encryption in transit is not required. For anything internet-facing, prefer
SFTP.

#### CLI

```sh
shepctl remote add my-ftp --ftp \
    --host 192.168.1.10 \
    --user shepherd \
    --password "${FTP_PASSWORD}" \
    --root-path /srv/shepherd \
    --set-default
```

`--host`, `--user`, `--password`, and `--root-path` are required for FTP.
`--port` is optional and defaults to `21`.

#### Config YAML

```yaml
remotes:
  - name: my-ftp
    type: ftp
    host: 192.168.1.10
    port: 21               # optional; default 21
    user: shepherd
    password: "${FTP_PASSWORD}"
    root_path: /srv/shepherd
    default: true          # optional; marks as the default remote
```

#### Notes

- Uses Python's stdlib `ftplib` — no additional dependencies.
- Always operates in passive mode (PASV).
- Existence checks use a single `NLST` listing per 2-char shard directory,
  cached for the lifetime of the backend connection. This avoids one
  round-trip per chunk during deduplication checks.
- Data is **not encrypted in transit**. Use only on private, trusted
  networks.

---

### SFTP

SFTP is the recommended built-in transport for most real deployments. It
provides SSH-level encryption and supports both key and password
authentication.

#### CLI — key-based auth (recommended)

```sh
shepctl remote add my-sftp --sftp \
    --host storage.example.com \
    --user deploy \
    --identity-file ~/.ssh/id_ed25519 \
    --root-path /srv/shepherd \
    --set-default
```

#### CLI — password auth

```sh
shepctl remote add my-sftp --sftp \
    --host storage.example.com \
    --user deploy \
    --password "${SFTP_PASSWORD}" \
    --root-path /srv/shepherd
```

`--identity-file` takes precedence over `--password` when both are given.
At least one of the two must be provided.

#### Config YAML (SFTP)

```yaml
remotes:
  - name: my-sftp
    type: sftp
    host: storage.example.com
    port: 22                          # optional; default 22
    user: deploy
    identity_file: ~/.ssh/id_ed25519  # takes precedence over password
    # password: "${SFTP_PASSWORD}"    # alternative when no key is available
    root_path: /srv/shepherd
    default: true
```

#### SFTP Notes

- Uses [`paramiko`](https://www.paramiko.org/). Supports Ed25519, ECDSA, and
  RSA private keys; key type is auto-detected at load time.
- `${VAR}` placeholders in `password` and `identity_file` are resolved from
  environment variables at runtime — credentials are never stored in their
  resolved form in `~/.shpd.conf`.
- When both `identity_file` and `password` are present, `identity_file`
  wins.

---

## Advanced: Chunk Tuning

The default FastCDC parameters work well for most environments. Override them
per remote when snapshots are consistently much smaller or larger than the
defaults:

```yaml
remotes:
  - name: my-sftp
    type: sftp
    # ... connection fields ...
    chunk:
      min_size_kb: 512    # default 512 KB
      avg_size_kb: 2048   # default 2 MB
      max_size_kb: 8192   # default 8 MB
```

Smaller chunks improve deduplication granularity at the cost of more objects
on the remote and higher manifest overhead. Larger chunks reduce file count
and suit bulk transfers on fast links. The constraint `min ≤ avg ≤ max` must
hold.

## Advanced: Local Chunk Cache

A local on-disk LRU cache avoids re-downloading chunks that were recently
pulled. Enable it per remote in `~/.shpd.conf`:

```yaml
remotes:
  - name: my-sftp
    type: sftp
    # ... connection fields ...
    local_cache:
      path: /tmp/shepherd-cache   # directory for cached chunk bytes
      max_size_gb: 20             # default 20 GB; evicts LRU when exceeded
```

The cache is transparent — Shepherd checks it before downloading from the
remote and populates it on every download.

## Credential Security

All string fields in a remote config entry support `${VAR_NAME}` placeholders
resolved from environment variables at runtime:

```yaml
password: "${SHEPHERD_FTP_PASSWORD}"
identity_file: "${HOME}/.ssh/shepherd_ed25519"
```

Values are never written back to disk in their resolved form. This keeps
credentials out of `~/.shpd.conf` and allows the same config file to be
shared across machines with different secrets.

## Custom Transports

Additional transports (S3, Azure Blob, GCS, and others) can be added as
Shepherd plugins without modifying core code. See
[Plugin-Contributed Remote Backends](plugins.md#plugin-contributed-remote-backends)
for the full authoring guide.
