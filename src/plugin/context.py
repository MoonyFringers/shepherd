# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Stable plugin context API injected into every plugin at startup.

Plugin authors import from this module (via ``from plugin import ...``) to
annotate constructor arguments and access Shepherd core managers without
depending on internal concrete classes.

All three views are :func:`runtime_checkable` Protocols satisfied
structurally by the concrete managers — no changes to the managers are
needed to implement them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

from config import (
    EnvironmentCfg,
    EnvironmentTemplateCfg,
    PluginCfg,
    ServiceTemplateCfg,
)
from config.config import RemoteCfg
from environment import Environment
from service import Service
from storage.snapshot import IndexCatalogue, SnapshotManifest


@runtime_checkable
class PluginConfigView(Protocol):
    """Config query operations exposed to plugins.

    Provides read access to the loaded Shepherd configuration — environments,
    templates, and plugin metadata.  Write operations (``store``, ``load``,
    ``set_plugin_enabled`` …) are intentionally excluded.
    """

    def get_environments(self) -> list[EnvironmentCfg]:
        """Return all configured environments."""
        ...

    def get_active_environment(self) -> Optional[EnvironmentCfg]:
        """Return the currently active environment, or ``None``."""
        ...

    def get_environment(self, envTag: str) -> Optional[EnvironmentCfg]:
        """Return the environment with the given tag, or ``None``."""
        ...

    def get_environment_templates(
        self,
    ) -> Optional[list[EnvironmentTemplateCfg]]:
        """Return all registered environment templates, or ``None``."""
        ...

    def get_service_templates(self) -> Optional[list[ServiceTemplateCfg]]:
        """Return all registered service templates, or ``None``."""
        ...

    def get_plugin(self, plugin_id: str) -> Optional[PluginCfg]:
        """Return the persisted config for *plugin_id*, or ``None``."""
        ...

    def get_plugin_dir(self, plugin_id: str) -> str:
        """Return the managed install directory for *plugin_id*."""
        ...


@runtime_checkable
class PluginEnvironmentView(Protocol):
    """Environment lifecycle operations exposed to plugins."""

    def list_envs(self) -> None:
        """Print a summary table of all environments."""
        ...

    def describe_env(self, env_tag: Optional[str]) -> None:
        """Print a kubectl-like single-row environment summary."""
        ...

    def get_environment_from_tag(
        self, env_tag: Optional[str]
    ) -> Optional[Environment]:
        """Resolve the environment for *env_tag*, or the active one."""
        ...

    def add_env(self, env_template: str, env_tag: str) -> None:
        """Realise a new environment from *env_template*."""
        ...

    def add_service(
        self,
        env_tag: Optional[str],
        svc_tag: str,
        svc_template: Optional[str],
        svc_class: Optional[str],
    ) -> None:
        """Add *svc_tag* to the environment identified by *env_tag*."""
        ...

    def delete_env(self, env_tag: str) -> None:
        """Delete the environment identified by *env_tag*."""
        ...

    def start_env(
        self,
        envCfg: EnvironmentCfg,
        timeout_seconds: Optional[int] = 60,
        watch: bool = False,
        keep_output: bool = False,
    ) -> None:
        """Start an environment."""
        ...

    def stop_env(self, envCfg: EnvironmentCfg, wait: bool = True) -> None:
        """Stop an environment."""
        ...

    def status_env(self, envCfg: EnvironmentCfg, watch: bool = False) -> None:
        """Display the live status of an environment."""
        ...


@runtime_checkable
class PluginServiceView(Protocol):
    """Service operations exposed to plugins."""

    def get_service(
        self, envCfg: EnvironmentCfg, svc_tag: str
    ) -> Optional[Service]:
        """Resolve *svc_tag* in *envCfg*, or ``None``."""
        ...

    def describe_svc(self, envCfg: EnvironmentCfg, svc_tag: str) -> None:
        """Print a kubectl-like single-row service summary."""
        ...

    def build_svc(
        self,
        envCfg: EnvironmentCfg,
        svc_tag: str,
        cnt_tag: Optional[str] = None,
    ) -> None:
        """Build the service (or one of its containers)."""
        ...

    def start_svc(
        self,
        envCfg: EnvironmentCfg,
        svc_tag: str,
        cnt_tag: Optional[str] = None,
    ) -> None:
        """Start the service (or one of its containers)."""
        ...

    def stop_svc(
        self,
        envCfg: EnvironmentCfg,
        svc_tag: str,
        cnt_tag: Optional[str] = None,
    ) -> None:
        """Stop the service (or one of its containers)."""
        ...

    def reload_svc(
        self,
        envCfg: EnvironmentCfg,
        svc_tag: str,
        cnt_tag: Optional[str] = None,
    ) -> None:
        """Reload the service (or one of its containers)."""
        ...

    def logs_svc(
        self,
        envCfg: EnvironmentCfg,
        svc_tag: str,
        cnt_tag: Optional[str] = None,
    ) -> None:
        """Stream stdout of the service (or one of its containers)."""
        ...

    def shell_svc(
        self,
        envCfg: EnvironmentCfg,
        svc_tag: str,
        cnt_tag: Optional[str] = None,
    ) -> None:
        """Open an interactive shell in the service container."""
        ...

    def render_svc(
        self,
        envCfg: EnvironmentCfg,
        svc_tag: str,
        target: bool,
        resolved: bool,
        output: str = "yaml",
    ) -> Optional[str]:
        """Render the service configuration as YAML or JSON."""
        ...


@runtime_checkable
class PluginRemoteView(Protocol):
    """Remote storage data access exposed to plugins.

    Provides programmatic access to configured remotes and their
    environment/snapshot indices.  Terminal-rendering helpers
    (``display_*``) and internal transport helpers (``_resolve_remote``,
    ``_build_backend``) are intentionally excluded — plugins that need to
    present remote data should format the returned objects themselves.
    """

    def list_envs(
        self, remote_name: Optional[str] = None
    ) -> tuple[RemoteCfg, IndexCatalogue]:
        """Return the index catalogue from *remote_name* (or the default)."""
        ...

    def list_snapshots(
        self, env_name: str, remote_name: Optional[str] = None
    ) -> tuple[RemoteCfg, list[SnapshotManifest]]:
        """Return all snapshot manifests for *env_name* from *remote_name*."""
        ...


@dataclass
class PluginContext:
    """Core manager access injected into every plugin at startup.

    Shepherd creates one ``PluginContext`` per plugin and passes it to
    :meth:`ShepherdPlugin.__init__`.  Plugin code stores it and accesses
    managers through the three typed view properties.

    ``config`` is always populated.

    ``environment``, ``service``, and ``remote`` are ``None`` during the Click
    command resolution phase (tab completion) and are set to the live managers
    once the full CLI bootstrap completes.  Plugin command handlers run after
    the full bootstrap, so by the time any handler executes, all three fields
    are available.
    """

    config: PluginConfigView
    environment: Optional[PluginEnvironmentView] = None
    service: Optional[PluginServiceView] = None
    remote: Optional[PluginRemoteView] = None
