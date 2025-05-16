# Copyright (c) 2025 Lunatic Fringers
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


from typing import Dict

import click

from config import ConfigMng
from database import DatabaseMng
from environment import EnvironmentMng
from factory import ShpdEnvironmentFactory
from service import ServiceMng
from util import Util


class ShepherdMng:
    def __init__(self, cli_flags: Dict[str, bool] = {}):
        self.configMng = ConfigMng("~/.shpd.conf")
        self.cli_flags = cli_flags
        Util.ensure_dirs(self.configMng.constants)
        Util.ensure_config_file(self.configMng.constants)
        self.configMng.load()
        self.environmentMng = EnvironmentMng(
            self.cli_flags,
            self.configMng,
            ShpdEnvironmentFactory(self.configMng),
        )
        self.serviceMng = ServiceMng(self.cli_flags, self.configMng)
        self.databaseMng = DatabaseMng(self.cli_flags, self.configMng)


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose mode.")
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    help="Automatic yes to prompts; run non-interactively.",
)
@click.option("-a", "--all", is_flag=True, help="Apply to all.")
@click.option("-f", "--follow", is_flag=True, help="Follow log output.")
@click.option(
    "-p", "--porcelain", is_flag=True, help="Produce machine-readable output."
)
@click.option("-k", "--keep", is_flag=True, help="Keep instead of drop.")
@click.option(
    "-r", "--replace", is_flag=True, help="Replace when already there."
)
@click.option(
    "-c",
    "--checkout",
    is_flag=True,
    help="Contextually checkout the environment.",
)
@click.pass_context
def cli(
    ctx: click.Context,
    verbose: bool,
    yes: bool,
    all: bool,
    follow: bool,
    porcelain: bool,
    keep: bool,
    replace: bool,
    checkout: bool,
):
    """Shepherd CLI:
    A tool to manage your environments, services, and databases.
    """
    cli_flags = {
        "verbose": verbose,
        "yes": yes,
        "all": all,
        "follow": follow,
        "porcelain": porcelain,
        "keep": keep,
        "replace": replace,
        "checkout": checkout,
    }

    if ctx.obj is None:
        ctx.obj = ShepherdMng(cli_flags)


@cli.command(name="test", hidden=True)
def empty():
    """Empty testing purpose stub"""
    pass


@cli.group()
def db():
    """Database related operations."""
    pass


@db.command(name="build")
@click.pass_obj
def db_build(shepherd: ShepherdMng):
    """Build database image."""
    shepherd.databaseMng.build_image_svc("")


@db.command(name="bootstrap")
@click.pass_obj
def db_bootstrap(shepherd: ShepherdMng):
    """Bootstrap database service."""
    shepherd.databaseMng.bootstrap_svc("")


@db.command(name="start")
@click.pass_obj
def db_start(shepherd: ShepherdMng):
    """Start database service."""
    shepherd.databaseMng.start_svc("")


@db.command(name="halt")
@click.pass_obj
def db_halt(shepherd: ShepherdMng):
    """Halt database service."""
    shepherd.databaseMng.halt_svc("")


@db.command(name="stdout")
@click.pass_obj
def db_stdout(shepherd: ShepherdMng):
    """Show database service stdout."""
    shepherd.databaseMng.stdout_svc("")


@db.command(name="shell")
@click.pass_obj
def db_shell(shepherd: ShepherdMng):
    """Get a shell session for the database service."""
    shepherd.databaseMng.shell_svc("")


@db.command(name="sql-shell")
@click.pass_obj
def db_sql_shell(shepherd: ShepherdMng):
    """Get a SQL session for the database service."""
    shepherd.databaseMng.sql_shell_svc()


# Environment commands
@cli.group()
def env():
    """Environment related operations."""
    pass


@env.command(name="init")
@click.argument("env_type", required=True)
@click.argument("env_tag", required=True)
@click.pass_obj
def env_init(shepherd: ShepherdMng, env_type: str, env_tag: str):
    """Init an environment with an environment type,
    a database type and an environment's tag name."""
    shepherd.environmentMng.init_env(env_type, env_tag)


