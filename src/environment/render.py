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

from typing import TYPE_CHECKING, Any, Optional, Protocol, Sequence, cast

import yaml
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree

from util import Util

# Import only for static analysis to avoid a runtime cycle with environment.py.
if TYPE_CHECKING:
    from .environment import Environment


def format_service_gate_glyphs(
    svc: Any,
    gate_status: Optional[dict[str, Optional[bool]]] = None,
) -> str:
    when_probes = (
        svc.svcCfg.start.when_probes
        if svc.svcCfg.start and svc.svcCfg.start.when_probes
        else None
    )
    if not when_probes:
        return "[dim]-[/dim]"
    if gate_status is None:
        return "".join("[dim]·[/dim]" for _ in when_probes)

    glyphs: list[str] = []
    for probe_tag in when_probes:
        probe_ok = gate_status.get(probe_tag)
        if probe_ok is True:
            glyphs.append("[bold green]✓[/bold green]")
        elif probe_ok is False:
            glyphs.append("[bold red]✗[/bold red]")
        else:
            glyphs.append("[dim]·[/dim]")
    return "".join(glyphs)


def format_service_gate_details(
    svc: Any,
    gate_status: Optional[dict[str, Optional[bool]]] = None,
) -> str:
    when_probes = (
        svc.svcCfg.start.when_probes
        if svc.svcCfg.start and svc.svcCfg.start.when_probes
        else None
    )
    if not when_probes:
        return "[dim]-[/dim]"

    probe_tags = sorted(when_probes)
    parts: list[str] = []
    for probe_tag in probe_tags:
        if gate_status is None:
            parts.append(f"[dim]{probe_tag}[/dim]")
            continue
        probe_ok = gate_status.get(probe_tag)
        if probe_ok is True:
            parts.append(f"[green]{probe_tag}[/green]")
        elif probe_ok is False:
            parts.append(f"[red]{probe_tag}[/red]")
        else:
            parts.append(f"[dim]{probe_tag}[/dim]")
    return ", ".join(parts)


def collect_env_status(
    env: Any,
    *,
    details_enabled: bool,
    gate_status: Optional[dict[str, Optional[bool]]] = None,
    include_gates: bool = True,
) -> tuple[dict[str, list[list[str]]], bool, bool, bool]:
    """
    Build grouped status rows used by table renderers and wait loops.

    Returns:
    - grouped rows keyed by service tag
    - all_running: every discovered container is running
    - any_running: at least one discovered container is running
    - has_containers: at least one container exists in config
    """
    env_status = env.status()
    services = env.get_services()
    status_by_service = {
        row.get("Service"): row for row in env_status if row.get("Service")
    }

    grouped: dict[str, list[list[str]]] = {}
    all_running = True
    any_running = False
    has_containers = False

    for svc in services:
        rows: list[list[str]] = []
        service_gates = ""
        service_gate_details = ""
        if include_gates:
            service_gates = format_service_gate_glyphs(
                svc,
                gate_status=gate_status,
            )
            service_gate_details = format_service_gate_details(
                svc,
                gate_status=gate_status,
            )
        for idx, container in enumerate(svc.svcCfg.containers or []):
            has_containers = True
            cnt_name = container.run_container_name or ""
            cnt_info = status_by_service.get(cnt_name)
            state = (
                cnt_info.get("State", "?").lower() if cnt_info else "stopped"
            )

            if state == "running":
                any_running = True
                state_colored = "[bold green]running[/bold green]"
            elif state == "stopped":
                state_colored = "[dim]stopped[/dim]"
            else:
                state_colored = f"[yellow]{state}[/yellow]"

            if state != "running":
                all_running = False

            gates_cell = service_gates if idx == 0 else ""
            row = [gates_cell, container.tag, state_colored]
            if details_enabled and include_gates:
                row.append(service_gate_details if idx == 0 else "")
            rows.append(row)

        if rows:
            grouped[svc.svcCfg.tag] = rows

    if not has_containers:
        all_running = False

    return grouped, all_running, any_running, has_containers


