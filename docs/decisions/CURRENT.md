# Current architecture snapshot

Net result of all decision records in this directory, organized by
area. Read this before the full corpus for a quick orientation.

**Maintenance rule**: every PR that adds or supersedes a decision
record must update this file in the same change.

## Decision-record format (ADR-0000)

MADR (Markdown Any Decision Records) 4.0.0, hosted in
`MoonyFringers/shepherd`, reviewed via the normal GitHub PR workflow.
New records: copy `adr-template.md` to `NNNN-title-with-dashes.md`.

## Licensing and CLA (ADR-0001, ADR-0005)

Shepherd Core Stack moved from MIT to AGPL-3.0 (ADR-0001, accepted
2025-03-31), then to a **dual-license model**: AGPL-3.0-only for open
source use, plus a proprietary commercial license, enabled by a
Contributor License Agreement (ADR-0005, accepted 2026-03-30). Every
contribution requires a signed CLA before merge — enforced
automatically by the CLA Assistant bot, tracked in
`.github/cla_signatures.json`. See the `pr-prep` workflow for the
signing mechanics.

## Plugin architecture (ADR-0002 superseded, ADR-0004 accepted)

ADR-0002 (2025-09-09) first defined what a plugin is; it is
**superseded by ADR-0004** (accepted 2026-03-21), which locked the
actual target architecture and a phased rollout plan:

- CLI model refactored to `scope verb [args] [opts]` (e.g.
  `shepctl env get`), replacing the older `verb scope` shape, to give
  plugins a clear command tree with low collision risk.
- Plugins own their contributions via **plugin-owned runtime
  registries** (templates, factories, commands, completion) rather
  than copying plugin templates into the main config — keeps plugins
  self-contained across install/enable/disable/upgrade/remove.
- Plugin installation is Shepherd-controlled (managed
  `~/.shpd/plugins/<id>/` root), not arbitrary paths.
- Delivered as 7 incremental PRs (CLI shape refactor → plugin domain
  model → lifecycle commands → runtime loader/registries → completion
  extensibility → factory/template refactor → core contribution
  alignment) — all landed; this is the architecture live today.

