# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Unit tests for :class:`~ingress.traefik_provider.TraefikIngressProvider`
and the `IngressProvider` plan shape."""

from __future__ import annotations

import pytest
import yaml

from config.config import ContainerCfg, EnvironmentCfg
from ingress import IngressContainerRef
from ingress.traefik_provider import TraefikIngressProvider

pytestmark = pytest.mark.tls


def _env_cfg(tag: str = "test-1") -> EnvironmentCfg:
    return EnvironmentCfg(
        template="default",
        factory="docker-compose",
        tag=tag,
        services=None,
        probes=None,
        networks=None,
        volumes=None,
    )


def test_plan_computes_hostname_and_labels_without_tls():
    provider = TraefikIngressProvider(domain="sslip.io")
    env_cfg = _env_cfg("test-1")
    ref = IngressContainerRef(
        service_tag="web", container=ContainerCfg(tag="app")
    )

    plan = provider.plan(env_cfg, [ref])

    assert len(plan.container_plans) == 1
    container_plan = plan.container_plans[0]
    assert container_plan.hostname == "app-web-test-1.sslip.io"
    assert plan.sans == ("app-web-test-1.sslip.io",)
    assert "traefik.enable=true" in container_plan.labels
    assert any(
        "rule=Host(`app-web-test-1.sslip.io`)" in label
        for label in container_plan.labels
    )
    assert any(
        "entrypoints=web" in label and "entrypoints=websecure" not in label
        for label in container_plan.labels
    )
    assert not any("tls=true" in label for label in container_plan.labels)
    assert plan.proxy_dynamic_config is None


def test_plan_requires_cert_and_key_together():
    with pytest.raises(ValueError):
        TraefikIngressProvider(domain="sslip.io", tls_cert_path="/x/leaf.crt")
    with pytest.raises(ValueError):
        TraefikIngressProvider(domain="sslip.io", tls_key_path="/x/leaf.key")


def test_plan_with_tls_enables_https_entrypoint_and_dynamic_config():
    provider = TraefikIngressProvider(
        domain="sslip.io",
        tls_cert_path="/certs/host/leaf.crt",
        tls_key_path="/certs/host/leaf.key",
        dynamic_config_host_path="/certs/host/dynamic.yml",
    )
    env_cfg = _env_cfg("test-1")
    ref = IngressContainerRef(
        service_tag="web", container=ContainerCfg(tag="app")
    )

    plan = provider.plan(env_cfg, [ref])

    container_plan = plan.container_plans[0]
    assert any(
        "entrypoints=websecure" in label for label in container_plan.labels
    )
    assert any("tls=true" in label for label in container_plan.labels)

    assert plan.proxy_dynamic_config is not None
    dynamic_config = yaml.safe_load(plan.proxy_dynamic_config)
    cert_entry = dynamic_config["tls"]["certificates"][0]
    assert cert_entry["certFile"] == "/certs/leaf.crt"
    assert cert_entry["keyFile"] == "/certs/leaf.key"

    proxy_spec = plan.proxy_spec
    assert "443:443" in proxy_spec.ports
    assert any(
        vol.startswith("/certs/host/leaf.crt:") for vol in proxy_spec.volumes
    )
    assert any(
        vol.startswith("/certs/host/leaf.key:") for vol in proxy_spec.volumes
    )
    assert any(
        vol.startswith("/certs/host/dynamic.yml:") for vol in proxy_spec.volumes
    )


def test_plan_dedupes_sans_across_containers():
    provider = TraefikIngressProvider(domain="sslip.io")
    env_cfg = _env_cfg("test-1")
    refs = [
        IngressContainerRef(
            service_tag="web", container=ContainerCfg(tag="app")
        ),
        IngressContainerRef(
            service_tag="api", container=ContainerCfg(tag="app")
        ),
    ]

    plan = provider.plan(env_cfg, refs)

    assert len(plan.container_plans) == 2
    assert len(plan.sans) == 2
    assert plan.sans == tuple(sorted(plan.sans))


def test_plan_env_tag_isolates_hostnames_across_environments():
    provider = TraefikIngressProvider(domain="sslip.io")
    ref = IngressContainerRef(
        service_tag="web", container=ContainerCfg(tag="app")
    )

    plan_1 = provider.plan(_env_cfg("env-a"), [ref])
    plan_2 = provider.plan(_env_cfg("env-b"), [ref])

    assert plan_1.sans != plan_2.sans


def test_proxy_fragment_without_tls_has_no_https_port():
    provider = TraefikIngressProvider(domain="sslip.io")
    plan = provider.plan(_env_cfg("test-1"), [])

    proxy_spec = plan.proxy_spec
    assert proxy_spec.ports == ("80:80",)
    assert "/var/run/docker.sock:/var/run/docker.sock:ro" in (
        proxy_spec.volumes
    )


def test_apply_and_reload_are_safe_no_ops():
    provider = TraefikIngressProvider(domain="sslip.io")
    plan = provider.plan(_env_cfg("test-1"), [])

    # Must not raise -- traefik's Docker/file providers self-discover
    # changes, so these are documented no-ops for this provider.
    provider.apply(plan)
    provider.reload(plan)


def test_proxy_spec_uses_stable_service_and_container_tags():
    provider = TraefikIngressProvider(domain="sslip.io")
    plan = provider.plan(_env_cfg("test-1"), [])

    assert plan.proxy_spec.service_tag == "ingress"
    assert plan.proxy_spec.container_tag == "proxy"
    assert plan.proxy_gate == "ungated"


def test_allocate_ports_is_deterministic_and_distinct_per_env():
    from ingress import allocate_ports

    http_1, https_1 = allocate_ports("env-a")
    http_1_again, https_1_again = allocate_ports("env-a")
    http_2, https_2 = allocate_ports("env-b")

    assert (http_1, https_1) == (http_1_again, https_1_again)
    assert http_1 != https_1
    assert (http_1, https_1) != (http_2, https_2)