def render_env_summary(env: Environment) -> None:
    """Render the default single-row environment summary table."""
    env_cfg = env.envCfg
    services = env_cfg.services or []
    probes = env_cfg.probes or []
    Util.render_table(
        title=None,
        columns=[
            {"header": "NAME", "style": "cyan"},
            {"header": "TEMPLATE", "style": "magenta"},
            {"header": "ENGINE", "style": "yellow"},
            {"header": "ACTIVE", "style": "white"},
            {"header": "SERVICES", "style": "white", "justify": "right"},
            {"header": "PROBES", "style": "white", "justify": "right"},
        ],
        rows=[
            [
                env_cfg.tag,
                env_cfg.template,
                env_cfg.factory,
                "yes" if env_cfg.status.active else "no",
                str(len(services)),
                str(len(probes)),
            ]
        ],
    )


def build_env_details_tree(env: Environment) -> Tree:
    """Build the details tree shown below the environment summary."""
    tree = Tree(f"[bold]{env.envCfg.tag}[/bold]", guide_style="dim")
    for svc in env.get_services():
        svc_node = tree.add(f"[cyan]{svc.svcCfg.tag}[/cyan]")
        containers = svc.svcCfg.containers or []
        if not containers:
            svc_node.add("[dim]-[/dim]")
            continue
        for container in containers:
            svc_node.add(f"[white]{container.tag}[/white]")
    return tree


class _LiteralDumper(yaml.SafeDumper):
    pass


def _repr_str(dumper: _LiteralDumper, data: str) -> yaml.ScalarNode:
    style = "|" if "\n" in data else None
    data_str: str = str(data)
    return cast(
        yaml.ScalarNode,
        cast(Any, dumper).represent_scalar(
            "tag:yaml.org,2002:str", data_str, style=style
        ),
    )


_LiteralDumper.add_representer(str, _repr_str)


def dump_grouped_yaml(data: dict[str, str]) -> str:
    return yaml.dump(data, Dumper=_LiteralDumper, sort_keys=False)


def build_command_log_panel(
    command_log: list[str], command_log_limit: int
) -> Panel:
    limit = max(0, command_log_limit)
    lines = [f"{cmd}" for cmd in command_log[-limit:]]
    while len(lines) < limit:
        lines.append("[dim]•[/dim]")
    body = "\n".join(lines)
    return Panel(
        body,
        title="Recent Commands",
        border_style="blue",
        padding=(1, 2),
        box=box.ROUNDED,
        expand=True,
    )


def build_command_error_panel(
    command_error: dict[str, str],
    command_error_limit: Optional[int],
) -> Panel:
    title = command_error.get("title") or "Command Error"
    body = command_error.get("body") or ""
    lines = body.splitlines()
    limit = command_error_limit or 0
    if limit > 0:
        lines = lines[-limit:]
        while len(lines) < limit:
            lines.append("[dim][/dim]")
    body = "\n".join(lines)
    return Panel(
        body,
        title=title,
        border_style="red",
        padding=(1, 2),
        box=box.ROUNDED,
        expand=True,
    )


def build_summary_renderable(items: list[tuple[str, str]]) -> Text:
    """Build a compact summary line renderable."""
    return build_summary_renderable_with_flash(items, flashing_keys=None)


def build_summary_renderable_with_flash(
    items: list[tuple[str, str]],
    *,
    flashing_keys: Optional[set[str]],
) -> Text:
    """Build a compact summary line renderable with optional flashes."""
    summary = Text("Summary:", style="bold")
    flashing = flashing_keys or set()
    for key, value in items:
        summary.append("  ")
        summary.append(f"{key}: ", style="dim")
        if key in flashing:
            summary.append(value, style=_summary_flash_style(key))
        else:
            summary.append(value)
    return summary


def build_tree_summary_group(
    tree: Tree,
    summary_items: list[tuple[str, str]],
    *,
    extras: Optional[list[Any]] = None,
    flashing_summary_keys: Optional[set[str]] = None,
) -> Any:
    """Combine a tree, summary, and optional extra panels."""
    renderables: list[Any] = [tree]
    if summary_items:
        renderables.append(
            build_summary_renderable_with_flash(
                summary_items,
                flashing_keys=flashing_summary_keys,
            )
        )
    renderables.extend(extras or [])
    if len(renderables) == 1:
        return tree
    return Group(*renderables)


