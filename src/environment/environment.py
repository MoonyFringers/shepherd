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

import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Optional

from config import ConfigMng, EnvironmentCfg, EnvironmentTemplateCfg
from service import Service, ServiceFactory
from util import Constants, Util
from util.constants import DEFAULT_COMPOSE_COMMAND_LOG_LIMIT

from .render import (
    build_command_error_panel,
    build_command_log_panel,
    build_env_status_table,
    build_probe_report,
    collect_env_status,
    dump_grouped_yaml,
    format_service_gate_details,
    format_service_gate_glyphs,
    render_probe_report,
)
from .status_wait import wait_for_env_state


@dataclass
class ProbeRunResult:
    tag: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: Optional[int] = None
    timed_out: bool = False


class NonRecoverableStartError(RuntimeError):
    """Raised when environment start cannot continue safely."""


class Environment(ABC):

    services: list[Service]

    def __init__(
        self,
        configMng: ConfigMng,
        svcFactory: ServiceFactory,
        envCfg: EnvironmentCfg,
        cli_flags: Optional[dict[str, Any]] = None,
    ):
        self.configMng = configMng
        self.svcFactory = svcFactory
        self.envCfg = envCfg
        self.cli_flags = cli_flags or {}
        self.services = (
            [
                self.svcFactory.new_service_from_cfg(
                    envCfg, svcCfg, cli_flags=self.cli_flags
                )
                for svcCfg in envCfg.services
            ]
            if envCfg.services
            else []
        )
        self._command_log_limit = int(
            self.cli_flags.get(
                "show_commands_limit", DEFAULT_COMPOSE_COMMAND_LOG_LIMIT
            )
        )
        if self._command_log_limit < 0:
            self._command_log_limit = 0
        self._command_log: deque[str] = deque(maxlen=self._command_log_limit)
        self._command_log_lock = threading.Lock()
        self._command_error_lock = threading.Lock()
        self._command_error: Optional[dict[str, str]] = None

    def _is_verbose(self) -> bool:
        return bool(self.cli_flags.get("verbose", False))

    def _is_quiet(self) -> bool:
        return bool(self.cli_flags.get("quiet", False))

    def _is_details(self) -> bool:
        return bool(self.cli_flags.get("details", False))

    @abstractmethod
    def clone_impl(self, dst_env_tag: str) -> Environment:
        """Clone the environment."""
        pass

    def clone(self, dst_env_tag: str) -> Environment:
        """Clone the environment."""
        return self.clone_impl(dst_env_tag)

    def start(self, timeout_seconds: Optional[int] = 60):
        """Start the environment."""
        self.clear_command_log()
        self.clear_command_error()
        self.on_start_cycle_begin()
        self.envCfg.status.rendered_config = self.render_target(True)
        self.sync_config()
        self.ensure_resources()

        rendered_config = self.envCfg.status.rendered_config or {}
        pending_gate_keys = set(rendered_config.keys())
        started_gate_keys: set[str] = set()

        try:
            started_now = self.start_impl(
                started_gate_keys=started_gate_keys,
                probe_results=None,
            )
            started_gate_keys.update(started_now)
            pending_gate_keys -= started_now
            self.run_inits(
                started_gate_keys=started_gate_keys,
                probe_results=None,
            )

            started_at = time.monotonic()
            while pending_gate_keys:
                probe_results = self.check_probes(
                    probe_tag=None,
                    fail_fast=False,
                    timeout_seconds=120,
                )
                if not probe_results:
                    break

                started_now = self.start_impl(
                    started_gate_keys=started_gate_keys,
                    probe_results=probe_results,
                )
                started_gate_keys.update(started_now)
                pending_gate_keys -= started_now
                self.run_inits(
                    started_gate_keys=started_gate_keys,
                    probe_results=probe_results,
                )
                if not started_now:
                    if timeout_seconds is not None:
                        elapsed = int(time.monotonic() - started_at)
                        if elapsed >= timeout_seconds:
                            break
                    time.sleep(1.0)
                    continue
        except NonRecoverableStartError as e:
            try:
                self.stop()
            except BaseException:
                logging.exception(
                    "Failed rollback stop after start failure for env '%s'",
                    self.envCfg.tag,
                )
            message = (
                str(e)
                or "Environment start failed due to a non-recoverable error."
            )
            Util.print_error_and_die(message)

    def add_command_log(self, command: str) -> None:
        """Add a command entry to the environment log."""
        if not command or self._command_log_limit <= 0:
            return
        with self._command_log_lock:
            self._command_log.append(command)

    def get_command_log(self) -> list[str]:
        """Return a snapshot of recent command entries."""
        with self._command_log_lock:
            return list(self._command_log)

    def clear_command_log(self) -> None:
        """Clear recent command entries."""
        with self._command_log_lock:
            self._command_log.clear()

    def get_command_log_limit(self) -> int:
        return self._command_log_limit

    def is_command_log_enabled(self) -> bool:
        return bool(self.cli_flags.get("show_commands", False)) and (
            self._command_log_limit > 0
        )

    def set_command_error(self, title: str, body: str) -> None:
        if not title or not body:
            return
        with self._command_error_lock:
            self._command_error = {"title": title, "body": body}

    def clear_command_error(self) -> None:
        with self._command_error_lock:
            self._command_error = None

    def get_command_error(self) -> Optional[dict[str, str]]:
        with self._command_error_lock:
            return dict(self._command_error) if self._command_error else None

    def stop(self):
        """Halt the environment."""
        return self.stop_impl()

    def reload(self):
        """Reload the environment."""
        return self.reload_impl()

    def render(self, resolved: bool) -> str:
        """Render the environment configuration."""
        return self.envCfg.get_yaml(resolved)

    def render_target(self, resolved: bool = False) -> dict[str, str]:
        """
        Render the environment configuration in the target system.
        """
        return self.render_target_impl(resolved)

    def render_target_merged(self, resolved: bool = False) -> str:
        """
        Render the environment configuration in the target system as a single
        merged config.
        """
        rendered = self.render_target(resolved)
        return rendered.get("ungated", "")

    def render_target_grouped(self, resolved: bool = False) -> str:
        """
        Render the environment configuration in the target system
        grouped by gate.
        """
        rendered = self.render_target(resolved)
        return dump_grouped_yaml(rendered)

    def render_probes(
        self, probe_tag: Optional[str], resolved: bool
    ) -> Optional[str]:
        """
        Render the environment probes configuration.
        """
        return self.envCfg.get_probes_yaml(probe_tag, resolved)

    def render_probes_target(
        self, probe_tag: Optional[str], resolved: bool
    ) -> Optional[str]:
        """
        Render the environment probes configuration in the target system.
        """
        return self.render_probes_target_impl(probe_tag, resolved)

    def check_probes(
        self,
        probe_tag: Optional[str] = None,
        fail_fast: bool = True,
        timeout_seconds: Optional[int] = 120,
    ) -> list[ProbeRunResult]:
        """
        Run environment probes synchronously against the running environment.

        Semantics:
          - If probe_tag is provided: run only that probe.
          - Otherwise: run all probes (sequentially).
          - fail_fast: stop at first failure.
          - timeout_seconds: per-probe timeout.
        """
        return self.check_probes_impl(
            probe_tag=probe_tag,
            fail_fast=fail_fast,
            timeout_seconds=timeout_seconds,
        )

    @abstractmethod
    def check_probes_impl(
        self,
        probe_tag: Optional[str],
        fail_fast: bool,
        timeout_seconds: Optional[int],
    ) -> list[ProbeRunResult]:
        pass

    def status(self) -> list[dict[str, str]]:
        """Get environment status."""
        return self.status_impl()

    def on_start_cycle_begin(self) -> None:
        """Hook called once at the beginning of environment start."""
        return None

    def run_inits(
        self,
        started_gate_keys: set[str],
        probe_results: Optional[list[ProbeRunResult]],
    ) -> None:
        """Hook for running service/container init flows during start."""
        return None

    def to_config(self) -> EnvironmentCfg:
        """To config"""
        self.envCfg.services = [svc.svcCfg for svc in self.services]
        return self.envCfg

    def get_path(self) -> str:
        """Return the directory of the environment."""
        return os.path.join(self.configMng.config.envs_path, self.envCfg.tag)

    def get_path_for_tag(self, env_tag: str) -> str:
        """Return the directory for the environment with a given tag."""
        return os.path.join(self.configMng.config.envs_path, env_tag)

    def ensure_resources(self):
        """Ensure the environment resources are available."""
        return self.ensure_resources_impl()

    @abstractmethod
    def stop_impl(self):
        """Halt the environment."""
        pass

    @abstractmethod
    def start_impl(
        self,
        started_gate_keys: set[str],
        probe_results: Optional[list[ProbeRunResult]] = None,
    ) -> set[str]:
        """Start the environment."""
        pass

    @abstractmethod
    def reload_impl(self):
        """Reload the environment."""
        pass

    @abstractmethod
    def render_target_impl(self, resolved: bool = False) -> dict[str, str]:
        """
        Render the environment configuration in the target system.
        """
        pass

    @abstractmethod
    def render_probes_target_impl(
        self, probe_tag: Optional[str], resolved: bool
    ) -> Optional[str]:
        """
        Render the environment probes configuration in the target system.
        """
        pass

    @abstractmethod
    def status_impl(self) -> list[dict[str, str]]:
        """Get environment status."""
        pass

    @abstractmethod
    def ensure_resources_impl(self):
        """Ensure the environment resources are available."""
        pass

    def realize(self):
        """Realize the environment."""
        Util.ensure_dir(
            self.get_path(),
            self.envCfg.tag,
        )

        for service in self.services:
            if svc_t_path := self.configMng.get_service_template_path(
                service.svcCfg.template
            ):
                Util.copy_dir(
                    svc_t_path,
                    os.path.join(self.get_path(), service.svcCfg.tag),
                )
            else:
                Util.print_error_and_die(
                    f"Service Template: '{service.svcCfg.template}' "
                    f"does not exist."
                )

        self.sync_config()

    def realize_from(self, src_env: Environment):
        """Realize the environment."""
        Util.copy_dir(src_env.get_path(), self.get_path())
        self.sync_config()

    def move_to(self, dst_env_tag: str):
        """Move the environment to a new tag."""
        Util.move_dir(self.get_path(), self.get_path_for_tag(dst_env_tag))
        self.configMng.remove_environment(self.envCfg.tag)
        self.envCfg.tag = dst_env_tag
        self.sync_config()

    def delete(self):
        """Delete the environment."""
        Util.remove_dir(self.get_path())
        self.configMng.remove_environment(self.envCfg.tag)

    def sync_config(self):
        """Sync the environment configuration."""
        self.configMng.add_or_set_environment(self.envCfg.tag, self.to_config())

    def get_tag(self) -> str:
        """Return the tag of the environment."""
        return self.envCfg.tag

    def set_tag(self, tag: str):
        """Set the tag of the environment."""
        self.envCfg.tag = tag

    def add_service(self, service: Service):
        """Add a service to the environment."""
        self.services.append(service)
        self.sync_config()

    def remove_service(self, service: Service):
        """Remove a service from the environment."""
        self.services.remove(service)
        self.sync_config()

    def get_services(self) -> list[Service]:
        """Return the list of services in the environment."""
        return self.services

    def get_service(self, svc_name: str) -> Optional[Service]:
        """Get a service by name."""
        for service in self.services:
            if service.svcCfg.tag == svc_name:
                return service
        return None


