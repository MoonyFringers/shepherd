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
from typing import Any, override

import yaml

from config import ConfigMng, EnvironmentCfg, ServiceCfg
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

            service_def: dict[str, Any] = {
                "image": self.svcCfg.image,
                "hostname": self.hostname,
                "container_name": self.container_name,
            }

            if self.svcCfg.labels:
                service_def["labels"] = self.svcCfg.labels
            if self.svcCfg.environment:
                service_def["environment"] = self.svcCfg.environment
            if self.svcCfg.volumes:
                service_def["volumes"] = self.svcCfg.volumes
            if self.svcCfg.ports:
                service_def["ports"] = self.svcCfg.ports
            if self.svcCfg.extra_hosts:
                service_def["extra_hosts"] = self.svcCfg.extra_hosts
            if self.svcCfg.networks:
                service_def["networks"] = self.svcCfg.networks

            return yaml.dump({self.name: service_def}, sort_keys=False)
        finally:
            if changed_state:
                if was_resolved:
                    self.envCfg.set_resolved()
                else:
                    self.envCfg.set_unresolved()

    @override
    def build(self):
        """Build the service."""
        if build := self.svcCfg.build:
            if dockerfile := build.dockerfile_path:
                if context_path := build.context_path:
                    build_docker_image(
                        Path(dockerfile),
                        Path(context_path),
                        self.svcCfg.image,
                    )
                else:
                    Util.print_error_and_die(
                        f"Service '{self.svcCfg.tag}' build configuration is "
                        f"missing a build context path."
                    )
            else:
                Util.print_error_and_die(
                    f"Service '{self.svcCfg.tag}' build configuration is "
                    f"missing a Dockerfile path."
                )
        else:
            Util.print_error_and_die(
                f"Service '{self.svcCfg.tag}' does not have a build "
                f"configuration."
            )

    @override
    def start(self):
        if self.envCfg.status.triggered_config:
            run_compose(
                self.envCfg.status.triggered_config,
                "up",
                "-d",
                self.canonical_name(),
            )
        else:
            Util.print_error_and_die(
                f"Environment: '{self.envCfg.tag}' is not running."
            )

    @override
    def stop(self):
        """Stop the service."""
        if self.envCfg.status.triggered_config:
            run_compose(
                self.envCfg.status.triggered_config,
                "stop",
                self.canonical_name(),
            )
        else:
            Util.print_error_and_die(
                f"Environment: '{self.envCfg.tag}' is not running."
            )

    @override
    def reload(self):
        """Reload the service."""
        if self.envCfg.status.triggered_config:
            run_compose(
                self.envCfg.status.triggered_config,
                "restart",
                self.canonical_name(),
            )
        else:
            Util.print_error_and_die(
                f"Environment: '{self.envCfg.tag}' is not running."
            )

    @override
    def get_stdout(self):
        """Show the service stdout."""
        if self.envCfg.status.triggered_config:
            run_compose(
                self.envCfg.status.triggered_config,
                "logs",
                self.canonical_name(),
            )
        else:
            Util.print_error_and_die(
                f"Environment: '{self.envCfg.tag}' is not running."
            )

    @override
    def get_shell(self):
        """Get a shell session for the service."""
        if self.envCfg.status.triggered_config:
            run_compose(
                self.envCfg.status.triggered_config,
                "exec",
                self.canonical_name(),
                "sh",
            )
        else:
            Util.print_error_and_die(
                f"Environment: '{self.envCfg.tag}' is not running."
            )
