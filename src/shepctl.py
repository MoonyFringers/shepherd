# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.


import builtins
import functools
import logging
import os
import sys
from typing import Any, Callable, List, Optional

import click

from completion import CompletionMng
from config import ConfigMng, EnvironmentCfg
from config.config import RemoteCfg
from environment import EnvironmentMng
from factory import ShpdEnvironmentFactory, ShpdServiceFactory
from plugin import PluginMng, PluginRuntimeMng
from remote import RemoteMng
from service import ServiceMng
from util import Util, setup_logging
from util.constants import DEFAULT_COMPOSE_COMMAND_LOG_LIMIT


class ShepherdMng:
    """
    Composition root for CLI managers/factories.

    The click context stores one instance per invocation so command handlers
    share the same loaded config and CLI flags.

    `load_runtime_plugins` keeps the bootstrap split explicit:
    normal commands eagerly load enabled plugins and fail fast on runtime
    errors, while the administrative `plugin` scope and raw completion entry
    point can opt into the safe path that skips external plugin imports.
    """

    def __init__(
        self,
        cli_flags: dict[str, Any] = {},
        *,
        load_runtime_plugins: bool = True,
        plugin_runtime_mng: Optional[PluginRuntimeMng] = None,
    ):
        shpd_conf = os.environ.get("SHPD_CONF") or "~/.shpd.conf"
        Util.ensure_config_values_file(shpd_conf)
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
        self.pluginMng = PluginMng(self.cli_flags, self.configMng)
        self.svcFactory = ShpdServiceFactory(self.configMng)
        self.envFactory = ShpdEnvironmentFactory(
            self.configMng, self.svcFactory, cli_flags=self.cli_flags
        )
        self.environmentMng = EnvironmentMng(
            self.cli_flags, self.configMng, self.envFactory, self.svcFactory
        )
        self.serviceMng = ServiceMng(
            self.cli_flags, self.configMng, self.svcFactory
        )
        self.remoteMng = RemoteMng(self.configMng)
        self.pluginRuntimeMng = plugin_runtime_mng
        if self.pluginRuntimeMng is None and load_runtime_plugins:
            self.pluginRuntimeMng = PluginRuntimeMng(
                self.configMng,
                self.environmentMng,
                self.serviceMng,
                self.remoteMng,
            )
        elif self.pluginRuntimeMng is not None and load_runtime_plugins:
            # Pre-bootstrapped during Click resolution: inject managers now
            # that they are available.
            self.pluginRuntimeMng.attach_managers(
                self.environmentMng, self.serviceMng, self.remoteMng
            )
        self.configMng.set_plugin_runtime_mng(self.pluginRuntimeMng)
        self.completionMng = CompletionMng(
            self.cli_flags,
            self.configMng,
            (
                None
                if self.pluginRuntimeMng is None
                else self.pluginRuntimeMng.registry
            ),
            self.remoteMng,
        )


def _load_plugin_runtime_for_click(ctx: click.Context) -> PluginRuntimeMng:
    """
    Load and cache the runtime plugin manager for Click command resolution.

    Click resolves commands before the root callback creates `ShepherdMng`, so
    plugin-provided scopes and verbs need a small pre-bootstrap path. The
    cached runtime manager lives on the root Click context to avoid repeated
    loads during one invocation.
    """
    root_ctx = ctx.find_root()
    runtime_mng = root_ctx.meta.get("plugin_runtime_mng")
    if runtime_mng is not None:
        return runtime_mng

    shpd_conf = os.environ.get("SHPD_CONF") or "~/.shpd.conf"
    Util.ensure_config_values_file(shpd_conf)
    configMng = ConfigMng(shpd_conf)
    Util.ensure_shpd_dirs(configMng.constants)
    Util.ensure_config_file(configMng.constants)
    configMng.load()
    configMng.ensure_dirs()
    runtime_mng = PluginRuntimeMng(configMng)
    root_ctx.meta["plugin_runtime_mng"] = runtime_mng
    return runtime_mng


