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


import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Literal, Optional, Union

import yaml
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .constants import Constants

JustifyMethod = Literal["default", "left", "center", "right", "full"]
ColumnJustify = Literal["left", "center", "right"]


class Util:
    console = Console()

    @dataclass
    class OsInfo:
        """Structured information about the operating system."""

        system: str
        distro: str | None = None
        codename: str | None = None

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
            Util.print_error_and_die(
                f"""Failed to copy directory:
                {src_path} to {dest_path}\nError: {e}"""
            )

    @staticmethod
    def move_dir(src_path: str, dest_path: str):
        try:
            os.rename(src_path, dest_path)
        except OSError as e:
            Util.print_error_and_die(
                f"""Failed to move directory:
                {src_path} to {dest_path}\nError: {e}"""
            )

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
        Util.console.print(f"[bold red]ERROR[/bold red]: {message}")
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
            Util.console.print("[yellow]No data.[/yellow]")
            return

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
        }

        for desc, dir_path in dirs.items():
            resolved_path = os.path.realpath(dir_path)
            Util.ensure_dir(resolved_path, desc)

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
        """Run a shell command and return the result.

        Args:
            cmd: Command to run (list or string)
            check: Whether to raise an exception on failure
            shell: Whether to run through shell
            capture_output: Whether to capture stdout/stderr

        Returns:
            CompletedProcess instance or CalledProcessError
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
        system = platform.system().lower()
        if system in ("windows", "win32", "darwin"):
            raise ValueError(f"Unsupported operating system: {system}")
        elif system == "linux":
            import distro

            dist_id = distro.id().lower()
            code_name = distro.codename().lower()
            return Util.OsInfo(
                system=system, distro=dist_id, codename=code_name
            )
        return Util.OsInfo(system=system)

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
