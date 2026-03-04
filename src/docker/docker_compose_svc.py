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

from typing import Any, Optional, override

import yaml

from config import ConfigMng, EnvironmentCfg, ServiceCfg
from service import Service
from util import Util

from .docker_compose_util import build_container, render_container, run_compose


class DockerComposeSvc(Service):

    def __init__(
        self,
        config: ConfigMng,
        envCfg: EnvironmentCfg,
        svcCfg: ServiceCfg,
        cli_flags: Optional[dict[str, Any]] = None,
    ):
        """Initialize a Docker service."""
        super().__init__(config, envCfg, svcCfg, cli_flags=cli_flags)

    @override
    def render_target_impl(self, resolved: bool) -> str:
        """
        Render the docker-compose service configuration for this service.

        Args:
            resolved: If True, ensure placeholders in svcCfg are resolved
            before rendering.
        """
        was_resolved = self.svcCfg.is_resolved()
        changed_state = False

        try:
            if resolved and not was_resolved:
                self.envCfg.set_resolved()
                changed_state = True
            elif not resolved and was_resolved:
                self.envCfg.set_unresolved()
                changed_state = True

            if not self.svcCfg.containers:
                return yaml.dump({self.name: {}}, sort_keys=False)

            services_def: dict[str, Any] = {"services": {}}

            for container in self.svcCfg.containers:
                services_def["services"][container.run_container_name] = (
                    render_container(container, self.svcCfg.labels)
                )

            return yaml.dump(services_def, sort_keys=False)

        finally:
            if changed_state:
                if was_resolved:
                    self.envCfg.set_resolved()
                else:
                    self.envCfg.set_unresolved()

    @override
    def build_impl(self, cnt_tag: Optional[str] = None) -> None:
        """Build the service."""
        verbose = self._is_verbose() or not self._is_quiet()
        if cnt_tag:
            container = self.svcCfg.get_container_by_tag(cnt_tag)
            if not container:
                Util.print_error_and_die(
                    f"Service '{self.svcCfg.tag}' does not have a "
                    f"container named '{cnt_tag}'."
                )
            if container:
                build_container(container, verbose=verbose)
            return

        containers = self.svcCfg.containers or []
        for container in containers:
            build_container(container, verbose=verbose)

    @override
    def start_impl(self, cnt_tag: Optional[str] = None):
        """
        Start one or all service containers using the full rendered env stack.
        """
        rendered_stack = self._get_rendered_compose_stack()
        verbose = self._is_verbose()

        if rendered_stack and self.svcCfg.containers:
            if cnt_tag:
                container = self.svcCfg.get_container_by_tag(cnt_tag)
                if not container:
                    Util.print_error_and_die(
                        f"Service '{self.svcCfg.tag}' does not have a "
                        f"container named '{cnt_tag}'."
                    )
                if container:
                    run_compose(
                        rendered_stack,
                        "up",
                        "-d",
                        container.run_container_name or "",
                        project_name=self.envCfg.tag,
                        capture=not verbose,
                    )
                return

            for container in self.svcCfg.containers or []:
                run_compose(
                    rendered_stack,
                    "up",
                    "-d",
                    container.run_container_name or "",
                    project_name=self.envCfg.tag,
                    capture=not verbose,
                )
        else:
            Util.print_error_and_die(
                f"Environment: '{self.envCfg.tag}' is not running."
            )

    @override
    def stop_impl(self, cnt_tag: Optional[str] = None):
        """Stop one or all containers for this service."""
        rendered_stack = self._get_rendered_compose_stack()
        verbose = self._is_verbose()

        if rendered_stack and self.svcCfg.containers:
            if cnt_tag:
                container = self.svcCfg.get_container_by_tag(cnt_tag)
                if not container:
                    Util.print_error_and_die(
                        f"Service '{self.svcCfg.tag}' does not have a "
                        f"container named '{cnt_tag}'."
                    )
                if container:
                    run_compose(
                        rendered_stack,
                        "stop",
                        container.run_container_name or "",
                        project_name=self.envCfg.tag,
                        capture=not verbose,
                    )
                return

            for container in self.svcCfg.containers or []:
                run_compose(
                    rendered_stack,
                    "stop",
                    container.run_container_name or "",
                    project_name=self.envCfg.tag,
                    capture=not verbose,
                )
        else:
            Util.print_error_and_die(
                f"Environment: '{self.envCfg.tag}' is not running."
            )

    @override
    def reload_impl(self, cnt_tag: Optional[str] = None):
        """Restart one or all containers for this service."""
        rendered_stack = self._get_rendered_compose_stack()
        verbose = self._is_verbose()

        if rendered_stack and self.svcCfg.containers:
            if cnt_tag:
                container = self.svcCfg.get_container_by_tag(cnt_tag)
                if not container:
                    Util.print_error_and_die(
                        f"Service '{self.svcCfg.tag}' does not have a "
                        f"container named '{cnt_tag}'."
                    )
                if container:
                    run_compose(
                        rendered_stack,
                        "restart",
                        container.run_container_name or "",
                        project_name=self.envCfg.tag,
                        capture=not verbose,
                    )
                return

            for container in self.svcCfg.containers or []:
                run_compose(
                    rendered_stack,
                    "restart",
                    container.run_container_name or "",
                    project_name=self.envCfg.tag,
                    capture=not verbose,
                )
        else:
            Util.print_error_and_die(
                f"Environment: '{self.envCfg.tag}' is not running."
            )

    @override
    def get_stdout_impl(self, cnt_tag: Optional[str] = None):
        """
        Show container logs for this service.

        If the service has multiple containers, caller must specify `cnt_tag`
        to avoid ambiguous output streams.
        """
        rendered_stack = self._get_rendered_compose_stack()
        capture = self._is_quiet() and not self._is_verbose()

        if rendered_stack:
            if cnt_tag:
                container = self.svcCfg.get_container_by_tag(cnt_tag)
                if not container:
                    Util.print_error_and_die(
                        f"Service '{self.svcCfg.tag}' does not have a "
                        f"container named '{cnt_tag}'."
                    )
                if container:
                    run_compose(
                        rendered_stack,
                        "logs",
                        container.run_container_name or "",
                        project_name=self.envCfg.tag,
                        capture=capture,
                    )
            elif self.svcCfg.containers and len(self.svcCfg.containers) == 1:
                run_compose(
                    rendered_stack,
                    "logs",
                    self.svcCfg.containers[0].run_container_name or "",
                    project_name=self.envCfg.tag,
                    capture=capture,
                )
            else:
                Util.print_error_and_die(
                    f"Service '{self.svcCfg.tag}' has multiple containers. "
                    f"Specify a container name."
                )
        else:
            Util.print_error_and_die(
                f"Environment: '{self.envCfg.tag}' is not running."
            )

    @override
    def get_shell_impl(self, cnt_tag: Optional[str] = None):
        """
        Open an interactive shell in a service container.

        For multi-container services, `cnt_tag` is required to select a target.
        """
        rendered_stack = self._get_rendered_compose_stack()
        capture = self._is_quiet() and not self._is_verbose()

        if rendered_stack:
            if cnt_tag:
                container = self.svcCfg.get_container_by_tag(cnt_tag)
                if not container:
                    Util.print_error_and_die(
                        f"Service '{self.svcCfg.tag}' does not have a "
                        f"container named '{cnt_tag}'."
                    )
                if container:
                    run_compose(
                        rendered_stack,
                        "exec",
                        container.run_container_name or "",
                        "sh",
                        project_name=self.envCfg.tag,
                        capture=capture,
                    )
            elif self.svcCfg.containers and len(self.svcCfg.containers) == 1:
                run_compose(
                    rendered_stack,
                    "exec",
                    self.svcCfg.containers[0].run_container_name or "",
                    "sh",
                    project_name=self.envCfg.tag,
                    capture=capture,
                )
            else:
                Util.print_error_and_die(
                    f"Service '{self.svcCfg.tag}' has multiple containers. "
                    f"Specify a container name."
                )
        else:
            Util.print_error_and_die(
                f"Environment: '{self.envCfg.tag}' is not running."
            )

    def _get_rendered_compose_stack(self) -> Optional[list[str]]:
        """
        Return all rendered compose fragments for the running environment.

        Compose applies multiple `-f` files in order, with later files
        overriding/extending earlier ones. We therefore always place the base
        `ungated` config first (when present), followed by gated overlays.

        This ordering is explicit on purpose and does not rely on dictionary
        insertion order from the render pipeline.
        """
        rendered_map = self.envCfg.status.rendered_config
        if not rendered_map:
            return None

        stack: list[str] = []
        base = rendered_map.get("ungated")
        if base:
            stack.append(base)

        for gate_key, gate_yaml in rendered_map.items():
            if gate_key == "ungated":
                continue
            if gate_yaml:
                stack.append(gate_yaml)

        return stack or None
