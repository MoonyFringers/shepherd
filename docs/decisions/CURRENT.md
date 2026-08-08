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