def build_env_status_summary(
    grouped: dict[str, list[list[str]]],
) -> list[tuple[str, str]]:
    """Build a compact env status summary from grouped rows."""
    services = len(grouped)
    containers = running = stopped = other = 0
    gates_ok = gates_failed = gates_pending = 0

    for items in grouped.values():
        containers += len(items)
        for idx, item in enumerate(items):
            state = item[2]
            if "running" in state:
                running += 1
            elif "stopped" in state:
                stopped += 1
            else:
                other += 1

            if idx != 0 or len(item) <= 3:
                continue
            probe_details = item[3]
            if probe_details == "[dim]-[/dim]":
                continue
            for probe_detail in probe_details.split(", "):
                if "[green]" in probe_detail or "[bold green]" in probe_detail:
                    gates_ok += 1
                elif "[red]" in probe_detail or "[bold red]" in probe_detail:
                    gates_failed += 1
                else:
                    gates_pending += 1

    summary = [
        ("SERVICES", str(services)),
        ("CONTAINERS", str(containers)),
        ("RUNNING", str(running)),
    ]
    if stopped:
        summary.append(("STOPPED", str(stopped)))
    if other:
        summary.append(("OTHER", str(other)))
    if gates_ok or gates_failed or gates_pending:
        summary.extend(
            [
                ("GATES OK", str(gates_ok)),
                ("GATES FAILED", str(gates_failed)),
                ("GATES PENDING", str(gates_pending)),
            ]
        )
    return summary


def build_env_status_tree(
    env_tag: str,
    grouped: dict[str, list[list[str]]],
    *,
    details_enabled: bool,
    status_suffix: Optional[str] = None,
    command_log: Optional[list[str]] = None,
    command_log_limit: Optional[int] = None,
    command_error: Optional[dict[str, str]] = None,
    command_error_limit: Optional[int] = None,
    hidden_columns: Optional[set[str]] = None,
    flashing_containers: Optional[set[str]] = None,
    flashing_probes: Optional[set[tuple[str, str]]] = None,
    flashing_summary_keys: Optional[set[str]] = None,
) -> Any:
    """Render the environment status as a tree with optional side panels."""
    title = f"[bold white]{env_tag}[/bold white]"
    if status_suffix:
        title = f"{title} {status_suffix}"

    hidden = hidden_columns or set()
    flashing_container_keys = flashing_containers or set()
    flashing_probe_keys = flashing_probes or set()
    tree = Tree(title, guide_style="dim")

    for service, items in grouped.items():
        service_node = tree.add(f"[bold cyan]{service}[/bold cyan]")
        if not items:
            continue

        first_row = items[0]
        probe_details = first_row[3] if len(first_row) > 3 else None
        has_probe_details = bool(
            probe_details and probe_details != "[dim]-[/dim]"
        )

        if "Gates" not in hidden and has_probe_details:
            probe_details_text = cast(str, probe_details)
            gates_node = service_node.add("[bold magenta]gates[/bold magenta]")
            for probe_detail in probe_details_text.split(", "):
                probe_tag = Text.from_markup(probe_detail).plain
                probe_key = (service, probe_tag)
                if probe_key in flashing_probe_keys:
                    gates_node.add(_flash_markup(probe_detail))
                else:
                    gates_node.add(probe_detail)
        elif details_enabled and has_probe_details:
            service_node.add(f"[white]probes[/white]: {probe_details}")

        for item in items:
            container = item[1]
            state = item[2]
            container_key = f"{service}/{container}"
            rendered_state = (
                _flash_markup(state)
                if container_key in flashing_container_keys
                else state
            )
            service_node.add(f"[white]{container}[/white]: {rendered_state}")

    panels: list[Any] = []
    if command_log is not None and command_log_limit is not None:
        panels.append(build_command_log_panel(command_log, command_log_limit))
    if command_error:
        panels.append(
            build_command_error_panel(command_error, command_error_limit)
        )
    return build_tree_summary_group(
        tree,
        build_env_status_summary(grouped),
        extras=panels,
        flashing_summary_keys=flashing_summary_keys,
    )


