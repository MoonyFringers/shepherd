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

from typing import Any, override

import yaml

from config import ConfigMng, EnvironmentCfg
from environment import Environment
from service import ServiceFactory


class DockerComposeEnv(Environment):

    def __init__(
        self,
        config: ConfigMng,
        svcFactory: ServiceFactory,
        envCfg: EnvironmentCfg,
    ):
        """Initialize a Docker Compose environment."""
        super().__init__(config, svcFactory, envCfg)

    @override
    def clone(self, dst_env_tag: str) -> DockerComposeEnv:
        """Clone the environment."""
        clonedCfg = self.configMng.env_cfg_from_other(self.to_config())
        clonedCfg.tag = dst_env_tag
        clonedEnv = DockerComposeEnv(
            self.configMng,
            self.svcFactory,
            clonedCfg,
        )
        return clonedEnv

    @override
    def start(self):
        """Start the environment."""
        pass

    @override
    def halt(self):
        """Halt the environment."""
        pass

    @override
    def reload(self):
        """Reload the environment."""
        pass

    @override
    def render(self) -> str:
        """
        Render the full docker-compose YAML configuration for the environment.
        """

        compose_config: dict[str, Any] = {
            "name": self.envCfg.tag,
            "services": {},
            "networks": {},
            "volumes": {},
        }

        for svc in self.services:
            svc_yaml = yaml.safe_load(svc.render())
            compose_config["services"].update(svc_yaml["services"])

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

                compose_config["networks"][net.tag] = net_config

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

                compose_config["volumes"][vol.tag] = vol_config

        return yaml.dump(compose_config, sort_keys=False)

    @override
    def status(self):
        """Get environment status."""
        pass
