# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""
Ingress provider abstraction (see ADR-0008).

`RemoteBackend` (`src/remote/backend.py`) is a stateless byte-mover -- a poor
fit here. `shepctl` is a one-shot CLI process with no place to hold live
topology state between invocations, and a proxy is itself a container that
must be woven into the same render as everything else. `IngressProvider` is
instead a desired-state reconciler: `plan()` is a pure function of
declared config (never of which containers happen to be running, to avoid
reissue/relabel churn across an environment's gated, multi-cycle startup),
producing a full description of what the proxy and every ingress-flagged
container need; `apply()`/`reload()` make that description true.

Wired into `Environment.start()` via `Environment._apply_ingress_plan()`.
The proxy itself is never expressed as a `ServiceCfg`/`ContainerCfg` in this
module: a provider only knows proxy-engine mechanics, not shepherd's config
model (which factory/template ids a `ServiceCfg` needs is core-internal
dispatch knowledge a plugin author can't reasonably guess). `IngressProxySpec`
is the config-model-free description a provider returns; core translates it
into a real `ServiceCfg` at the call site.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from config.config import ContainerCfg, EnvironmentCfg

# Type_ids handled internally by a future core ingress dispatcher, mirroring
# `RemoteMng.CORE_BACKEND_TYPE_IDS`: kept as the single source of truth a
# plugin registry check consults, rather than a value hand-copied and left
# to drift out of sync with whatever the real dispatcher ends up handling.
CORE_INGRESS_PROVIDER_TYPE_IDS: frozenset[str] = frozenset({"traefik"})

# Deterministic per-environment host port allocation range. Two environments
# both running ingress must not collide on host :80/:443, but hostnames are
# per-env-tag already (see `traefik_provider.py`'s hostname scheme), so each
# environment's ingress proxy gets its own deterministic, stable pair of
# host ports instead of the conventional 80/443 -- clients reach it via
# `https://<host>:<port>` rather than the bare default port. Acceptable for
# local dev/test tooling; a hash collision between two concurrently active
# environments is a documented, low-probability limitation, not handled.
_PORT_ALLOCATION_BASE = 20000
_PORT_ALLOCATION_SPAN = 20000


def allocate_ports(env_tag: str) -> tuple[int, int]:
    """Return a deterministic `(http_port, https_port)` pair for `env_tag`,
    stable across repeated calls (same env tag always gets the same ports)
    and distinct between different env tags with overwhelming probability."""

    def _port(salt: str) -> int:
        digest = hashlib.sha256(f"{env_tag}:{salt}".encode()).digest()
        return _PORT_ALLOCATION_BASE + (
            int.from_bytes(digest[:4], "big") % _PORT_ALLOCATION_SPAN
        )

    return _port("http"), _port("https")


@dataclass(frozen=True)
class IngressContainerRef:
    """One ingress-flagged container from an environment's declared config,
    identified by the service that owns it."""

    service_tag: str
    container: "ContainerCfg"


@dataclass(frozen=True)
class IngressContainerPlan:
    """The routing outcome planned for one ingress-flagged container."""

    service_tag: str
    container_tag: str
    hostname: str
    labels: tuple[str, ...]


@dataclass(frozen=True)
class IngressProxySpec:
    """Config-model-free description of the proxy container a provider
    needs. Core translates this into a real `ServiceCfg`/`ContainerCfg` --
    a provider never constructs those directly (see module docstring)."""

    service_tag: str
    container_tag: str
    image: str
    command: tuple[str, ...] = ()
    ports: tuple[str, ...] = ()
    volumes: tuple[str, ...] = ()
    environment: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class IngressPlan:
    """Full desired-state output of `IngressProvider.plan()`.

    `sans` is exactly the hostname set `container_plans` declares -- the
    caller passes it to `tls.CertificateAuthorityMng.issue_leaf_cert()`
    unchanged, so the leaf certificate always covers precisely what the
    proxy will route.

    `proxy_gate` names which gate the proxy belongs to in the caller's
    gated-startup model -- `"ungated"` means it starts before every other
    service, which is what fronting them requires.
    """

    env_tag: str
    sans: tuple[str, ...]
    container_plans: tuple[IngressContainerPlan, ...]
    proxy_spec: IngressProxySpec
    proxy_gate: str = "ungated"
    # Static file-provider config content (e.g. traefik's dynamic.yml) for
    # TLS termination, when the provider was given certificate material to
    # mount. `None` when the provider has no certificate to wire in yet.
    proxy_dynamic_config: str | None = None


class IngressProvider(ABC):
    """Contract every ingress/reverse-proxy implementation must satisfy.

    A provider owns proxy-engine mechanics (traefik, nginx, caddy, ...);
    the caller (`Environment._apply_ingress_plan()`) owns orchestration --
    deciding when `plan()`/`apply()` run, translating `IngressProxySpec`
    into the config model, and issuing the TLS certificate `plan()` asks
    for.
    """

    @abstractmethod
    def plan(
        self,
        env_cfg: "EnvironmentCfg",
        ingress_containers: Sequence[IngressContainerRef],
    ) -> IngressPlan:
        """Compute the full desired ingress state for `env_cfg`.

        Must be a pure function of `env_cfg`'s declared config: MUST NOT
        consult which containers are currently running, and MUST be safe to
        call repeatedly with the same input (idempotent, no side effects).
        """
        raise NotImplementedError

    @abstractmethod
    def apply(self, plan: IngressPlan) -> None:
        """Make a freshly computed `plan` true against the running
        environment (e.g. reload the proxy so new routes/certs take
        effect). Must be idempotent."""
        raise NotImplementedError

    @abstractmethod
    def reload(self, plan: IngressPlan) -> None:
        """Re-apply `plan` after it changed (e.g. the SAN set or a
        container's hostname changed). Distinct from `apply()` so a
        provider that can hot-reload in place (vs. needing a full
        recreate) can implement the two differently."""
        raise NotImplementedError
