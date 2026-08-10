# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Core-shipped default `IngressProvider`, using traefik's Docker
provider for label-based routing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence

import yaml

from ingress.provider import (
    IngressContainerPlan,
    IngressContainerRef,
    IngressPlan,
    IngressProvider,
    IngressProxySpec,
)

if TYPE_CHECKING:
    from config.config import EnvironmentCfg

DEFAULT_TRAEFIK_IMAGE = "traefik:v3.1"

# Container-internal mount points for leaf certificate material, when the
# caller supplies one (see `TraefikIngressProvider.__init__`).
_CERT_MOUNT_DIR = "/certs"
_CERT_MOUNT_PATH = f"{_CERT_MOUNT_DIR}/leaf.crt"
_KEY_MOUNT_PATH = f"{_CERT_MOUNT_DIR}/leaf.key"
_DYNAMIC_CONFIG_MOUNT_PATH = "/dynamic/dynamic.yml"


def _router_name(env_tag: str, service_tag: str, container_tag: str) -> str:
    # Compose/Docker-safe (alnum + `-`), and matches the naming convention
    # `docker_compose_svc.py` already uses for container names
    # (`<container>-<service>-<env>`), so a router is easy to correlate
    # with the container it fronts.
    return f"{container_tag}-{service_tag}-{env_tag}"


def _hostname(
    domain: str, env_tag: str, service_tag: str, container_tag: str
) -> str:
    return f"{_router_name(env_tag, service_tag, container_tag)}.{domain}"


class TraefikIngressProvider(IngressProvider):
    """Label-driven reverse proxy: traefik watches the Docker socket and
    routes to any container carrying `traefik.*` labels -- no explicit
    `apply()`/`reload()` action is needed for routing changes to take
    effect (see the docstrings on those methods below for why they are
    documented no-ops here)."""

    def __init__(
        self,
        domain: str,
        *,
        image: str = DEFAULT_TRAEFIK_IMAGE,
        http_port: int = 80,
        https_port: int = 443,
        tls_cert_path: Optional[str] = None,
        tls_key_path: Optional[str] = None,
        dynamic_config_host_path: Optional[str] = None,
    ):
        """
        :param domain: DNS domain hostnames are generated under (e.g.
            `sslip.io`). Must match the domain the environment's TLS
            certificate (see `tls.CertificateAuthorityMng`) was issued for.
        :param tls_cert_path: Host path to a leaf certificate to mount into
            the proxy and terminate TLS with (e.g. from
            `CertificateAuthorityMng.leaf_cert_paths(env_tag)`, deterministic
            even before the certificate is actually issued). `tls_cert_path`,
            `tls_key_path`, and `dynamic_config_host_path` must all be given
            together, or none -- without them, `plan()` still computes
            hostnames and labels (useful for tests and plain-HTTP setups),
            but the generated proxy spec has no TLS termination configured.
        :param tls_key_path: Host path to the matching private key.
        :param dynamic_config_host_path: Host path the caller will write
            `IngressPlan.proxy_dynamic_config`'s content to before the proxy
            starts (e.g. `<env_dir>/ingress/dynamic.yml`) -- mounted into the
            proxy so its file provider can read the TLS wiring.
        """
        tls_args = (tls_cert_path, tls_key_path, dynamic_config_host_path)
        if any(tls_args) and not all(tls_args):
            raise ValueError(
                "tls_cert_path, tls_key_path, and dynamic_config_host_path "
                "must all be given together, or none."
            )
        self.domain = domain
        self.image = image
        self.http_port = http_port
        self.https_port = https_port
        self.tls_cert_path = tls_cert_path
        self.tls_key_path = tls_key_path
        self.dynamic_config_host_path = dynamic_config_host_path

    def plan(
        self,
        env_cfg: "EnvironmentCfg",
        ingress_containers: Sequence[IngressContainerRef],
    ) -> IngressPlan:
        container_plans = tuple(
            self._plan_container(env_cfg.tag, ref) for ref in ingress_containers
        )
        sans = tuple(sorted({p.hostname for p in container_plans}))
        return IngressPlan(
            env_tag=env_cfg.tag,
            sans=sans,
            container_plans=container_plans,
            proxy_spec=self._build_proxy_spec(),
            proxy_gate="ungated",
            proxy_dynamic_config=self._render_dynamic_config(),
        )

    def _plan_container(
        self, env_tag: str, ref: IngressContainerRef
    ) -> IngressContainerPlan:
        hostname = _hostname(
            self.domain, env_tag, ref.service_tag, ref.container.tag
        )
        router = _router_name(env_tag, ref.service_tag, ref.container.tag)
        labels = (
            "traefik.enable=true",
            f"traefik.http.routers.{router}.rule=Host(`{hostname}`)",
            f"traefik.http.routers.{router}.entrypoints="
            + ("websecure" if self._tls_enabled else "web"),
        )
        if self._tls_enabled:
            labels += (f"traefik.http.routers.{router}.tls=true",)
        if ref.container.ingress_port is not None:
            # Traefik's Docker provider only auto-detects a port when the
            # container exposes exactly one -- ambiguous otherwise, so any
            # container declaring `ingress_port` gets it wired explicitly.
            labels += (
                f"traefik.http.services.{router}.loadbalancer.server.port="
                f"{ref.container.ingress_port}",
            )
        return IngressContainerPlan(
            service_tag=ref.service_tag,
            container_tag=ref.container.tag,
            hostname=hostname,
            labels=labels,
        )

    @property
    def _tls_enabled(self) -> bool:
        return bool(self.tls_cert_path and self.tls_key_path)

    def _build_proxy_spec(self) -> IngressProxySpec:
        command = [
            "--providers.docker=true",
            "--providers.docker.exposedbydefault=false",
            "--entrypoints.web.address=:80",
        ]
        ports = [f"{self.http_port}:80"]
        volumes = ["/var/run/docker.sock:/var/run/docker.sock:ro"]

        if self._tls_enabled:
            command += [
                "--entrypoints.websecure.address=:443",
                "--providers.file.filename=" + _DYNAMIC_CONFIG_MOUNT_PATH,
                "--providers.file.watch=true",
            ]
            ports.append(f"{self.https_port}:443")
            volumes += [
                f"{self.tls_cert_path}:{_CERT_MOUNT_PATH}:ro",
                f"{self.tls_key_path}:{_KEY_MOUNT_PATH}:ro",
                f"{self.dynamic_config_host_path}:"
                f"{_DYNAMIC_CONFIG_MOUNT_PATH}:ro",
            ]

        return IngressProxySpec(
            service_tag="ingress",
            container_tag="proxy",
            image=self.image,
            command=tuple(command),
            ports=tuple(ports),
            volumes=tuple(volumes),
        )

    def _render_dynamic_config(self) -> Optional[str]:
        if not self._tls_enabled:
            return None
        return yaml.dump(
            {
                "tls": {
                    "certificates": [
                        {
                            "certFile": _CERT_MOUNT_PATH,
                            "keyFile": _KEY_MOUNT_PATH,
                        }
                    ]
                }
            },
            sort_keys=False,
        )

    def apply(self, plan: IngressPlan) -> None:
        """No-op: traefik's Docker provider discovers label changes on its
        own (`--providers.docker=true`), and its file provider re-reads
        `proxy_dynamic_config` on change when mounted with
        `--providers.file.watch=true` (set whenever TLS is configured).
        Nothing needs to be told to reload."""

    def reload(self, plan: IngressPlan) -> None:
        """See `apply()` -- traefik picks up both routing and TLS
        certificate changes on its own; this is a no-op for the same
        reason."""
