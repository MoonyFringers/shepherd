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


from __future__ import annotations

from typing import Any, override

import yaml

from config import ConfigMng, EnvironmentCfg, ServiceCfg
from service import Service


class DockerSvc(Service):

    def __init__(
        self, config: ConfigMng, envCfg: EnvironmentCfg, svcCfg: ServiceCfg
    ):
        """Initialize a Docker service."""
        super().__init__(config, envCfg, svcCfg)

    @override
    def clone(self, dst_svc_tag: str) -> DockerSvc:
        """Clone a service."""
        clonedCfg = self.configMng.svc_cfg_from_other(self.to_config())
        clonedCfg.tag = dst_svc_tag
        clonedSvc = DockerSvc(
            self.configMng,
            self.envCfg,
            clonedCfg,
        )
        return clonedSvc

    @override
    def render(self) -> str:
        """
        Render the docker-compose service configuration for this service.
        """
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

        return yaml.dump(
            {"services": {self.name: service_def}}, sort_keys=False
        )

    @override
    def build(self):
        """Build the service."""
        pass

    @override
    def start(self):
        """Start the service."""
        pass

    @override
    def halt(self):
        """Stop the service."""
        pass

    @override
    def reload(self):
        """Reload the service."""
        pass

    @override
    def show_stdout(self):
        """Show the service stdout."""
        pass

    @override
    def get_shell(self):
        """Get a shell session for the service."""
        pass
