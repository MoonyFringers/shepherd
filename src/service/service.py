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
        self._generate_containers_names()

    def canonical_name(self) -> str:
        """
        Get the canonical name of the service.
        """
        return f"{self.svcCfg.tag}-{self.envCfg.tag}"

    def _generate_containers_names(self):
        """
        Generate the container names for the service.
        """
        if self.svcCfg.containers:
            if len(self.svcCfg.containers) > 1:
                for container in self.svcCfg.containers:
                    container.run_hostname = (
                        container.hostname
                        if container.hostname
                        else (
                            f"{container.tag}-"
                            f"{self.svcCfg.tag}-{self.envCfg.tag}"
                        )
                    )
                    container.run_container_name = (
                        container.container_name
                        if container.container_name
                        else (
                            f"{container.tag}-"
                            f"{self.svcCfg.tag}-{self.envCfg.tag}"
                        )
                    )
            elif len(self.svcCfg.containers) == 1:
                container = self.svcCfg.containers[0]
                container.run_hostname = (
                    container.hostname
                    if container.hostname
                    else f"{container.tag}-"
                    f"{self.svcCfg.tag}-{self.envCfg.tag}"
                )
                container.run_container_name = (
                    container.container_name
                    if container.container_name
                    else f"{container.tag}-"
                    f"{self.svcCfg.tag}-{self.envCfg.tag}"
                )

    def render(self, resolved: bool) -> str:
        """Render the service configuration."""
        return self.svcCfg.get_yaml(resolved)

    def render_target(self, resolved: bool) -> str:
        """
        Render the service configuration in the target system.
        """
        return self.render_target_impl(resolved)

    def build(self, cnt_tag: Optional[str] = None):
        """Build the service."""
        return self.build_impl(cnt_tag)

    def start(self, cnt_tag: Optional[str] = None):
        """Start the service."""
        return self.start_impl(cnt_tag)

    def stop(self, cnt_tag: Optional[str] = None):
        """Stop the service."""
        return self.stop_impl(cnt_tag)

    def reload(self, cnt_tag: Optional[str] = None):
        """Reload the service."""
        return self.reload_impl(cnt_tag)

    def get_stdout(self, cnt_tag: Optional[str] = None):
        """Show the service stdout."""
        return self.get_stdout_impl(cnt_tag)

    def get_shell(self, cnt_tag: Optional[str] = None):
        """Get a shell session for the service."""
        return self.get_shell_impl(cnt_tag)

    @abstractmethod
    def render_target_impl(self, resolved: bool) -> str:
        """
        Render the service configuration in the target system.
        """
        pass

    @abstractmethod
    def build_impl(self, cnt_tag: Optional[str] = None):
        """Build the service."""
        pass

    @abstractmethod
    def start_impl(self, cnt_tag: Optional[str] = None):
        """Start the service."""
        pass

    @abstractmethod
    def stop_impl(self, cnt_tag: Optional[str] = None):
        """Stop the service."""
        pass

    @abstractmethod
    def reload_impl(self, cnt_tag: Optional[str] = None):
        """Reload the service."""
        pass

    @abstractmethod
    def get_stdout_impl(self, cnt_tag: Optional[str] = None):
        """Show the service stdout."""
        pass

    @abstractmethod
    def get_shell_impl(self, cnt_tag: Optional[str] = None):
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

    @classmethod
    def get_name(cls) -> str:
        return cls.get_name_impl()

    def new_service_from_cfg(
        self, envCfg: EnvironmentCfg, svcCfg: ServiceCfg
    ) -> Service:
        """
        Create a new service.
        """
        return self.new_service_from_cfg_impl(envCfg, svcCfg)

    @classmethod
    @abstractmethod
    def get_name_impl(cls) -> str:
        pass

    @abstractmethod
    def new_service_from_cfg_impl(
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

    def build_svc(
        self,
        envCfg: EnvironmentCfg,
        svc_tag: str,
        cnt_tag: Optional[str] = None,
    ):
        """Build a service."""
        service = self.get_service(envCfg, svc_tag)
        if service:
            service.build(cnt_tag)

    def start_svc(
        self,
        envCfg: EnvironmentCfg,
        svc_tag: str,
        cnt_tag: Optional[str] = None,
    ):
        """Start a service."""
        service = self.get_service(envCfg, svc_tag)
        if service:
            service.start(cnt_tag)

    def stop_svc(
        self,
        envCfg: EnvironmentCfg,
        svc_tag: str,
        cnt_tag: Optional[str] = None,
    ):
        """Halt a service."""
        service = self.get_service(envCfg, svc_tag)
        if service:
            service.stop(cnt_tag)

    def reload_svc(
        self,
        envCfg: EnvironmentCfg,
        svc_tag: str,
        cnt_tag: Optional[str] = None,
    ):
        """Reload a service."""
        service = self.get_service(envCfg, svc_tag)
        if service:
            service.reload(cnt_tag)

    def render_svc(
        self, envCfg: EnvironmentCfg, svc_tag: str, target: bool, resolved: bool
    ) -> Optional[str]:
        """Render a service configuration."""
        service = self.get_service(envCfg, svc_tag)
        if service:
            if target:
                return service.render_target(resolved)
            return service.render(resolved)
        return None

    def logs_svc(
        self,
        envCfg: EnvironmentCfg,
        svc_tag: str,
        cnt_tag: Optional[str] = None,
    ):
        """Get service stdout."""
        service = self.get_service(envCfg, svc_tag)
        if service:
            service.get_stdout(cnt_tag)

    def shell_svc(
        self,
        envCfg: EnvironmentCfg,
        svc_tag: str,
        cnt_tag: Optional[str] = None,
    ):
        """Get a shell session for a service."""
        service = self.get_service(envCfg, svc_tag)
        if service:
            service.get_shell(cnt_tag)
