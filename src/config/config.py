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


import json
import os
import re
from copy import copy, deepcopy
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Dict, Match, Optional, cast

from glom import glom  # type: ignore[import]

from util import Constants, Util

# Regular expression for variables in .shpd.conf or environment variables
# es: ${VAR_NAME}
VAR_RE = re.compile(r"\$\{([^}]+)\}")

# Regular expression for references inside .shpd.json
# es: #{REF_NAME}
REF_RE = re.compile(r"#\{([^}]+)\}")

# Reference constants
REF_CFG: str = "cfg"
REF_ENV: str = "env"
REF_SVC: str = "svc"
REF_VOL: str = "vol"
REF_NET: str = "net"


REF_MAP: dict[str, str] = {
    "Config": REF_CFG,
    "EnvironmentCfg": REF_ENV,
    "ServiceCfg": REF_SVC,
    "VolumeCfg": REF_VOL,
    "NetworkCfg": REF_NET,
}


def str_to_bool(val: str) -> bool:
    if val == "true":
        return True
    if val == "false":
        return False
    raise ValueError(
        f"Invalid boolean string: {val!r}. Expected 'true' or 'false'."
    )


def bool_to_str(val: bool) -> str:
    return "true" if val else "false"


def cfg_asdict(obj: Any) -> dict[str, Any] | list[Any] | Any:
    """
    Recursively convert a dataclass (including Resolvable objects) into a
    plain Python structure of dicts, lists, and primitives, with special
    handling for fields marked as boolean.

    Behavior:
        • Traverses dataclasses, lists, and dictionaries recursively.
        • Fields with ``metadata={"boolify": True}`` that contain the strings
          "true" or "false" (case-insensitive) are converted to actual
          booleans. Any other string values are preserved as-is.
        • All nested dataclasses are converted to dicts using the same logic.
        • Lists and dicts are deep-converted element by element.

    Args:
        obj: The object to convert. May be a dataclass instance, list,
             dictionary, or primitive value.

    Returns:
        A representation of the input object where all dataclasses are replaced
        with dictionaries, lists are deep-converted, and booleans are parsed
        from marked string fields.

    Example:
        @dataclass
        class Config:
            flag: str = field(metadata={"boolify": True})
            name: str

        cfg = Config(flag="true", name="test")
        cfg_asdict(cfg)  # -> {"flag": True, "name": "test"}

    Notes:
        • Dictionary keys are left untouched.
        • For boolean conversion, only exact string matches of "true" or "false"
          (case-insensitive) are considered.
    """

    if is_dataclass(obj):
        result: dict[str, Any] = {}
        for f in fields(obj):
            val = getattr(obj, f.name)
            if f.metadata.get("boolify") and isinstance(val, str):
                if val.lower() == "true":
                    result[f.name] = True
                elif val.lower() == "false":
                    result[f.name] = False
                else:
                    # keep original string
                    result[f.name] = val
            else:
                result[f.name] = cfg_asdict(val)
        return result
    elif isinstance(obj, list):
        return [cfg_asdict(v) for v in cast(list[Any], obj)]
    elif isinstance(obj, dict):
        return {k: cfg_asdict(v) for k, v in cast(dict[str, Any], obj).items()}
    else:
        return obj