@env.command(name="clone")
@click.argument("src_env_tag", required=True)
@click.argument("dst_env_tag", required=True)
@click.pass_obj
def env_clone(shepherd: ShepherdMng, src_env_tag: str, dst_env_tag: str):
    """Clone an environment."""
    shepherd.environmentMng.clone_env(src_env_tag, dst_env_tag)


@env.command(name="rename")
@click.argument("src_env_tag", required=True)
@click.argument("dst_env_tag", required=True)
@click.pass_obj
def env_rename(shepherd: ShepherdMng, src_env_tag: str, dst_env_tag: str):
    """Rename an environment."""
    shepherd.environmentMng.rename_env(src_env_tag, dst_env_tag)


@env.command(name="checkout")
@click.argument("env_tag", required=True)
@click.pass_obj
def env_checkout(shepherd: ShepherdMng, env_tag: str):
    """Checkout an environment."""
    shepherd.environmentMng.checkout_env(env_tag)


@env.command(name="delete")
@click.argument("env_tag", required=True)
@click.pass_obj
def env_delete(shepherd: ShepherdMng, env_tag: str):
    """Delete an environment."""
    shepherd.environmentMng.delete_env(env_tag)


@env.command(name="noactive")
@click.pass_obj
def env_set_noactive(shepherd: ShepherdMng):
    """Set all environments as non-active."""
    shepherd.environmentMng.set_all_envs_non_active()


@env.command(name="list")
@click.pass_obj
def env_list(shepherd: ShepherdMng):
    """List all available environments."""
    shepherd.environmentMng.list_envs()


@env.command(name="start")
@click.pass_obj
def env_start(shepherd: ShepherdMng):
    """Start environment."""
    shepherd.environmentMng.start_env()


@env.command(name="halt")
@click.pass_obj
def env_halt(shepherd: ShepherdMng):
    """Halt environment."""
    shepherd.environmentMng.halt_env()


@env.command(name="reload")
@click.pass_obj
def env_reload(shepherd: ShepherdMng):
    """Reload environment."""
    shepherd.environmentMng.reload_env()


@env.command(name="status")
@click.pass_obj
def env_status(shepherd: ShepherdMng):
    """Print environment's status."""
    shepherd.environmentMng.status_env()


@cli.group()
def svc():
    """Service related operations."""
    pass


@svc.command(name="build")
@click.argument("service_type", type=str, required=True)
@click.pass_obj
def srv_build(shepherd: ShepherdMng, service_type: str):
    """Build service image."""
    shepherd.serviceMng.build_image_svc(service_type)


@svc.command(name="bootstrap")
@click.argument("service_type", type=str, required=True)
@click.pass_obj
def srv_bootstrap(shepherd: ShepherdMng, service_type: str):
    """Bootstrap service."""
    shepherd.serviceMng.bootstrap_svc(service_type)


@svc.command(name="start")
@click.argument("service_type", type=str, required=True)
@click.pass_obj
def srv_start(shepherd: ShepherdMng, service_type: str):
    """Start service."""
    shepherd.serviceMng.start_svc(service_type)


@svc.command(name="halt")
@click.argument("service_type", type=str, required=True)
@click.pass_obj
def srv_halt(shepherd: ShepherdMng, service_type: str):
    """Halt service."""
    shepherd.serviceMng.halt_svc(service_type)


@svc.command(name="reload")
@click.argument("service_type", type=str, required=True)
@click.pass_obj
def srv_reload(shepherd: ShepherdMng, service_type: str):
    """Reload service."""
    shepherd.serviceMng.reload_svc(service_type)


@svc.command(name="stdout")
@click.argument("service_id", type=str, required=True)
@click.pass_obj
def srv_stdout(shepherd: ShepherdMng, service_id: str):
    """Show service stdout."""
    shepherd.serviceMng.stdout_svc(service_id)


@svc.command(name="shell")
@click.argument("service_id", type=str, required=True)
@click.pass_obj
def srv_shell(shepherd: ShepherdMng, service_id: str):
    """Get a shell session for the service."""
    shepherd.serviceMng.shell_svc(service_id)


if __name__ == "__main__":
    cli(obj=None)
