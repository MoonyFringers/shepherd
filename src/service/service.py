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

from abc import ABC, abstractmethod
from typing import Optional

from config import ConfigMng, EnvironmentCfg, ServiceCfg


class Service(ABC):

    def __init__(
        self, configMng: ConfigMng, envCfg: EnvironmentCfg, svcCfg: ServiceCfg
    ):
        self.configMng = configMng
        self.envCfg = envCfg
        self.svcCfg = svcCfg
        self.name = self.canonical_name()
        self.hostname = (
            svcCfg.hostname if svcCfg.hostname else self.canonical_name()
        )
        self.container_name = (
            svcCfg.container_name
            if svcCfg.container_name
            else self.canonical_name()
        )

    def canonical_name(self) -> str:
        """
        Get the canonical name of the service.
        """
        return f"{self.svcCfg.tag}-{self.envCfg.tag}"

    @abstractmethod
    def clone(self, dst_svc_tag: str) -> Service:
        """Clone a service."""
        pass

    @abstractmethod
    def render(self) -> str:
        """
        Render the service configuration.
        """
        pass

    @abstractmethod
    def build(self):
        """Build the service."""
        pass

    @abstractmethod
    def start(self):
        """Start the service."""
        pass

    @abstractmethod
    def halt(self):
        """Stop the service."""
        pass

    @abstractmethod
    def reload(self):
        """Reload the service."""
        pass

    @abstractmethod
    def show_stdout(self):
        """Show the service stdout."""
        pass

    @abstractmethod
    def get_shell(self):
        """Get a shell session for the service."""
        pass

    def to_config(self) -> ServiceCfg:
        return self.svcCfg


class ServiceFactory(ABC):
    """
    Factory class for services.
    """

    def __init__(self, config: ConfigMng):
        self.config = config

    @abstractmethod
    def get_name() -> str:
        pass

    @abstractmethod
    def new_service_from_cfg(
        self, envCfg: EnvironmentCfg, svcCfg: ServiceCfg
    ) -> Service:
        """
        Create a new service.
        """
        pass


class ServiceMng:

    def __init__(
        self,
        cli_flags: dict[str, bool],
        configMng: ConfigMng,
        svcFactory: ServiceFactory,
    ):
        self.cli_flags = cli_flags
        self.configMng = configMng
        self.svcFactory = svcFactory

    def get_service(
        self, envCfg: EnvironmentCfg, svc_tag: str
    ) -> Optional[Service]:
        """Get a service by environment tag and service tag."""
        if svcCfg := envCfg.get_service(svc_tag):
            return self.svcFactory.new_service_from_cfg(envCfg, svcCfg)
        else:
            return None

    def build_image_svc(self, service_template: str):
        pass

    def start_svc(self, envCfg: EnvironmentCfg, service_tag: str):
        """Start a service."""
        pass

    def halt_svc(self, envCfg: EnvironmentCfg, service_tag: str):
        """Halt a service."""
        pass

    def reload_svc(self, envCfg: EnvironmentCfg, service_tag: str):
        """Reload a service."""
        pass

    def render_svc(self, envCfg: EnvironmentCfg, svc_tag: str) -> Optional[str]:
        """Render a service configuration."""
        service = self.get_service(envCfg, svc_tag)
        if service:
            return service.render()
        return None

    def stdout_svc(self, envCfg: EnvironmentCfg, svc_tag: str):
        """Get service stdout."""
        pass

    def shell_svc(self, envCfg: EnvironmentCfg, svc_tag: str):
        """Get a shell session for a service."""
        pass
