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


import json
import os
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from util import Constants, Util


@dataclass
class UpstreamCfg:
    """
    Represents an upstream service configuration.
    """

    type: str
    tag: str
    enabled: bool
    properties: Optional[dict[str, str]] = field(default_factory=dict)


@dataclass
class ServiceTypeCfg:
    """
    Represents a service type configuration.
    """

    type: str
    image: str
    ingress: Optional[bool] = None
    empty_env: Optional[str] = None
    envvars: Optional[dict[str, str]] = field(default_factory=dict)
    ports: Optional[dict[str, str]] = field(default_factory=dict)
    properties: Optional[dict[str, str]] = field(default_factory=dict)
    subject_alternative_name: Optional[str] = None


@dataclass
class ServiceCfg:
    """
    Represents a service configuration.
    """

    type: str
    tag: str
    image: str
    ingress: Optional[bool] = None
    empty_env: Optional[str] = None
    envvars: Optional[dict[str, str]] = field(default_factory=dict)
    ports: Optional[dict[str, str]] = field(default_factory=dict)
    properties: Optional[dict[str, str]] = field(default_factory=dict)
    subject_alternative_name: Optional[str] = None
    upstreams: Optional[List[UpstreamCfg]] = field(default_factory=list)


@dataclass
class EnvironmentCfg:
    """
    Represents an environment configuration.
    """

    type: str
    tag: str
    services: Optional[List[ServiceCfg]]
    archived: bool
    active: bool

    @classmethod
    def from_tag(cls, env_type: str, env_tag: str):
        """
        Creates an EnvironmentCfg object from a tag.
        """
        return EnvironmentCfg(
            type=env_type,
            tag=env_tag,
            services=[],
            archived=False,
            active=False,
        )

    @classmethod
    def from_other(cls, other: "EnvironmentCfg"):
        """
        Creates a copy of an existing EnvironmentCfg object.
        """
        return cls(
            type=other.type,
            tag=other.tag,
            services=deepcopy(other.services),
            archived=other.archived,
            active=other.active,
        )


@dataclass
class ShpdRegistryCfg:
    """
    Represents the configuration for the shepherd registry.
    """

    ftp_server: str
    ftp_user: str
    ftp_psw: str
    ftp_shpd_path: str
    ftp_env_imgs_path: str


@dataclass
class CACfg:
    """
    Represents the configuration for the Certificate Authority.
    """

    country: str
    state: str
    locality: str
    organization: str
    organizational_unit: str
    common_name: str
    email: str
    passphrase: str


@dataclass
class CertCfg:
    """
    Represents the configuration for the certificate.
    """

    country: str
    state: str
    locality: str
    organization: str
    organizational_unit: str
    common_name: str
    email: str
    subject_alternative_names: List[str] = field(default_factory=list)


@dataclass
class Config:
    """
    Represents the shepherd configuration.
    """

    shpd_registry: ShpdRegistryCfg
    host_inet_ip: str
    domain: str
    dns_type: str
    ca: CACfg
    cert: CertCfg
    service_types: Optional[List[ServiceTypeCfg]] = field(default_factory=list)
    envs: List[EnvironmentCfg] = field(default_factory=list)


def parse_config(json_str: str) -> Config:
    """
    Parses a JSON string into a `Config` object.
    """

    data = json.loads(json_str)

    def parse_upstream(item: Any) -> UpstreamCfg:
        return UpstreamCfg(
            type=item["type"],
            tag=item["tag"],
            properties=item.get("properties", {}),
            enabled=item["enabled"],
        )

    def parse_service_type(item: Any) -> ServiceTypeCfg:
        return ServiceTypeCfg(
            type=item["type"],
            image=item["image"],
            ingress=item.get("ingress"),
            empty_env=item.get("empty_env"),
            envvars=item.get("envvars", {}),
            ports=item.get("ports", {}),
            properties=item.get("properties", {}),
            subject_alternative_name=item.get("subject_alternative_name"),
        )

    def parse_service(item: Any) -> ServiceCfg:
        return ServiceCfg(
            type=item["type"],
            tag=item["tag"],
            image=item["image"],
            ingress=item.get("ingress"),
            empty_env=item.get("empty_env"),
            envvars=item.get("envvars", {}),
            ports=item.get("ports", {}),
            properties=item.get("properties", {}),
            subject_alternative_name=item.get("subject_alternative_name"),
            upstreams=[
                parse_upstream(upstream)
                for upstream in item.get("upstreams", [])
            ],
        )

    def parse_environment(item: Any) -> EnvironmentCfg:
        return EnvironmentCfg(
            type=item["type"],
            tag=item["tag"],
            services=[
                parse_service(service) for service in item.get("services", [])
            ],
            archived=item["archived"],
            active=item["active"],
        )

    def parse_shpd_registry(item: Any) -> ShpdRegistryCfg:
        return ShpdRegistryCfg(
            ftp_server=item["ftp_server"],
            ftp_user=item["ftp_user"],
            ftp_psw=item["ftp_psw"],
            ftp_shpd_path=item["ftp_shpd_path"],
            ftp_env_imgs_path=item["ftp_env_imgs_path"],
        )

    def parse_ca_config(item: Any) -> CACfg:
        return CACfg(
            country=item["country"],
            state=item["state"],
            locality=item["locality"],
            organization=item["organization"],
            organizational_unit=item["organizational_unit"],
            common_name=item["common_name"],
            email=item["email"],
            passphrase=item["passphrase"],
        )

    def parse_cert_config(item: Any) -> CertCfg:
        return CertCfg(
            country=item["country"],
            state=item["state"],
            locality=item["locality"],
            organization=item["organization"],
            organizational_unit=item["organizational_unit"],
            common_name=item["common_name"],
            email=item["email"],
            subject_alternative_names=item.get("subject_alternative_names", []),
        )

    return Config(
        service_types=[
            parse_service_type(service_type)
            for service_type in data.get("service_types", [])
        ],
        shpd_registry=parse_shpd_registry(data["shpd_registry"]),
        host_inet_ip=data["host_inet_ip"],
        domain=data["domain"],
        dns_type=data["dns_type"],
        ca=parse_ca_config(data["ca"]),
        cert=parse_cert_config(data["cert"]),
        envs=[parse_environment(env) for env in data["envs"]],
    )


