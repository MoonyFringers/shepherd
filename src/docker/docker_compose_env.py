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

import json
import logging
import time
from typing import Any, Optional, cast, override

import yaml

from config import ConfigMng, EnvironmentCfg
from config.config import ProbeCfg
from environment import Environment
from environment.environment import ProbeRunResult
from service import ServiceFactory
from util.util import Util

from .docker_compose_util import render_container, run_compose


class DockerComposeEnv(Environment):
    _command_category_width = 16

    def __init__(
        self,
        config: ConfigMng,
        svcFactory: ServiceFactory,
        envCfg: EnvironmentCfg,
        cli_flags: Optional[dict[str, Any]] = None,
    ):
        """Initialize a Docker Compose environment."""
        super().__init__(config, svcFactory, envCfg, cli_flags=cli_flags)

    @override
    def ensure_resources_impl(self):
        """Ensure the environment resources are available."""
        if self.envCfg.volumes:
            for vol in self.envCfg.volumes:
                # Check if it's a host bind mount,
                # in case create the host path
                if (
                    vol.driver == "local"
                    and vol.driver_opts
                    and vol.driver_opts.get("type") == "none"
                    and vol.driver_opts.get("o") == "bind"
                ):
                    device_path = vol.driver_opts.get("device")
                    if device_path:
                        Util.ensure_dir(device_path, vol.tag)

    @override
    def clone_impl(self, dst_env_tag: str) -> DockerComposeEnv:
        """Clone the environment."""
        clonedCfg = self.configMng.env_cfg_from_other(self.to_config())
        clonedCfg.tag = dst_env_tag
        clonedEnv = DockerComposeEnv(
            self.configMng,
            self.svcFactory,
            clonedCfg,
            cli_flags=self.cli_flags,
        )
        return clonedEnv

    @override
    def start_impl(
        self,
        started_gate_keys: set[str],
        probe_results: Optional[list[ProbeRunResult]] = None,
    ) -> set[str]:
        """Start the environment according to probe-gate availability."""
        rendered_map = self.envCfg.status.rendered_config or {}
        if not rendered_map:
            return set()

        probe_status: dict[str, bool] = {"base": True}
        if probe_results:
            for result in probe_results:
                probe_status[result.tag] = (
                    result.exit_code == 0
                ) and not result.timed_out

        started_now: set[str] = set()
        for gate_key, _ in rendered_map.items():
            if gate_key in started_gate_keys:
                continue

            if gate_key != "ungated":
                required_tags = [tag for tag in gate_key.split("|") if tag]
                if not required_tags:
                    continue
                if not all(
                    probe_status.get(tag, False) for tag in required_tags
                ):
                    continue

            compose_stack = [
                rendered_map[k]
                for k in rendered_map.keys()
                if k in started_gate_keys or k == gate_key
            ]
            self._run_compose(
                compose_stack,
                "up",
                "-d",
                capture=not self._is_verbose(),
                category=f"start:{gate_key}",
            )
            started_now.add(gate_key)

        return started_now

    @override
    def stop_impl(self):
        """Halt the environment."""
        rendered_map = self.envCfg.status.rendered_config
        if rendered_map:
            self._run_compose(
                list(rendered_map.values()),
                "down",
                capture=not self._is_verbose(),
                category="stop",
            )

    @override
    def reload_impl(self):
        """Reload the environment."""
        rendered_map = self.envCfg.status.rendered_config
        if rendered_map:
            self._run_compose(
                list(rendered_map.values()),
                "restart",
                capture=not self._is_verbose(),
                category="reload",
            )

    @override
    def render_target_impl(self, resolved: bool = False) -> dict[str, str]:
        """
        Render the full docker-compose YAML configuration for the environment.

        Args:
            resolved: If True, ensure placeholders in envCfg and child services
                      are resolved before rendering.
        """
        was_resolved = self.envCfg.is_resolved()
        changed_state = False

        try:
            if resolved and not was_resolved:
                self.envCfg.set_resolved()
                changed_state = True
            elif not resolved and was_resolved:
                self.envCfg.set_unresolved()
                changed_state = True

            ungated_compose_config: dict[str, Any] = {
                "name": self.envCfg.tag,
                "services": {},
                "networks": {},
                "volumes": {},
            }

            gated_compose_config: dict[str, Any] = {
                "ungated": ungated_compose_config,
            }

            # --- Networks ---
            if self.envCfg.networks:
                for net in self.envCfg.networks:
                    net_config = {}

                    if net.is_external():
                        if net.name:
                            net_config["name"] = net.name
                        net_config["external"] = True
                    else:
                        if net.driver:
                            net_config["driver"] = net.driver
                        if net.attachable is not None:
                            net_config["attachable"] = net.is_attachable()
                        if net.enable_ipv6 is not None:
                            net_config["enable_ipv6"] = net.is_enable_ipv6()
                        if net.driver_opts:
                            net_config["driver_opts"] = net.driver_opts
                        if net.ipam:
                            net_config["ipam"] = net.ipam

                    ungated_compose_config["networks"][net.tag] = net_config

            # --- Volumes ---
            if self.envCfg.volumes:
                for vol in self.envCfg.volumes:
                    vol_config = {}

                    if vol.is_external():
                        if vol.name:
                            vol_config["name"] = vol.name
                        vol_config["external"] = True
                    else:
                        if vol.driver:
                            vol_config["driver"] = vol.driver
                        if vol.driver_opts:
                            vol_config["driver_opts"] = vol.driver_opts
                        if vol.labels:
                            vol_config["labels"] = vol.labels

                    ungated_compose_config["volumes"][vol.tag] = vol_config

            # --- Services ---
            for svc in self.services:
                when_probes = (
                    svc.svcCfg.start.when_probes
                    if svc.svcCfg.start and svc.svcCfg.start.when_probes
                    else None
                )

                probe_key = "|".join(when_probes) if when_probes else "ungated"

                if probe_key not in gated_compose_config:
                    gated_compose_config[probe_key] = {
                        "name": self.envCfg.tag,
                        "services": {},
                    }
                compose_config = gated_compose_config[probe_key]

                svc_yaml = yaml.safe_load(
                    svc.render_target_impl(resolved=resolved)
                )
                compose_config["services"].update(svc_yaml["services"])

            # --- Render YAML ---
            rendered_gated_map: dict[str, str] = {}
            for probe_key, compose_config in gated_compose_config.items():
                rendered_yaml = yaml.dump(compose_config, sort_keys=False)
                rendered_gated_map[probe_key] = rendered_yaml

            return rendered_gated_map
        finally:
            if changed_state:
                if was_resolved:
                    self.envCfg.set_resolved()
                else:
                    self.envCfg.set_unresolved()

    @override
    def render_target_merged(self, resolved: bool = False) -> str:
        rendered = self.render_target(resolved)
        base_yaml = rendered.get("ungated")
        if not base_yaml:
            return ""

        base_cfg = cast(dict[str, Any], yaml.safe_load(base_yaml) or {})
        base_services = cast(
            dict[str, Any], base_cfg.setdefault("services", {})
        )
        base_networks = cast(
            dict[str, Any], base_cfg.setdefault("networks", {})
        )
        base_volumes = cast(dict[str, Any], base_cfg.setdefault("volumes", {}))

        for gate_key, gate_yaml in rendered.items():
            if gate_key == "ungated":
                continue
            gate_cfg = cast(dict[str, Any], yaml.safe_load(gate_yaml) or {})
            base_services.update(gate_cfg.get("services") or {})
            base_networks.update(gate_cfg.get("networks") or {})
            base_volumes.update(gate_cfg.get("volumes") or {})

        return yaml.dump(base_cfg, sort_keys=False)

    def render_probe_service(
        self, probe: ProbeCfg, labels: Optional[list[str]] = None
    ) -> Optional[dict[str, Any]]:
        """
        Render a probe as a docker-compose service definition.
        """
        if not probe.container:
            return None

        svc = render_container(probe.container, labels)

        if probe.script:
            svc["command"] = probe.script

        svc.setdefault("restart", "no")

        return svc

    @override
    def render_probes_target_impl(
        self, probe_tag: Optional[str], resolved: bool
    ) -> Optional[str]:
        was_resolved = self.envCfg.is_resolved()
        changed_state = False

        if not self.envCfg.probes:
            return None

        try:
            if resolved and not was_resolved:
                self.envCfg.set_resolved()
                changed_state = True
            elif not resolved and was_resolved:
                self.envCfg.set_unresolved()
                changed_state = True

            compose_config: dict[str, Any] = {
                "name": self.envCfg.tag,
                "services": {},
            }
            services_def: dict[str, Any] = compose_config["services"]

            probes = self.envCfg.probes
            if probe_tag is not None:
                probes = [p for p in probes if p.tag == probe_tag]
                if not probes:
                    return None

            for probe in probes:
                svc = self.render_probe_service(probe, labels=None)
                if svc:
                    services_def[probe.tag] = svc

            if not services_def:
                return None

            return yaml.dump(compose_config, sort_keys=False)

        finally:
            if changed_state:
                if was_resolved:
                    self.envCfg.set_resolved()
                else:
                    self.envCfg.set_unresolved()

    @override
    def check_probes_impl(
        self,
        probe_tag: Optional[str],
        fail_fast: bool,
        timeout_seconds: Optional[int],
    ) -> list[ProbeRunResult]:
        """Check probes in the environment."""
        base_yaml = (
            self.envCfg.status.rendered_config["ungated"]
            if self.envCfg.status.rendered_config
            else None
        )
        if not base_yaml:
            return []

        if not self.envCfg.probes:
            return []

        probes = self.envCfg.probes
        if probe_tag is not None:
            probes = [p for p in probes if p.tag == probe_tag]
        if not probes:
            if probe_tag is not None:
                available = self.configMng.get_probe_tags(self.envCfg)
                if available:
                    tags = ", ".join(available)
                    Util.print_error_and_die(
                        f"Probe '{probe_tag}' not found in environment "
                        f"'{self.envCfg.tag}'. Available probes: {tags}."
                    )
                Util.print_error_and_die(
                    f"Probe '{probe_tag}' not found in environment "
                    f"'{self.envCfg.tag}'."
                )
            return []

        probes_yaml = self.render_probes_target(probe_tag=None, resolved=True)
        if not probes_yaml:
            return []

        results: list[ProbeRunResult] = []

        for p in probes:
            probe_service = p.tag

            started = time.time()
            timed_out = False

            # Execute probe container and capture its exit code/output
            # --no-deps: do not start dependencies
            # --rm: remove container after it exits
            cp = self._run_compose(
                [base_yaml, probes_yaml],
                "run",
                "--rm",
                "--no-deps",
                probe_service,
                capture=True,
                timeout_seconds=timeout_seconds,
                category=f"probe:{probe_service}",
            )

            duration_ms = int((time.time() - started) * 1000)

            # Timeout normalization
            if cp.returncode == 124:
                timed_out = True

            res = ProbeRunResult(
                tag=p.tag,
                exit_code=cp.returncode,
                stdout=cp.stdout or "",
                stderr=cp.stderr or "",
                duration_ms=duration_ms,
                timed_out=timed_out,
            )
            results.append(res)

            ok = (cp.returncode == 0) and not timed_out
            if fail_fast and not ok:
                break

        return results

    def status_impl(self) -> list[dict[str, str]]:
        """Get environment status (list of services with state)."""

        rendered_map = self.envCfg.status.rendered_config
        yaml = rendered_map.get("ungated") if rendered_map else None
        if not yaml:
            yaml = self.render_target_impl()["ungated"]

        result = self._run_compose(
            yaml,
            "ps",
            "--format",
            "json",
            capture=True,
            log_command=False,
        )
        stdout_str = result.stdout.strip()

        services: list[dict[str, str]] = []
        for line in stdout_str.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if obj:
                    services.append(obj)
            except json.JSONDecodeError:
                logging.debug(
                    "Ignoring non-JSON docker compose ps line for env '%s': %r",
                    self.envCfg.tag,
                    line,
                )
                continue

        logging.debug(
            "Collected %d docker compose status row(s) for env '%s'.",
            len(services),
            self.envCfg.tag,
        )
        return services

    def _run_compose(
        self,
        yamls: str | list[str],
        *args: str,
        capture: bool = False,
        timeout_seconds: Optional[int] = None,
        log_command: bool = True,
        category: Optional[str] = None,
    ):
        should_log = log_command and self.is_command_log_enabled()
        result = run_compose(
            yamls,
            *args,
            capture=capture,
            project_name=self.envCfg.tag,
            timeout_seconds=timeout_seconds,
            log_command=False,
            on_command=None,
        )
        if should_log:
            self._log_compose_result(result, category=category)
        if (
            category
            and category.startswith("start:")
            and result.returncode != 0
        ):
            self._record_compose_failure(result, category=category)
        return result

    def _log_compose_result(
        self,
        result: Any,
        *,
        category: Optional[str],
    ) -> None:
        if not self.is_command_log_enabled():
            return
        exit_code = getattr(result, "returncode", None)
        if exit_code == 0:
            dot = "[bold green]●[/bold green]"
        elif exit_code == 124:
            dot = "[bold yellow]●[/bold yellow]"
        else:
            dot = "[bold red]●[/bold red]"

        cmd = getattr(result, "args", None)
        if isinstance(cmd, list):
            cmd_str = " ".join(cast(list[str], cmd))
        else:
            cmd_str = str(cmd) if cmd is not None else ""

        category_label = (category or "-").ljust(self._command_category_width)
        prefix = f"[cyan]{category_label}[/cyan] "
        suffix = (
            f" [dim](exit {exit_code})[/dim]" if exit_code is not None else ""
        )
        self.add_command_log(f"{dot} {prefix}{cmd_str}{suffix}")

    def _record_compose_failure(
        self,
        result: Any,
        *,
        category: str,
    ) -> None:
        stdout = (getattr(result, "stdout", "") or "").strip()
        stderr = (getattr(result, "stderr", "") or "").strip()
        parts: list[str] = []
        if stdout:
            parts.append("--- stdout ---")
            parts.append(stdout)
        if stderr:
            parts.append("--- stderr ---")
            parts.append(stderr)
        if not parts:
            return
        body = "\n".join(parts)
        self.set_command_error(
            f"Docker compose {category} failed",
            body,
        )
