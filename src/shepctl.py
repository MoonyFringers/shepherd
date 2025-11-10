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


import functools
import logging
import os
from typing import Any, Callable, List, Optional

import click

from completion import CompletionMng
from config import ConfigMng, EnvironmentCfg
from environment import EnvironmentMng
from factory import ShpdEnvironmentFactory, ShpdServiceFactory
from service import ServiceMng
from util import Util, setup_logging


class ShepherdMng:
    def __init__(self, cli_flags: dict[str, bool] = {}):
        shpd_conf = os.environ.get("SHPD_CONF", "~/.shpd.conf")
        self.configMng = ConfigMng(shpd_conf)
        setup_logging(
            self.configMng.constants.LOG_FILE,
            self.configMng.constants.LOG_FORMAT,
            self.configMng.constants.LOG_LEVEL,
            self.configMng.constants.LOG_STDOUT,
        )
        logging.debug(
            "### shepctl version:%s started",
            self.configMng.constants.APP_VERSION,
        )
        self.cli_flags = cli_flags
        Util.ensure_shpd_dirs(self.configMng.constants)
        Util.ensure_config_file(self.configMng.constants)
        self.configMng.load()
        self.configMng.ensure_dirs()
        self.completionMng = CompletionMng(self.cli_flags, self.configMng)
        self.svcFactory = ShpdServiceFactory(self.configMng)
        self.envFactory = ShpdEnvironmentFactory(
            self.configMng, self.svcFactory
        )
        self.environmentMng = EnvironmentMng(
            self.cli_flags, self.configMng, self.envFactory, self.svcFactory
        )
        self.serviceMng = ServiceMng(
            self.cli_flags, self.configMng, self.svcFactory
        )


def require_active_env(func: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(func)
    def wrapper(
        shepherd: ShepherdMng, *args: List[str], **kwargs: dict[str, str]
    ) -> Callable[..., Any]:
        envCfg = shepherd.configMng.get_active_environment()
        if not envCfg:
            raise click.UsageError("No active environment found.")
        return func(shepherd, envCfg, *args, **kwargs)

    return wrapper


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose mode.")
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    help="Automatic yes to prompts; run non-interactively.",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, yes: bool):
    """Shepherd CLI:
    A tool to manage your environments, services, and databases.
    """
    cli_flags = {"verbose": verbose, "yes": yes}

    if ctx.obj is None:
        ctx.obj = ShepherdMng(cli_flags)


@cli.command(name="test", hidden=True)
def empty():
    """Empty testing purpose stub."""
    pass