class PluginRootGroup(click.Group):
    """Root Click group extended with runtime plugin scopes."""

    def list_commands(self, ctx: click.Context) -> list[str]:
        commands = builtins.list(super().list_commands(ctx))
        registry = _load_plugin_runtime_for_click(ctx).registry
        for scope in sorted(registry.commands):
            if scope not in commands:
                commands.append(scope)
        return commands

    def get_command(
        self, ctx: click.Context, cmd_name: str
    ) -> Optional[click.Command]:
        command = super().get_command(ctx, cmd_name)
        if command is not None:
            return command

        registry = _load_plugin_runtime_for_click(ctx).registry
        if cmd_name in registry.commands:
            return PluginScopeGroup(
                name=cmd_name,
                help=f"Manage plugin scope '{cmd_name}'.",
            )
        return None


class PluginScopeGroup(click.Group):
    """Click scope group extended with runtime plugin verbs."""

    def list_commands(self, ctx: click.Context) -> list[str]:
        commands = builtins.list(super().list_commands(ctx))
        if self.name == "plugin":
            return commands

        registry = _load_plugin_runtime_for_click(ctx).registry
        for verb in sorted(registry.commands.get(self.name or "", {})):
            if verb not in commands:
                commands.append(verb)
        return commands

    def get_command(
        self, ctx: click.Context, cmd_name: str
    ) -> Optional[click.Command]:
        command = super().get_command(ctx, cmd_name)
        if command is not None or self.name == "plugin":
            return command

        registry = _load_plugin_runtime_for_click(ctx).registry
        registered = registry.commands.get(self.name or "", {}).get(cmd_name)
        if registered is None:
            return None
        return registered.spec.command