class ConfigMng:
    """
    Manages the loading, substitution, and storage of configuration data.

    This class handles:
    - Reading user-defined key-value pairs from a configuration values file.
    - Loading a JSON configuration file and replacing placeholders with
      user-defined values.
    - Storing the final configuration, converting known values back into
      placeholders.
    """

    file_values_path: str
    original_placeholders: Dict[str, str] = {}
    config: Config

    def __init__(self, file_values_path: str):
        """
        Initializes the configuration manager.

        :param shpd_dir: The base directory where configuration files
        are stored.
        """
        self.file_values_path = os.path.expanduser(file_values_path)
        self.values = self.load_user_values()
        self.constants = Constants(
            SHPD_CONFIG_VALUES_FILE=self.file_values_path,
            SHPD_DIR=os.path.expanduser(self.values["shpd_dir"]),
        )

    def load_user_values(self) -> Dict[str, str]:
        """
        Loads user-defined configuration values from a file in key=value format.

        Reads the configuration values file and returns a dictionary of
        key-value pairs.
        Ignores empty lines and comments (lines starting with '#').

        :return: A dictionary containing user-defined key-value pairs.

        :raises FileNotFoundError: If the configuration values file is missing.
        :raises ValueError: If a line is incorrectly formatted
        (i.e., missing '=' separator).
        """
        user_values: Dict[str, str] = {}

        if not os.path.exists(self.file_values_path):
            Util.print_error_and_die(
                f"'{self.file_values_path}' does not exist."
            )

        try:
            with open(self.file_values_path, "r") as file:
                for line in file:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    if "=" in line:
                        key, value = line.split("=", 1)
                        user_values[key.strip()] = value.strip()
                    else:
                        raise ValueError(
                            f"Invalid line format in config file: '{line}'"
                        )
        except Exception as e:
            Util.print_error_and_die(f"Error reading configuration file: {e}")

        return user_values

    def substitute_placeholders(
        self, config_data: Dict[Any, Any], values: Dict[str, str]
    ) -> Dict[Any, Any]:
        """
        Replaces placeholders in the configuration data with actual values.

        This function performs a recursive traversal of the configuration
        dictionary, replacing placeholders in the format '${key}' with
        their corresponding values from the provided dictionary.
        If a placeholder key is not found, it is replaced with `None`.

        :param config_data: The configuration dictionary containing
        placeholders.
        :param values: A dictionary of user-defined values used to replace
        placeholders.
        :return: A new dictionary with placeholders replaced by actual values.
        """

        def replace(value: Any, path: str = "") -> Any:
            """
            Helper function to recursively replace placeholders in
            nested structures.
            Tracks original placeholders for potential restoration
            during saving.
            """
            if (
                isinstance(value, str)
                and value.startswith("${")
                and value.endswith("}")
            ):
                key = value[2:-1]
                if path:
                    self.original_placeholders[path] = value
                return values.get(key, None)

            elif isinstance(value, dict):
                valDict: Dict[Any, Any] = value
                return {
                    k: replace(v, f"{path}.{k}" if path else k)
                    for k, v in valDict.items()
                }
            elif isinstance(value, list):
                valList: List[Any] = value
                return [
                    replace(v, f"{path}[{i}]") for i, v in enumerate(valList)
                ]
            return value

        return replace(config_data)

    def load_config(self) -> Config:
        """
        Loads and processes the configuration file.

        Steps:
        1. Reads the JSON configuration file.
        2. Loads user-defined values from the values file.
        3. Replaces placeholders in the configuration with actual values.
        4. Parses the resulting JSON into a `Config` object.

        :return: A `Config` object with placeholders resolved.

        :raises FileNotFoundError: If the configuration file is missing.
        :raises ValueError: If the configuration file is malformed.
        """
        with open(self.constants.SHPD_CONFIG_FILE, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        substituted_config = self.substitute_placeholders(
            config_data, self.values
        )

        return parse_config(json.dumps(substituted_config))

    def load(self):
        """
        Loads the configuration and stores it in the `config` attribute.
        """
        self.config = self.load_config()

    def store_config(self, config: Config):
        """
        Stores the modified configuration while preserving placeholders.

        This function:
        - Converts the `Config` object into a dictionary.
        - Restores placeholders for known keys (those tracked in
        `original_placeholders`).
        - Writes the final configuration back to a JSON file.

        :param config: The `Config` object to be saved.
        """

        def replace_keys_with_placeholders(
            config: Any, parent_key: str = ""
        ) -> Any:
            """
            Recursively traverses the configuration dictionary, restoring
            placeholders for keys stored in `original_placeholders`.
            """
            if isinstance(config, dict):
                new_dict: Dict[Any, Any] = {}
                configDict: Dict[Any, Any] = config
                for k, v in configDict.items():
                    full_key = f"{parent_key}.{k}" if parent_key else k
                    new_dict[k] = (
                        replace_keys_with_placeholders(v, full_key)
                        if isinstance(v, (dict, list))
                        else self.original_placeholders.get(full_key, v)
                    )
                return new_dict
            elif isinstance(config, list):
                configList: List[Any] = config
                return [
                    replace_keys_with_placeholders(item, f"{parent_key}[{i}]")
                    for i, item in enumerate(configList)
                ]

        processed_config = replace_keys_with_placeholders(asdict(config))

        with open(self.constants.SHPD_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(processed_config, f, indent=2)

    def store(self):
        """
        Stores the current configuration by calling `store_config`.
        """
        self.store_config(self.config)

    def get_environment(self, envTag: str) -> Optional[EnvironmentCfg]:
        """
        Retrieves an environment configuration by its tag.

        :param envTag: The tag of the environment to retrieve.
        :return: The environment configuration if found, else None.
        """
        for env in self.config.envs:
            if env.tag == envTag:
                return env
        return None

    def get_environments(self) -> List[EnvironmentCfg]:
        """
        Retrieves all environments.

        :return: A list of all environments.
        """
        return self.config.envs

    def add_environment(self, newEnv: EnvironmentCfg):
        """
        Adds a new environment to the configuration.

        :param newEnv: The new environment to be added.
        """
        self.config.envs.append(newEnv)
        self.store()

    def set_environment(
        self, envTag: str, newEnv: EnvironmentCfg
    ) -> Optional[EnvironmentCfg]:
        """
        Sets a new environment configuration.

        :param envTag: The tag of the environment to be replaced.
        :param newEnv: The new environment configuration.
        :return: The replaced environment configuration if found, else None.
        """
        for i, env in enumerate(self.config.envs):
            if env.tag == envTag:
                self.config.envs[i] = newEnv
                self.store()
                return env
        return None

    def add_or_set_environment(self, envTag: str, newEnv: EnvironmentCfg):
        """
        Adds or replaces an environment configuration.

        :param envTag: The tag of the environment to be added/replaced.
        :param newEnv: The new environment configuration.
        """
        for i, env in enumerate(self.config.envs):
            if env.tag == envTag:
                self.config.envs[i] = newEnv
                self.store()
                return
        self.config.envs.append(newEnv)
        self.store()

    def remove_environment(self, envTag: str):
        """
        Removes an environment from the configuration.

        :param envTag: The tag of the environment to be removed.
        """
        self.config.envs = [
            env for env in self.config.envs if env.tag != envTag
        ]
        self.store()

    def exists_environment(self, envTag: str) -> bool:
        """
        Checks if an environment exists in the configuration.

        :param envTag: The tag of the environment to check.
        :return: True if the environment exists, else False.
        """
        return any(env.tag == envTag for env in self.config.envs)

    def get_active_environment(self) -> Optional[EnvironmentCfg]:
        """
        Retrieves the active environment configuration.

        :return: The active environment configuration if found, else None.
        """
        for env in self.config.envs:
            if env.active:
                return env
        return None

    def set_active_environment(self, envTag: str):
        """
        Sets an environment as active.

        :param envTag: The tag of the environment to be set as active.
        """
        for env in self.config.envs:
            if env.tag == envTag:
                env.active = True
            else:
                env.active = False
        self.store()