class ProbeRunResultLike(Protocol):
    """Minimal probe result contract needed for probe report rendering."""

    tag: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: Optional[int]
    timed_out: bool


def probe_status_key(r: ProbeRunResultLike) -> str:
    if r.timed_out:
        return "timeout"
    if r.exit_code == 0:
        return "ok"
    return "failed"


def probe_status_color_tag(key: str) -> str:
    if key == "ok":
        return "green"
    if key == "timeout":
        return "yellow"
    return "red"


def _flash_markup(markup: str) -> str:
    plain = Text.from_markup(markup).plain
    if "[green]" in markup or "[bold green]" in markup:
        return f"[bold black on green]{plain}[/bold black on green]"
    if "[red]" in markup or "[bold red]" in markup:
        return f"[bold white on red]{plain}[/bold white on red]"
    if "[yellow]" in markup or "[bold yellow]" in markup:
        return f"[bold black on yellow]{plain}[/bold black on yellow]"
    return f"[bold black on white]{plain}[/bold black on white]"


def build_probe_error_from_results(
    results: Sequence[ProbeRunResultLike],
) -> Optional[dict[str, str]]:
    """Build an error panel dict from the first failed or timed-out probe."""
    for r in results:
        if r.exit_code == 0 and not r.timed_out:
            continue
        parts: list[str] = []
        if r.timed_out:
            parts.append("[yellow]Probe timed out.[/yellow]")
        if r.stdout and r.stdout.strip():
            parts.append(f"--- stdout ---\n{r.stdout.strip()}")
        if r.stderr and r.stderr.strip():
            parts.append(f"--- stderr ---\n{r.stderr.strip()}")
        if not parts:
            return None
        label = "timed out" if r.timed_out else "failed"
        return {
            "title": f"Probe '{r.tag}' {label}",
            "body": "\n".join(parts),
        }
    return None


def build_probe_status_tree(
    results: Sequence[ProbeRunResultLike],
    *,
    title: str,
    flashing_summary_keys: Optional[set[str]] = None,
    probe_error: Optional[dict[str, str]] = None,
    command_log: Optional[list[str]] = None,
    command_log_limit: Optional[int] = None,
) -> Any:
    """Render probe check results as a tree of color-coded probe tags."""
    tree = Tree(title, guide_style="dim")
    for r in results:
        key = probe_status_key(r)
        color = probe_status_color_tag(key)
        tree.add(f"[{color}]{r.tag}[/{color}]")
    extras: list[Any] = []
    if command_log is not None and command_log_limit is not None:
        extras.append(build_command_log_panel(command_log, command_log_limit))
    if probe_error:
        extras.append(build_command_error_panel(probe_error, None))
    return build_tree_summary_group(
        tree,
        build_probe_status_summary(results),
        extras=extras,
        flashing_summary_keys=flashing_summary_keys,
    )


def _summary_flash_style(key: str) -> str:
    if key in {"RUNNING", "GATES OK", "OK"}:
        return "bold black on green"
    if key in {"STOPPED", "GATES FAILED", "FAILED"}:
        return "bold white on red"
    if key in {"OTHER", "GATES PENDING", "TIMEOUT"}:
        return "bold black on yellow"
    return "bold black on white"


def build_probe_status_summary(
    results: Sequence[ProbeRunResultLike],
) -> list[tuple[str, str]]:
    """Build the OK/FAILED/TIMEOUT summary shown below probe trees."""
    ok = failed = timeout = 0
    for r in results:
        key = probe_status_key(r)
        if key == "ok":
            ok += 1
        elif key == "timeout":
            timeout += 1
        else:
            failed += 1
    return [
        ("OK", str(ok)),
        ("FAILED", str(failed)),
        ("TIMEOUT", str(timeout)),
    ]
