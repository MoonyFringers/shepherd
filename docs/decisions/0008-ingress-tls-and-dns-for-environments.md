---
status: "proposed"
date: 2026-08-09
decision-makers:
  - '@giubacc'
---

# Ingress, TLS and Per-Environment DNS for Shepherd Environments

## Context and Problem Statement

Real platforms provisioned through Shepherd plugins commonly need several
containers reachable over HTTPS at stable, predictable hostnames, fronted by
a single reverse proxy that terminates TLS. A predecessor bash-based
provisioning tool solved this for its multi-service environments with: one
self-signed CA generated once per install, a per-environment leaf
certificate whose SAN list is recomputed from whichever services are
ingress-enabled, a reverse proxy (traefik, label-routed) terminating TLS
with that certificate, and a `${service}-${docker-ip}.sslip.io`-style
autoresolving hostname scheme.

None of this exists in Shepherd core today. Because it is a cross-cutting
concern — any plugin fronting containers with HTTPS hits the same wall — the
question is how much of it belongs in core versus in a plugin, and in what
shape.

## Decision Drivers

- Must stay generic: no plugin-specific hostnames, domains, or proxy engine
  choices baked into core.
- Must follow Shepherd's existing plugin/core boundary (ADR-0004): core stays
  domain-agnostic, proprietary/platform-specific orchestration is a plugin's
  job.
- Must fit the actual control flow of `Environment.start`/`EnvironmentMng`,
  not an idealized one — compose config is rendered once and frozen before
  any container starts (`environment.py:151-152`), and orchestration runs on
  a background thread under a Rich Live display
  (`status_wait.py:232-243`), which rules out hook points that print/prompt.
- Must not introduce a redundant cert-reissue storm across the environment's
  gated, multi-cycle startup (`environment.py:160-201`).
- Local CA material must never leak into the existing snapshot/push path
  (ADR-0006/ADR-0007 tar and upload the environment directory to
  FTP/SFTP/OCI remotes).

## Considered Options

- Hardcode a traefik-based ingress directly into core.
- A pluggable `IngressProvider`, shaped like a stateless transport (mirroring
  `RemoteBackend` in `src/remote/backend.py`).
- A pluggable `IngressProvider`, shaped as a desired-state reconciler
  (`plan()`/`apply()` over the full container tree), with a core-shipped
  traefik default.
- A general lifecycle hook/event bus in core (pre/post `env up`, `svc up`,
  etc.), with cert regeneration and ingress wiring as plugin-registered
  callbacks.
- Derive TLS SANs and ingress labels from live/running container state,
  recomputed on each service coming up.
- Derive TLS SANs and ingress labels from declared config
  (`envCfg.services[*].containers[*].ingress == true`), computed once before
  render.

## Decision Outcome

Chosen options: **a pluggable `IngressProvider` shaped as a desired-state
reconciler** (not a `RemoteBackend`-style transport), **a dedicated `src/tls/`
subsystem for CA/leaf certificate issuance**, and **SANs/labels derived from
declared config, wired at render time** — not via a new general lifecycle
hook system.

`RemoteBackend` is a stateless byte-mover, constructed per `shepctl`
invocation, holding no domain state (`remote_mng.py:116-160`). Ingress does
not fit that shape: `shepctl` is a one-shot CLI process
(`ShepherdMng` is constructed fresh per invocation, `shepctl.py:36-110`), the
proxy is itself a container that must be woven into the same gated compose
render as everything else (`docker_compose_env.py:666-693`), and there is no
live process to "register a routable container" into between separate CLI
invocations. The provider must instead be a `plan(env_cfg,
ingress_containers) -> IngressPlan` / `apply()`/`reload()` reconciler:
full-state, idempotent, safe to call on every render.

A general lifecycle hook/event bus was considered and rejected for this use
case. The one seam that actually matters — injecting proxy labels and a cert
mount before containers start — sits inside `Environment.start`'s gated loop,
which runs pre-render-freeze and on a background thread with no safe
print/prompt path. That makes ingress wiring a **render-time** concern
(`render_target_impl`/`render_container`), not an event-time one. Core
already has the right idiom for this — overridable no-op methods on the
abstract base, e.g. `Environment.on_start_cycle_begin()`/`run_inits()`
(`environment.py:382,386`) — and only one real consumer (ingress) exists
today. Building a general hook contract now would freeze it (ordering,
thread-safety, error policy) against a single use case whose real
requirement is render-time, not event-time. Revisit a general hook bus only
if a second, non-ingress consumer actually appears.

SANs and ingress labels are derived from **declared** config
(`envCfg.services[*].containers[*].ingress == true`), fully known before
`Environment.start:151` renders the compose config — not from which
containers are currently running. This gives one certificate issuance per
`env up`, avoids reissue storms and partial-SAN certs for services gated
behind `when_probes` that join late, and reissues only on SAN-set
content-hash change or approaching expiry.

### Core subsystems

**`src/tls/` — CA and leaf certificate issuance**

- `CertificateAuthorityMng.ensure_ca()`: self-signed root CA under
  `~/.shpd/ca/`, idempotent, `0700`/`0600` permissions, atomic write
  (temp file + `os.replace`), a lock file to close the cross-process
  generation race.
- The CA carries **X.509 NameConstraints** scoped to the configured ingress
  domain. This is not optional: autoresolving domains such as `sslip.io` are
  public and attacker-steerable (they resolve to whatever IP is embedded in
  the hostname), so an unconstrained CA trusted on the user's machine could
  mint a valid certificate for any hostname under that domain.