@dataclass
class Resolvable:
    """
    A mixin class for dataclasses that supports deferred resolution of string
    placeholders from a mapping, environment variables, or references to other
    configuration objects.

    This class enables any nested dataclass structure to have string fields
    containing placeholders of the form ``${VAR_NAME}`` or references of the
    form ``#{REF_NAME}``, both of which can be dynamically resolved at
    attribute access time. Resolution can be toggled on or off.

    Supported Placeholders:
        • Environment / mapping variables:
          ``${VAR_NAME}`` → replaced from the resolver mapping or, if missing,
          from process environment variables.
        • Object references:
          ``#{REF_TYPE.path.to.attr}`` → replaced by accessing attributes from
          other `Resolvable` objects within the same configuration tree. The
          `REF_TYPE` is a symbolic root (e.g., ``env``, ``svc``, ``vol``,
          ``net``) automatically registered in the reference map.

    Features:
        • Recursive traversal of dataclasses, lists, and dicts to propagate a
          variable mapping, reference map, and resolution state.
        • Placeholder substitution using a resolver mapping (dict[str, str])
          with environment fallback.
        • Reference substitution using `REF_MAP` to navigate to related
          configuration objects.
        • Support for setting/unsetting resolution state without modifying
          field values.
        • Resolution is performed lazily when accessing attributes.

    Key Methods:
        set_resolver(mapping):
            Set the placeholder resolver mapping and mark the object
            as resolved.

        set_resolved():
            Mark the object (and its nested structures) as resolved, causing
            future string accesses to have placeholders and references
            substituted.

        set_unresolved():
            Mark the object (and its nested structures) as unresolved,
            returning raw placeholder and reference strings.

    Example:
        @dataclass
        class ServiceCfg(Resolvable):
            tag: str
            service_class: str

        cfg = ServiceCfg(tag="${HOME}/data", service_class="#{env.tag}")
        cfg.set_resolver({"HOME": "/tmp"})
        cfg.set_resolved()

        print(cfg.tag)            # -> "/tmp/data"
        print(cfg.service_class)  # -> "alice"   (resolved from env.tag)

    Implementation Notes:
        • The `_walk_and_set` method traverses the structure to propagate the
          resolver mapping, reference map, and resolution state.
        • The `_set_refMap` method maintains the mapping of reference roots
          (env, svc, vol, net) to their corresponding objects.
        • The `__getattribute__` method intercepts attribute access to perform
          lazy resolution only when `_resolved` is True.
        • Lists and dictionaries are deeply resolved, but dictionary keys are
          assumed to be literal strings without placeholders.
    """

    def _set_refMap(
        self, refMap: dict[str, "Resolvable"] | None
    ) -> dict[str, "Resolvable"]:
        lRefMap = copy(refMap) if refMap else dict[str, Resolvable]()
        object.__setattr__(self, "_refMap", lRefMap)
        if self.__class__.__name__ in REF_MAP:
            lRefMap[REF_MAP[self.__class__.__name__]] = self
        return lRefMap

    def _walk_and_set(
        self,
        resolver: dict[str, str] | None,
        resolved: bool,
        obj: Any = None,
        refMap: dict[str, "Resolvable"] | None = None,
    ):
        if obj is None:
            obj = self

        if is_dataclass(obj) and isinstance(obj, Resolvable):
            lRefMap = obj._set_refMap(refMap)
            object.__setattr__(obj, "_resolver", resolver or os.environ)
            for f in fields(obj):
                if fVal := getattr(obj, f.name, None):
                    self._walk_and_set(resolver, resolved, fVal, lRefMap)
            object.__setattr__(obj, "_resolved", resolved)

        elif isinstance(obj, list):
            for item in cast(list[Any], obj):
                self._walk_and_set(resolver, resolved, item, refMap)

        elif isinstance(obj, dict):
            for _, v in cast(dict[str, Any], obj).items():
                self._walk_and_set(resolver, resolved, v, refMap)

    def set_resolved(self):
        self._walk_and_set(getattr(self, "_resolver", None), True)

    def set_unresolved(self):
        self._walk_and_set(getattr(self, "_resolver", None), False)

    def set_resolver(self, mapping: dict[str, str] | None):
        self._walk_and_set(mapping, True)

    def _is_resolved(self) -> bool:
        return getattr(self, "_resolved", False)

    def _resolve_str(self, s: str) -> str:
        mapping = getattr(self, "_resolver", None) or os.environ
        refMap = cast(dict[str, Resolvable], getattr(self, "_refMap", {}))

        def var_repl(match: Match[str]) -> str:
            key = match.group(1)
            if key in mapping:
                return str(mapping[key])
            return os.environ.get(key, match.group(0))

        def ref_repl(match: Match[str]) -> str:
            expr = match.group(1)  # e.g. "env.tag"
            parts = expr.split(".", 1)
            root = parts[0]
            if root not in refMap:
                return match.group(0)  # return untouched
            target = refMap[root]
            try:
                return cast(
                    str, glom(target, parts[1] if len(parts) > 1 else "")
                )
            except Exception:
                return match.group(0)

        # first resolve ${...}, then #{...}
        s = VAR_RE.sub(var_repl, s)
        s = REF_RE.sub(ref_repl, s)
        return s

    def _expand_path(self, name: str, value: str) -> str:
        """Expand paths if field name ends with '_path'."""
        value = self._resolve_str(value)
        if name.endswith("_path"):
            return os.path.expanduser(value)
        return value

    def __getattribute__(self, name: str) -> Any:
        if (
            name.startswith("_")
            or name
            in (
                "set_resolver",
                "set_resolved",
                "set_unresolved",
            )
            or not self._is_resolved()
        ):
            return object.__getattribute__(self, name)

        val = object.__getattribute__(self, name)

        # resolve plain strings with placeholders
        if isinstance(val, str):
            return self._expand_path(name, val)

        # pass resolver to nested dataclasses
        elif is_dataclass(val) and isinstance(val, Resolvable):
            return val

        # resolve lists
        elif isinstance(val, list):
            resultList: list[Any] = []
            for v in cast(list[Any], val):
                if isinstance(v, str):
                    resultList.append(self._resolve_str(v))
                elif is_dataclass(v) and isinstance(v, Resolvable):
                    resultList.append(v)
                else:
                    resultList.append(v)
            return resultList

        # resolve dicts
        elif isinstance(val, dict):
            resultDict: dict[str, Any] = {}
            for k, v in cast(dict[str, Any], val).items():
                # keys are assumed to be strings and not placeholders
                if isinstance(v, str):
                    resultDict[k] = self._resolve_str(v)
                elif is_dataclass(v) and isinstance(v, Resolvable):
                    resultDict[k] = v
                elif isinstance(v, list):
                    # resolve strings and dataclasses
                    # inside lists in dict values
                    lst: list[Any] = []
                    for item in cast(list[Any], v):
                        if isinstance(item, str):
                            lst.append(self._resolve_str(item))
                        elif is_dataclass(item) and isinstance(
                            item, Resolvable
                        ):
                            lst.append(item)
                        else:
                            lst.append(item)
                    resultDict[k] = lst
                else:
                    resultDict[k] = v
            return resultDict

        return val


