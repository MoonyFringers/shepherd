# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.


import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Optional, Union

import yaml
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .constants import Constants

JustifyMethod = Literal["default", "left", "center", "right", "full"]
ColumnJustify = Literal["left", "center", "right"]
DEFAULT_SHPD_VALUES_TEMPLATE = """# Shepherd workspace directory
shpd_path=~/shpd
templates_path=${shpd_path}/templates
envs_path=${shpd_path}/envs
volumes_path=${shpd_path}/volumes
staging_area_volumes_path=${shpd_path}/sa_volumes
staging_area_images_path=${shpd_path}/sa_images

# Shepherd default environment type
default_env_type=docker-compose

# Logging Configuration
log_file=${shpd_path}/logs/shepctl.log
log_level=WARNING
log_stdout=false
log_format=%(asctime)s - %(levelname)s - %(message)s
"""


class Util:
    console = Console()

    @dataclass
    class OsInfo:
        """Structured information about the operating system."""

        system: str
        distro: str | None = None
        codename: str | None = None

    @dataclass(frozen=True)
    class InstallPaths:
        """Default install locations for the current platform."""

        install_dir: Path
        symlink_dir: Path

    @staticmethod
    def confirm(prompt: str) -> bool:
        while True:
            response = input(f"{prompt} [y/n]: ").strip().lower()
            if response in {"y", "yes"}:
                return True
            elif response in {"n", "no"}:
                return False
            else:
                Util.console.print(
                    "Please answer yes or no. [y/n]", style="yellow"
                )

    @staticmethod
    def create_dir(dir_path: str, desc: str, mode: int = 0o755):
        try:
            os.makedirs(dir_path, exist_ok=True)
            os.chmod(dir_path, mode)
        except OSError as e:
            Util.print_error_and_die(
                f"[{desc}] Failed to create directory: {dir_path}\nError: {e}"
            )

    @staticmethod
    def copy_dir(src_path: str, dest_path: str):
        """
        Copy directory contents recursively using hard links for files.

        This is intentionally link-based (`os.link`) rather than byte-copy to
        keep clone-like operations fast and space-efficient.
        """
        try:
            os.makedirs(dest_path, exist_ok=True)
            for item in os.listdir(src_path):
                src_item = os.path.join(src_path, item)
                dest_item = os.path.join(dest_path, item)
                if os.path.isdir(src_item):
                    Util.copy_dir(src_item, dest_item)
                else:
                    os.link(src_item, dest_item)
        except OSError as e:
            Util.print_error_and_die(f"""Failed to copy directory:
                {src_path} to {dest_path}\nError: {e}""")

    @staticmethod
    def move_dir(src_path: str, dest_path: str):
        try:
            os.rename(src_path, dest_path)
        except OSError as e:
            Util.print_error_and_die(f"""Failed to move directory:
                {src_path} to {dest_path}\nError: {e}""")

    @staticmethod
    def remove_dir(dir_path: str):
        try:
            shutil.rmtree(dir_path)
        except OSError as e:
            Util.print_error_and_die(
                f"Failed to remove directory: {dir_path}\nError: {e}"
            )

    @staticmethod
    def print_error_and_die(message: str):
        Util.console.print(f"[red]Error:[/red] {message}", highlight=False)
        sys.exit(1)

    @staticmethod
    def print(message: str):
        Util.console.print(f"{message}", highlight=False)

    @staticmethod
    def render_table(
        title: Optional[str],
        columns: list[dict[str, Any]],
        rows: list[list[Any]],
        *,
        box_style: Any = box.SIMPLE,
        title_justify: JustifyMethod = "left",
        title_style: str = "bold",
        show_lines: bool = False,
        expand: bool = False,
    ) -> None:
        """
        Render a table using rich.

        Args:
            title: Table title (None for no title).
            columns: list of dicts with keys:
                     - "header" (required): column name
                     - "style" (optional): rich style string
                     - "justify" (optional): "left" | "right" | "center"
                     - "no_wrap" (optional): bool (default True)
                     - "ratio" (optional): int
                     - "min_width" (optional): int
                     - "max_width" (optional): int
            rows: list of row values (must match number of columns).
                  Cells may be strings OR any Rich renderable (e.g., Text).
        """
        table = Table(
            title=title or "",
            box=box_style,
            title_justify=title_justify,
            title_style=title_style,
            show_lines=show_lines,
            expand=expand,
        )

        for col in columns:
            justify: ColumnJustify = col.get("justify", "left")
            table.add_column(
                col["header"],
                style=col.get("style", ""),
                justify=justify,
                no_wrap=col.get("no_wrap", True),
                ratio=col.get("ratio", None),
                min_width=col.get("min_width", None),
                max_width=col.get("max_width", None),
            )

        for row in rows:
            table.add_row(*row)

        Util.console.print(table)

    @staticmethod
    def build_grouped_table(
        title: Optional[str],
        group_column_header: str,
        item_columns: list[dict[str, str]],
        groups: dict[str, list[list[str]]],
        *,
        branch_glyph_mid: str = "├─",
        branch_glyph_last: str = "└─",
        group_style: str = "bold",
        group_col_style: str = "cyan",
        box_style: box.Box = box.SIMPLE,
    ) -> Table:
        """
        Build a grouped table using rich.

        Args:
            title: Table title (None for no title).
            group_column_header: header for the left-most "group"
            column (e.g., "Service").

            item_columns: like in render_table, list of dicts with keys:
                         - "header" (required)
                         - "style" (optional)

            groups: mapping from group label -> list of item rows
            (each list[str] must match item_columns length)

            branch_glyph_mid: glyph used before non-last items
            (visual nesting).

            branch_glyph_last: glyph used before the last item in a group.
            group_style: style applied to the group label row.
            group_col_style: style for the group column.
            box_style: rich box style.
        """
        table = Table(
            title=title or "",
            box=box_style,
            title_justify="left",
            title_style="bold",
        )

        # Add columns: group column + item columns
        table.add_column(
            group_column_header, style=group_col_style, no_wrap=True
        )
        for col in item_columns:
            table.add_column(
                col["header"], style=col.get("style", ""), no_wrap=False
            )

        if not groups:
            return table

        for group_label in sorted(groups.keys()):
            items = groups[group_label] or []

            # Group header row
            table.add_row(
                f"[{group_style}]{group_label}[/{group_style}]",
                *[""] * len(item_columns),
            )

            # Nested items
            for idx, row in enumerate(items):
                is_last = idx == len(items) - 1
                branch = branch_glyph_last if is_last else branch_glyph_mid

                # Prepend branch glyph to the first item column
                # (if there is at least one)
                if row:
                    first_cell = f"{branch} {row[0]}"
                    rest = row[1:]
                    table.add_row("", first_cell, *rest, end_section=is_last)
                else:
                    table.add_row(
                        "",
                        "",
                        *[""] * (len(item_columns) - 1),
                        end_section=is_last,
                    )

        return table

    @staticmethod
    def render_grouped_table(
        title: Optional[str],
        group_column_header: str,
        item_columns: list[dict[str, str]],
        groups: dict[str, list[list[str]]],
        *,
        branch_glyph_mid: str = "├─",
        branch_glyph_last: str = "└─",
        group_style: str = "bold",
        group_col_style: str = "cyan",
        box_style: box.Box = box.SIMPLE,
    ) -> None:
        """
        Render a grouped table using rich.

        Args:
            title: Table title (None for no title).
            group_column_header: header for the left-most "group"
            column (e.g., "Service").

            item_columns: like in render_table, list of dicts with keys:
                         - "header" (required)
                         - "style" (optional)

            groups: mapping from group label -> list of item rows
            (each list[str] must match item_columns length)

            branch_glyph_mid: glyph used before non-last items
            (visual nesting).

            branch_glyph_last: glyph used before the last item in a group.
            group_style: style applied to the group label row.
            group_col_style: style for the group column.
            box_style: rich box style.
        """
        table = Util.build_grouped_table(
            title,
            group_column_header,
            item_columns,
            groups,
            branch_glyph_mid=branch_glyph_mid,
            branch_glyph_last=branch_glyph_last,
            group_style=group_style,
            group_col_style=group_col_style,
            box_style=box_style,
        )

        if not groups:
            Util.console.print("[yellow]No data.[/yellow]")
            return

        Util.console.print(table)

    @staticmethod
    def render_panels(
        *,
        panels: list[dict[str, Any]],
        padding: tuple[int, int] = (1, 2),
    ) -> None:
        """
        panels: [{ "title": str, "body": str, "border_style": str }]
        """
        for p in panels:
            body = (p.get("body") or "").rstrip()
            if not body:
                continue
            Util.console.print(
                Panel(
                    body,
                    title=p.get("title") or "",
                    border_style=p.get("border_style") or "white",
                    padding=padding,
                )
            )

    @staticmethod
    def render_kv_summary(items: list[tuple[str, str]]) -> None:
        # generic compact line: "Summary: OK: 1  FAILED: 0  TIMEOUT: 0"
        parts = ["Summary:"]
        for k, v in items:
            parts.append(f"{k}: {v}")
        Util.console.print("  ".join(parts))

    # Directory management and other utilities

    @staticmethod
    def ensure_dir(dir_path: str, desc: str, mode: int = 0o755):
        if os.path.exists(dir_path):
            if not os.path.isdir(dir_path):
                Util.print_error_and_die(
                    f"[{desc}] Path exists and is not a directory: {dir_path}"
                )
        else:
            Util.create_dir(dir_path, desc, mode)

    @staticmethod
    def ensure_shpd_dirs(constants: Constants):
        dirs = {
            "SHPD_CERTS_DIR": constants.SHPD_CERTS_DIR,
            "SHPD_SSH_DIR": constants.SHPD_SSH_DIR,
            "SHPD_SSHD_DIR": constants.SHPD_SSHD_DIR,
            "SHPD_PLUGINS_DIR": constants.SHPD_PLUGINS_DIR,
        }

        for desc, dir_path in dirs.items():
            resolved_path = os.path.realpath(dir_path)
            Util.ensure_dir(resolved_path, desc)

    @staticmethod
    def ensure_config_values_file(file_values_path: str) -> None:
        config_values_path = os.path.expanduser(
            file_values_path or "~/.shpd.conf"
        )
        if os.path.exists(config_values_path):
            return

        parent_dir = os.path.dirname(config_values_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        try:
            with open(config_values_path, "w", encoding="utf-8") as f:
                f.write(DEFAULT_SHPD_VALUES_TEMPLATE)
        except OSError as e:
            Util.print_error_and_die(
                f"Failed to create config values file: "
                f"{config_values_path}\nError: {e}"
            )

    @staticmethod
    def ensure_config_file(constants: Constants):
        config_file_path = constants.SHPD_CONFIG_FILE
        if os.path.exists(config_file_path):
            try:
                with open(config_file_path, "r", encoding="utf-8") as f:
                    yaml.safe_load(f)
            except (yaml.YAMLError, OSError) as e:
                Util.print_error_and_die(
                    f"Invalid config file: {config_file_path}\nError: {e}"
                )
            return

        default_config = constants.DEFAULT_CONFIG
        try:
            with open(config_file_path, "w", encoding="utf-8") as f:
                yaml.dump(default_config, f, indent=2, sort_keys=False)
        except OSError as e:
            Util.print_error_and_die(
                f"Failed to create config file: {config_file_path}\nError: {e}"
            )

    @staticmethod
    def is_root() -> bool:
        return os.geteuid() == 0

    @staticmethod
    def run_command(
        cmd: Union[list[str], str],
        check: bool = True,
        shell: bool = False,
        capture_output: bool = False,
    ) -> Union[subprocess.CompletedProcess[Any], subprocess.CalledProcessError]:
        """
        Run a shell command and return the result.

        Args:
            cmd: Command to run (list or string)
            check: Whether to raise an exception on failure
            shell: Whether to run through shell
            capture_output: Whether to capture stdout/stderr

        Returns:
            CompletedProcess instance or CalledProcessError

        Notes:
            - When `cmd` is a string and `shell=False`, it is split on spaces.
            - When `check=True`, failures terminate the process via
              `print_error_and_die` style behavior (`sys.exit(1)`).
        """
        if isinstance(cmd, str) and not shell:
            cmd = cmd.split()

        try:
            result = subprocess.run(
                cmd,
                check=check,
                shell=shell,
                text=True,
                capture_output=capture_output,
            )
            return result
        except subprocess.CalledProcessError as e:
            Util.console.print(f"Command failed: {e}", style="red")
            if check:
                sys.exit(1)
            return e

    @staticmethod
    def get_current_user() -> str:
        """Get the actual user, even when running with sudo."""
        return os.environ.get("SUDO_USER") or Util._get_user_fallback()

    @staticmethod
    def _get_user_fallback() -> str:
        try:
            return os.getlogin()
        except OSError:
            import getpass

            return getpass.getuser()

    @staticmethod
    def check_file_exists(path: str) -> bool:
        """Check if a file exists and is readable at the given path."""
        return os.path.isfile(path) and os.access(path, os.R_OK)

    @staticmethod
    def get_architecture() -> str:
        bits, linkage = platform.architecture()
        machine = platform.machine().lower()
        arch_mapping = getattr(Constants, "ARCH_MAPPING", {})
        if (bits, linkage) in arch_mapping:
            return arch_mapping[(bits, linkage)]
        if "arm" in machine or "aarch" in machine:
            return "arm64"
        return "amd64" if "64" in bits else "i386"

    @staticmethod
    def get_os_info() -> "Util.OsInfo":
        """
        Return normalized OS metadata for installer/repository selection.
        """
        system = platform.system().lower()
        if system in ("windows", "win32"):
            raise ValueError(f"Unsupported operating system: {system}")
        if system == "linux":
            import distro

            dist_id = distro.id().lower()
            code_name = distro.codename().lower()
            return Util.OsInfo(
                system=system, distro=dist_id, codename=code_name
            )
        if system == "darwin":
            return Util.OsInfo(system=system)
        raise ValueError(f"Unsupported operating system: {system}")

    @staticmethod
    def get_default_install_paths(
        system: Optional[str] = None,
    ) -> "Util.InstallPaths":
        current_system = system or platform.system().lower()
        if current_system == "darwin":
            brew_prefix = (
                Path("/opt/homebrew")
                if platform.machine().lower() in ("arm64", "aarch64")
                else Path("/usr/local")
            )
            return Util.InstallPaths(
                install_dir=brew_prefix / "opt" / "shepctl",
                symlink_dir=brew_prefix / "bin",
            )
        return Util.InstallPaths(
            install_dir=Path("/opt/shepctl"),
            symlink_dir=Path("/usr/local/bin"),
        )

    @staticmethod
    def get_home_directory() -> str:
        return str(Path.home())

    @staticmethod
    def is_macos() -> bool:
        return platform.system().lower() == "darwin"

    @staticmethod
    def translate_host_path(path: str) -> str:
        """
        Translate common Linux host-home paths to the active platform.

        Container-internal paths are intentionally left to callers to preserve
        Linux paths inside images and compose specs.
        """
        if not Util.is_macos():
            return path

        home_dir = Util.get_home_directory()
        expanded = path

        if path == "~":
            expanded = home_dir
        elif path.startswith("~/"):
            expanded = str(Path(home_dir) / path[2:])

        if expanded.startswith("/home/"):
            parts = Path(expanded).parts
            translated = Path(home_dir)
            if len(parts) > 3:
                translated = translated.joinpath(*parts[3:])
            return str(translated)

        return expanded

    @staticmethod
    def translate_volume_binding(volume: str) -> str:
        """
        Translate only the host-side portion of a bind-mount definition.
        """
        if not volume:
            return volume

        if not Util.is_macos():
            return volume

        parts = volume.split(":")
        if len(parts) < 2:
            return Util.translate_host_path(volume)

        parts[0] = Util.translate_host_path(parts[0])
        return ":".join(parts)

    @staticmethod
    def download_package(url: str, dest: str) -> None:
        Util.run_command(["curl", "-fsSL", url, "-o", dest], check=True)
        Util.console.print(
            f"Package downloaded to {dest}",
            style="green",
        )

    @staticmethod
    def extract_package(package_path: str, extract_to: str) -> None:
        Util.run_command(
            [
                "tar",
                "-xzf",
                package_path,
                "-C",
                extract_to,
            ],
            check=True,
        )
        Util.console.print(
            f"Package extracted to {extract_to}",
            style="green",
        )

    @staticmethod
    def fmt_bytes(n: int) -> str:
        """Return a human-readable byte count (e.g. ``1.2 MiB``)."""
        for unit, threshold in (
            ("GiB", 1 << 30),
            ("MiB", 1 << 20),
            ("KiB", 1 << 10),
        ):
            if n >= threshold:
                return f"{n / threshold:.1f} {unit}"
        return f"{n} B"
