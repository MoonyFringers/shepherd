# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

from __future__ import annotations

import importlib
import os
import sys
from collections import deque
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any, Callable, Sequence

import click
import yaml
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from completion import CompletionMng
from config import (
    ConfigMng,
    EnvironmentTemplateCfg,
    EnvTemplateFragmentCfg,
    FragmentRefCfg,
    PluginCfg,
    PluginDescriptorCfg,
    ServiceTemplateCfg,
    ServiceTemplateRefCfg,
    parse_plugin_descriptor,
)
from environment import EnvironmentFactory, EnvironmentMng
from plugin.api import (
    PluginCommandSpec,
    PluginCompletionSpec,
    PluginEnvFactorySpec,
    PluginRemoteBackendSpec,
    PluginSvcFactorySpec,
    ShepherdPlugin,
)
from plugin.context import (
    PluginContext,
    PluginEnvironmentView,
    PluginServiceView,
)
from remote import RemoteBackend
from service import ServiceFactory, ServiceMng
from util import Constants, Util

SUPPORTED_PLUGIN_API_VERSION = 1


def _loaded_plugin_registry() -> dict[str, "LoadedPlugin"]:
    """Create a typed default for the loaded-plugin registry."""
    return {}


def _command_registry() -> dict[str, dict[str, "RegisteredPluginCommand"]]:
    """Create a typed default for contributed executable commands."""
    return {}


def _completion_registry() -> dict[str, list["PluginCompletionSpec"]]:
    """Create a typed default for completion providers grouped by scope."""
    return {}


def _env_template_registry() -> dict[str, EnvironmentTemplateCfg]:
    """Create a typed default for canonical environment templates."""
    return {}


def _service_template_registry() -> dict[str, ServiceTemplateCfg]:
    """Create a typed default for canonical service templates."""
    return {}


def _env_factory_registry() -> dict[str, "PluginEnvFactorySpec"]:
    """Create a typed default for env factory registrations."""
    return {}


def _svc_factory_registry() -> dict[str, "PluginSvcFactorySpec"]:
    """Create a typed default for canonical service factory registrations."""
    return {}


def _remote_backend_registry() -> dict[str, "PluginRemoteBackendSpec"]:
    """Create a typed default for remote backend registrations."""
    return {}


def _fragment_registry() -> dict[str, EnvTemplateFragmentCfg]:
    """Create a typed default for fragment registrations."""
    return {}


@dataclass(frozen=True)
class LoadedPlugin:
    """Runtime record for one loaded plugin."""

    config: PluginCfg
    descriptor: PluginDescriptorCfg
    plugin_dir: str
    instance: ShepherdPlugin


@dataclass
class PluginRegistry:
    """
    In-memory registry of loaded plugin contributions.

    The runtime loader populates this once during CLI startup. Later rollout
    steps will consume these registries to inject commands, delegate
    completion, and resolve plugin-owned templates and factories.
    """

    plugins: dict[str, LoadedPlugin] = field(
        default_factory=_loaded_plugin_registry
    )
    commands: dict[str, dict[str, "RegisteredPluginCommand"]] = field(
        default_factory=_command_registry
    )
    completion_providers: dict[str, list[PluginCompletionSpec]] = field(
        default_factory=_completion_registry
    )
    env_templates: dict[str, EnvironmentTemplateCfg] = field(
        default_factory=_env_template_registry
    )
    service_templates: dict[str, ServiceTemplateCfg] = field(
        default_factory=_service_template_registry
    )
    env_template_fragments: dict[str, EnvTemplateFragmentCfg] = field(
        default_factory=_fragment_registry
    )
    env_factories: dict[str, PluginEnvFactorySpec] = field(
        default_factory=_env_factory_registry
    )
    service_factories: dict[str, PluginSvcFactorySpec] = field(
        default_factory=_svc_factory_registry
    )
    remote_backends: dict[str, PluginRemoteBackendSpec] = field(
        default_factory=_remote_backend_registry
    )


@dataclass(frozen=True)
class RegisteredPluginCommand:
    """One validated command contribution stored in the runtime registry."""

    plugin_id: str
    spec: PluginCommandSpec