@dataclass
class EntityStatus(Resolvable):
    """
    Represents the status of an entity.

    - `active`: Whether this entity should be considered in
      start/stop commands.
      (Note: this is *not* the runtime state, which is queried dynamically.)
    - `archived`: Marks the entity as archived (e.g., not used anymore).
    - `triggered_config`: The rendered configuration for the target engine
      (e.g., Docker Compose). This field is populated on `start` and
      cleared on `stop`.
    """

    active: bool = False
    archived: bool = False
    triggered_config: Optional[str] = None


@dataclass
class LoggingCfg(Resolvable):
    """
    Represents the logging configuration.
    """

    file: str
    level: str
    stdout: str = field(default="false", metadata={"boolify": True})
    format: str = ""

    def is_stdout(self) -> bool:
        return str_to_bool(self.stdout)


@dataclass
class UpstreamCfg(Resolvable):
    """
    Represents an upstream service configuration.
    """

    type: str
    tag: str
    enabled: str = field(default="false", metadata={"boolify": True})
    properties: Optional[dict[str, str]] = None

    def is_enabled(self) -> bool:
        return str_to_bool(self.enabled)


@dataclass
class NetworkCfg(Resolvable):
    """
    Represents an network configuration.
    """

    tag: str
    name: Optional[str] = None
    external: str = field(default="false", metadata={"boolify": True})
    driver: Optional[str] = None  # bridge / overlay
    attachable: Optional[str] = field(default=None, metadata={"boolify": True})
    enable_ipv6: Optional[str] = field(default=None, metadata={"boolify": True})
    driver_opts: Optional[dict[str, str]] = None
    ipam: Optional[dict[str, Any]] = None  # full IPAM config

    def is_external(self) -> bool:
        return str_to_bool(self.external)

    def is_attachable(self) -> bool:
        return str_to_bool(
            self.attachable if self.attachable is not None else "false"
        )

    def is_enable_ipv6(self) -> bool:
        return str_to_bool(
            self.enable_ipv6 if self.enable_ipv6 is not None else "false"
        )


@dataclass
class VolumeCfg(Resolvable):
    """
    Represents a volume configuration.
    """

    tag: str
    external: str = field(default="false", metadata={"boolify": True})
    name: Optional[str] = None
    driver: Optional[str] = None
    driver_opts: Optional[dict[str, str]] = None
    labels: Optional[dict[str, str]] = None

    def is_external(self) -> bool:
        return str_to_bool(self.external)


