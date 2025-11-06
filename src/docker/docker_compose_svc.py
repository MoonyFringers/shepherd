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

from pathlib import Path
from typing import Any, Optional, override

import yaml

from config import ConfigMng, EnvironmentCfg, ServiceCfg
from config.config import ContainerCfg
from service import Service
from util import Util

from .docker_compose_util import build_docker_image, run_compose


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
                service_def: dict[str, Any] = {}
                if container.image:
                    service_def["image"] = container.image
                if container.run_hostname:
                    service_def["hostname"] = container.run_hostname
                if container.run_container_name:
                    service_def["container_name"] = container.run_container_name
                if container.workdir:
                    service_def["working_dir"] = container.workdir
                if container.volumes:
                    service_def["volumes"] = container.volumes
                if container.environment:
                    service_def["environment"] = container.environment
                if container.ports:
                    service_def["ports"] = container.ports
                if container.networks:
                    service_def["networks"] = container.networks
                if container.extra_hosts:
                    service_def["extra_hosts"] = container.extra_hosts
                if self.svcCfg.labels:
                    service_def["labels"] = self.svcCfg.labels
                services_def["services"][
                    container.run_container_name
                ] = service_def

            return yaml.dump(services_def, sort_keys=False)

        finally:
            if changed_state:
                if was_resolved:
                    self.envCfg.set_resolved()
                else:
                    self.envCfg.set_unresolved()

    def _build_one_container(self, container: ContainerCfg) -> None:
        """Validate config and build a single container."""
        if not container.build:
            Util.print_error_and_die(
                f"Service '{self.svcCfg.tag}' "
                f"container '{container.tag}' "
                f"does not have a build configuration."
            )

        if build := container.build:
            if not build.dockerfile_path:
                Util.print_error_and_die(
                    f"Service '{self.svcCfg.tag}' "
                    f"container '{container.tag}' "
                    f"build configuration is missing "
                    f"a Dockerfile path."
                )
            if not build.context_path:
                Util.print_error_and_die(
                    f"Service '{self.svcCfg.tag}' "
                    f"container '{container.tag}' "
                    f"build configuration is missing "
                    f"a build context path."
                )

            if build.dockerfile_path and build.context_path:
                build_docker_image(
                    Path(build.dockerfile_path),
                    Path(build.context_path),
                    container.image or "",
                )

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
                self._build_one_container(container)
            return

        containers = self.svcCfg.containers or []
        for container in containers:
            self._build_one_container(container)

    @override
    def start(self, cnt_tag: Optional[str] = None):
        """Start the service."""
        if self.envCfg.status.triggered_config and self.svcCfg.containers:
            if cnt_tag:
                container = self.svcCfg.get_container_by_tag(cnt_tag)
                if not container:
                    Util.print_error_and_die(
                        f"Service '{self.svcCfg.tag}' does not have a "
                        f"container named '{cnt_tag}'."
                    )
                if container:
                    run_compose(
                        self.envCfg.status.triggered_config,
                        "up",
                        "-d",
                        container.run_container_name or "",
                    )
                return
            for container in self.svcCfg.containers or []:
                run_compose(
                    self.envCfg.status.triggered_config,
                    "up",
                    "-d",
                    container.run_container_name or "",
                )
        else:
            Util.print_error_and_die(
                f"Environment: '{self.envCfg.tag}' is not running."
            )

    @override
    def stop(self, cnt_tag: Optional[str] = None):
        """Stop the service."""
        if self.envCfg.status.triggered_config and self.svcCfg.containers:
            if cnt_tag:
                container = self.svcCfg.get_container_by_tag(cnt_tag)
                if not container:
                    Util.print_error_and_die(
                        f"Service '{self.svcCfg.tag}' does not have a "
                        f"container named '{cnt_tag}'."
                    )
                if container:
                    run_compose(
                        self.envCfg.status.triggered_config,
                        "stop",
                        container.run_container_name or "",
                    )
                return
            for container in self.svcCfg.containers or []:
                run_compose(
                    self.envCfg.status.triggered_config,
                    "stop",
                    container.run_container_name or "",
                )
        else:
            Util.print_error_and_die(
                f"Environment: '{self.envCfg.tag}' is not running."
            )

    @override
    def reload(self, cnt_tag: Optional[str] = None):
        """Reload the service."""
        if self.envCfg.status.triggered_config and self.svcCfg.containers:
            if cnt_tag:
                container = self.svcCfg.get_container_by_tag(cnt_tag)
                if not container:
                    Util.print_error_and_die(
                        f"Service '{self.svcCfg.tag}' does not have a "
                        f"container named '{cnt_tag}'."
                    )
                if container:
                    run_compose(
                        self.envCfg.status.triggered_config,
                        "restart",
                        container.run_container_name or "",
                    )
                return
            for container in self.svcCfg.containers or []:
                run_compose(
                    self.envCfg.status.triggered_config,
                    "restart",
                    container.run_container_name or "",
                )
        else:
            Util.print_error_and_die(
                f"Environment: '{self.envCfg.tag}' is not running."
            )

    @override
    def get_stdout(self, cnt_tag: Optional[str] = None):
        """Show the service stdout."""
        if self.envCfg.status.triggered_config:
            if cnt_tag:
                container = self.svcCfg.get_container_by_tag(cnt_tag)
                if not container:
                    Util.print_error_and_die(
                        f"Service '{self.svcCfg.tag}' does not have a "
                        f"container named '{cnt_tag}'."
                    )
                if container:
                    run_compose(
                        self.envCfg.status.triggered_config,
                        "logs",
                        container.run_container_name or "",
                    )
            elif self.svcCfg.containers and len(self.svcCfg.containers) == 1:
                run_compose(
                    self.envCfg.status.triggered_config,
                    "logs",
                    self.svcCfg.containers[0].run_container_name or "",
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
        if self.envCfg.status.triggered_config:
            if cnt_tag:
                container = self.svcCfg.get_container_by_tag(cnt_tag)
                if not container:
                    Util.print_error_and_die(
                        f"Service '{self.svcCfg.tag}' does not have a "
                        f"container named '{cnt_tag}'."
                    )
                if container:
                    run_compose(
                        self.envCfg.status.triggered_config,
                        "exec",
                        container.run_container_name or "",
                        "sh",
                    )
            elif self.svcCfg.containers and len(self.svcCfg.containers) == 1:
                run_compose(
                    self.envCfg.status.triggered_config,
                    "exec",
                    self.svcCfg.containers[0].run_container_name or "",
                    "sh",
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
