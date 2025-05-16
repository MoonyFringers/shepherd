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

from abc import ABC, abstractmethod
from typing import Dict

from config import ConfigMng, ServiceCfg


class Service(ABC):

    def __init__(
        self,
        type: str,
        tag: str,
        image: str,
        ingress: bool = False,
        empty_env: str = "",
        envvars: dict[str, str] = {},
        ports: dict[str, str] = {},
        properties: dict[str, str] = {},
        subject_alternative_name: str = "",
    ):
        self.type = type
        self.tag = tag
        self.image = image
        self.ingress = ingress
        self.empty_env = empty_env
        self.envvars = envvars or {}
        self.ports = ports or {}
        self.properties = properties or {}
        self.subject_alternative_name = subject_alternative_name

    @abstractmethod
    def build_image(self):
        """Build the service image."""
        pass

    @abstractmethod
    def bootstrap(self):
        """Bootstrap the service."""
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
        return ServiceCfg(
            type=self.type,
            tag=self.tag,
            image=self.image,
            ingress=self.ingress,
            empty_env=self.empty_env,
            envvars=self.envvars,
            ports=self.ports,
            properties=self.properties,
            subject_alternative_name=self.subject_alternative_name,
        )


class ServiceMng:

    def __init__(self, cli_flags: Dict[str, bool], configMng: ConfigMng):
        self.cli_flags = cli_flags
        self.configMng = configMng
        pass

    def build_image_svc(self, service_type: str):
        pass

    def bootstrap_svc(self, service_type: str):
        """Bootstrap a service."""
        pass

    def start_svc(self, service_type: str):
        """Start a service."""
        pass

    def halt_svc(self, service_type: str):
        """Halt a service."""
        pass

    def reload_svc(self, service_type: str):
        """Reload a service."""
        pass

    def stdout_svc(self, service_id: str):
        """Get service stdout."""
        pass

    def shell_svc(self, service_id: str):
        """Get a shell session for a service."""
        pass
