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
        self, config: ConfigMng, envCfg: EnvironmentCfg, svcCfg: ServiceCfg
    ):
        """Initialize a Docker service."""
        super().__init__(config, envCfg, svcCfg)

    @override
    def render_target(self, resolved: bool) -> str:
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
    def build(self, cnt_tag: Optional[str] = None) -> None:
        """Build the service."""
        if cnt_tag:
            container = self.svcCfg.get_container_by_tag(cnt_tag)
            if not container:
                Util.print_error_and_die(
                    f"Service '{self.svcCfg.tag}' does not have a "
                    f"container named '{cnt_tag}'."
                )
            if container:
                build_container(container)
            return

        containers = self.svcCfg.containers or []
        for container in containers:
            build_container(container)

    @override
    def start(self, cnt_tag: Optional[str] = None):
        """Start the service."""
        rendered_map = self.envCfg.status.rendered_config
        rendered = rendered_map.get("ungated") if rendered_map else None

        if rendered and self.svcCfg.containers:
            if cnt_tag:
                container = self.svcCfg.get_container_by_tag(cnt_tag)
                if not container:
                    Util.print_error_and_die(
                        f"Service '{self.svcCfg.tag}' does not have a "
                        f"container named '{cnt_tag}'."
                    )
                if container:
                    run_compose(
                        rendered,
                        "up",
                        "-d",
                        container.run_container_name or "",
                        project_name=self.envCfg.tag,
                    )
                return

            for container in self.svcCfg.containers or []:
                run_compose(
                    rendered,
                    "up",
                    "-d",
                    container.run_container_name or "",
                    project_name=self.envCfg.tag,
                )
        else:
            Util.print_error_and_die(
                f"Environment: '{self.envCfg.tag}' is not running."
            )

    @override
    def stop(self, cnt_tag: Optional[str] = None):
        """Stop the service."""
        rendered_map = self.envCfg.status.rendered_config
        rendered = rendered_map.get("ungated") if rendered_map else None

        if rendered and self.svcCfg.containers:
            if cnt_tag:
                container = self.svcCfg.get_container_by_tag(cnt_tag)
                if not container:
                    Util.print_error_and_die(
                        f"Service '{self.svcCfg.tag}' does not have a "
                        f"container named '{cnt_tag}'."
                    )
                if container:
                    run_compose(
                        rendered,
                        "stop",
                        container.run_container_name or "",
                        project_name=self.envCfg.tag,
                    )
                return

            for container in self.svcCfg.containers or []:
                run_compose(
                    rendered,
                    "stop",
                    container.run_container_name or "",
                    project_name=self.envCfg.tag,
                )
        else:
            Util.print_error_and_die(
                f"Environment: '{self.envCfg.tag}' is not running."
            )

    @override
    def reload(self, cnt_tag: Optional[str] = None):
        """Reload the service."""
        rendered_map = self.envCfg.status.rendered_config
        rendered = rendered_map.get("ungated") if rendered_map else None

        if rendered and self.svcCfg.containers:
            if cnt_tag:
                container = self.svcCfg.get_container_by_tag(cnt_tag)
                if not container:
                    Util.print_error_and_die(
                        f"Service '{self.svcCfg.tag}' does not have a "
                        f"container named '{cnt_tag}'."
                    )
                if container:
                    run_compose(
                        rendered,
                        "restart",
                        container.run_container_name or "",
                        project_name=self.envCfg.tag,
                    )
                return

            for container in self.svcCfg.containers or []:
                run_compose(
                    rendered,
                    "restart",
                    container.run_container_name or "",
                    project_name=self.envCfg.tag,
                )
        else:
            Util.print_error_and_die(
                f"Environment: '{self.envCfg.tag}' is not running."
            )

    @override
    def get_stdout(self, cnt_tag: Optional[str] = None):
        """Show the service stdout."""
        rendered_map = self.envCfg.status.rendered_config
        rendered = rendered_map.get("ungated") if rendered_map else None

        if rendered:
            if cnt_tag:
                container = self.svcCfg.get_container_by_tag(cnt_tag)
                if not container:
                    Util.print_error_and_die(
                        f"Service '{self.svcCfg.tag}' does not have a "
                        f"container named '{cnt_tag}'."
                    )
                if container:
                    run_compose(
                        rendered,
                        "logs",
                        container.run_container_name or "",
                        project_name=self.envCfg.tag,
                    )
            elif self.svcCfg.containers and len(self.svcCfg.containers) == 1:
                run_compose(
                    rendered,
                    "logs",
                    self.svcCfg.containers[0].run_container_name or "",
                    project_name=self.envCfg.tag,
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
    def get_shell(self, cnt_tag: Optional[str] = None):
        """Get a shell session for the service."""
        rendered_map = self.envCfg.status.rendered_config
        rendered = rendered_map.get("ungated") if rendered_map else None

        if rendered:
            if cnt_tag:
                container = self.svcCfg.get_container_by_tag(cnt_tag)
                if not container:
                    Util.print_error_and_die(
                        f"Service '{self.svcCfg.tag}' does not have a "
                        f"container named '{cnt_tag}'."
                    )
                if container:
                    run_compose(
                        rendered,
                        "exec",
                        container.run_container_name or "",
                        "sh",
                        project_name=self.envCfg.tag,
                    )
            elif self.svcCfg.containers and len(self.svcCfg.containers) == 1:
                run_compose(
                    rendered,
                    "exec",
                    self.svcCfg.containers[0].run_container_name or "",
                    "sh",
                    project_name=self.envCfg.tag,
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