class EnvironmentFactory(ABC):
    """
    Factory class for environments.
    """

    def __init__(
        self, config: ConfigMng, cli_flags: Optional[dict[str, Any]] = None
    ):
        self.config = config
        self.cli_flags = cli_flags or {}

    def new_environment(
        self,
        env_tmpl_cfg: EnvironmentTemplateCfg,
        env_tag: str,
    ) -> Environment:
        """
        Create an environment.
        """
        return self.new_environment_impl(env_tmpl_cfg, env_tag)

    def new_environment_cfg(self, envCfg: EnvironmentCfg) -> Environment:
        """
        Create an environment.
        """
        return self.new_environment_cfg_impl(envCfg)

    @abstractmethod
    def new_environment_impl(
        self,
        env_tmpl_cfg: EnvironmentTemplateCfg,
        env_tag: str,
    ) -> Environment:
        """
        Create an environment.
        """
        pass

    @abstractmethod
    def new_environment_cfg_impl(self, envCfg: EnvironmentCfg) -> Environment:
        """
        Create an environment.
        """
        pass


class EnvironmentMng:

    def __init__(
        self,
        cli_flags: dict[str, Any],
        configMng: ConfigMng,
        envFactory: EnvironmentFactory,
        svcFactory: ServiceFactory,
    ):
        self.cli_flags = cli_flags
        self.configMng = configMng
        self.envFactory = envFactory
        self.svcFactory = svcFactory
        self._status_poll_seconds = 1.0

    def _is_verbose(self) -> bool:
        return bool(self.cli_flags.get("verbose", False))

    def _is_quiet(self) -> bool:
        return bool(self.cli_flags.get("quiet", False))

    def _is_details(self) -> bool:
        return bool(self.cli_flags.get("details", False))

    def get_environment_from_tag(
        self, env_tag: Optional[str]
    ) -> Optional[Environment]:
        if env_tag and env_tag.strip():
            envCfg = self.configMng.get_environment(env_tag)
            if not envCfg:
                Util.print_error_and_die(
                    f"Environment: '{env_tag}' does not exist."
                )
        else:
            envCfg = self.configMng.get_active_environment()
            if not envCfg:
                Util.print_error_and_die("No active environment configured.")

        if envCfg:
            env = self.envFactory.new_environment_cfg(envCfg)
            return env
        else:
            return None

    def get_environment_from_cfg(self, env_cfg: EnvironmentCfg) -> Environment:
        env = self.envFactory.new_environment_cfg(env_cfg)
        return env

    def add_env(self, env_template: str, env_tag: str):
        """Initialize an environment."""
        if self.configMng.get_environment(env_tag):
            Util.print_error_and_die(
                f"Environment: '{env_tag}' already exists."
            )
        if envTmplCfg := self.configMng.get_environment_template(env_template):
            env = self.envFactory.new_environment(
                envTmplCfg,
                env_tag,
            )
            env.realize()
            Util.print(f"{env_tag}")
        else:
            Util.print_error_and_die(
                f"Environment Template: '{env_template}' " f"does not exist."
            )

    def clone_env(self, src_env_tag: str, dst_env_tag: str):
        """Clone an environment."""
        envCfg = self.configMng.get_environment(src_env_tag)
        if not envCfg:
            Util.print_error_and_die(
                f"Environment: '{src_env_tag}' does not exist."
            )
        else:
            env = self.envFactory.new_environment_cfg(envCfg)
            clonedEnv = env.clone(dst_env_tag)
            clonedEnv.realize_from(env)
            Util.print(f"Cloned to: {dst_env_tag}")

    def rename_env(self, src_env_tag: str, dst_env_tag: str):
        """Rename an environment."""
        envCfg = self.configMng.get_environment(src_env_tag)
        if not envCfg:
            Util.print_error_and_die(
                f"Environment: '{src_env_tag}' does not exist."
            )
        else:
            env = self.envFactory.new_environment_cfg(envCfg)
            env.move_to(dst_env_tag)
            Util.print(f"Renamed to: {dst_env_tag}")

    def checkout_env(self, env_tag: str):
        """Checkout an environment."""
        envCfg = self.configMng.get_environment(env_tag)
        if not envCfg:
            Util.print_error_and_die(
                f"Environment: '{env_tag}' does not exist."
            )
        else:
            envCfg.status.active = True
            self.configMng.set_active_environment(env_tag)
            Util.print(f"Switched to: {env_tag}")

    def delete_env(self, env_tag: str):
        """Delete an environment."""
        envCfg = self.configMng.get_environment(env_tag)
        if not envCfg:
            Util.print_error_and_die(
                f"Environment: '{env_tag}' does not exist."
            )
        else:
            if not self.cli_flags["yes"]:
                if not Util.confirm(
                    f"Are you sure you want to "
                    f"delete the environment '{env_tag}'?"
                ):
                    Util.console.print("Aborted.", style="yellow")
                    return

            env = self.envFactory.new_environment_cfg(envCfg)
            env.delete()
            Util.print(f"Deleted: {env.envCfg.tag}")

    def list_envs(self):
        """List all available environments."""
        envs = self.configMng.get_environments()
        if not envs:
            Util.console.print("[yellow]No environments available.[/yellow]")
            return

        rows = [[env.tag, env.template] for env in envs]

        Util.render_table(
            title="Environments",
            columns=[
                {"header": "Tag", "style": "cyan"},
                {"header": "Template", "style": "magenta"},
            ],
            rows=rows,
        )
        Util.console.print(
            f"{len(envs)} environment(s) found.", highlight=False
        )

    def start_env(
        self,
        envCfg: EnvironmentCfg,
        timeout_seconds: Optional[int] = 60,
        watch: bool = False,
    ):
        """Start an environment."""
        if timeout_seconds is not None and timeout_seconds < 0:
            Util.print_error_and_die(
                "Timeout must be greater than or equal to 0."
            )
        env = self.get_environment_from_cfg(envCfg)
        self.wait_for_env_up(
            env,
            timeout_seconds=timeout_seconds,
            start_action=lambda: env.start(timeout_seconds=timeout_seconds),
            watch_after=watch,
        )
        Util.print(f"Started environment: {env.envCfg.tag}")

    def stop_env(self, envCfg: EnvironmentCfg):
        """Halt an environment."""
        env = self.get_environment_from_cfg(envCfg)
        self.wait_for_env_down(env, stop_action=env.stop)
        env.envCfg.status.rendered_config = None
        env.sync_config()
        Util.print(f"Halted environment: {env.envCfg.tag}")

    def reload_env(self, envCfg: EnvironmentCfg, watch: bool = False):
        """Reload an environment."""
        env = self.get_environment_from_cfg(envCfg)
        if not env.envCfg.status.rendered_config:
            Util.print_error_and_die(
                f"Environment '{env.envCfg.tag}' is not started."
            )

        env.reload()
        if watch:
            self.wait_for_env_up(
                env,
                timeout_seconds=None,
                start_action=None,
                watch_after=True,
            )
        Util.print(f"Reloaded environment: {env.envCfg.tag}")

    def render_env(
        self, env_tag: str, target: bool, resolved: bool, grouped: bool = False
    ) -> Optional[str]:
        """Render an environment configuration."""
        env = self.get_environment_from_tag(env_tag)
        if env:
            if target:
                if grouped:
                    return env.render_target_grouped(resolved)
                return env.render_target_merged(resolved)
            return env.render(resolved)
        return None

    def render_probes(
        self,
        envCfg: EnvironmentCfg,
        probe_tag: Optional[str],
        target: bool,
        resolved: bool,
    ) -> Optional[str]:
        """Render a probe configuration."""
        env = self.get_environment_from_cfg(envCfg)
        if target:
            return env.render_probes_target(probe_tag, resolved)
        return env.render_probes(probe_tag, resolved)

    def check_probes(self, envCfg: EnvironmentCfg, probe_tag: Optional[str]):
        """Check probes."""
        env = self.get_environment_from_cfg(envCfg)

        if not env.envCfg.status.rendered_config:
            Util.print_error_and_die(
                f"Environment '{env.envCfg.tag}' is not started."
            )

        results = env.check_probes(
            probe_tag=probe_tag,
            fail_fast=True,
            timeout_seconds=120,
        )

        verbose = bool(self.cli_flags.get("verbose", False))
        title = f"[white]{envCfg.tag}[/white] probes"

        report = self.build_probe_report(results, verbose=verbose, title=title)
        self.render_probe_report(report)

        # ---- aggregate exit code ----
        for r in results:
            if r.exit_code != 0:
                return r.exit_code

        return 0

    # --- probe presentation policy ---

    def build_probe_report(
        self,
        results: list[ProbeRunResult],
        *,
        verbose: bool,
        title: str,
    ) -> dict[str, Any]:
        return build_probe_report(results, verbose=verbose, title=title)

    def render_probe_report(self, report: dict[str, Any]):
        render_probe_report(report)

    def status_env(self, envCfg: EnvironmentCfg, watch: bool = False):
        """Get environment status."""
        env = self.get_environment_from_cfg(envCfg)
        if watch:
            self.wait_for_env_up(
                env,
                timeout_seconds=None,
                start_action=None,
                watch_after=True,
            )
            return
        grouped, _, _, has_containers = self._collect_env_status(env)
        if not has_containers or not grouped:
            Util.console.print(
                f"[yellow]No services found for "
                f"environment '{envCfg.tag}'[/yellow]"
            )
            return
        Util.console.print(
            self._build_env_status_table(
                envCfg.tag,
                grouped,
                hidden_columns={"Gates"},
            )
        )

    def wait_for_env_up(
        self,
        env: Environment,
        timeout_seconds: Optional[int] = None,
        start_action: Optional[Callable[[], Any]] = None,
        watch_after: bool = False,
    ):
        self._wait_for_env_state(
            env,
            timeout_seconds=timeout_seconds,
            action=start_action,
            wait_until_up=True,
            watch_after=watch_after,
        )

    def wait_for_env_down(
        self,
        env: Environment,
        timeout_seconds: Optional[int] = None,
        stop_action: Optional[Callable[[], Any]] = None,
        watch_after: bool = False,
    ):
        self._wait_for_env_state(
            env,
            timeout_seconds=timeout_seconds,
            action=stop_action,
            wait_until_up=False,
            watch_after=watch_after,
        )

    def _wait_for_env_state(
        self,
        env: Environment,
        timeout_seconds: Optional[int],
        action: Optional[Callable[[], Any]],
        wait_until_up: bool,
        watch_after: bool = False,
    ):
        wait_for_env_state(
            env,
            timeout_seconds=timeout_seconds,
            action=action,
            wait_until_up=wait_until_up,
            watch_after=watch_after,
            status_poll_seconds=self._status_poll_seconds,
            is_quiet=self._is_quiet,
            get_required_gate_tags=self._get_required_gate_tags,
            evaluate_gate_status=self._evaluate_gate_status,
            collect_env_status=self._collect_env_status,
            build_env_status_table=self._build_env_status_table,
            remaining_timeout_seconds=self._remaining_timeout_seconds,
        )

    def _build_env_status_table(
        self,
        env_tag: str,
        grouped: dict[str, list[list[str]]],
        remaining_seconds: Optional[int] = None,
        command_log: Optional[list[str]] = None,
        command_log_limit: Optional[int] = None,
        command_error: Optional[dict[str, str]] = None,
        command_error_limit: Optional[int] = None,
        hidden_columns: Optional[set[str]] = None,
    ):
        return build_env_status_table(
            env_tag,
            grouped,
            details_enabled=self._is_details(),
            remaining_seconds=remaining_seconds,
            command_log=command_log,
            command_log_limit=command_log_limit,
            command_error=command_error,
            command_error_limit=command_error_limit,
            hidden_columns=hidden_columns,
        )

    def _build_command_log_panel(
        self, command_log: list[str], command_log_limit: int
    ):
        return build_command_log_panel(command_log, command_log_limit)

    def _build_command_error_panel(
        self,
        command_error: dict[str, str],
        command_error_limit: Optional[int],
    ):
        return build_command_error_panel(command_error, command_error_limit)

    def _remaining_timeout_seconds(
        self, started_at: float, timeout_seconds: Optional[int]
    ) -> Optional[int]:
        if timeout_seconds is None:
            return None
        elapsed = int(time.monotonic() - started_at)
        remaining = timeout_seconds - elapsed
        return remaining if remaining > 0 else 0

    def _collect_env_status(
        self,
        env: Environment,
        gate_status: Optional[dict[str, Optional[bool]]] = None,
    ) -> tuple[dict[str, list[list[str]]], bool, bool, bool]:
        return collect_env_status(
            env,
            details_enabled=self._is_details(),
            gate_status=gate_status,
        )

    def _format_service_gate_glyphs(
        self,
        svc: Service,
        gate_status: Optional[dict[str, Optional[bool]]] = None,
    ) -> str:
        return format_service_gate_glyphs(svc, gate_status=gate_status)

    def _format_service_gate_details(
        self,
        svc: Service,
        gate_status: Optional[dict[str, Optional[bool]]] = None,
    ) -> str:
        return format_service_gate_details(svc, gate_status=gate_status)

    def _get_required_gate_tags(self, env: Environment) -> set[str]:
        required: set[str] = set()
        for svc in env.get_services():
            when_probes = (
                svc.svcCfg.start.when_probes
                if svc.svcCfg.start and svc.svcCfg.start.when_probes
                else None
            )
            if when_probes:
                required.update(when_probes)
        return required

    def _evaluate_gate_status(
        self,
        env: Environment,
        required_gate_tags: set[str],
    ) -> dict[str, Optional[bool]]:
        status: dict[str, Optional[bool]] = {
            tag: None for tag in required_gate_tags
        }
        if not required_gate_tags:
            return status
        try:
            results = env.check_probes(
                probe_tag=None,
                fail_fast=False,
                timeout_seconds=10,
            )
        except Exception as e:
            logging.debug(
                "Gate evaluation failed for env '%s': %s", env.envCfg.tag, e
            )
            return status

        for r in results:
            if r.tag in status:
                status[r.tag] = (r.exit_code == 0) and not r.timed_out
        return status

    def add_service(
        self,
        env_tag: Optional[str],
        svc_tag: str,
        svc_template: Optional[str],
        svc_class: Optional[str],
    ):
        """Add a service to an environment."""
        env = self.get_environment_from_tag(env_tag)

        if env:
            envCfg = env.to_config()
            if env.get_service(svc_tag):
                Util.print_error_and_die(
                    f"Service: '{svc_tag}' already "
                    f"defined in environment: '{envCfg.tag}'."
                )
            svc_type_cfg = self.configMng.get_service_template(
                svc_template if svc_template else Constants.SVC_TEMPLATE_DEFAULT
            )

            if svc_type_cfg:
                svcCfg = self.configMng.svc_cfg_from_service_template(
                    svc_type_cfg, svc_tag, svc_class
                )
            else:
                svcCfg = self.configMng.svc_cfg_from_tag(
                    (
                        svc_template
                        if svc_template
                        else Constants.SVC_TEMPLATE_DEFAULT
                    ),
                    svc_tag,
                    svc_class,
                )

            try:
                service = self.svcFactory.new_service_from_cfg(
                    envCfg, svcCfg, cli_flags=self.cli_flags
                )
                env.add_service(service)
                Util.print(
                    f"Service '{service.svcCfg.tag}' added to "
                    f"environment '{env.envCfg.tag}'."
                )
            except ValueError as e:
                Util.print_error_and_die(f"Failed to create service: {e}")