Full spec and authoring guide: `docs/plugins.md` and the
`plugin-authoring` workflow, which also tracks live gaps found while
building real plugins against this API
(MoonyFringers/shepherd#260–#265).

## Changelog tooling (ADR-0003 — proposed, not decided)

**Status: proposed, unresolved.** ADR-0003 (2025-12-30) opened the
question of which automatic changelog-generation tool to standardize
on (must integrate with GitHub Actions, support Conventional Commits).
`docs/release-process.md` and the `release-process` workflow already
describe git-cliff in active use (`cliff.toml`, `scripts/release.sh`),
so the de facto answer is git-cliff — but ADR-0003 itself has not been
formally accepted. Don't treat this as settled; if the tooling changes,
ADR-0003 needs to move to accepted (or be superseded) in the same PR.

## Remote storage deduplication (ADR-0006, registry transport ADR-0007)

Accepted 2026-04-12. Environments include backing-service state
(Postgres dumps, Redis snapshots, etc.) alongside service definitions.
Naive one-`.tar.gz`-per-backup retransmits unchanged data on every
push. ADR-0006 defines client-side, remote-agnostic deduplication (the
remote stays a passive store — FTP/S3/similar, read/write/list only,
no server-side compute) so repeated backups only transfer changed
chunks. Three transports ship in core: FTP, SFTP, and an OCI
container-registry transport (added 2026-08-07). The registry
transport's object layout was revised 2026-08-08 (ADR-0007, which
supersedes ADR-0006's original registry section): chunks are stored as
bare content-addressed blobs (no per-chunk tag — a chunk's SHA-256
hash *is* its OCI blob digest, resolved straight from its path), and
each snapshot additionally gets a real multi-layer OCI image
(immutable per-snapshot tag + mutable per-environment `latest`-style
tag) assembled from those chunk blobs, so `docker pull`/`crane` see a
real artifact instead of one tag per chunk. This is a
transport-internal change only — `RemoteMng` and the chunking
algorithm itself are unaffected. Details: [docs/remote.md](../remote.md).

## Ingress, TLS, DNS (ADR-0008 — proposed, wired end-to-end)

**Status: proposed, fully implemented at the core level.** Opened 2026-08-09 while
scoping core gaps ahead of a downstream platform plugin. Landed: `src/tls/`
(`CertificateAuthorityMng` — CA generation with `NameConstraints`,
idempotent leaf-cert issuance keyed on a SAN-set/expiry hash,
cross-process `flock`ing, a `shepctl tls` CLI scope, and a
deterministic `leaf_cert_paths(env_tag)` path calculator usable before
issuance); `ContainerCfg.labels`/`ingress`/`run_labels`/`command`
fields plus a three-way service/container/run label-merge rule (run —
ingress-computed, transient — wins); `EnvironmentCfg.ingress`
(`IngressCfg`: `domain` + `provider` type_id, default `"traefik"`);
`src/ingress/` (`IngressProvider` ABC as a desired-state
`plan()`/`apply()`/`reload()` reconciler — not `RemoteBackend`-shaped,
see the ADR for why — `IngressProxySpec` as the config-model-free proxy
description a provider returns, `TraefikIngressProvider` default, and
plugin registration mirroring `RemoteBackend`'s pattern, including a
fix to a real pre-existing bug in that pattern:
`RemoteMng.CORE_BACKEND_TYPE_IDS` was missing `"registry"`).

**Wired into `Environment.start()`** via `_apply_ingress_plan()`,
called once before the render freeze: resolves the provider
(`"traefik"` built in, or via `configMng.pluginRuntimeMng` — no
`Environment.__init__` signature change needed, reusing the same
late-bound attachment point `factory/shpd_env_factory.py` already
uses), issues/refreshes the leaf certificate, writes the proxy's
dynamic TLS config to `<env_dir>/ingress/dynamic.yml`, merges routing
labels via the transient `run_labels` (never the declared `labels`,
which would otherwise persist stale routes after a rename), and
appends the proxy as a real, transient `Service` — excluded from
`to_config()` so it's never persisted into `.shpd.yaml` and is instead
recomputed fresh on every `start()`. `provider.apply()` is called once
the proxy's `ungated` gate is up. Two environments running ingress
concurrently get distinct, deterministic host ports (`allocate_ports`)
instead of colliding on :80/:443. `delete_env` and `rename_env` both
remove the (old-tag) leaf certificate; rename also clears the stale
`rendered_config`. Verified with a full `env up` integration test
(cert files land on disk, dynamic config is written, the proxy renders
into the compose stack with real traefik labels, and the proxy is
absent from the persisted config).

**Probe CA trust — closed.** `_apply_ingress_plan` mounts the CA
certificate (`CertificateAuthorityMng.ca_cert_path()`) into every
probe's container at a fixed path (`environment.PROBE_CA_CERT_MOUNT_PATH`,
`/etc/shepherd/ca.crt`) via a new `ContainerCfg.run_volumes` transient
field (additive to declared `volumes`, mirroring `run_labels` — never
persisted). Automatic: a probe author references the fixed path in
their script (e.g. `curl --cacert /etc/shepherd/ca.crt ...`); no
config authoring needed beyond that. This was the last open item in
this ADR's Confirmation checklist — the whole ingress/TLS design is
now implemented end-to-end at the core level.

## Environment teardown failure visibility (ADR-0009 — proposed, not decided)

**Status: proposed, unresolved.** Opened 2026-08-09 alongside ADR-0008.
`stop_impl` (`docker_compose_env.py`) never checks `docker compose
down`'s return code, so a failed teardown is reported as a successful
halt, and a retried `env halt` silently no-ops since `stop_env` blanks
`rendered_config` regardless of outcome. Surfaced by a service pattern
(Docker-outside-of-Docker: a container spawning sibling containers via
a mounted `/var/run/docker.sock`) that causes Compose-owned networks
to fail removal when foreign container endpoints are still attached.
ADR-0009 proposes fixing the return-code check in core
(unconditional, benefits every environment) while keeping
sibling-container sweep/teardown ordering as a plugin-level
`stop_impl` override rather than a core-level sweep, per the
plugin/core boundary in ADR-0004.
