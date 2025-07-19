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

import os
from abc import ABC, abstractmethod
from typing import Optional

from config import ConfigMng, EnvironmentCfg, ServiceCfg
from service import Service, ServiceFactory
from util import Constants, Util


class Environment(ABC):

    services: list[Service]

    def __init__(
        self,
        configMng: ConfigMng,
        svcFactory: ServiceFactory,
        envCfg: EnvironmentCfg,
    ):
        self.configMng = configMng
        self.svcFactory = svcFactory
        self.envCfg = envCfg
        self.services = (
            [
                self.svcFactory.new_service_from_cfg(envCfg, svcCfg)
                for svcCfg in envCfg.services
            ]
            if envCfg.services
            else []
        )

    @abstractmethod
    def clone(self, dst_env_tag: str) -> Environment:
        """Clone an environment."""
        pass

    @abstractmethod
    def start(self):
        """Start an environment."""
        pass

    @abstractmethod
    def halt(self):
        """Halt an environment."""
        pass

    @abstractmethod
    def reload(self):
        """Reload an environment."""
        pass

    @abstractmethod
    def status(self):
        """Get environment status."""
        pass

    def to_config(self) -> EnvironmentCfg:
        """To config"""
        self.envCfg.services = [svc.svcCfg for svc in self.services]
        return self.envCfg

    def get_dir(self) -> str:
        """Return the directory of the environment."""
        return os.path.join(
            self.configMng.constants.SHPD_ENVS_DIR, self.envCfg.tag
        )

    def get_dir_for_tag(self, env_tag: str) -> str:
        """Return the directory for the environment with a given tag."""
        return os.path.join(self.configMng.constants.SHPD_ENVS_DIR, env_tag)

    def realize(self):
        """Realize the environment."""
        Util.create_dir(
            self.get_dir(),
            self.envCfg.tag,
        )
        self.sync_config()

    def realize_from(self, src_env: Environment):
        """Realize the environment."""
        Util.copy_dir(src_env.get_dir(), self.get_dir())
        self.sync_config()

    def move_to(self, dst_env_tag: str):
        """Move the environment to a new tag."""
        Util.move_dir(self.get_dir(), self.get_dir_for_tag(dst_env_tag))
        self.configMng.remove_environment(self.envCfg.tag)
        self.envCfg.tag = dst_env_tag
        self.sync_config()

    def delete(self):
        """Delete the environment."""
        Util.remove_dir(self.get_dir())
        self.configMng.remove_environment(self.envCfg.tag)

    def sync_config(self):
        """Sync the environment configuration."""
        self.configMng.add_or_set_environment(self.envCfg.tag, self.to_config())

    def get_tag(self) -> str:
        """Return the tag of the environment."""
        return self.envCfg.tag

    def set_tag(self, tag: str):
        """Set the tag of the environment."""
        self.envCfg.tag = tag

    def is_archived(self) -> bool:
        return self.envCfg.archived

    def set_archived(self, archived: bool):
        self.envCfg.archived = archived

    def is_active(self) -> bool:
        return self.envCfg.active

    def set_active(self, active: bool):
        self.envCfg.active = active

    def add_service(self, service: Service):
        """Add a service to the environment."""
        self.services.append(service)
        self.sync_config()

    def remove_service(self, service: Service):
        """Remove a service from the environment."""
        self.services.remove(service)
        self.sync_config()

    def get_services(self) -> list[Service]:
        """Return the list of services in the environment."""
        return self.services

    def get_service(self, svc_name: str) -> Optional[Service]:
        """Get a service by name."""
        for service in self.services:
            if service.svcCfg.tag == svc_name:
                return service
        return None


class EnvironmentFactory(ABC):
    """
    Factory class for environments.
    """

    def __init__(self, config: ConfigMng):
        self.config = config

    @abstractmethod
    def new_environment(
        self, env_template: str, env_factory: str, env_tag: str
    ) -> Environment:
        """
        Create an environment.
        """
        pass

    @abstractmethod
    def new_environment_cfg(self, envCfg: EnvironmentCfg) -> Environment:
        """
        Create an environment.
        """
        pass


