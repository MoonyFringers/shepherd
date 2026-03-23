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

import json
import os
import shutil
import tarfile
import tempfile
from typing import Any

import yaml

from config import ConfigMng, parse_plugin_descriptor
from config.config import PluginCfg, PluginDescriptorCfg, cfg_asdict
from util import Util


class PluginMng:
    """Manage the persisted plugin inventory and managed plugin files."""

    def __init__(
        self,
        cli_flags: dict[str, Any],
        configMng: ConfigMng,
    ):
        self.cli_flags = cli_flags
        self.configMng = configMng

    def list_plugins(self) -> None:
        plugins = self.configMng.get_plugins()
        if not plugins:
            Util.print("No plugins installed.")
            return

        rows = [
            [
                plugin.id,
                "true" if plugin.is_enabled() else "false",
                plugin.version or "",
            ]
            for plugin in plugins
        ]
        Util.render_table(
            "Plugins",
            [
                {"header": "Id", "style": "cyan"},
                {"header": "Enabled"},
                {"header": "Version"},
            ],
            rows,
        )

    def render_plugin(self, plugin_id: str, output: str = "yaml") -> str:
        plugin = self._require_plugin(plugin_id)
        rendered = cfg_asdict(plugin)
        if output == "json":
            return json.dumps(rendered, indent=2)
        return yaml.dump(rendered, sort_keys=False)

    def enable_plugin(self, plugin_id: str) -> None:
        self._require_plugin(plugin_id)
        plugin = self.configMng.set_plugin_enabled(plugin_id, True)
        Util.print(f"Plugin '{plugin.id}' enabled.")

    def disable_plugin(self, plugin_id: str) -> None:
        self._require_plugin(plugin_id)
        plugin = self.configMng.set_plugin_enabled(plugin_id, False)
        Util.print(f"Plugin '{plugin.id}' disabled.")

    def remove_plugin(self, plugin_id: str) -> None:
        plugin = self._require_plugin(plugin_id)
        plugin_dir = self.configMng.get_plugin_dir(plugin.id)
        if os.path.isdir(plugin_dir):
            shutil.rmtree(plugin_dir)
        self.configMng.remove_plugin(plugin.id)
        Util.print(f"Plugin '{plugin.id}' removed.")

    def install_plugin(self, archive_path: str) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            extracted_dir = os.path.join(tmp_dir, "plugin")
            os.makedirs(extracted_dir, exist_ok=True)
            self._extract_plugin_archive(archive_path, extracted_dir)
            descriptor_path = self._find_descriptor_path(extracted_dir)
            descriptor = self._load_descriptor(descriptor_path)
            self._validate_reserved_plugin_id(descriptor.id)

            if self.configMng.get_plugin(descriptor.id) is not None:
                Util.print_error_and_die(
                    f"Plugin '{descriptor.id}' is already installed."
                )

            descriptor_dir = os.path.dirname(descriptor_path)
            target_dir = self.configMng.get_plugin_dir(descriptor.id)
            if os.path.exists(target_dir):
                Util.print_error_and_die(
                    f"Managed plugin directory already exists: {target_dir}"
                )

            shutil.move(descriptor_dir, target_dir)
            self.configMng.set_plugin(
                PluginCfg(
                    id=descriptor.id,
                    enabled="true",
                    version=descriptor.version,
                    config=descriptor.default_config,
                )
            )
        Util.print(f"Plugin '{descriptor.id}' installed.")

    def _require_plugin(self, plugin_id: str) -> PluginCfg:
        plugin = self.configMng.get_plugin(plugin_id)
        if plugin is None:
            Util.print_error_and_die(f"Plugin '{plugin_id}' not found.")
            raise AssertionError("unreachable")
        return plugin

    def _load_descriptor(self, descriptor_path: str) -> PluginDescriptorCfg:
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
                f"Invalid plugin descriptor '{descriptor_path}': {exc}"
            )
            raise AssertionError("unreachable")

    def _validate_reserved_plugin_id(self, plugin_id: str) -> None:
        """Reject plugin ids reserved for internal canonical namespaces."""
        if plugin_id == self.configMng.constants.CORE_PLUGIN_ID:
            Util.print_error_and_die(
                f"Plugin id '{plugin_id}' is reserved for core resources."
            )

    def _find_descriptor_path(self, extracted_dir: str) -> str:
        descriptor_name = self.configMng.constants.PLUGIN_DESCRIPTOR_FILE
        matches: list[str] = []
        for root, _, files in os.walk(extracted_dir):
            if descriptor_name in files:
                matches.append(os.path.join(root, descriptor_name))

        if not matches:
            Util.print_error_and_die(
                f"Plugin archive does not contain '{descriptor_name}'."
            )
        if len(matches) > 1:
            Util.print_error_and_die(
                f"Plugin archive contains multiple '{descriptor_name}' files."
            )
        return matches[0]

    def _extract_plugin_archive(
        self, archive_path: str, extracted_dir: str
    ) -> None:
        try:
            with tarfile.open(archive_path, "r:*") as archive:
                self._safe_extract_tar(archive, extracted_dir)
        except (tarfile.TarError, OSError) as exc:
            Util.print_error_and_die(
                f"Failed to extract plugin archive '{archive_path}': {exc}"
            )

    def _safe_extract_tar(
        self, archive: tarfile.TarFile, destination: str
    ) -> None:
        for member in archive.getmembers():
            member_path = os.path.join(destination, member.name)
            resolved_path = os.path.realpath(member_path)
            resolved_destination = os.path.realpath(destination)
            if not resolved_path.startswith(resolved_destination + os.sep):
                Util.print_error_and_die(
                    "Plugin archive contains an invalid path."
                )
        try:
            archive.extractall(destination, filter="data")
        except TypeError:
            archive.extractall(destination)
