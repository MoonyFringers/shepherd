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
from typing import Any, Callable, Optional, cast

import yaml
from rich import box
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from config import ConfigMng, EnvironmentCfg, EnvironmentTemplateCfg
from service import Service, ServiceFactory
from util import Constants, Util
from util.constants import DEFAULT_COMPOSE_COMMAND_LOG_LIMIT


@dataclass
class ProbeRunResult:
    tag: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: Optional[int] = None
    timed_out: bool = False


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
            self.cli_flags.get("log_limit", DEFAULT_COMPOSE_COMMAND_LOG_LIMIT)
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
        self.envCfg.status.rendered_config = self.render_target(True)
        self.sync_config()
        self.ensure_resources()

        rendered_config = self.envCfg.status.rendered_config or {}
        pending_gate_keys = set(rendered_config.keys())
        started_gate_keys: set[str] = set()

        started_now = self.start_impl(
            started_gate_keys=started_gate_keys,
            probe_results=None,
        )
        started_gate_keys.update(started_now)
        pending_gate_keys -= started_now

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
            if not started_now:
                if timeout_seconds is not None:
                    elapsed = int(time.monotonic() - started_at)
                    if elapsed >= timeout_seconds:
                        break
                time.sleep(1.0)
                continue

            started_gate_keys.update(started_now)
            pending_gate_keys -= started_now

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
        return bool(self.cli_flags.get("logs", False)) and (
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
        return _dump_grouped_yaml(rendered)

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

    def _probe_status_key(self, r: ProbeRunResult) -> str:
        if r.timed_out:
            return "timeout"
        if r.exit_code == 0:
            return "ok"
        return "failed"

    def _probe_status_glyph(self, key: str) -> str:
        return "✔" if key == "ok" else "✖"

    def _probe_status_color_tag(self, key: str) -> str:
        if key == "ok":
            return "bold green"
        if key == "timeout":
            return "bold yellow"
        return "bold red"

    def _fmt_duration_ms(self, ms: Optional[int]) -> str:
        return "?" if ms is None else f"{ms} ms"

    def build_probe_report(
        self,
        results: list[ProbeRunResult],
        *,
        verbose: bool,
        title: str,
    ) -> dict[str, Any]:
        """
        Returns a probe 'view model' as plain dicts:
          {
            "title": str,
            "rows": [[probe, status_markup, duration], ...],
            "summary": [("OK","1"), ("FAILED","0"), ("TIMEOUT","0")],
            "single_ok_stdout": "first line …" | "",
            "panels": [{"title":..., "body":..., "border_style":...}, ...]
          }
        """
        rows: list[list[str]] = []
        panels: list[dict[str, Any]] = []

        ok = failed = timeout = 0

        for r in results:
            key = self._probe_status_key(r)
            if key == "ok":
                ok += 1
            elif key == "timeout":
                timeout += 1
            else:
                failed += 1

            glyph = self._probe_status_glyph(key)
            label = key.upper()
            color = self._probe_status_color_tag(key)
            status_markup = f"[{color}]{glyph} {label}[/{color}]"

            rows.append(
                [r.tag, status_markup, self._fmt_duration_ms(r.duration_ms)]
            )

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

    def render_probe_report(self, report: dict[str, Any]):
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

    def status_env(self, envCfg: EnvironmentCfg):
        """Get environment status."""
        env = self.get_environment_from_cfg(envCfg)
        grouped, _, _, has_containers = self._collect_env_status(env)
        if not has_containers or not grouped:
            Util.console.print(
                f"[yellow]No services found for "
                f"environment '{envCfg.tag}'[/yellow]"
            )
            return
        Util.console.print(self._build_env_status_table(envCfg.tag, grouped))

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
        phase = "up" if wait_until_up else "down"
        phase_gerund = "starting" if wait_until_up else "stopping"
        timeout_target = "up" if wait_until_up else "down"

        if self._is_quiet():
            if action:
                action()
            return

        action_error: Optional[BaseException] = None
        action_done = threading.Event()

        if action:

            def run_action():
                nonlocal action_error
                try:
                    action()
                except BaseException as e:
                    action_error = e
                finally:
                    action_done.set()

            threading.Thread(target=run_action, daemon=True).start()
        else:
            action_done.set()

        def raise_action_error():
            if action_error is not None:
                raise action_error

        def in_action() -> bool:
            return not action_done.is_set()

        def condition_met(all_running: bool, any_running: bool) -> bool:
            if wait_until_up:
                return all_running and not in_action()
            return (not any_running) and not in_action()

        required_gate_tags = self._get_required_gate_tags(env)
        gate_status: dict[str, Optional[bool]] = {
            tag: None for tag in required_gate_tags
        }
        next_gate_eval_at = time.monotonic() + max(
            1.0, self._status_poll_seconds * 2
        )

        def get_gate_status() -> Optional[dict[str, Optional[bool]]]:
            nonlocal gate_status, next_gate_eval_at
            if not wait_until_up or not required_gate_tags:
                return None
            now = time.monotonic()
            if now < next_gate_eval_at:
                return gate_status
            gate_status = self._evaluate_gate_status(env, required_gate_tags)
            # Avoid running probes on every visual refresh tick.
            next_gate_eval_at = now + max(1.0, self._status_poll_seconds * 2)
            return gate_status

        started = time.monotonic()
        logging.debug(
            "wait_for_env_%s started for env='%s' (timeout=%s, terminal=%s)",
            phase,
            env.envCfg.tag,
            timeout_seconds,
            Util.console.is_terminal,
        )
        if not Util.console.is_terminal:
            while in_action():
                raise_action_error()
                remaining = self._remaining_timeout_seconds(
                    started, timeout_seconds
                )
                if timeout_seconds is not None and remaining is not None:
                    if remaining <= 0:
                        Util.print_error_and_die(
                            "Timed out waiting for environment "
                            f"'{env.envCfg.tag}' to be {timeout_target}."
                        )
                time.sleep(self._status_poll_seconds)

            raise_action_error()
            current_gate_status = get_gate_status()
            grouped, all_running, any_running, has_containers = (
                self._collect_env_status(
                    env,
                    gate_status=current_gate_status,
                )
            )
            remaining = self._remaining_timeout_seconds(
                started, timeout_seconds
            )
            logging.debug(
                "wait_for_env_%s non-terminal snapshot env='%s': "
                "groups=%d has_containers=%s all_running=%s any_running=%s "
                "remaining=%s",
                phase,
                env.envCfg.tag,
                len(grouped),
                has_containers,
                all_running,
                any_running,
                remaining,
            )
            if not has_containers or not grouped:
                Util.console.print(
                    f"[yellow]No services found for "
                    f"environment '{env.envCfg.tag}'[/yellow]"
                )
                return
            Util.console.print(
                self._build_env_status_table(
                    env.envCfg.tag,
                    grouped,
                    remaining_seconds=remaining,
                    command_log=(
                        env.get_command_log()
                        if env.is_command_log_enabled()
                        else None
                    ),
                    command_log_limit=(
                        env.get_command_log_limit()
                        if env.is_command_log_enabled()
                        else None
                    ),
                    command_error=env.get_command_error(),
                    command_error_limit=(
                        env.get_command_log_limit()
                        if env.is_command_log_enabled()
                        else None
                    ),
                )
            )
            return

        live_refresh_per_second = max(
            4, int(1 / max(self._status_poll_seconds, 0.001))
        )
        with Live(
            refresh_per_second=live_refresh_per_second,
            console=Util.console,
            transient=True,
            screen=False,
        ) as live:
            completed = False
            while True:
                raise_action_error()
                current_gate_status = get_gate_status()
                grouped, all_running, any_running, has_containers = (
                    self._collect_env_status(
                        env,
                        gate_status=current_gate_status,
                    )
                )
                remaining = self._remaining_timeout_seconds(
                    started, timeout_seconds
                )
                logging.debug(
                    "wait_for_env_%s poll env='%s': groups=%d "
                    "has_containers=%s all_running=%s any_running=%s "
                    "in_action=%s remaining=%s",
                    phase,
                    env.envCfg.tag,
                    len(grouped),
                    has_containers,
                    all_running,
                    any_running,
                    in_action(),
                    remaining,
                )

                if not has_containers or not grouped:
                    if in_action():
                        title = f"[white]{env.envCfg.tag}[/white]"
                        if remaining is not None:
                            title = (
                                f"{title} "
                                f"[dim](Time left: {remaining}s)[/dim]"
                            )
                        live.update(f"{title} [dim]({phase_gerund}...)[/dim]")
                    else:
                        live.stop()
                        Util.console.print(
                            f"[yellow]No services found for "
                            f"environment '{env.envCfg.tag}'[/yellow]"
                        )
                        return
                else:
                    live.update(
                        self._build_env_status_table(
                            env.envCfg.tag,
                            grouped,
                            remaining_seconds=remaining,
                            command_log=(
                                env.get_command_log()
                                if env.is_command_log_enabled()
                                else None
                            ),
                            command_log_limit=(
                                env.get_command_log_limit()
                                if env.is_command_log_enabled()
                                else None
                            ),
                            command_error=env.get_command_error(),
                            command_error_limit=(
                                env.get_command_log_limit()
                                if env.is_command_log_enabled()
                                else None
                            ),
                        )
                    )

                if condition_met(all_running, any_running):
                    logging.debug(
                        "wait_for_env_%s complete env='%s'",
                        phase,
                        env.envCfg.tag,
                    )
                    if not watch_after:
                        return
                    completed = True

                if (
                    not completed
                    and timeout_seconds is not None
                    and remaining is not None
                ):
                    if remaining <= 0:
                        live.stop()
                        Util.print_error_and_die(
                            "Timed out waiting for environment "
                            f"'{env.envCfg.tag}' to be {timeout_target}."
                        )
                time.sleep(self._status_poll_seconds)

    def _build_env_status_table(
        self,
        env_tag: str,
        grouped: dict[str, list[list[str]]],
        remaining_seconds: Optional[int] = None,
        command_log: Optional[list[str]] = None,
        command_log_limit: Optional[int] = None,
        command_error: Optional[dict[str, str]] = None,
        command_error_limit: Optional[int] = None,
    ):
        title = f"[white]{env_tag}[/white]"
        if remaining_seconds is not None:
            title = f"{title} " f"[dim](Time left: {remaining_seconds}s)[/dim]"
        table = Table(
            title=title,
            box=box.SIMPLE,
            title_justify="left",
            title_style="bold",
        )
        table.add_column("Gates", style="cyan", no_wrap=True)
        table.add_column("Service", style="cyan", no_wrap=True)
        table.add_column("Container", style="white", no_wrap=True)
        table.add_column("State", no_wrap=True)
        if self._is_details():
            table.add_column("Probes", style="white")

        for service, items in grouped.items():
            for idx, item in enumerate(items):
                gate_details = ""
                if self._is_details():
                    gates, container, state, gate_details = item
                else:
                    gates, container, state = item
                is_last = idx == len(items) - 1
                branch = "└─" if is_last else "├─"
                row: list[str] = [
                    gates if idx == 0 else "",
                    f"[bold]{service}[/bold]" if idx == 0 else "",
                    f"{branch} {container}",
                    state,
                ]
                if self._is_details():
                    row.append(gate_details if idx == 0 else "")
                table.add_row(*row)

        panels: list[Any] = [table]
        if command_log is not None and command_log_limit is not None:
            panels.append(
                self._build_command_log_panel(command_log, command_log_limit)
            )
        if command_error:
            panels.append(
                self._build_command_error_panel(
                    command_error, command_error_limit
                )
            )
        if len(panels) == 1:
            return table
        return Group(*panels)

    def _build_command_log_panel(
        self, command_log: list[str], command_log_limit: int
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

    def _build_command_error_panel(
        self,
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
        env_status = env.status()
        services: list[Service] = env.get_services()
        status_by_service = {
            row.get("Service"): row for row in env_status if row.get("Service")
        }

        grouped: dict[str, list[list[str]]] = {}
        all_running = True
        any_running = False
        has_containers = False

        for svc in services:
            rows: list[list[str]] = []
            service_gates = self._format_service_gate_glyphs(
                svc,
                gate_status=gate_status,
            )
            service_gate_details = self._format_service_gate_details(
                svc,
                gate_status=gate_status,
            )
            for idx, container in enumerate(svc.svcCfg.containers or []):
                has_containers = True
                cnt_name = container.run_container_name or ""
                cnt_info = status_by_service.get(cnt_name)
                state = (
                    cnt_info.get("State", "?").lower()
                    if cnt_info
                    else "stopped"
                )

                if state == "running":
                    any_running = True
                    state_colored = "[bold green]● running[/bold green]"
                elif state == "stopped":
                    state_colored = "[bold red]● stopped[/bold red]"
                else:
                    state_colored = f"[yellow]● {state}[/yellow]"

                if state != "running":
                    all_running = False

                gates_cell = service_gates if idx == 0 else ""
                row = [gates_cell, container.tag, state_colored]
                if self._is_details():
                    row.append(service_gate_details if idx == 0 else "")
                rows.append(row)

            if rows:
                grouped[svc.svcCfg.tag] = rows

        if not has_containers:
            all_running = False

        return grouped, all_running, any_running, has_containers

    def _format_service_gate_glyphs(
        self,
        svc: Service,
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

    def _format_service_gate_details(
        self,
        svc: Service,
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


def _dump_grouped_yaml(data: dict[str, str]) -> str:
    return yaml.dump(data, Dumper=_LiteralDumper, sort_keys=False)