@dataclass
class ServiceTemplateCfg(Resolvable):
    """
    Represents a service template configuration.
    """

    tag: str
    factory: str
    image: str
    hostname: Optional[str] = None
    container_name: Optional[str] = None
    labels: Optional[list[str]] = None
    workdir: Optional[str] = None
    volumes: Optional[list[str]] = None
    ingress: Optional[str] = field(default=None, metadata={"boolify": True})
    empty_env: Optional[str] = None
    environment: Optional[list[str]] = None
    ports: Optional[list[str]] = None
    properties: Optional[dict[str, str]] = None
    networks: Optional[list[str]] = None
    extra_hosts: Optional[list[str]] = None
    subject_alternative_name: Optional[str] = None

    def is_ingress(self) -> bool:
        return str_to_bool(
            self.ingress if self.ingress is not None else "false"
        )


@dataclass
class ServiceTemplateRefCfg(Resolvable):
    """
    Represents a service template reference.
    """

    template: str
    tag: str


@dataclass
class ServiceCfg(Resolvable):
    """
    Represents a service configuration.
    """

    template: str
    factory: str
    tag: str
    service_class: Optional[str] = None
    image: str = ""
    hostname: Optional[str] = None
    container_name: Optional[str] = None
    labels: Optional[list[str]] = None
    workdir: Optional[str] = None
    volumes: Optional[list[str]] = None
    ingress: Optional[str] = field(default=None, metadata={"boolify": True})
    empty_env: Optional[str] = None
    environment: Optional[list[str]] = None
    ports: Optional[list[str]] = None
    properties: Optional[dict[str, str]] = None
    networks: Optional[list[str]] = None
    extra_hosts: Optional[list[str]] = None
    subject_alternative_name: Optional[str] = None
    upstreams: Optional[list[UpstreamCfg]] = None
    status: EntityStatus = field(
        default_factory=lambda: EntityStatus(active=True)
    )

    def is_ingress(self) -> bool:
        return str_to_bool(
            self.ingress if self.ingress is not None else "false"
        )


@dataclass
class EnvironmentTemplateCfg(Resolvable):
    """
    Represents an environment template configuration.
    """

    tag: str
    factory: str
    service_templates: Optional[list[ServiceTemplateRefCfg]]
    networks: Optional[list[NetworkCfg]]
    volumes: Optional[list[VolumeCfg]]


@dataclass
class EnvironmentCfg(Resolvable):
    """
    Represents an environment configuration.
    """

    template: str
    factory: str
    tag: str
    services: Optional[list[ServiceCfg]]
    networks: Optional[list[NetworkCfg]]
    volumes: Optional[list[VolumeCfg]]
    status: EntityStatus = field(default_factory=EntityStatus)

    def get_service(self, svcTag: str) -> Optional[ServiceCfg]:
        """
        Retrieves a service configuration by its tag.

        :param svcTag: The tag of the service to retrieve.
        :return: The service configuration if found, else None.
        """
        if not self.services:
            return None
        for svc in self.services:
            if svc.tag == svcTag:
                return svc
        return None


@dataclass
class StagingAreaCfg(Resolvable):
    """
    Represents the configuration for the staging area.
    """

    volumes_path: str
    images_path: str


@dataclass
class ShpdRegistryCfg(Resolvable):
    """
    Represents the configuration for the shepherd registry.
    """

    ftp_server: str
    ftp_user: str
    ftp_psw: str
    ftp_shpd_path: str
    ftp_env_imgs_path: str


@dataclass
class CACfg(Resolvable):
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
class CertCfg(Resolvable):
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
    subject_alternative_names: Optional[list[str]] = None


@dataclass
class Config(Resolvable):
    """
    Represents the shepherd configuration.
    """

    logging: LoggingCfg
    shpd_registry: ShpdRegistryCfg
    envs_path: str
    volumes_path: str
    host_inet_ip: str
    domain: str
    dns_type: str
    ca: CACfg
    cert: CertCfg
    staging_area: StagingAreaCfg
    env_templates: Optional[list[EnvironmentTemplateCfg]] = None
    service_templates: Optional[list[ServiceTemplateCfg]] = None
    envs: list[EnvironmentCfg] = field(default_factory=list[EnvironmentCfg])


