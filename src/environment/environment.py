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

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from config import ConfigMng, EnvironmentCfg, EnvironmentTemplateCfg
from service import Service, ServiceFactory
from util import Constants, Util


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
    ):
        self.configMng = configMng
        self.svcFactory = svcFactory
        self.envCfg = envCfg
        self.services = (
            [
                self.svcFactory.new_service_from_cfg(envCfg, svcCfg)
                for svcCfg in envCfg.services
            ]
            if envCfg.services
            else []
        )

    @abstractmethod
    def clone(self, dst_env_tag: str) -> Environment:
        """Clone the environment."""
        pass

    def start(self):
        """Start the environment."""
        self.ensure_resources()

    @abstractmethod
    def stop(self):
        """Halt the environment."""
        pass

    @abstractmethod
    def reload(self):
        """Reload the environment."""
        pass

    def render(self, resolved: bool) -> str:
        """Render the environment configuration."""
        return self.envCfg.get_yaml(resolved)

    @abstractmethod
    def render_target(self, resolved: bool) -> dict[str, str]:
        """
        Render the environment configuration in the target system.
        """
        pass

    def render_probes(
        self, probe_tag: Optional[str], resolved: bool
    ) -> Optional[str]:
        """
        Render the environment probes configuration.
        """
        return self.envCfg.get_probes_yaml(probe_tag, resolved)

    @abstractmethod
    def render_probes_target(
        self, probe_tag: Optional[str], resolved: bool
    ) -> Optional[str]:
        """
        Render the environment probes configuration in the target system.
        """
        pass

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

    @abstractmethod
    def status(self) -> list[dict[str, str]]:
        """Get environment status."""
        pass

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

    @abstractmethod
    def ensure_resources(self):
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

    def __init__(self, config: ConfigMng):
        self.config = config

    @abstractmethod
    def new_environment(
        self,
        env_tmpl_cfg: EnvironmentTemplateCfg,
        env_tag: str,
    ) -> Environment:
        """
        Create an environment.
        """
        pass

    @abstractmethod
    def new_environment_cfg(self, envCfg: EnvironmentCfg) -> Environment:
        """
        Create an environment.
        """
        pass


class EnvironmentMng:

    def __init__(
        self,
        cli_flags: dict[str, bool],
        configMng: ConfigMng,
        envFactory: EnvironmentFactory,
        svcFactory: ServiceFactory,
    ):
        self.cli_flags = cli_flags
        self.configMng = configMng
        self.envFactory = envFactory
        self.svcFactory = svcFactory

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

    def start_env(self, envCfg: EnvironmentCfg):
        """Start an environment."""
        env = self.get_environment_from_cfg(envCfg)
        env.envCfg.status.rendered_config = env.render_target(True)
        env.sync_config()
        env.start()
        Util.print(f"Started environment: {env.envCfg.tag}")

    def stop_env(self, envCfg: EnvironmentCfg):
        """Halt an environment."""
        env = self.get_environment_from_cfg(envCfg)
        env.stop()
        env.envCfg.status.rendered_config = None
        env.sync_config()
        Util.print(f"Halted environment: {env.envCfg.tag}")

    def reload_env(self, envCfg: EnvironmentCfg):
        """Reload an environment."""
        env = self.get_environment_from_cfg(envCfg)
        if not env.envCfg.status.rendered_config:
            Util.print_error_and_die(
                f"Environment '{env.envCfg.tag}' is not started."
            )

        env.reload()
        Util.print(f"Reloaded environment: {env.envCfg.tag}")

    def render_env(
        self, env_tag: str, target: bool, resolved: bool
    ) -> Optional[str]:
        """Render an environment configuration."""
        env = self.get_environment_from_tag(env_tag)
        if env:
            if target:
                return env.render_target(resolved)["ungated"]
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

        return results

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

    def probe_exit_code(self, results: list[ProbeRunResult]) -> int:
        saw_failed = False
        for r in results:
            k = self._probe_status_key(r)
            if k == "timeout":
                return 2
            if k == "failed":
                saw_failed = True
        return 1 if saw_failed else 0

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
        env_status = env.status()

        services: list[Service] = env.get_services()
        status_by_service = {
            row.get("Service"): row for row in env_status if row.get("Service")
        }

        grouped: dict[str, list[list[str]]] = {}

        for svc in services:
            rows: list[list[str]] = []
            for container in svc.svcCfg.containers or []:
                cnt_name = container.run_container_name or ""
                cnt_info = status_by_service.get(cnt_name)
                state = (
                    cnt_info.get("State", "?").lower()
                    if cnt_info
                    else "stopped"
                )

                if state == "running":
                    state_colored = "[bold green]● running[/bold green]"
                elif state == "stopped":
                    state_colored = "[bold red]● stopped[/bold red]"
                else:
                    state_colored = f"[yellow]● {state}[/yellow]"

                rows.append([container.tag, state_colored])

            if rows:
                grouped[svc.svcCfg.tag] = rows

        if not grouped:
            Util.console.print(
                f"[yellow]No services found for "
                f"environment '{envCfg.tag}'[/yellow]"
            )
            return

        Util.render_grouped_table(
            title=f"[white]{envCfg.tag}[/white]",
            group_column_header="Service",
            item_columns=[
                {"header": "Container", "style": "white"},
                {"header": "State"},
            ],
            groups=grouped,
        )

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
                service = self.svcFactory.new_service_from_cfg(envCfg, svcCfg)
                env.add_service(service)
                Util.print(
                    f"Service '{service.svcCfg.tag}' added to "
                    f"environment '{env.envCfg.tag}'."
                )
            except ValueError as e:
                Util.print_error_and_die(f"Failed to create service: {e}")
