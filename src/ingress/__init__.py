# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Ingress provider abstraction and the core-shipped traefik default."""

from .provider import (
    CORE_INGRESS_PROVIDER_TYPE_IDS,
    IngressContainerPlan,
    IngressContainerRef,
    IngressPlan,
    IngressProvider,
    IngressProxySpec,
    allocate_ports,
)
from .traefik_provider import TraefikIngressProvider

__all__ = [
    "CORE_INGRESS_PROVIDER_TYPE_IDS",
    "IngressContainerPlan",
    "IngressContainerRef",
    "IngressPlan",
    "IngressProvider",
    "IngressProxySpec",
    "TraefikIngressProvider",
    "allocate_ports",
]
