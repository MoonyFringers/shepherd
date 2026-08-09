---
status: "proposed"
date: 2026-08-09
decision-makers:
  - '@giubacc'
---

# Environment Teardown Failure Visibility (Docker-outside-of-Docker Sibling Containers)

## Context and Problem Statement

Some services provisioned inside a Shepherd environment need to spawn
sibling containers of their own at runtime. A real-world example: a
launcher service that mounts `/var/run/docker.sock` and spawns pooled
worker containers on demand (`docker run --name <pool>-<uuid> --network
<env>_lonet ...`, confirmed from that service's own runtime logs on an
investigated deployment). These spawned containers are not declared in
Shepherd's own compose config, attach to the environment's own Docker
network, and are not created with any `--label` that would let Shepherd
recognize them as belonging to the environment.

The predecessor bash-based provisioning tool this design draws on never
addressed this — its scripts contain zero references to worker-container
spawning — but also never needed to: it creates its environment network
with a bare `docker network create` and declares it `external: true` in
compose, so `docker compose down` never owns and never touches that
network, and never fails because of foreign endpoints attached to it.

Shepherd's `ensure_resources_impl` (`docker_compose_env.py:154-164`) does not
pre-create external networks — only bind-mount host directories — so a
plugin cannot replicate that `external: true` trick without a hard
`docker compose up` failure. A plugin must therefore let Compose own the
environment network. A Compose-owned network with foreign (non-compose)
container endpoints still attached causes `docker compose down` to remove
its own containers successfully and then **fail** to remove the network
("network has active endpoints"). Since `stop_impl` (`docker_compose_env.py:534-543`)
never inspects `docker compose down`'s return code, this failure is
currently silent: `stop_env` (`environment.py:905-914`) blanks
`rendered_config` regardless of outcome, making a retry of `env halt` a
silent no-op, and `status_impl`'s `docker compose ps` scoping means the
leaked network and any still-running sibling containers are invisible to
`env status` too. Net effect: a leaked Docker network on every halt of such
an environment, colliding with itself on the next `env start` of the same
tag — a regression relative to the predecessor tool's accidental-but-working
behavior, not merely an unaddressed gap.

Because a launcher service of this kind is new, with no production history
to preserve compatibility with, this can be designed correctly from the
start rather than worked around.

## Decision Drivers

- `docker compose down` failures must not be silently swallowed, for any
  environment, regardless of cause — this is a pre-existing core robustness
  gap independent of Docker-outside-of-Docker.
- Docker-outside-of-Docker orchestration (spawning, labeling, reaping
  sibling containers) is platform-specific behavior and belongs to the
  plugin that owns the spawning service, per the plugin/core boundary
  already established in ADR-0004.
- A fix must not impose a `docker ps` sweep cost on every `env halt` for the
  overwhelming majority of environments that never spawn sibling containers.
- Teardown ordering matters and is service-specific (the spawning service
  must be stopped before its network is torn down, or its pool will keep
  respawning into a network being deleted) — this ordering knowledge belongs
  to the plugin, not a generic core sweep.

## Considered Options

- Leave `stop_impl` as-is; treat sibling-container cleanup as entirely the
  spawning service's own runtime responsibility (SIGTERM reaping), matching
  the predecessor tool's status quo exactly.
- Add an unconditional label-based `docker ps` / `docker rm -f` sweep to
  core's `stop_impl`/`delete_env`, run for every environment in addition to
  `docker compose down`.
- Fix `stop_impl` to surface `docker compose down` failures (core, generic,
  unconditional), and handle sibling-container teardown ordering as a
  plugin-level `stop_impl` override (plugin-specific, opt-in).

## Decision Outcome

Chosen option: **fix the silent-failure bug in core; put the sibling-
container sweep in the plugin.**

The unconditional core-sweep option was rejected: it runs a `docker ps`
sweep on every `env halt`/`delete` even for environments that never spawn
anything, which is exactly the core/plugin bleed ADR-0004 argues against,
and it does not solve the actual defect on its own — sweeping containers
without first stopping the spawning service races against that service's
own respawn loop (a pool with a fast health-check interval and
spawn-on-demand enabled will keep refilling itself), and sweeping
containers without addressing network teardown ordering still leaves
`docker compose down` failing on the network step.