class PluginRuntimeMng:
    """
    Load enabled plugins and register their declared runtime contributions.

    This manager is used only on the normal fail-fast startup path. The
    administrative `plugin` scope keeps using the safe bootstrap path exposed
    by `PluginMng`, so operators can still disable or remove a broken plugin.
    """

    CORE_SCOPE_VERBS = {
        scope: set(verbs)
        for scope, verbs in CompletionMng.CORE_SCOPE_VERBS.items()
    }
    PLUGIN_TEMPLATES_DIR = "templates"

    def __init__(
        self,
        configMng: ConfigMng,
        environmentMng: EnvironmentMng | None = None,
        serviceMng: ServiceMng | None = None,
    ):
        self.configMng = configMng
        self._environmentMng: PluginEnvironmentView | None = environmentMng
        self._serviceMng: PluginServiceView | None = serviceMng
        self.registry = PluginRegistry()
        self.load_enabled_plugins()

    def attach_managers(
        self,
        environmentMng: EnvironmentMng,
        serviceMng: ServiceMng,
    ) -> None:
        """Inject managers into already-loaded plugin contexts.

        Called by :class:`ShepherdMng` when plugins were pre-loaded during
        the Click command resolution phase (tab completion) and the full
        manager set becomes available only after the root CLI callback runs.
        """
        self._environmentMng = environmentMng
        self._serviceMng = serviceMng
        for loaded in self.registry.plugins.values():
            loaded.instance.context.environment = environmentMng
            loaded.instance.context.service = serviceMng

    def load_enabled_plugins(self) -> PluginRegistry:
        """
        Load all enabled plugins from config into the runtime registry.

        Plugins are loaded eagerly so command registration, collision checks,
        and later extension hooks see the complete active plugin set.
        Dependencies declared via ``depends_on`` are validated and plugins are
        loaded in dependency order (dependents after their dependencies).
        """
        enabled = [p for p in self.configMng.get_plugins() if p.is_enabled()]
        sorted_plugins, descriptors = self._topo_sort_plugins(enabled)
        for plugin_cfg in sorted_plugins:
            loaded = self._load_plugin(plugin_cfg, descriptors[plugin_cfg.id])
            self._register_plugin(loaded)
        return self.registry

    def _topo_sort_plugins(
        self, enabled: list[PluginCfg]
    ) -> tuple[list[PluginCfg], dict[str, PluginDescriptorCfg]]:
        """Return *enabled* plugins in dependency order (Kahn's algorithm).

        Reads each plugin's descriptor (parse-only, no import) to inspect
        ``depends_on``.  Hard-fails when a declared dependency is absent from
        the enabled set, when a version constraint is not satisfied, or when
        the dependency graph contains a cycle.

        Returns the sorted plugin list together with the already-parsed
        descriptor map so callers can reuse it without a second disk read.
        """
        by_id: dict[str, PluginCfg] = {p.id: p for p in enabled}

        # Load descriptors (parse only) to inspect depends_on.
        descriptors: dict[str, PluginDescriptorCfg] = {}
        for plugin_cfg in enabled:
            plugin_dir = self.configMng.get_plugin_dir(plugin_cfg.id)
            if not os.path.isdir(plugin_dir):
                Util.print_error_and_die(
                    f"Enabled plugin '{plugin_cfg.id}' is missing from the "
                    f"managed plugin root: {plugin_dir}"
                )
            descriptor_path = os.path.join(
                plugin_dir, self.configMng.constants.PLUGIN_DESCRIPTOR_FILE
            )
            descriptors[plugin_cfg.id] = self._load_descriptor(
                plugin_cfg.id, descriptor_path
            )

        # Build adjacency: plugin_id → set of plugin_ids it depends on.
        in_degree: dict[str, int] = {p.id: 0 for p in enabled}
        dependents: dict[str, list[str]] = {p.id: [] for p in enabled}

        for plugin_cfg in enabled:
            desc = descriptors[plugin_cfg.id]
            for dep in desc.depends_on or []:
                if dep.id not in by_id:
                    Util.print_error_and_die(
                        f"Plugin '{plugin_cfg.id}' depends on '{dep.id}' "
                        "which is not installed or not enabled."
                    )
                if dep.version is not None:
                    self._validate_version_constraint(
                        plugin_cfg.id,
                        dep.id,
                        descriptors[dep.id].version,
                        dep.version,
                    )
                dependents[dep.id].append(plugin_cfg.id)
                in_degree[plugin_cfg.id] += 1

        # Kahn's BFS topological sort.
        queue: deque[str] = deque(
            pid for pid, deg in in_degree.items() if deg == 0
        )
        sorted_ids: list[str] = []
        while queue:
            pid = queue.popleft()
            sorted_ids.append(pid)
            for dependent_id in dependents[pid]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(dependent_id)

        if len(sorted_ids) != len(enabled):
            Util.print_error_and_die(
                "Circular dependency detected among enabled plugins: "
                + ", ".join(pid for pid in in_degree if in_degree[pid] > 0)
            )

        return [by_id[pid] for pid in sorted_ids], descriptors

    def _validate_version_constraint(
        self,
        dependent_id: str,
        dependency_id: str,
        installed_version: str,
        specifier: str,
    ) -> None:
        """Hard-fail if *installed_version* does not satisfy *specifier*."""
        try:
            ver = Version(installed_version)
            spec = SpecifierSet(specifier)
        except InvalidVersion as exc:
            Util.print_error_and_die(
                f"Plugin '{dependency_id}' has invalid version string "
                f"'{installed_version}': {exc}"
            )
            raise AssertionError("unreachable")
        except InvalidSpecifier as exc:
            Util.print_error_and_die(
                f"Plugin '{dependent_id}' declares invalid version specifier "
                f"'{specifier}' for dependency '{dependency_id}': {exc}"
            )
            raise AssertionError("unreachable")

        if ver not in spec:
            Util.print_error_and_die(
                f"Plugin '{dependent_id}' requires "
                f"'{dependency_id}{specifier}' but "
                f"installed version is '{installed_version}'."
            )

    def _load_plugin(
        self,
        plugin_cfg: PluginCfg,
        descriptor: PluginDescriptorCfg | None = None,
    ) -> LoadedPlugin:
        """Load one enabled plugin from its managed install directory.

        *descriptor* may be supplied when the caller has already parsed it
        (e.g. from ``_topo_sort_plugins``) to avoid a redundant disk read.
        """
        plugin_dir = self.configMng.get_plugin_dir(plugin_cfg.id)
        if not os.path.isdir(plugin_dir):
            Util.print_error_and_die(
                f"Enabled plugin '{plugin_cfg.id}' is missing from the "
                f"managed plugin root: {plugin_dir}"
            )

        if descriptor is None:
            descriptor_path = os.path.join(
                plugin_dir, self.configMng.constants.PLUGIN_DESCRIPTOR_FILE
            )
            descriptor = self._load_descriptor(plugin_cfg.id, descriptor_path)
        self._validate_descriptor(plugin_cfg, descriptor)
        plugin = self._import_plugin(plugin_cfg.id, plugin_dir, descriptor)
        return LoadedPlugin(
            config=plugin_cfg,
            descriptor=descriptor,
            plugin_dir=plugin_dir,
            instance=plugin,
        )

    def _load_descriptor(
        self, plugin_id: str, descriptor_path: str
    ) -> PluginDescriptorCfg:
        """Parse and validate the installed descriptor for one plugin."""
        try:
            with open(
                descriptor_path, "r", encoding="utf-8"
            ) as descriptor_file:
                return parse_plugin_descriptor(descriptor_file.read())
        except (
            OSError,
            KeyError,
            TypeError,
            ValueError,
            yaml.YAMLError,
        ) as exc:
            Util.print_error_and_die(
                f"Invalid plugin descriptor for '{plugin_id}': {exc}"
            )
            raise AssertionError("unreachable")

    def _validate_descriptor(
        self, plugin_cfg: PluginCfg, descriptor: PluginDescriptorCfg
    ) -> None:
        """Reject stale or incompatible installed plugin metadata."""
        if descriptor.id == self.configMng.constants.CORE_PLUGIN_ID:
            Util.print_error_and_die(
                f"Plugin id '{descriptor.id}' is reserved for core "
                "resources."
            )
        if descriptor.id != plugin_cfg.id:
            Util.print_error_and_die(
                f"Installed plugin '{plugin_cfg.id}' has descriptor id "
                f"'{descriptor.id}'."
            )
        if (
            plugin_cfg.version is not None
            and descriptor.version != plugin_cfg.version
        ):
            Util.print_error_and_die(
                f"Installed plugin '{plugin_cfg.id}' version "
                f"'{descriptor.version}' does not match configured version "
                f"'{plugin_cfg.version}'."
            )
        if descriptor.plugin_api_version != SUPPORTED_PLUGIN_API_VERSION:
            Util.print_error_and_die(
                f"Plugin '{plugin_cfg.id}' declares unsupported "
                f"plugin_api_version={descriptor.plugin_api_version}. "
                f"Supported version: {SUPPORTED_PLUGIN_API_VERSION}."
            )

    def _import_plugin(
        self,
        plugin_id: str,
        plugin_dir: str,
        descriptor: PluginDescriptorCfg,
    ) -> ShepherdPlugin:
        """
        Import and instantiate the plugin entrypoint declared in the descriptor.

        The declared module name is imported as-is so plugin-internal absolute
        imports keep working. We still guard against module-root collisions by
        tracking which plugin owns each imported top-level package name.
        """
        module_name = descriptor.entrypoint.module
        class_name = descriptor.entrypoint.class_name
        module_root = module_name.split(".", 1)[0]
        self._prepare_module_root(plugin_id, plugin_dir, module_root)

        try:
            sys.path.insert(0, plugin_dir)
            module = importlib.import_module(module_name)
        except Exception as exc:
            self._purge_module_root(module_root)
            Util.print_error_and_die(
                f"Failed to import plugin '{plugin_id}' entrypoint "
                f"'{module_name}.{class_name}': {exc}"
            )
            raise AssertionError("unreachable")
        finally:
            if sys.path and sys.path[0] == plugin_dir:
                sys.path.pop(0)

        self._tag_plugin_modules(plugin_id, plugin_dir, module_root)

        try:
            plugin_class = getattr(module, class_name)
        except AttributeError:
            Util.print_error_and_die(
                f"Plugin '{plugin_id}' entrypoint class '{class_name}' was "
                f"not found in module '{module_name}'."
            )
            raise AssertionError("unreachable")

        if not (
            isinstance(plugin_class, type)
            and issubclass(plugin_class, ShepherdPlugin)
        ):
            Util.print_error_and_die(
                f"Plugin '{plugin_id}' entrypoint "
                f"'{module_name}.{class_name}' "
                "must implement ShepherdPlugin."
            )
            raise AssertionError("unreachable")

        ctx = PluginContext(
            config=self.configMng,
            environment=self._environmentMng,
            service=self._serviceMng,
        )
        try:
            plugin = plugin_class(ctx)
        except Exception as exc:
            Util.print_error_and_die(
                f"Failed to instantiate plugin '{plugin_id}' entrypoint "
                f"'{module_name}.{class_name}': {exc}"
            )
            raise AssertionError("unreachable")

        return plugin

    def _prepare_module_root(
        self, plugin_id: str, plugin_dir: str, module_root: str
    ) -> None:
        """
        Validate or reset the declared top-level module root before import.

        Repeated loads of the same plugin id in one Python process are allowed
        and force a fresh import from the current managed directory. A
        different plugin claiming the same module root is rejected.
        """
        root_module = sys.modules.get(module_root)
        if root_module is None:
            return

        owner_id = getattr(root_module, "__shepherd_plugin_id__", None)
        owner_dir = getattr(root_module, "__shepherd_plugin_dir__", None)
        if owner_id == plugin_id:
            self._purge_module_root(module_root)
            return

        if owner_id is not None and owner_dir is not None:
            Util.print_error_and_die(
                f"Plugin '{plugin_id}' module root '{module_root}' collides "
                f"with plugin '{owner_id}'."
            )

        Util.print_error_and_die(
            f"Plugin '{plugin_id}' module root '{module_root}' collides with "
            "an existing Python module."
        )

    def _purge_module_root(self, module_root: str) -> None:
        """Remove a previously loaded plugin module root and its submodules."""
        for module_name in list(sys.modules):
            if module_name == module_root or module_name.startswith(
                f"{module_root}."
            ):
                del sys.modules[module_name]

    def _tag_plugin_modules(
        self, plugin_id: str, plugin_dir: str, module_root: str
    ) -> None:
        """Tag loaded plugin modules so future loads can detect ownership."""
        for module_name, module in sys.modules.items():
            if module_name == module_root or module_name.startswith(
                f"{module_root}."
            ):
                self._tag_plugin_module(module, plugin_id, plugin_dir)

    def _tag_plugin_module(
        self, module: ModuleType, plugin_id: str, plugin_dir: str
    ) -> None:
        """Attach plugin ownership metadata to one loaded module."""
        setattr(module, "__shepherd_plugin_id__", plugin_id)
        setattr(module, "__shepherd_plugin_dir__", plugin_dir)

    def _register_plugin(self, loaded: LoadedPlugin) -> None:
        """Register every contribution published by one loaded plugin."""
        plugin_id = loaded.descriptor.id
        if plugin_id in self.registry.plugins:
            Util.print_error_and_die(f"Plugin '{plugin_id}' is already loaded.")

        # Collect contributions once so they can be capability-checked and
        # registered without calling each getter twice.
        commands = loaded.instance.get_commands()
        completions = loaded.instance.get_completion_providers()
        env_factories = loaded.instance.get_env_factories()
        svc_factories = loaded.instance.get_service_factories()
        remote_backends = loaded.instance.get_remote_backends()

        self._check_capabilities(
            loaded,
            commands,
            completions,
            env_factories,
            svc_factories,
            remote_backends,
        )

        self.registry.plugins[plugin_id] = loaded
        self._register_commands(plugin_id, commands)
        self._register_completion_providers(plugin_id, completions)
        self._register_descriptor_templates(loaded)
        self._register_env_factories(plugin_id, env_factories)
        self._register_svc_factories(plugin_id, svc_factories)
        self._register_remote_backends(plugin_id, remote_backends)

    def _check_capabilities(
        self,
        loaded: LoadedPlugin,
        commands: Sequence[PluginCommandSpec],
        completions: Sequence[PluginCompletionSpec],
        env_factories: Sequence[PluginEnvFactorySpec],
        svc_factories: Sequence[PluginSvcFactorySpec],
        remote_backends: Sequence[PluginRemoteBackendSpec],
    ) -> None:
        """Reject plugins that contribute to undeclared capability areas.

        If ``capabilities`` is absent or empty the check is skipped entirely
        (backward-compatible with plugins that predate the field).  A declared
        area that returns no contributions is allowed — advertised ≠ mandatory.
        """
        caps = loaded.descriptor.capabilities
        if not caps:
            return
        plugin_id = loaded.descriptor.id
        descriptor = loaded.descriptor
        checks: list[tuple[str, bool]] = [
            ("commands", bool(commands)),
            ("completion", bool(completions)),
            (
                # Templates are declared statically in plugin.yaml, not
                # returned by a getter — hence the descriptor field check
                # rather than a get_*() call like the other areas.
                "templates",
                bool(
                    descriptor.env_templates
                    or descriptor.service_templates
                    or descriptor.env_template_fragments
                ),
            ),
            ("env_factories", bool(env_factories)),
            ("svc_factories", bool(svc_factories)),
            ("remote_backends", bool(remote_backends)),
        ]
        for area, has_contributions in checks:
            if has_contributions and not caps.get(area, False):
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}': contributions found for '{area}' "
                    f"but 'capabilities.{area}' is not declared true in "
                    f"plugin.yaml."
                )

    def _register_commands(
        self,
        plugin_id: str,
        commands: Sequence[PluginCommandSpec],
    ) -> None:
        """Register scope and verb contributions with collision checks."""
        seen: set[tuple[str, str]] = set()
        for command in commands:
            scope = command.scope
            verb = command.verb
            command_obj: Any = command.command
            if (scope, verb) in seen:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' declares duplicate command "
                    f"'{scope} {verb}'."
                )
            seen.add((scope, verb))

            if scope == "plugin":
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' command '{scope} {verb}' "
                    "uses reserved administrative scope 'plugin'."
                )
            if verb in self.CORE_SCOPE_VERBS.get(scope, set()):
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' command '{scope} {verb}' "
                    "collides with a core command."
                )
            if not isinstance(command_obj, click.Command):
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' command '{scope} {verb}' must "
                    "provide a Click command."
                )
            if command_obj.name != verb:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' command '{scope} {verb}' must "
                    "use a Click command with the same verb name."
                )

            scope_commands = self.registry.commands.setdefault(scope, {})
            owner = scope_commands.get(verb)
            if owner is not None:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' command '{scope} {verb}' "
                    f"collides with plugin '{owner.plugin_id}'."
                )
            scope_commands[verb] = RegisteredPluginCommand(
                plugin_id=plugin_id, spec=command
            )

    def _register_completion_providers(
        self,
        plugin_id: str,
        providers: Sequence[PluginCompletionSpec],
    ) -> None:
        """Register completion providers, grouped by the scope they serve."""
        seen_scopes: set[str] = set()
        for provider in providers:
            if provider.scope in seen_scopes:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' declares multiple completion "
                    f"providers for scope '{provider.scope}'."
                )
            if not self._is_completion_provider(provider.provider):
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' completion provider for scope "
                    f"'{provider.scope}' must be callable or expose "
                    "'get_completions(args)'."
                )
            seen_scopes.add(provider.scope)
            self.registry.completion_providers.setdefault(
                provider.scope, []
            ).append(provider)

    def _is_completion_provider(
        self, provider: Callable[[list[str]], list[str]]
    ) -> bool:
        """
        Return whether the completion provider exposes an executable shape.
        """
        if callable(provider):
            return True
        return callable(getattr(provider, "get_completions", None))

    def _register_descriptor_templates(self, loaded: LoadedPlugin) -> None:
        """Register declarative templates loaded from one plugin descriptor."""
        plugin_id = loaded.descriptor.id
        service_local_ids = {
            template.tag
            for template in (loaded.descriptor.service_templates or [])
        }
        fragment_local_ids = {
            fragment.tag
            for fragment in (loaded.descriptor.env_template_fragments or [])
        }
        self._register_env_templates(
            plugin_id,
            loaded.descriptor.env_templates or (),
            service_local_ids,
            fragment_local_ids,
        )
        self._register_service_templates(
            plugin_id,
            loaded.descriptor.service_templates or (),
        )
        self._register_fragments(
            plugin_id,
            loaded.descriptor.env_template_fragments or (),
            service_local_ids,
        )

    def _register_env_templates(
        self,
        plugin_id: str,
        templates: Sequence[EnvironmentTemplateCfg],
        service_local_ids: set[str],
        fragment_local_ids: set[str] | None = None,
    ) -> None:
        """Register namespaced environment templates from the descriptor."""
        for template in templates:
            if "/" in template.tag:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' environment template id "
                    f"'{template.tag}' must "
                    "not contain '/'."
                )
            canonical_id = f"{plugin_id}/{template.tag}"
            if canonical_id in self.registry.env_templates:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' declares duplicate environment "
                    f"template '{canonical_id}'."
                )
            self.registry.env_templates[canonical_id] = (
                self._namespace_environment_template(
                    plugin_id,
                    template,
                    service_local_ids,
                    fragment_local_ids or set(),
                )
            )

    def _register_service_templates(
        self,
        plugin_id: str,
        templates: Sequence[ServiceTemplateCfg],
    ) -> None:
        """Register namespaced service templates from the descriptor."""
        for template in templates:
            if "/" in template.tag:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' service template id "
                    f"'{template.tag}' must not contain '/'."
                )
            canonical_id = f"{plugin_id}/{template.tag}"
            if canonical_id in self.registry.service_templates:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' declares duplicate service "
                    f"template '{canonical_id}'."
                )
            self.registry.service_templates[canonical_id] = (
                self._namespace_service_template(plugin_id, template)
            )

    def _register_fragments(
        self,
        plugin_id: str,
        fragments: Sequence[EnvTemplateFragmentCfg],
        service_local_ids: set[str],
    ) -> None:
        """Register namespaced env template fragments from the descriptor."""
        for fragment in fragments:
            if "/" in fragment.tag:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' fragment id '{fragment.tag}' must "
                    "not contain '/'."
                )
            canonical_id = f"{plugin_id}/{fragment.tag}"
            if canonical_id in self.registry.env_template_fragments:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' declares duplicate fragment "
                    f"'{canonical_id}'."
                )
            self.registry.env_template_fragments[canonical_id] = (
                self._namespace_fragment(plugin_id, fragment, service_local_ids)
            )

    def _namespace_fragment(
        self,
        plugin_id: str,
        fragment: EnvTemplateFragmentCfg,
        service_local_ids: set[str],
    ) -> EnvTemplateFragmentCfg:
        """Return one plugin fragment with canonicalized ids."""
        return EnvTemplateFragmentCfg(
            tag=f"{plugin_id}/{fragment.tag}",
            service_template=self._namespace_service_template_ref(
                plugin_id, fragment.service_template, service_local_ids
            ),
            probes=fragment.probes,
            volumes=fragment.volumes,
            networks=fragment.networks,
        )

    def _namespace_environment_template(
        self,
        plugin_id: str,
        template: EnvironmentTemplateCfg,
        service_local_ids: set[str],
        fragment_local_ids: set[str] | None = None,
    ) -> EnvironmentTemplateCfg:
        """Return one plugin env template with canonicalized ids."""
        service_templates = template.service_templates
        if service_templates is not None:
            service_templates = [
                self._namespace_service_template_ref(
                    plugin_id, service_template, service_local_ids
                )
                for service_template in service_templates
            ]

        fragments = template.fragments
        if fragments is not None:
            fragments = [
                self._namespace_fragment_ref(
                    plugin_id, frag_ref, fragment_local_ids or set()
                )
                for frag_ref in fragments
            ]

        return EnvironmentTemplateCfg(
            tag=f"{plugin_id}/{template.tag}",
            factory=self._namespace_factory_id(
                plugin_id,
                template.factory,
                Constants.ENV_FACTORY_DEFAULT,
            ),
            service_templates=service_templates,
            probes=template.probes,
            networks=template.networks,
            volumes=template.volumes,
            fragments=fragments,
            ready=template.ready,
        )

    def _namespace_service_template(
        self,
        plugin_id: str,
        template: ServiceTemplateCfg,
    ) -> ServiceTemplateCfg:
        """Return one plugin service template with canonicalized ids."""
        return ServiceTemplateCfg(
            tag=f"{plugin_id}/{template.tag}",
            factory=self._namespace_factory_id(
                plugin_id,
                template.factory,
                Constants.SVC_FACTORY_DEFAULT,
            ),
            labels=template.labels,
            properties=template.properties,
            containers=template.containers,
            start=template.start,
        )

    def _namespace_service_template_ref(
        self,
        plugin_id: str,
        template_ref: ServiceTemplateRefCfg,
        service_local_ids: set[str],
    ) -> ServiceTemplateRefCfg:
        """Return one env->service template reference with canonical ids."""
        template_name = template_ref.template
        if "/" not in template_name and template_name in service_local_ids:
            template_name = f"{plugin_id}/{template_name}"
        return type(template_ref)(
            template=template_name,
            tag=template_ref.tag,
        )

    def _namespace_fragment_ref(
        self,
        plugin_id: str,
        frag_ref: FragmentRefCfg,
        fragment_local_ids: set[str],
    ) -> FragmentRefCfg:
        """Return one env_template->fragment reference with a canonical id.

        A local fragment id (no ``/``) that matches one declared in the same
        plugin's ``env_template_fragments`` is expanded to
        ``plugin-id/local-id``.  Already-namespaced ids (containing ``/``) are
        left unchanged so cross-plugin references work transparently.
        """
        frag_id = frag_ref.id
        if "/" not in frag_id and frag_id in fragment_local_ids:
            frag_id = f"{plugin_id}/{frag_id}"
        return type(frag_ref)(id=frag_id, with_values=frag_ref.with_values)

    def _namespace_factory_id(
        self,
        plugin_id: str,
        factory_id: str,
        core_factory_id: str,
    ) -> str:
        """Namespace plugin-owned factory ids while preserving core ids."""
        if not factory_id or factory_id == core_factory_id or "/" in factory_id:
            return factory_id
        return f"{plugin_id}/{factory_id}"

    def _register_env_factories(
        self,
        plugin_id: str,
        factories: Sequence[PluginEnvFactorySpec],
    ) -> None:
        """Register namespaced environment factories in the runtime registry."""
        for factory in factories:
            if "/" in factory.id:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' environment factory id "
                    f"'{factory.id}' must not contain '/'."
                )
            canonical_id = f"{plugin_id}/{factory.id}"
            if canonical_id in self.registry.env_factories:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' declares duplicate environment "
                    f"factory '{canonical_id}'."
                )
            if not self._is_env_factory_provider(factory.provider):
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' environment factory "
                    f"'{canonical_id}' must provide a factory instance, "
                    "factory class, or factory builder callable."
                )
            self.registry.env_factories[canonical_id] = factory

    def _register_svc_factories(
        self,
        plugin_id: str,
        factories: Sequence[PluginSvcFactorySpec],
    ) -> None:
        """Register namespaced service factories in the runtime registry."""
        for factory in factories:
            if "/" in factory.id:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' service factory id "
                    f"'{factory.id}' must not contain '/'."
                )
            canonical_id = f"{plugin_id}/{factory.id}"
            if canonical_id in self.registry.service_factories:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' declares duplicate service "
                    f"factory '{canonical_id}'."
                )
            if not self._is_svc_factory_provider(factory.provider):
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' service factory '{canonical_id}' "
                    "must provide a factory instance, factory class, or "
                    "factory builder callable."
                )
            self.registry.service_factories[canonical_id] = factory

    def _is_env_factory_provider(self, provider: Any) -> bool:
        # provider: Any — pyright cannot narrow the EnvFactoryProvider union
        # (EnvironmentFactory | Callable[...]) via isinstance alone.
        """Return whether the env factory provider can be materialized."""
        return isinstance(provider, EnvironmentFactory) or callable(provider)

    def _is_svc_factory_provider(self, provider: Any) -> bool:
        # provider: Any — pyright cannot narrow the SvcFactoryProvider union
        # (ServiceFactory | Callable[...]) via isinstance alone.
        """Return whether the svc factory provider can be materialized."""
        return isinstance(provider, ServiceFactory) or callable(provider)

    _CORE_BACKEND_TYPE_IDS: frozenset[str] = frozenset({"ftp", "sftp"})

    def _register_remote_backends(
        self,
        plugin_id: str,
        backends: Sequence[PluginRemoteBackendSpec],
    ) -> None:
        """Register plugin-contributed remote backend transports."""
        for backend in backends:
            if backend.type_id in self._CORE_BACKEND_TYPE_IDS:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' remote backend type_id "
                    f"'{backend.type_id}' collides with a core built-in."
                )
            if backend.type_id in self.registry.remote_backends:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' declares duplicate remote "
                    f"backend type_id '{backend.type_id}'."
                )
            if not self._is_remote_backend_provider(backend.provider):
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' remote backend "
                    f"'{backend.type_id}' must provide a RemoteBackend "
                    "instance or a zero-argument factory callable."
                )
            self.registry.remote_backends[backend.type_id] = backend

    def _is_remote_backend_provider(self, provider: Any) -> bool:
        """Return whether the remote backend provider can be materialized."""
        return isinstance(provider, RemoteBackend) or callable(provider)

    def build_remote_backend(self, type_id: str) -> RemoteBackend | None:
        """Return a plugin-owned RemoteBackend for *type_id*, or None."""
        spec = self.registry.remote_backends.get(type_id)
        if spec is None:
            return None
        provider = spec.provider
        if isinstance(provider, RemoteBackend):
            return provider
        if callable(provider):
            return provider()
        raise ValueError(
            f"Plugin remote backend '{type_id}' provider is invalid."
        )

    def get_environment_template(
        self, template_id: str
    ) -> EnvironmentTemplateCfg | None:
        """Return one plugin-owned environment template by canonical id."""
        return self.registry.env_templates.get(template_id)

    def get_service_template(
        self, template_id: str
    ) -> ServiceTemplateCfg | None:
        """Return one plugin-owned service template by canonical id."""
        return self.registry.service_templates.get(template_id)

    def get_service_template_path(self, template_id: str) -> str | None:
        """
        Return the installed asset path for a plugin-owned service template.
        """
        if template_id not in self.registry.service_templates:
            return None

        plugin_id, local_template_id = self._split_canonical_id(template_id)
        plugin = self.registry.plugins.get(plugin_id)
        if plugin is None:
            return None

        template_path = os.path.join(
            plugin.plugin_dir,
            self.PLUGIN_TEMPLATES_DIR,
            Constants.SVC_TEMPLATES_DIR,
            local_template_id,
        )
        if os.path.isdir(template_path):
            return template_path
        return None

    def build_service_factory(
        self,
        factory_id: str,
        configMng: ConfigMng,
    ) -> ServiceFactory | None:
        """Materialize one plugin-owned service factory by canonical id."""
        spec = self.registry.service_factories.get(factory_id)
        if spec is None:
            return None
        return self._materialize_service_factory(
            factory_id, spec.provider, configMng
        )

    def build_environment_factory(
        self,
        factory_id: str,
        configMng: ConfigMng,
        svc_factory: ServiceFactory,
        cli_flags: dict[str, Any] | None = None,
    ) -> EnvironmentFactory | None:
        """Materialize one plugin-owned environment factory by canonical id."""
        spec = self.registry.env_factories.get(factory_id)
        if spec is None:
            return None
        return self._materialize_environment_factory(
            factory_id, spec.provider, configMng, svc_factory, cli_flags
        )

    def _materialize_service_factory(
        self,
        factory_id: str,
        provider: Any,
        configMng: ConfigMng,
    ) -> ServiceFactory:
        """Build a concrete service factory from the stored provider."""
        if isinstance(provider, ServiceFactory):
            return provider

        if callable(provider):
            instance = provider(configMng)
            if isinstance(instance, ServiceFactory):
                return instance

        raise ValueError(f"Plugin service factory '{factory_id}' is invalid.")

    def _materialize_environment_factory(
        self,
        factory_id: str,
        provider: Any,
        configMng: ConfigMng,
        svc_factory: ServiceFactory,
        cli_flags: dict[str, Any] | None = None,
    ) -> EnvironmentFactory:
        """Build a concrete environment factory from the stored provider."""
        if isinstance(provider, EnvironmentFactory):
            return provider

        if callable(provider):
            instance = provider(configMng, svc_factory, cli_flags)
            if isinstance(instance, EnvironmentFactory):
                return instance

        raise ValueError(
            f"Plugin environment factory '{factory_id}' is invalid."
        )

    def _split_canonical_id(self, canonical_id: str) -> tuple[str, str]:
        """Split one canonical plugin-owned id into plugin and local parts."""
        if "/" not in canonical_id:
            raise ValueError(
                f"Plugin-owned identifier '{canonical_id}' is not namespaced."
            )
        plugin_id, local_id = canonical_id.split("/", 1)
        return plugin_id, local_id