def parse_config(json_str: str) -> Config:
    """
    Parses a JSON string into a `Config` object.
    """

    data = json.loads(json_str)

    def parse_status(item: Any) -> EntityStatus:
        return EntityStatus(
            active=item["active"],
            archived=item["archived"],
            triggered_config=item.get("triggered_config"),
        )

    def parse_logging(item: Any) -> LoggingCfg:
        return LoggingCfg(
            file=item["file"],
            level=item["level"],
            stdout=(
                bool_to_str(val)
                if isinstance(val := item["stdout"], bool)
                else val
            ),
            format=item["format"],
        )

    def parse_upstream(item: Any) -> UpstreamCfg:
        return UpstreamCfg(
            type=item["type"],
            tag=item["tag"],
            properties=item.get("properties", {}),
            enabled=(
                bool_to_str(val)
                if isinstance(val := item["enabled"], bool)
                else val
            ),
        )

    def parse_service_template(item: Any) -> ServiceTemplateCfg:
        return ServiceTemplateCfg(
            tag=item["tag"],
            factory=item["factory"],
            image=item["image"],
            hostname=item.get("hostname"),
            container_name=item.get("container_name"),
            labels=item.get("labels", []),
            workdir=item.get("workdir"),
            volumes=item.get("volumes", []),
            ingress=(
                bool_to_str(val)
                if isinstance(val := item["ingress"], bool)
                else val
            ),
            empty_env=item.get("empty_env"),
            environment=item.get("environment", []),
            ports=item.get("ports", []),
            properties=item.get("properties", {}),
            networks=item.get("networks", []),
            extra_hosts=item.get("extra_hosts", []),
            subject_alternative_name=item.get("subject_alternative_name"),
        )

    def parse_service(item: Any) -> ServiceCfg:
        return ServiceCfg(
            template=item["template"],
            factory=item["factory"],
            tag=item["tag"],
            service_class=item.get("service_class"),
            image=item["image"],
            hostname=item.get("hostname"),
            container_name=item.get("container_name"),
            labels=item.get("labels", []),
            workdir=item.get("workdir"),
            volumes=item.get("volumes", []),
            ingress=(
                bool_to_str(val)
                if isinstance(val := item["ingress"], bool)
                else val
            ),
            empty_env=item.get("empty_env"),
            environment=item.get("environment", []),
            ports=item.get("ports", []),
            properties=item.get("properties", {}),
            networks=item.get("networks", []),
            extra_hosts=item.get("extra_hosts", []),
            subject_alternative_name=item.get("subject_alternative_name"),
            upstreams=[
                parse_upstream(upstream)
                for upstream in item.get("upstreams", [])
            ],
            status=parse_status(item["status"]),
        )

    def parse_network(item: Any) -> NetworkCfg:
        return NetworkCfg(
            tag=item["tag"],
            name=item.get("name", None),
            external=(
                bool_to_str(val)
                if isinstance(val := item["external"], bool)
                else val
            ),
            driver=item.get("driver", None),
            attachable=(
                bool_to_str(val)
                if isinstance(val := item.get("attachable"), bool)
                else val
            ),
            enable_ipv6=(
                bool_to_str(val)
                if isinstance(val := item.get("enable_ipv6"), bool)
                else val
            ),
            driver_opts=item.get("driver_opts"),
            ipam=item.get("ipam"),
        )

    def parse_volume(item: Any) -> VolumeCfg:
        return VolumeCfg(
            tag=item["tag"],
            external=(
                bool_to_str(val)
                if isinstance(val := item["external"], bool)
                else val
            ),
            name=item.get("name"),
            driver=item.get("driver"),
            driver_opts=item.get("driver_opts"),
            labels=item.get("labels"),
        )

    def parse_service_template_refs(item: Any) -> ServiceTemplateRefCfg:
        return ServiceTemplateRefCfg(template=item["template"], tag=item["tag"])

    def parse_environment_template(item: Any) -> EnvironmentTemplateCfg:
        return EnvironmentTemplateCfg(
            tag=item["tag"],
            factory=item["factory"],
            service_templates=[
                parse_service_template_refs(svc_templ_ref)
                for svc_templ_ref in item.get("service_templates", [])
            ],
            networks=[
                parse_network(network) for network in item.get("networks", [])
            ],
            volumes=[
                parse_volume(volume) for volume in item.get("volumes", [])
            ],
        )

    def parse_staging_area(item: Any) -> StagingAreaCfg:
        return StagingAreaCfg(
            volumes_path=item["volumes_path"],
            images_path=item["images_path"],
        )

    def parse_environment(item: Any) -> EnvironmentCfg:
        return EnvironmentCfg(
            template=item["template"],
            factory=item["factory"],
            tag=item["tag"],
            services=[
                parse_service(service) for service in item.get("services", [])
            ],
            networks=[
                parse_network(network) for network in item.get("networks", [])
            ],
            volumes=[
                parse_volume(volume) for volume in item.get("volumes", [])
            ],
            status=parse_status(item["status"]),
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
        env_templates=[
            parse_environment_template(environment_template)
            for environment_template in data.get("env_templates", [])
        ],
        service_templates=[
            parse_service_template(service_template)
            for service_template in data.get("service_templates", [])
        ],
        shpd_registry=parse_shpd_registry(data["shpd_registry"]),
        envs_path=data["envs_path"],
        volumes_path=data["volumes_path"],
        host_inet_ip=data["host_inet_ip"],
        domain=data["domain"],
        dns_type=data["dns_type"],
        ca=parse_ca_config(data["ca"]),
        logging=parse_logging(data["logging"]),
        cert=parse_cert_config(data["cert"]),
        staging_area=parse_staging_area(data["staging_area"]),
        envs=[parse_environment(env) for env in data["envs"]],
    )


