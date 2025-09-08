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


from config import ConfigMng
from config.config import EnvironmentCfg
from docker.docker_compose_svc import DockerComposeSvc
from service import ServiceMng


class DatabaseService(DockerComposeSvc):

    def get_sql_shell(self):
        """Get a SQL shell session."""
        pass

    def create_user(self, user: str, psw: str):
        """Create a new database user."""
        pass

    def create_directory(self, user: str, directory_name: str):
        """Create a directory object in the database."""
        pass

    def remove_user(self, user: str):
        """Drop an existing database user."""
        pass


class DatabaseMng(ServiceMng):

    def __init__(self, cli_flags: dict[str, bool], configMng: ConfigMng):
        self.cli_flags = cli_flags
        self.configMng = configMng
        pass

    def sql_shell_svc(self, envCfg: EnvironmentCfg, svc_tag: str):
        """Get a SQL shell session."""
        pass

    def create_database_user_svc(
        self, envCfg: EnvironmentCfg, svc_tag: str, user: str, psw: str
    ):
        """Create a new database user."""
        pass

    def create_database_directory_svc(
        self,
        envCfg: EnvironmentCfg,
        svc_tag: str,
        user: str,
        directory_name: str,
    ):
        """Create a directory object in a database."""
        pass

    def remove_database_user_svc(
        self, envCfg: EnvironmentCfg, svc_tag: str, user: str
    ):
        """Drop an existing user."""
        pass