class EnvironmentMng:

    def __init__(
        self,
        cli_flags: dict[str, bool],
        configMng: ConfigMng,
        envFactory: EnvironmentFactory,
        svcFactory: ServiceFactory,
    ):
        self.cli_flags = cli_flags
        self.configMng = configMng
        self.envFactory = envFactory
        self.svcFactory = svcFactory

    def get_environment(self, env_tag: Optional[str]) -> Optional[Environment]:
        if env_tag and env_tag.strip():
            envCfg = self.configMng.get_environment(env_tag)
            if not envCfg:
                Util.print_error_and_die(
                    f"Environment with tag '{env_tag}' does not exist."
                )
        else:
            envCfg = self.configMng.get_active_environment()
            if not envCfg:
                Util.print_error_and_die("No active environment configured.")

        if envCfg:
            env = self.envFactory.new_environment_cfg(envCfg)
            return env
        else:
            return None

    def init_env(self, env_template: str, env_tag: str):
        """Initialize an environment."""
        if self.configMng.get_environment(env_tag):
            Util.print_error_and_die(
                f"Environment with tag '{env_tag}' already exists."
            )
        if envCfg := self.configMng.get_environment_template(env_template):
            env = self.envFactory.new_environment(
                self.configMng.constants.ENV_TEMPLATE_DEFAULT,
                envCfg.factory,
                env_tag,
            )
            env.realize()
            Util.print(f"{env_tag}")
        else:
            Util.print_error_and_die(
                f"Environment Template with tag '{env_template}' "
                f"does not exist."
            )

    def clone_env(self, src_env_tag: str, dst_env_tag: str):
        """Clone an environment."""
        envCfg = self.configMng.get_environment(src_env_tag)
        if not envCfg:
            Util.print_error_and_die(
                f"Environment with tag '{src_env_tag}' does not exist."
            )
        else:
            env = self.envFactory.new_environment_cfg(envCfg)
            clonedEnv = env.clone(dst_env_tag)
            clonedEnv.realize_from(env)
            Util.print(f"Cloned to: {dst_env_tag}")

    def rename_env(self, src_env_tag: str, dst_env_tag: str):
        """Rename an environment."""
        envCfg = self.configMng.get_environment(src_env_tag)
        if not envCfg:
            Util.print_error_and_die(
                f"Environment with tag '{src_env_tag}' does not exist."
            )
        else:
            env = self.envFactory.new_environment_cfg(envCfg)
            env.move_to(dst_env_tag)
            Util.print(f"Renamed to: {dst_env_tag}")

    def checkout_env(self, env_tag: str):
        """Checkout an environment."""
        envCfg = self.configMng.get_environment(env_tag)
        if not envCfg:
            Util.print_error_and_die(
                f"Environment with tag '{env_tag}' does not exist."
            )
        else:
            envCfg.active = True
            self.configMng.set_active_environment(env_tag)
            Util.print(f"Switched to: {env_tag}")

    def delete_env(self, env_tag: str):
        """Delete an environment."""
        envCfg = self.configMng.get_environment(env_tag)
        if not envCfg:
            Util.print_error_and_die(
                f"Environment with tag '{env_tag}' does not exist."
            )
        else:
            if not self.cli_flags["yes"]:
                if not Util.confirm(
                    f"""Are you sure you want to
                      delete the environment '{env_tag}'?"""
                ):
                    Util.console.print("Aborted.", style="yellow")
                    return

            env = self.envFactory.new_environment_cfg(envCfg)
            env.delete()
            Util.print(f"Deleted: {env.envCfg.tag}")

    def list_envs(self):
        """List all available environments."""
        envs = self.configMng.get_environments()
        if not envs:
            Util.print("No environments available.")
            return
        Util.print("Available environments:")
        for env in envs:
            Util.print(f" - {env.tag} ({env.template})")

    def start_env(self, envCfg: EnvironmentCfg):
        """Start an environment."""
        pass

    def halt_env(self, envCfg: EnvironmentCfg):
        """Halt an environment."""
        pass

    def reload_env(self, envCfg: EnvironmentCfg):
        """Reload an environment."""
        pass

    def status_env(self, envCfg: EnvironmentCfg):
        """Get environment status."""
        pass

    def add_service(
        self,
        env_tag: Optional[str],
        svc_tag: str,
        svc_template: Optional[str],
        svc_class: Optional[str],
    ):
        """Add a service to an environment."""
        env = self.get_environment(env_tag)

        if env:
            envCfg = env.to_config()
            if env.get_service(svc_tag):
                Util.print_error_and_die(
                    f"""Service with tag '{svc_tag}' already
                    exists in environment '{envCfg.tag}'."""
                )
            svc_type_cfg = self.configMng.get_service_template(
                svc_template if svc_template else Constants.SVC_TEMPLATE_DEFAULT
            )

            if svc_type_cfg:
                svcCfg = ServiceCfg.from_service_template(
                    svc_type_cfg, svc_tag, svc_class
                )
            else:
                svcCfg = ServiceCfg.from_tag(
                    (
                        svc_template
                        if svc_template
                        else Constants.SVC_TEMPLATE_DEFAULT
                    ),
                    svc_tag,
                    svc_class,
                )

            try:
                service = self.svcFactory.new_service_from_cfg(envCfg, svcCfg)
                env.add_service(service)
                Util.print(
                    f"Service '{service.svcCfg.tag}' added to "
                    f"environment '{env.envCfg.tag}'."
                )
            except ValueError as e:
                Util.print_error_and_die(f"Failed to create service: {e}")