Leaving `stop_impl` entirely as-is was rejected because it does not fix the
part of this that is a real, unconditional core bug: **any** failing
`docker compose down`, for any reason, is silently reported as a successful
halt today, and worse, permanently — `stop_env` nulls `rendered_config`
regardless of outcome, so re-running `env halt` after a failure is a no-op
that reports success without retrying.

### Core change (unconditional, benefits every environment)

- `stop_impl` must check the return code of `docker compose down` and route
  a non-zero result through `_record_compose_failure`, the same path
  `start:`-category failures already use — `stop`-category failures are
  currently excluded from that path by construction.
- `stop_env` must not blank `status.rendered_config` when teardown failed,
  so a retried `env halt` actually retries instead of silently no-op'ing.

### Plugin change (opt-in, platform-specific)

- The launcher service's own `docker run` invocation is changed to tag
  spawned worker containers with a label (e.g. `shepherd.env=<tag>`) — a
  change to that service itself, not to Shepherd.
- The owning plugin's environment class overrides `stop_impl`: stop the
  launcher service first (halting its respawn loop), sweep containers
  matching the `shepherd.env=<tag>` label, then call `super().stop_impl()`
  so Compose can remove its own containers and network cleanly. `stop_impl`
  is already `@abstractmethod` on `Environment`
  (`environment.py:453-456`), overridden per backing implementation — this
  requires no new core API.
- `delete_env` needs no change: it already assumes a prior successful halt
  and performs no teardown for declared containers either, so it should not
  become the place where undeclared containers get special-cased handling.

### Consequences

- Good, because the core fix (return-code checking on teardown) closes a
  real, currently-silent failure mode for every environment, not just
  Docker-outside-of-Docker ones.
- Good, because sibling-container teardown ordering — which is inherently
  service-specific knowledge (stop the spawner before its network) — stays
  where that knowledge lives, in the plugin, rather than being approximated
  by a generic core sweep that cannot know the right order.
- Good, because environments that never spawn sibling containers pay zero
  additional cost (no extra `docker ps` call) from this change.
- Neutral, because this does not attempt to make Docker-outside-of-Docker a
  first-class Shepherd concept — a future plugin needing the same pattern
  re-implements a similar `stop_impl` override rather than reusing a shared
  core mechanism. Acceptable for now: only one real consumer exists.
- Bad, because the label convention and the stop-before-sweep ordering are
  not enforced or validated by core — a plugin author who gets this wrong
  reproduces the exact leaked-network bug this ADR fixes, silently, since
  nothing in core checks that a plugin's `stop_impl` override actually calls
  `super().stop_impl()` or in what order.

### Confirmation

- A test environment with a service that spawns an unlabeled sibling
  container attached to the environment's own Compose-owned network must
  demonstrate: (a) before this change, `env halt` reports success while
  leaving a leaked network; (b) after the core fix alone (no plugin
  override), `env halt` reports failure and a retry is not a no-op; (c)
  with the plugin's `stop_impl` override in place, `env halt` succeeds and
  leaves no leaked network or containers.

## More Information

Investigated via two independent passes: an initial code-reading pass
against `Environment`/`ServiceMng`/`docker_compose_env.py`, followed by a
second review (Claude Opus) that traced the actual launcher-service spawn
command and shutdown behavior from live runtime logs rather than relying on
the config schema alone — this is what surfaced the network-teardown
failure as the real defect, as opposed to the originally-assumed "orphaned
container" framing. No leftover worker containers were found on the
investigated host at review time; the launcher service does reap its pool
on shutdown (its own logs show an orderly "terminating N live instance(s)"
sequence), so the residual risk this ADR addresses is specifically the
silent network-teardown failure, not general container leakage. Motivating
scenario: a real deployment using this Docker-outside-of-Docker pattern,
targeted by an in-progress downstream plugin. Related:
[ADR-0008](0008-ingress-tls-and-dns-for-environments.md) covers the other
core gap identified in the same assessment.
