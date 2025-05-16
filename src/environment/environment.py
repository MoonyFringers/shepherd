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
from typing import Dict, List

from config import ConfigMng, EnvironmentCfg
from service import Service
from util import Util


class Environment(ABC):

    type: str
    tag: str
    archived: bool
    active: bool
    services: List[Service]

    def __init__(self, configMng: ConfigMng, envCfg: EnvironmentCfg):
        self.configMng = configMng
        self.type = envCfg.type
        self.tag = envCfg.tag
        self.archived = envCfg.archived
        self.active = envCfg.active
        self.services = []

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
        return EnvironmentCfg(
            type=self.type,
            tag=self.tag,
            services=[service.to_config() for service in self.services],
            archived=self.archived,
            active=self.active,
        )

    def get_dir(self) -> str:
        """Return the directory of the environment."""
        return os.path.join(self.configMng.constants.SHPD_ENVS_DIR, self.tag)

    def get_dir_for_tag(self, env_tag: str) -> str:
        """Return the directory for the environment with a given tag."""
        return os.path.join(self.configMng.constants.SHPD_ENVS_DIR, env_tag)

    def realize(self):
        """Realize the environment."""
        Util.create_dir(
            self.get_dir(),
            self.tag,
        )
        self.sync_config()

    def realize_from(self, src_env: Environment):
        """Realize the environment."""
        Util.copy_dir(src_env.get_dir(), self.get_dir())
        self.sync_config()

    def move_to(self, dst_env_tag: str):
        """Move the environment to a new tag."""
        Util.move_dir(self.get_dir(), self.get_dir_for_tag(dst_env_tag))
        self.configMng.remove_environment(self.tag)
        self.tag = dst_env_tag
        self.sync_config()

    def delete(self):
        """Delete the environment."""
        Util.remove_dir(self.get_dir())
        self.configMng.remove_environment(self.tag)

    def sync_config(self):
        """Sync the environment configuration."""
        self.configMng.add_or_set_environment(self.tag, self.to_config())

    def get_tag(self) -> str:
        """Return the tag of the environment."""
        return self.tag

    def set_tag(self, tag: str):
        """Set the tag of the environment."""
        self.tag = tag

    def is_archived(self) -> bool:
        return self.archived

    def set_archived(self, archived: bool):
        self.archived = archived

    def is_active(self) -> bool:
        return self.active

    def set_active(self, active: bool):
        self.active = active

    def add_service(self, service: Service):
        """Add a service to the environment."""
        self.services.append(service)

    def remove_service(self, service: Service):
        """Remove a service from the environment."""
        self.services.remove(service)

    def get_services(self) -> List[Service]:
        """Return the list of services in the environment."""
        return self.services


class EnvironmentFactory(ABC):
    """
    Factory class for environments.
    """

    def __init__(self, config: ConfigMng):
        self.config = config

    @abstractmethod
    def new_environment(self, env_type: str, env_tag: str) -> Environment:
        """
        Create a new environment.
        """
        pass

    @abstractmethod
    def get_environment(self, envCfg: EnvironmentCfg) -> Environment:
        """
        Get an environment.
        """
        pass


class EnvironmentMng:

    def __init__(
        self,
        cli_flags: Dict[str, bool],
        configMng: ConfigMng,
        envFactory: EnvironmentFactory,
    ):
        self.cli_flags = cli_flags
        self.configMng = configMng
        self.envFactory = envFactory

    def init_env(self, env_type: str, env_tag: str):
        """Initialize an environment."""
        if self.configMng.get_environment(env_tag):
            Util.print_error_and_die(
                f"Environment with tag '{env_tag}' already exists."
            )
        env = self.envFactory.new_environment(env_type, env_tag)
        env.realize()
        Util.print(f"{env_tag}")

    def clone_env(self, src_env_tag: str, dst_env_tag: str):
        """Clone an environment."""
        envCfg = self.configMng.get_environment(src_env_tag)
        if not envCfg:
            Util.print_error_and_die(
                f"Environment with tag '{src_env_tag}' does not exist."
            )
        else:
            env = self.envFactory.get_environment(envCfg)
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
            env = self.envFactory.get_environment(envCfg)
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

            env = self.envFactory.get_environment(envCfg)
            env.delete()
            Util.print(f"Deleted: {env.tag}")

    def set_all_envs_non_active(self):
        """Set all environments as non-active."""
        envs = self.configMng.get_environments()
        for env in envs:
            env.active = False
        self.configMng.store()
        Util.print("All environments set to non-active.")

    def list_envs(self):
        """List all available environments."""
        envs = self.configMng.get_environments()
        if not envs:
            Util.print("No environments available.")
            return
        Util.print("Available environments:")
        for env in envs:
            Util.print(f" - {env.tag} ({env.type})")

    def start_env(self):
        """Start an environment."""
        pass

    def halt_env(self):
        """Halt an environment."""
        pass

    def reload_env(self):
        """Reload an environment."""
        pass

    def status_env(self):
        """Get environment status."""
        pass
