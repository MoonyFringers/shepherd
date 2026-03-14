from __future__ import annotations

from typing import TYPE_CHECKING

from rich.tree import Tree

from util import Util

# Import only for static analysis to avoid a runtime cycle with service.py.
if TYPE_CHECKING:
    from .service import Service


def render_svc_summary(service: Service) -> None:
    """Render the default single-row service summary table."""
    svc_cfg = service.svcCfg
    containers = svc_cfg.containers or []
    Util.render_table(
        title=None,
        columns=[
            {"header": "NAME", "style": "cyan"},
            {"header": "TEMPLATE", "style": "magenta"},
            {
                "header": "CONTAINERS",
                "style": "white",
                "justify": "right",
            },
            {"header": "ACTIVE", "style": "white"},
        ],
        rows=[
            [
                svc_cfg.tag,
                svc_cfg.template,
                str(len(containers)),
                "yes" if svc_cfg.status.active else "no",
            ]
        ],
    )


def build_svc_details_tree(service: Service) -> Tree:
    """Build the details tree shown below the service summary."""
    tree = Tree(f"[bold]{service.svcCfg.tag}[/bold]", guide_style="dim")
    containers = service.svcCfg.containers or []
    if not containers:
        tree.add("[dim]-[/dim]")
        return tree
    for container in containers:
        name = container.run_container_name or container.tag
        tree.add(f"[white]{name}[/white]")
    return tree
