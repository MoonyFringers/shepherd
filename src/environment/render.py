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
            if details_enabled:
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
            name = container.run_container_name or container.tag
            svc_node.add(f"[white]{name}[/white]")
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
) -> Any:
    """Render the environment status as a tree with optional side panels."""
    title = f"[bold white]{env_tag}[/bold white]"
    if status_suffix:
        title = f"{title} {status_suffix}"

    hidden = hidden_columns or set()
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
                gates_node.add(probe_detail)
        elif details_enabled and has_probe_details:
            service_node.add(f"[white]probes[/white]: {probe_details}")

        for item in items:
            container = item[1]
            state = item[2]
            service_node.add(f"[white]{container}[/white]: {state}")

    panels: list[Any] = [tree]
    if command_log is not None and command_log_limit is not None:
        panels.append(build_command_log_panel(command_log, command_log_limit))
    if command_error:
        panels.append(
            build_command_error_panel(command_error, command_error_limit)
        )
    if len(panels) == 1:
        return tree
    return Group(*panels)


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


def probe_status_glyph(key: str) -> str:
    return "✔" if key == "ok" else "✖"


def probe_status_color_tag(key: str) -> str:
    if key == "ok":
        return "bold green"
    if key == "timeout":
        return "bold yellow"
    return "bold red"


def fmt_duration_ms(ms: Optional[int]) -> str:
    return "?" if ms is None else f"{ms} ms"


def build_probe_report(
    results: Sequence[ProbeRunResultLike],
    *,
    verbose: bool,
    title: str,
) -> dict[str, Any]:
    """
    Convert probe execution results into a presentation-ready view model.

    Policy:
    - Always include one summary row per probe.
    - Include detail panels for failures/timeouts.
    - Include OK detail panels only in verbose mode.
    """
    rows: list[list[str]] = []
    panels: list[dict[str, Any]] = []

    ok = failed = timeout = 0

    for r in results:
        key = probe_status_key(r)
        if key == "ok":
            ok += 1
        elif key == "timeout":
            timeout += 1
        else:
            failed += 1

        glyph = probe_status_glyph(key)
        label = key.upper()
        color = probe_status_color_tag(key)
        status_markup = f"[{color}]{glyph} {label}[/{color}]"

        rows.append([r.tag, status_markup, fmt_duration_ms(r.duration_ms)])

        want_details = verbose or key in ("failed", "timeout")
        if want_details:
            out = (r.stdout or "").strip("\n")
            err = (r.stderr or "").strip("\n")

            body_parts: list[str] = []
            if out.strip():
                body_parts.append("--- stdout ---")
                body_parts.append(out)

            if err.strip() and (verbose or key in ("failed", "timeout")):
                body_parts.append("--- stderr ---")
                body_parts.append(err)

            if key != "ok":
                body_parts.append("--- meta ---")
                body_parts.append(f"exit_code: {r.exit_code}")
                body_parts.append(f"timed_out: {r.timed_out}")

            body = "\n".join(body_parts).strip()
            if body:
                border = (
                    "green"
                    if key == "ok"
                    else ("yellow" if key == "timeout" else "red")
                )
                panels.append(
                    {
                        "title": f"{r.tag} ({label})",
                        "body": body,
                        "border_style": border,
                    }
                )
    return {
        "title": title,
        "rows": rows,
        "summary": [
            ("OK", str(ok)),
            ("FAILED", str(failed)),
            ("TIMEOUT", str(timeout)),
        ],
        "panels": panels,
    }


def render_probe_report(report: dict[str, Any]) -> None:
    Util.render_table(
        title=report["title"],
        columns=[
            {"header": "Probe", "style": "white", "no_wrap": True},
            {"header": "Status", "no_wrap": True},
            {
                "header": "Duration",
                "justify": "right",
                "style": "white",
                "no_wrap": True,
            },
        ],
        rows=report["rows"],
    )
    Util.render_kv_summary(report["summary"])
    Util.render_panels(panels=report.get("panels") or [])
