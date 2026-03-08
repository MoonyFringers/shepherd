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

from typing import Any, Optional, Protocol, Sequence, cast

import yaml
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table

from util import Util


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
        return "".join("[dim]○[/dim]" for _ in when_probes)

    glyphs: list[str] = []
    for probe_tag in when_probes:
        probe_ok = gate_status.get(probe_tag)
        if probe_ok is True:
            glyphs.append("[bold green]●[/bold green]")
        elif probe_ok is False:
            glyphs.append("[bold red]●[/bold red]")
        else:
            glyphs.append("[dim]○[/dim]")
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
            parts.append(f"[bold green]{probe_tag}[/bold green]")
        elif probe_ok is False:
            parts.append(f"[bold red]{probe_tag}[/bold red]")
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
                state_colored = "[bold red]stopped[/bold red]"
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


def build_env_status_table(
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
    """
    Render the environment status table and optional side panels.

    The table is driven by `grouped` rows from `collect_env_status`.
    When command log/error inputs are provided, the function returns a
    Rich `Group` with the table plus panels; otherwise it returns `Table`.
    """
    title = f"[white]{env_tag}[/white]"
    if status_suffix:
        title = f"{title} {status_suffix}"
    table = Table(
        title=title,
        box=box.SIMPLE,
        title_justify="left",
        title_style="bold",
    )
    hidden = hidden_columns or set()
    column_order = ["Gates", "Service", "Container", "State"]
    if details_enabled:
        column_order.append("Probes")
    visible_columns = [c for c in column_order if c not in hidden]

    for col in visible_columns:
        if col in ("Gates", "Service"):
            table.add_column(col, style="cyan", no_wrap=True)
        elif col == "Container":
            table.add_column(col, style="white", no_wrap=True)
        elif col == "Probes":
            table.add_column(col, style="white")
        else:
            table.add_column(col, no_wrap=True)

    for service, items in grouped.items():
        for idx, item in enumerate(items):
            gate_details = ""
            if details_enabled:
                gates, container, state, gate_details = item
            else:
                gates, container, state = item
            is_last = idx == len(items) - 1
            branch = "└─" if is_last else "├─"
            row_map = {
                "Gates": gates if idx == 0 else "",
                "Service": f"[bold]{service}[/bold]" if idx == 0 else "",
                "Container": f"{branch} {container}",
                "State": state,
                "Probes": gate_details if idx == 0 else "",
            }
            row = [row_map[c] for c in visible_columns]
            table.add_row(*row)

    panels: list[Any] = [table]
    if command_log is not None and command_log_limit is not None:
        panels.append(build_command_log_panel(command_log, command_log_limit))
    if command_error:
        panels.append(
            build_command_error_panel(command_error, command_error_limit)
        )
    if len(panels) == 1:
        return table
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