- Bounded lifetimes on both CA and leaf certificates (leaf ≤ 90 days,
  reissued automatically; CA bounded too, with its fingerprint printed at
  generation and a rotation path — an unbounded, manually-trusted root the
  user will never remember to remove is worse than a bounded one).
- `issue_leaf_cert(env_tag, sans: list[str]) -> (cert_path, key_path)`.
- Leaf and CA key material live under `~/.shpd/ca/`, explicitly **outside**
  `envs_path` — the environment directory is tarred and pushed to
  FTP/SFTP/OCI remotes by the existing snapshot path (ADR-0006/ADR-0007);
  private key material must never enter that stream.
- A new `tls` CLI scope (`show fingerprint`, `rotate`, `remove`, `list`),
  registered in `CompletionMng.CORE_SCOPE_VERBS` (`runtime.py:169`) before
  any plugin can claim the name.

**`src/ingress/` — pluggable reconciler**

- `IngressProvider(ABC)`: `plan(env_cfg, ingress_containers) -> IngressPlan`
  (proxy compose fragment(s), per-container label sets, per-container
  hostname, and the SAN list for `src/tls/` to issue against) plus
  `apply()`/`reload()` for the running case. Gate-aware, since compose
  fragments are grouped by probe gate (`docker_compose_env.py:666-686`) and
  the proxy and its backends may land in different gates.
- New plugin capability `ingress_providers: true` + `get_ingress_providers()`
  on `ShepherdPlugin` + `PluginIngressProviderSpec` in `plugin/api.py`,
  following the existing contribution-registry pattern
  (`plugin/runtime.py`).
- Core ships a default traefik-based `IngressProvider` implementation as its
  own module — the ABC itself stays proxy-agnostic — so a plugin needing
  HTTPS ingress gets working behavior without writing proxy glue.
- Before this capability type is added, the existing
  `_CORE_BACKEND_TYPE_IDS` inconsistency (`runtime.py:990` hand-lists
  `{"ftp", "sftp"}` while `remote_mng.py:154` also dispatches `"registry"`
  in core) must be fixed so the reserved-id set is derived from the real
  dispatch table. Otherwise `ingress_providers` inherits the same
  silent-no-op bug on day one for a plugin that names its provider the same
  as the core default.

### Config model changes

- `ContainerCfg` (`src/config/config.py:518`) gains `labels:
  Optional[list[str]]`. Today only `ServiceCfg.labels` exists and is applied
  uniformly to every container in a service
  (`render_container(container, self.svcCfg.labels)` in
  `docker_compose_svc.py:66` and `docker_compose_env.py:736`) — wrong for
  multi-container services and a prerequisite for per-container proxy
  routing labels. This is a real, independent modelling fix, not
  ingress-specific.
- `ContainerCfg` gains `ingress: Optional[bool]`, the direct analogue of
  the predecessor tool's per-service `ingress: true` flag, opting a
  container in to being SAN-listed and proxy-routed.
- Label merge rule: `ServiceCfg.labels` ∪ `ContainerCfg.labels`, container
  wins on key conflict. Must be implemented and tested explicitly — the
  current `list["k=v"]` representation makes key-level dedup easy to get
  wrong by accident.
- Default hostname scheme includes the environment tag, not just service
  name and IP, to avoid collisions between same-named services in different
  environments.

### Consequences

- Good, because CA/cert issuance and per-container labels are self-contained
  additions usable by any future ingress-needing plugin, not just the one
  motivating this ADR.
- Good, because deriving SANs from declared config (not running state)
  eliminates an entire class of reissue-storm and partial-cert bugs before
  they're written.
- Good, because rejecting the general hook bus keeps core's extension
  surface exactly as large as its actual use cases, per the same discipline
  ADR-0004 already applies to templates/factories/commands.
- Bad, because generating and asking users to manually trust a local CA is
  inherently a security-sensitive default; NameConstraints, bounded
  lifetimes, and a `tls` management surface are required, not optional
  polish, and must ship in the same change as CA generation, not after.
- Bad, because `IngressProvider` as a reconciler is more surface than a
  `RemoteBackend`-style transport would have been — justified by the shape
  mismatch (§Decision Outcome), but it means the ABC needs to get the
  gate-awareness and plan/apply split right on the first attempt, since a
  wrong shape is expensive to unwind once a plugin depends on it.

### Confirmation

Before this ships, each of the following must be explicitly resolved (found
during design review, not yet designed):

- Teardown: `stop_env`/`delete_env` need a cert-cleanup step — nothing today
  removes per-environment cert material outside the environment directory.
- Clone/rename: a cloned environment must get a **regenerated** certificate,
  not a copied one (hostname collision risk); a renamed environment must
  reissue.
- Probe containers hitting HTTPS ingress have no CA to trust — probes run as
  `compose run --rm` with only `[base_yaml, probes_yaml]`
  (`docker_compose_env.py:844-853`). Either mount the CA into probe
  containers or document HTTP-only/`--insecure` for probes.
- Cert delivery into the proxy container (bind mount or compose secret)
  needs a concrete trace against `ensure_resources_impl`
  (`docker_compose_env.py:154-164`), which today only pre-creates bind-mount
  directories for declared volumes.

## More Information

Design review conducted by a second independent pass (Claude Opus) against
the actual codebase before this ADR was written; findings are folded into
the Decision Outcome and Confirmation sections above rather than kept as a
separate document. Motivating platform: a real multi-service environment
run today via a predecessor bash-based provisioning tool, targeted by an
in-progress downstream plugin.