class ConfigMng:
    """
    Manages the loading and storage of configuration data.

    This class handles:
    - Reading user-defined key-value pairs from a configuration values file.
    - Loading a JSON configuration file.
    - Storing the configuration back to file.
    """

    file_values_path: str
    user_values: Dict[str, str]
    config: Config

    def __init__(self, file_values_path: str):
        """
        Initializes the configuration manager.

        :param shpd_path: The base directory where configuration files
        are stored.
        """
        self.file_values_path = os.path.expanduser(file_values_path)
        self.user_values = self.load_user_values()
        self.constants = Constants(
            SHPD_CONFIG_VALUES_FILE=self.file_values_path,
            SHPD_PATH=os.path.expanduser(self.user_values["shpd_path"]),
        )

    def ensure_dirs(self):
        dirs = {
            "ENVS": self.config.envs_path,
            "VOLUMES": self.config.volumes_path,
            "VOLUMES_SA": self.config.staging_area.volumes_path,
            "IMAGES_SA": self.config.staging_area.images_path,
        }
        for desc, dir_path in dirs.items():
            resolved_path = os.path.realpath(dir_path)
            if not os.path.exists(resolved_path) or not os.path.isdir(
                resolved_path
            ):
                Util.create_dir(resolved_path, desc)

    def expand_value(self, value: str, variables: Dict[str, str]) -> str:
        """
        Expand ${VAR} references using values from the given dictionary or
        environment.
        """
        pattern = re.compile(r"\$\{([^}]+)\}")

        def replacer(match: Match[str]) -> str:
            var_name = match.group(1)
            return variables.get(
                var_name, os.environ.get(var_name, match.group(0))
            )

        return pattern.sub(replacer, value)

    def load_user_values(self) -> Dict[str, str]:
        """
        Loads user-defined configuration values from a file in key=value
        format.

        Supports variable interpolation using ${VAR} referencing previous
        keys or environment variables.
        Ignores empty lines and comments (starting with '#').

        :return: A dictionary of resolved key-value pairs.

        :raises FileNotFoundError: If the config file is missing.
        :raises ValueError: If a line is invalid (missing '=' separator).
        """
        user_values: Dict[str, str] = {}

        if not os.path.exists(self.file_values_path):
            Util.print_error_and_die(
                f"'{self.file_values_path}' does not exist."
            )

        try:
            raw_values: Dict[str, str] = {}

            with open(self.file_values_path, "r") as file:
                for line in file:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    if "=" in line:
                        key, value = line.split("=", 1)
                        raw_values[key.strip()] = value.strip()
                    else:
                        raise ValueError(
                            f"Invalid line format in config file: '{line}'"
                        )

            # Expand values using previously defined keys and environment
            # variables
            for key, raw_value in raw_values.items():
                user_values[key] = self.expand_value(raw_value, user_values)

        except Exception as e:
            Util.print_error_and_die(f"Error reading configuration file: {e}")

        return user_values

    def load_config(self) -> Config:
        """
        Loads and processes the configuration file.
        Reads the JSON configuration file.

        :raises FileNotFoundError: If the configuration file is missing.
        :raises ValueError: If the configuration file is malformed.
        """
        with open(self.constants.SHPD_CONFIG_FILE, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        config = parse_config(json.dumps(config_data))
        config.set_resolver(self.user_values)
        return config

    def load(self):
        """
        Loads the configuration and stores it in the `config` attribute.
        """
        self.config = self.load_config()

    def store_config(self, config: Config):
        """
        Stores the configuration.
        Writes the final configuration back to a JSON file.

        :param config: The `Config` object to be saved.
        """
        config.set_unresolved()
        config_dict = cfg_asdict(config)
        config.set_resolved()

        with open(self.constants.SHPD_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2)

    def store(self):
        """
        Stores the current configuration by calling `store_config`.
        """
        self.store_config(self.config)

    def get_environment_template(
        self, envTemplate: str
    ) -> Optional[EnvironmentTemplateCfg]:
        """
        Retrieves an environment template configuration by its tag.

        :param envTemplate: The template of the environment to retrieve.
        :return: The environment template configuration if found, else None.
        """
        if self.config.env_templates:
            for env_template in self.config.env_templates:
                if env_template.tag == envTemplate:
                    return env_template
        return None

    def get_environment_templates(
        self,
    ) -> Optional[list[EnvironmentTemplateCfg]]:
        """
        Retrieves all environment templates.

        :return: A list of all environment templates.
        """
        if self.config.env_templates:
            return self.config.env_templates
        return None

    def get_environment_template_tags(self) -> list[str]:
        if env_templates := self.get_environment_templates():
            return sorted([env_template.tag for env_template in env_templates])
        return []

    def get_service_template(
        self, serviceTemplate: str
    ) -> Optional[ServiceTemplateCfg]:
        """
        Retrieves a service template configuration by its tag.

        :param serviceTemplate: The template of the service to retrieve.
        :return: The service template configuration if found, else None.
        """
        if self.config.service_templates:
            for svc_template in self.config.service_templates:
                if svc_template.tag == serviceTemplate:
                    return svc_template
        return None

    def get_service_templates(self) -> Optional[list[ServiceTemplateCfg]]:
        """
        Retrieves all service templates.

        :return: A list of all service templates.
        """
        if self.config.service_templates:
            return self.config.service_templates
        return None

    def get_resource_templates(self, resource_type: str) -> list[str]:
        match resource_type:
            case self.constants.RESOURCE_TYPE_SVC:
                if self.config.service_templates:
                    return sorted(
                        [
                            svc_template.tag
                            for svc_template in self.config.service_templates
                        ]
                    )
                return []
            case _:
                return []

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

    def get_environments(self) -> list[EnvironmentCfg]:
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
        self.config.set_unresolved()
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
            if env.status.active:
                return env
        return None

    def set_active_environment(self, envTag: str):
        """
        Sets an environment as active.

        :param envTag: The tag of the environment to be set as active.
        """
        for env in self.config.envs:
            if env.tag == envTag:
                env.status.active = True
            else:
                env.status.active = False
        self.store()

    def get_resource_classes(
        self, env: EnvironmentCfg, resource_type: str
    ) -> list[str]:
        """
        Retrieves all unique resource classes from the service configurations.

        :return: A list of unique resource classes.
        """
        match resource_type:
            case self.constants.RESOURCE_TYPE_SVC:
                if env.services:
                    return sorted(
                        {
                            svc.service_class
                            for svc in env.services
                            if svc.service_class
                        }
                    )
                return []
            case _:
                return []

    def get_service_tags(self, env: EnvironmentCfg) -> list[str]:
        """
        Retrieves all unique service tags from the service configurations.

        :return: A list of unique service tags.
        """
        if env.services:
            return sorted({svc.tag for svc in env.services if svc.tag})
        return []

    def env_cfg_from_tag(
        self,
        env_tmpl_cfg: EnvironmentTemplateCfg,
        env_tag: str,
    ):
        """
        Creates an EnvironmentCfg object from a tag.
        """

        services: Optional[list[ServiceCfg]] = []

        if env_tmpl_cfg.service_templates:
            services = [
                self.svc_cfg_from_service_template(
                    template, svc_template_ref.tag, None
                )
                for svc_template_ref in env_tmpl_cfg.service_templates
                if (
                    template := self.get_service_template(
                        svc_template_ref.template
                    )
                )
                is not None
            ]

        return EnvironmentCfg(
            template=env_tmpl_cfg.tag,
            factory=env_tmpl_cfg.factory,
            tag=env_tag,
            services=services,
            networks=env_tmpl_cfg.networks,
            volumes=env_tmpl_cfg.volumes,
        )

    def env_cfg_from_other(self, other: EnvironmentCfg):
        """
        Creates a copy of an existing EnvironmentCfg object.
        """
        return EnvironmentCfg(
            template=other.template,
            factory=other.factory,
            tag=other.tag,
            services=deepcopy(other.services),
            networks=deepcopy(other.networks),
            volumes=deepcopy(other.volumes),
        )

    def svc_tmpl_cfg_from_other(self, other: ServiceTemplateCfg):
        """
        Creates a copy of an existing ServiceTemplateCfg object.
        """
        return ServiceTemplateCfg(
            tag=other.tag,
            factory=other.factory,
            image=other.image,
            hostname=other.hostname,
            container_name=other.container_name,
            labels=deepcopy(other.labels),
            workdir=other.workdir,
            volumes=deepcopy(other.volumes),
            ingress=other.ingress,
            empty_env=other.empty_env,
            environment=deepcopy(other.environment),
            ports=deepcopy(other.ports),
            properties=deepcopy(other.properties),
            networks=deepcopy(other.networks),
            extra_hosts=deepcopy(other.extra_hosts),
            subject_alternative_name=other.subject_alternative_name,
        )

    def svc_cfg_from_tag(
        self,
        service_template: str,
        service_tag: str,
        service_class: Optional[str],
    ):
        """
        Creates a ServiceCfg object from a tag.
        """
        return ServiceCfg(
            template=service_template,
            factory="",
            tag=service_tag,
            service_class=service_class,
            image="",
            hostname=None,
            container_name=None,
            labels=[],
            workdir=None,
            volumes=[],
            ingress="false",
            empty_env=None,
            environment=[],
            ports=[],
            properties={},
            networks=[],
            extra_hosts=[],
            subject_alternative_name=None,
            upstreams=[],
        )

    def svc_cfg_from_other(self, other: ServiceCfg):
        """
        Creates a copy of an existing ServiceCfg object.
        """
        return ServiceCfg(
            template=other.template,
            factory=other.factory,
            tag=other.tag,
            service_class=other.service_class,
            image=other.image,
            hostname=other.hostname,
            container_name=other.container_name,
            labels=deepcopy(other.labels),
            workdir=other.workdir,
            volumes=deepcopy(other.volumes),
            ingress=other.ingress,
            empty_env=other.empty_env,
            environment=deepcopy(other.environment),
            ports=deepcopy(other.ports),
            properties=deepcopy(other.properties),
            networks=deepcopy(other.networks),
            extra_hosts=deepcopy(other.extra_hosts),
            subject_alternative_name=other.subject_alternative_name,
            upstreams=deepcopy(other.upstreams),
            status=deepcopy(other.status),
        )

    def svc_cfg_from_service_template(
        self,
        service_template: ServiceTemplateCfg,
        service_tag: str,
        service_class: Optional[str],
    ):
        """
        Creates a ServiceCfg object from a ServiceTemplateCfg object.
        """
        return ServiceCfg(
            template=service_template.tag,
            factory=service_template.factory,
            tag=service_tag,
            service_class=service_class,
            image=service_template.image,
            hostname=service_template.hostname,
            container_name=service_template.container_name,
            labels=deepcopy(service_template.labels),
            workdir=service_template.workdir,
            volumes=deepcopy(service_template.volumes),
            ingress=service_template.ingress,
            empty_env=service_template.empty_env,
            environment=deepcopy(service_template.environment),
            ports=deepcopy(service_template.ports),
            properties=deepcopy(service_template.properties),
            networks=deepcopy(service_template.networks),
            extra_hosts=deepcopy(service_template.extra_hosts),
            subject_alternative_name=service_template.subject_alternative_name,
            upstreams=[],
        )
