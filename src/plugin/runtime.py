# Copyright (c) 2025 Moony Fringers
#
# This file is part of Shepherd Core Stack
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass, field
from types import ModuleType
from typing import Sequence

import yaml

from completion import CompletionMng
from config import (
    ConfigMng,
    PluginCfg,
    PluginDescriptorCfg,
    parse_plugin_descriptor,
)
from plugin.api import (
    PluginCommandSpec,
    PluginCompletionSpec,
    PluginFactorySpec,
    PluginTemplateSpec,
    ShepherdPlugin,
)
from util import Util

SUPPORTED_PLUGIN_API_VERSION = 1


def _loaded_plugin_registry() -> dict[str, "LoadedPlugin"]:
    """Create a typed default for the loaded-plugin registry."""
    return {}


def _command_registry() -> dict[str, dict[str, str]]:
    """Create a typed default for contributed scope and verb ownership."""
    return {}


def _completion_registry() -> dict[str, list["PluginCompletionSpec"]]:
    """Create a typed default for completion providers grouped by scope."""
    return {}


def _template_registry() -> dict[str, "PluginTemplateSpec"]:
    """Create a typed default for canonical template registrations."""
    return {}


def _factory_registry() -> dict[str, "PluginFactorySpec"]:
    """Create a typed default for canonical factory registrations."""
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
    commands: dict[str, dict[str, str]] = field(
        default_factory=_command_registry
    )
    completion_providers: dict[str, list[PluginCompletionSpec]] = field(
        default_factory=_completion_registry
    )
    env_templates: dict[str, PluginTemplateSpec] = field(
        default_factory=_template_registry
    )
    service_templates: dict[str, PluginTemplateSpec] = field(
        default_factory=_template_registry
    )
    env_factories: dict[str, PluginFactorySpec] = field(
        default_factory=_factory_registry
    )
    service_factories: dict[str, PluginFactorySpec] = field(
        default_factory=_factory_registry
    )


class PluginRuntimeMng:
    """
    Load enabled plugins and register their declared runtime contributions.

    This manager is used only on the normal fail-fast startup path. The
    administrative `plugin` scope keeps using the safe bootstrap path exposed
    by `PluginMng`, so operators can still disable or remove a broken plugin.
    """

    CORE_SCOPE_VERBS = {
        scope: set(verbs) for scope, verbs in CompletionMng.SCOPE_VERBS.items()
    }

    def __init__(self, configMng: ConfigMng):
        self.configMng = configMng
        self.registry = PluginRegistry()
        self.load_enabled_plugins()

    def load_enabled_plugins(self) -> PluginRegistry:
        """
        Load all enabled plugins from config into the runtime registry.

        Plugins are loaded eagerly so command registration, collision checks,
        and later extension hooks see the complete active plugin set.
        """
        for plugin_cfg in self.configMng.get_plugins():
            if not plugin_cfg.is_enabled():
                continue
            loaded = self._load_plugin(plugin_cfg)
            self._register_plugin(loaded)
        return self.registry

    def _load_plugin(self, plugin_cfg: PluginCfg) -> LoadedPlugin:
        """Load one enabled plugin from its managed install directory."""
        plugin_dir = self.configMng.get_plugin_dir(plugin_cfg.id)
        if not os.path.isdir(plugin_dir):
            Util.print_error_and_die(
                f"Enabled plugin '{plugin_cfg.id}' is missing from the "
                f"managed plugin root: {plugin_dir}"
            )

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

        try:
            plugin = plugin_class()
        except Exception as exc:
            Util.print_error_and_die(
                f"Failed to instantiate plugin '{plugin_id}' entrypoint "
                f"'{module_name}.{class_name}': {exc}"
            )
            raise AssertionError("unreachable")

        if not isinstance(plugin, ShepherdPlugin):
            Util.print_error_and_die(
                f"Plugin '{plugin_id}' entrypoint '{module_name}.{class_name}' "
                "must implement ShepherdPlugin."
            )
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
        self.registry.plugins[plugin_id] = loaded
        self._register_commands(plugin_id, loaded.instance.get_commands())
        self._register_completion_providers(
            plugin_id, loaded.instance.get_completion_providers()
        )
        self._register_templates(
            plugin_id,
            loaded.instance.get_env_templates(),
            self.registry.env_templates,
            "environment template",
        )
        self._register_templates(
            plugin_id,
            loaded.instance.get_service_templates(),
            self.registry.service_templates,
            "service template",
        )
        self._register_factories(
            plugin_id,
            loaded.instance.get_env_factories(),
            self.registry.env_factories,
            "environment factory",
        )
        self._register_factories(
            plugin_id,
            loaded.instance.get_service_factories(),
            self.registry.service_factories,
            "service factory",
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
            if (scope, verb) in seen:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' declares duplicate command "
                    f"'{scope} {verb}'."
                )
            seen.add((scope, verb))

            if verb in self.CORE_SCOPE_VERBS.get(scope, set()):
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' command '{scope} {verb}' "
                    "collides with a core command."
                )

            scope_commands = self.registry.commands.setdefault(scope, {})
            owner = scope_commands.get(verb)
            if owner is not None:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' command '{scope} {verb}' "
                    f"collides with plugin '{owner}'."
                )
            scope_commands[verb] = plugin_id

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
            seen_scopes.add(provider.scope)
            self.registry.completion_providers.setdefault(
                provider.scope, []
            ).append(provider)

    def _register_templates(
        self,
        plugin_id: str,
        templates: Sequence[PluginTemplateSpec],
        registry: dict[str, PluginTemplateSpec],
        kind: str,
    ) -> None:
        """Register namespaced templates in the selected runtime registry."""
        for template in templates:
            if "/" in template.id:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' {kind} id '{template.id}' must "
                    "not contain '/'."
                )
            canonical_id = f"{plugin_id}/{template.id}"
            if canonical_id in registry:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' declares duplicate {kind} "
                    f"'{canonical_id}'."
                )
            registry[canonical_id] = template

    def _register_factories(
        self,
        plugin_id: str,
        factories: Sequence[PluginFactorySpec],
        registry: dict[str, PluginFactorySpec],
        kind: str,
    ) -> None:
        """Register namespaced factories in the selected runtime registry."""
        for factory in factories:
            if "/" in factory.id:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' {kind} id '{factory.id}' must "
                    "not contain '/'."
                )
            canonical_id = f"{plugin_id}/{factory.id}"
            if canonical_id in registry:
                Util.print_error_and_die(
                    f"Plugin '{plugin_id}' declares duplicate {kind} "
                    f"'{canonical_id}'."
                )
            registry[canonical_id] = factory