@cli.command(
    name="__complete",
    hidden=True,
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
@click.pass_obj
def complete(shepherd: ShepherdMng, args: list[str]):
    """
    Internal shell completion entrypoint.
    Usage: shepctl __complete <args...>

    This command disables Click’s usual option parsing
    to treat all arguments as raw strings.
    """
    completions = shepherd.completionMng.get_completions(args)
    for c in completions:
        click.echo(c)


# =====================================================
# GET
# =====================================================
@cli.group()
def get():
    """Get resources."""
    pass


@get.command(name="env")
@click.argument("tag", required=False)
@click.option(
    "-o", "--output", type=click.Choice(["yaml", "json"]), default="yaml"
)
@click.option(
    "-t", "--target", is_flag=True, help="Get the target configuration."
)
@click.option(
    "-r", "--resolved", is_flag=True, help="Get the resolved configuration."
)
@click.pass_obj
def get_env(
    shepherd: ShepherdMng,
    tag: str,
    output: Optional[str],
    target: bool,
    resolved: bool,
):
    """Get environment details or config."""
    if output:
        click.echo(shepherd.environmentMng.render_env(tag, target, resolved))


@get.command(name="svc")
@click.argument("tag", required=True)
@click.option(
    "-o", "--output", type=click.Choice(["yaml", "json"]), default="yaml"
)
@click.option(
    "-t", "--target", is_flag=True, help="Get the target configuration."
)
@click.option(
    "-r", "--resolved", is_flag=True, help="Get the resolved configuration."
)
@click.pass_obj
@require_active_env
def get_svc(
    shepherd: ShepherdMng,
    envCfg: EnvironmentCfg,
    tag: str,
    output: Optional[str],
    target: bool,
    resolved: bool,
):
    """Get service details or config."""
    if output:
        click.echo(
            shepherd.serviceMng.render_svc(envCfg, tag, target, resolved)
        )


# =====================================================
# ADD
# =====================================================
@cli.group()
def add():
    """Add resources."""
    pass


@add.command(name="env")
@click.argument("template", required=True)
@click.argument("tag", required=True)
@click.pass_obj
def add_env(shepherd: ShepherdMng, template: str, tag: str):
    """Add a new environment."""
    shepherd.environmentMng.add_env(template, tag)


@add.command(name="svc")
@click.argument("svc_template", required=True)
@click.argument("svc_tag", required=True)
@click.argument("svc_class", required=False)
@click.pass_obj
@require_active_env
def add_svc(
    shepherd: ShepherdMng,
    envCfg: EnvironmentCfg,
    svc_template: str,
    svc_tag: str,
    svc_class: Optional[str] = None,
):
    """Add a new service."""
    shepherd.environmentMng.add_service(
        envCfg.tag, svc_tag, svc_template, svc_class
    )


# =====================================================
# CLONE
# =====================================================
@cli.group()
def clone():
    """Clone resources."""
    pass


@clone.command(name="env")
@click.argument("src_tag", required=True)
@click.argument("dst_tag", required=True)
@click.pass_obj
def clone_env(shepherd: ShepherdMng, src_tag: str, dst_tag: str):
    """Clone an environment."""
    shepherd.environmentMng.clone_env(src_tag, dst_tag)


# =====================================================
# RENAME
# =====================================================
@cli.group()
def rename():
    """Rename resources."""
    pass


@rename.command(name="env")
@click.argument("src_tag", required=True)
@click.argument("dst_tag", required=True)
@click.pass_obj
def rename_env(shepherd: ShepherdMng, src_tag: str, dst_tag: str):
    """Rename an environment."""
    shepherd.environmentMng.rename_env(src_tag, dst_tag)


# =====================================================
# CHECKOUT
# =====================================================
@cli.command(name="checkout")
@click.argument("tag", required=True)
@click.pass_obj
def checkout(shepherd: ShepherdMng, tag: str):
    """Checkout an environment."""
    shepherd.environmentMng.checkout_env(tag)


# =====================================================
# DELETE
# =====================================================
@cli.group()
def delete():
    """Delete resources."""
    pass


@delete.command(name="env")
@click.argument("tag", required=True)
@click.pass_obj
def delete_env(shepherd: ShepherdMng, tag: str):
    """Delete an environment."""
    shepherd.environmentMng.delete_env(tag)


# =====================================================
# LIST
# =====================================================
@cli.command(name="list")
@click.pass_obj
def list(shepherd: ShepherdMng):
    """List environments."""
    shepherd.environmentMng.list_envs()


# =====================================================
# UP
# =====================================================
@cli.group(invoke_without_command=True)
@click.pass_obj
@require_active_env
def up(shepherd: ShepherdMng, envCfg: EnvironmentCfg):
    """Start resources."""
    # If no subcommand is given, default to "env"
    ctx = click.get_current_context()
    if ctx.invoked_subcommand is None:
        shepherd.environmentMng.start_env(envCfg)


@up.command(name="env")
@click.pass_obj
@require_active_env
def up_env(shepherd: ShepherdMng, envCfg: EnvironmentCfg):
    """Start environment."""
    shepherd.environmentMng.start_env(envCfg)


@up.command(name="svc")
@click.argument("svc_tag", required=True)
@click.argument("cnt_tag", required=False)
@click.pass_obj
@require_active_env
def up_svc(
    shepherd: ShepherdMng,
    envCfg: EnvironmentCfg,
    svc_tag: str,
    cnt_tag: Optional[str] = None,
):
    """Start service."""
    shepherd.serviceMng.start_svc(envCfg, svc_tag, cnt_tag)


# =====================================================
# STOP
# =====================================================
@cli.group(invoke_without_command=True)
@click.pass_obj
@require_active_env
def halt(shepherd: ShepherdMng, envCfg: EnvironmentCfg):
    """Stop resources."""
    # If no subcommand is given, default to "env"
    ctx = click.get_current_context()
    if ctx.invoked_subcommand is None:
        shepherd.environmentMng.stop_env(envCfg)


@halt.command(name="env")
@click.pass_obj
@require_active_env
def halt_env(shepherd: ShepherdMng, envCfg: EnvironmentCfg):
    """Stop environment."""
    shepherd.environmentMng.stop_env(envCfg)


@halt.command(name="svc")
@click.argument("svc_tag", required=True)
@click.argument("cnt_tag", required=False)
@click.pass_obj
@require_active_env
def halt_svc(
    shepherd: ShepherdMng,
    envCfg: EnvironmentCfg,
    svc_tag: str,
    cnt_tag: Optional[str] = None,
):
    """Stop service."""
    shepherd.serviceMng.stop_svc(envCfg, svc_tag, cnt_tag)


# =====================================================
# RELOAD
# =====================================================
@cli.group()
def reload():
    """Reload resources."""
    pass


@reload.command(name="env")
@click.pass_obj
@require_active_env
def reload_env(shepherd: ShepherdMng, envCfg: EnvironmentCfg):
    """Reload environment."""
    shepherd.environmentMng.reload_env(envCfg)


@reload.command(name="svc")
@click.argument("svc_tag", required=True)
@click.argument("cnt_tag", required=False)
@click.pass_obj
@require_active_env
def reload_svc(
    shepherd: ShepherdMng,
    envCfg: EnvironmentCfg,
    svc_tag: str,
    cnt_tag: Optional[str] = None,
):
    """Reload service."""
    shepherd.serviceMng.reload_svc(envCfg, svc_tag, cnt_tag)


# =====================================================
# BUILD
# =====================================================
@cli.command(name="build")
@click.argument("svc_tag", required=True)
@click.argument("cnt_tag", required=False)
@click.pass_obj
@require_active_env
def build(
    shepherd: ShepherdMng,
    envCfg: EnvironmentCfg,
    svc_tag: str,
    cnt_tag: Optional[str] = None,
):
    """Build service."""
    shepherd.serviceMng.build_svc(envCfg, svc_tag, cnt_tag)


# =====================================================
# LOGS
# =====================================================
@cli.command(name="logs")
@click.argument("svc_tag", required=True)
@click.argument("cnt_tag", required=False)
@click.pass_obj
@require_active_env
def logs(
    shepherd: ShepherdMng,
    envCfg: EnvironmentCfg,
    svc_tag: str,
    cnt_tag: Optional[str] = None,
):
    """Show service logs."""
    shepherd.serviceMng.logs_svc(envCfg, svc_tag, cnt_tag)


# =====================================================
# SHELL
# =====================================================
@cli.command(name="shell")
@click.argument("svc_tag", required=True)
@click.argument("cnt_tag", required=False)
@click.pass_obj
@require_active_env
def shell(
    shepherd: ShepherdMng,
    envCfg: EnvironmentCfg,
    svc_tag: str,
    cnt_tag: Optional[str] = None,
):
    """Get a shell session for a service."""
    shepherd.serviceMng.shell_svc(envCfg, svc_tag, cnt_tag)


# =====================================================
# STATUS
# =====================================================
@cli.group(invoke_without_command=True)
@click.pass_obj
@require_active_env
def status(shepherd: ShepherdMng, envCfg: EnvironmentCfg):
    """Show status of resources."""
    ctx = click.get_current_context()
    if ctx.invoked_subcommand is None:
        shepherd.environmentMng.status_env(envCfg)


@status.command(name="env")
@click.pass_obj
@require_active_env
def status_env(shepherd: ShepherdMng, envCfg: EnvironmentCfg):
    """Show environment status."""
    shepherd.environmentMng.status_env(envCfg)


if __name__ == "__main__":
    cli(obj=None)