def require_active_env(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Ensure an active environment exists before running a command handler.

    Decorated handlers receive `envCfg` injected as the first argument after
    `shepherd`, which keeps command functions small and consistent.
    """

    @functools.wraps(func)
    def wrapper(
        shepherd: ShepherdMng, *args: List[str], **kwargs: dict[str, str]
    ) -> Callable[..., Any]:
        envCfg = shepherd.configMng.get_active_environment()
        if not envCfg:
            raise click.UsageError("No active environment found.")
        return func(shepherd, envCfg, *args, **kwargs)

    return wrapper


@click.group(cls=PluginRootGroup)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose mode.")
@click.option("--quiet", is_flag=True, help="Suppress command output.")
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    help="Automatic yes to prompts; run non-interactively.",
)
@click.pass_context
def cli(
    ctx: click.Context,
    verbose: bool,
    quiet: bool,
    yes: bool,
):
    """Shepherd CLI:
    A tool to manage your environments, services, and databases.
    """
    cli_flags = {
        "verbose": verbose,
        "quiet": quiet,
        "details": False,
        "show_commands": False,
        "show_commands_limit": DEFAULT_COMPOSE_COMMAND_LOG_LIMIT,
        "yes": yes,
    }

    if ctx.obj is None:
        load_runtime_plugins = ctx.invoked_subcommand != "plugin"
        preloaded_runtime = ctx.meta.get("plugin_runtime_mng")
        if preloaded_runtime is None:
            ctx.obj = ShepherdMng(
                cli_flags,
                load_runtime_plugins=load_runtime_plugins,
            )
        else:
            ctx.obj = ShepherdMng(
                cli_flags,
                load_runtime_plugins=load_runtime_plugins,
                plugin_runtime_mng=preloaded_runtime,
            )


@cli.command(name="test", hidden=True)
def empty():
    """Empty testing purpose stub."""
    pass


def _apply_show_commands_flags(
    shepherd: ShepherdMng, show_commands: bool, show_commands_limit: int
) -> None:
    """Apply shared status-panel command logging flags to the live CLI state."""
    shepherd.cli_flags["show_commands"] = show_commands
    shepherd.cli_flags["show_commands_limit"] = show_commands_limit


def _apply_details_flag(shepherd: ShepherdMng, details: bool) -> None:
    """Apply shared details-mode flag to the live CLI state."""
    shepherd.cli_flags["details"] = details


@cli.command(
    name="__complete",
    hidden=True,
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
@click.pass_obj
def complete(shepherd: ShepherdMng, args: Any):
    """
    Internal shell completion entrypoint.
    Usage: shepctl __complete <args...>

    This command disables Click’s usual option parsing
    to treat all arguments as raw strings.
    """
    completions = shepherd.completionMng.get_completions(builtins.list(args))
    for c in completions:
        click.echo(c)


# =====================================================
# ENV
# =====================================================
@cli.group(cls=PluginScopeGroup)
def env():
    """Manage environments."""
    pass


@env.command(name="get")
@click.argument("tag", required=False)
@click.option("-o", "--output", type=click.Choice(["yaml", "json"]))
@click.option(
    "-t", "--target", is_flag=True, help="Get the target configuration."
)
@click.option(
    "--by-gate",
    is_flag=True,
    help="Return target configuration grouped by gate.",
)
@click.option(
    "-r", "--resolved", is_flag=True, help="Get the resolved configuration."
)
@click.option("--details", is_flag=True, help="Show container details.")
@click.pass_obj
def get_env(
    shepherd: ShepherdMng,
    tag: str,
    output: Optional[str],
    target: bool,
    by_gate: bool,
    resolved: bool,
    details: bool,
):
    """Get environment details or config."""
    if (target or resolved or by_gate) and not output:
        raise click.UsageError(
            "--target, --resolved, and --by-gate require --output"
        )
    if by_gate and not target:
        raise click.UsageError("--by-gate requires --target")
    _apply_details_flag(shepherd, details)
    if output:
        click.echo(
            shepherd.environmentMng.render_env(
                tag, target, resolved, output=output, grouped=by_gate
            )
        )
        return
    shepherd.environmentMng.describe_env(tag)


@env.command(name="add")
@click.argument("template", required=True)
@click.argument("tag", required=True)
@click.pass_obj
def add_env(shepherd: ShepherdMng, template: str, tag: str):
    """Add a new environment."""
    shepherd.environmentMng.add_env(template, tag)


@env.command(name="clone")
@click.argument("src_tag", required=True)
@click.argument("dst_tag", required=True)
@click.pass_obj
def clone_env(shepherd: ShepherdMng, src_tag: str, dst_tag: str):
    """Clone an environment."""
    shepherd.environmentMng.clone_env(src_tag, dst_tag)


@env.command(name="rename")
@click.argument("src_tag", required=True)
@click.argument("dst_tag", required=True)
@click.pass_obj
def rename_env(shepherd: ShepherdMng, src_tag: str, dst_tag: str):
    """Rename an environment."""
    shepherd.environmentMng.rename_env(src_tag, dst_tag)


# =====================================================
# CHECKOUT
# =====================================================
@env.command(name="checkout")
@click.argument("tag", required=True)
@click.pass_obj
def checkout(shepherd: ShepherdMng, tag: str):
    """Checkout an environment."""
    shepherd.environmentMng.checkout_env(tag)


# =====================================================
# DELETE
# =====================================================
@env.command(name="delete")
@click.argument("tag", required=True)
@click.pass_obj
def delete_env(shepherd: ShepherdMng, tag: str):
    """Delete an environment.

    May prompt for sudo to recover ownership of container-written files.
    """
    shepherd.environmentMng.delete_env(tag)


# =====================================================
# LIST
# =====================================================
@env.command(name="list")
@click.pass_obj
def list_envs(shepherd: ShepherdMng):
    """List environments."""
    shepherd.environmentMng.list_envs()


# =====================================================
# UP
# =====================================================
@env.command(name="up")
@click.option(
    "--show-commands",
    is_flag=True,
    help="Show recent commands in status panels.",
)
@click.option(
    "--show-commands-limit",
    type=int,
    default=DEFAULT_COMPOSE_COMMAND_LOG_LIMIT,
    show_default=True,
    help="Number of recent commands to display.",
)
@click.option(
    "-t",
    "--timeout",
    type=int,
    default=120,
    show_default=True,
    help="Maximum seconds to wait for all containers to be running.",
)
@click.option(
    "-w",
    "--watch",
    is_flag=True,
    help="Keep updating the output until interrupted.",
)
@click.option(
    "--keep-output",
    is_flag=True,
    help=(
        "On start failure, preserve the status display and keep "
        "updating it until interrupted. Useful with --show-commands "
        "to inspect the command log after an init script error."
    ),
)
@click.pass_obj
@require_active_env
def up_env(
    shepherd: ShepherdMng,
    envCfg: EnvironmentCfg,
    show_commands: bool,
    show_commands_limit: int,
    timeout: Optional[int],
    watch: bool,
    keep_output: bool,
):
    """Start environment."""
    _apply_show_commands_flags(shepherd, show_commands, show_commands_limit)
    shepherd.environmentMng.start_env(
        envCfg, timeout_seconds=timeout, watch=watch, keep_output=keep_output
    )


# =====================================================
# HALT
# =====================================================
@env.command(name="halt")
@click.option(
    "--no-wait",
    is_flag=True,
    help="Return after issuing the stop command without waiting.",
)
@click.pass_obj
@require_active_env
def halt_env(shepherd: ShepherdMng, envCfg: EnvironmentCfg, no_wait: bool):
    """Stop environment."""
    shepherd.environmentMng.stop_env(envCfg, wait=not no_wait)


# =====================================================
# RELOAD
# =====================================================
@env.command(name="reload")
@click.option(
    "--show-commands",
    is_flag=True,
    help="Show recent commands in status panels.",
)
@click.option(
    "--show-commands-limit",
    type=int,
    default=DEFAULT_COMPOSE_COMMAND_LOG_LIMIT,
    show_default=True,
    help="Number of recent commands to display.",
)
@click.option(
    "-w",
    "--watch",
    is_flag=True,
    help="Keep updating the output until interrupted.",
)
@click.pass_obj
@require_active_env
def reload_env(
    shepherd: ShepherdMng,
    envCfg: EnvironmentCfg,
    show_commands: bool,
    show_commands_limit: int,
    watch: bool,
):
    """Reload environment."""
    _apply_show_commands_flags(shepherd, show_commands, show_commands_limit)
    shepherd.environmentMng.reload_env(envCfg, watch=watch)


# =====================================================
# STATUS
# =====================================================
@env.command(name="status")
@click.option(
    "--show-commands",
    is_flag=True,
    help="Show recent commands in status panels.",
)
@click.option(
    "--show-commands-limit",
    type=int,
    default=DEFAULT_COMPOSE_COMMAND_LOG_LIMIT,
    show_default=True,
    help="Number of recent commands to display.",
)
@click.option(
    "-w",
    "--watch",
    is_flag=True,
    help="Keep updating the output until interrupted.",
)
@click.pass_obj
@require_active_env
def status_env(
    shepherd: ShepherdMng,
    envCfg: EnvironmentCfg,
    show_commands: bool,
    show_commands_limit: int,
    watch: bool,
):
    """Show environment status."""
    _apply_show_commands_flags(shepherd, show_commands, show_commands_limit)
    shepherd.environmentMng.status_env(envCfg, watch=watch)


@env.command(name="push")
@click.argument("env_tag")
@click.option(
    "--remote",
    "remote_name",
    default=None,
    help="Name of the remote to push to (defaults to the configured default).",
)
@click.option(
    "--set-tracking-remote",
    "set_tracking",
    is_flag=True,
    default=False,
    help="Persist this remote as the env's tracking remote.",
)
@click.option(
    "--labels",
    default=None,
    help="Comma-separated key=value labels to attach to the snapshot.",
)
@click.pass_obj
def push_env(
    shepherd: ShepherdMng,
    env_tag: str,
    remote_name: Optional[str],
    set_tracking: bool,
    labels: Optional[str],
) -> None:
    """Push a new snapshot of ENV_TAG to a remote."""
    label_list = [lbl.strip() for lbl in labels.split(",")] if labels else []
    shepherd.remoteMng.push(
        env_name=env_tag,
        environment_mng=shepherd.environmentMng,
        remote_name=remote_name,
        set_tracking=set_tracking,
        labels=label_list,
    )


@env.command(name="dehydrate")
@click.argument("env_tag")
@click.pass_obj
def dehydrate_env(shepherd: ShepherdMng, env_tag: str) -> None:
    """Strip local data for ENV_TAG while preserving its config entry."""
    shepherd.remoteMng.dehydrate(env_tag, shepherd.environmentMng)


# =====================================================
# SVC
# =====================================================
@cli.group(cls=PluginScopeGroup)
def svc():
    """Manage services."""
    pass


@svc.command(name="get")
@click.argument("tag", required=True)
@click.option("-o", "--output", type=click.Choice(["yaml", "json"]))
@click.option(
    "-t", "--target", is_flag=True, help="Get the target configuration."
)
@click.option(
    "-r", "--resolved", is_flag=True, help="Get the resolved configuration."
)
@click.option("--details", is_flag=True, help="Show container details.")
@click.pass_obj
@require_active_env
def get_svc(
    shepherd: ShepherdMng,
    envCfg: EnvironmentCfg,
    tag: str,
    output: Optional[str],
    target: bool,
    resolved: bool,
    details: bool,
):
    """Get service details or config."""
    if (target or resolved) and not output:
        raise click.UsageError("--target and --resolved require --output")
    _apply_details_flag(shepherd, details)
    if output:
        click.echo(
            shepherd.serviceMng.render_svc(
                envCfg, tag, target, resolved, output=output
            )
        )
        return
    shepherd.serviceMng.describe_svc(envCfg, tag)


@svc.command(name="add")
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


@svc.command(name="up")
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


@svc.command(name="halt")
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


@svc.command(name="reload")
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


@svc.command(name="build")
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


@svc.command(name="logs")
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


@svc.command(name="shell")
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
# PROBE
# =====================================================
@cli.group(cls=PluginScopeGroup)
def probe():
    """Manage probes."""
    pass


@probe.command(name="get")
@click.argument("probe_tag", required=False)
@click.option(
    "-o", "--output", type=click.Choice(["yaml", "json"]), default="yaml"
)
@click.option(
    "-t", "--target", is_flag=True, help="Get the target configuration."
)
@click.option(
    "-r", "--resolved", is_flag=True, help="Get the resolved configuration."
)
@click.option("-a", "--all", is_flag=True, help="Get all probes.")
@click.pass_obj
@require_active_env
def get_probe(
    shepherd: ShepherdMng,
    envCfg: EnvironmentCfg,
    probe_tag: Optional[str],
    output: Optional[str],
    target: bool,
    resolved: bool,
    all: bool,
):
    """Get probe details."""
    if all:
        probe_tag = None
    if output:
        click.echo(
            shepherd.environmentMng.render_probes(
                envCfg, probe_tag, target, resolved
            )
        )


@probe.command(name="check")
@click.argument("probe_tag", required=False)
@click.option("-a", "--all", is_flag=True, help="Check all probes.")
@click.option(
    "-w",
    "--watch",
    is_flag=True,
    help=(
        "Continuously re-run probes and keep the display updated. "
        "Interactive only — exits 0 on Ctrl+C regardless of probe state."
    ),
)
@click.option(
    "--show-commands",
    is_flag=True,
    help="Show recent probe commands in the output panel.",
)
@click.option(
    "--show-commands-limit",
    type=int,
    default=DEFAULT_COMPOSE_COMMAND_LOG_LIMIT,
    show_default=True,
    help="Number of recent commands to display.",
)
@click.pass_obj
@require_active_env
def check_probe(
    shepherd: ShepherdMng,
    envCfg: EnvironmentCfg,
    probe_tag: Optional[str],
    all: bool,
    watch: bool,
    show_commands: bool,
    show_commands_limit: int,
):
    """Run probe checks and return a process exit code based on results."""
    if all:
        probe_tag = None
    _apply_show_commands_flags(shepherd, show_commands, show_commands_limit)
    if watch:
        shepherd.environmentMng.watch_probes(envCfg, probe_tag)
        return
    exit_code = shepherd.environmentMng.check_probes(envCfg, probe_tag)
    sys.exit(exit_code)


# =====================================================
# PLUGIN
# =====================================================
@cli.group(cls=PluginScopeGroup)
def plugin():
    """Manage plugins."""
    pass


@plugin.command(name="list")
@click.pass_obj
def list_plugins(shepherd: ShepherdMng):
    """List installed plugins."""
    shepherd.pluginMng.list_plugins()


@plugin.command(name="get")
@click.argument("plugin_id", required=True)
@click.option(
    "-o",
    "--output",
    type=click.Choice(["yaml", "json"]),
    default="yaml",
    show_default=True,
)
@click.pass_obj
def get_plugin(shepherd: ShepherdMng, plugin_id: str, output: str):
    """Get plugin details."""
    click.echo(shepherd.pluginMng.render_plugin(plugin_id, output))


@plugin.command(name="install")
@click.argument(
    "archive_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=str),
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Replace an already-installed plugin.",
)
@click.pass_obj
def install_plugin(shepherd: ShepherdMng, archive_path: str, force: bool):
    """Install a plugin archive into the managed plugin root."""
    shepherd.pluginMng.install_plugin(archive_path, force=force)


@plugin.command(name="enable")
@click.argument("plugin_id", required=True)
@click.pass_obj
def enable_plugin(shepherd: ShepherdMng, plugin_id: str):
    """Enable one installed plugin."""
    shepherd.pluginMng.enable_plugin(plugin_id)


@plugin.command(name="disable")
@click.argument("plugin_id", required=True)
@click.pass_obj
def disable_plugin(shepherd: ShepherdMng, plugin_id: str):
    """Disable one installed plugin."""
    shepherd.pluginMng.disable_plugin(plugin_id)


@plugin.command(name="remove")
@click.argument("plugin_id", required=True)
@click.pass_obj
def remove_plugin(shepherd: ShepherdMng, plugin_id: str):
    """Remove one installed plugin."""
    shepherd.pluginMng.remove_plugin(plugin_id)


# =====================================================
# REMOTE
# =====================================================
@cli.group(cls=PluginScopeGroup)
def remote():
    """Manage remote storage backends."""
    pass


@remote.command(name="add")
@click.argument("name", required=True)
@click.option("--ftp", "backend_type", flag_value="ftp", help="FTP transport.")
@click.option(
    "--sftp", "backend_type", flag_value="sftp", help="SFTP transport."
)
@click.option("--host", required=True, help="Remote server hostname.")
@click.option("--user", required=True, help="Login username.")
@click.option(
    "--port",
    type=int,
    default=None,
    help="Server port (default: 21 for FTP, 22 for SFTP).",
)
@click.option(
    "--password",
    default=None,
    help="Login password. Supports ${VAR} placeholders.",
)
@click.option(
    "--identity-file",
    default=None,
    help="Path to SSH private key (SFTP only). Supports ${VAR} placeholders.",
)
@click.option(
    "--root-path",
    required=True,
    help="Root directory on the remote for the chunk store.",
)
@click.option(
    "--set-default",
    is_flag=True,
    default=False,
    help="Mark this remote as the default.",
)
@click.pass_obj
def add_remote(
    shepherd: ShepherdMng,
    name: str,
    backend_type: Optional[str],
    host: str,
    user: str,
    port: Optional[int],
    password: Optional[str],
    identity_file: Optional[str],
    root_path: str,
    set_default: bool,
) -> None:
    """Register a new remote storage backend."""
    if not backend_type:
        raise click.UsageError("Specify a transport with --ftp or --sftp.")
    if backend_type == "ftp" and not password:
        raise click.UsageError("FTP remotes require --password.")
    if backend_type == "sftp" and not password and not identity_file:
        raise click.UsageError(
            "SFTP remotes require --password or --identity-file."
        )
    remote_cfg = RemoteCfg(
        name=name,
        type=backend_type,
        host=host,
        port=port,
        user=user,
        password=password,
        root_path=root_path,
        identity_file=identity_file,
        default="true" if set_default else "false",
    )
    try:
        shepherd.configMng.add_remote(remote_cfg)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    Util.print(f"Remote '{name}' registered.")


@remote.command(name="list")
@click.pass_obj
def list_remotes(shepherd: ShepherdMng) -> None:
    """List registered remote storage backends."""
    shepherd.remoteMng.display_registered()


@remote.command(name="delete")
@click.argument("name", required=True)
@click.pass_obj
def delete_remote(shepherd: ShepherdMng, name: str) -> None:
    """Unregister a remote (does not delete remote data)."""
    if shepherd.configMng.get_remote(name) is None:
        raise click.UsageError(f"Remote '{name}' is not configured.")
    shepherd.configMng.remove_remote(name)
    Util.print(f"Remote '{name}' removed.")


@remote.command(name="envs")
@click.option(
    "--remote",
    "remote_name",
    default=None,
    help="Remote name (uses default if omitted).",
)
@click.pass_obj
def list_remote_envs(shepherd: ShepherdMng, remote_name: Optional[str]) -> None:
    """List environments available on a remote."""
    shepherd.remoteMng.display_envs(remote_name)


@remote.command(name="get")
@click.argument("env_name", required=True)
@click.option(
    "--remote",
    "remote_name",
    default=None,
    help="Remote name (uses default if omitted).",
)
@click.pass_obj
def get_remote_env(
    shepherd: ShepherdMng, env_name: str, remote_name: Optional[str]
) -> None:
    """List snapshots for ENV_NAME on a remote."""
    shepherd.remoteMng.display_snapshots(env_name, remote_name)


if __name__ == "__main__":
    cli(obj=None)
