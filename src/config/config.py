# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.


import json
import os
import re
from copy import copy, deepcopy
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Dict, Match, Optional, cast

import yaml
from glom import glom  # type: ignore[import]

from util import Constants, Util

# Regular expression for variables in .shpd.conf or environment variables
# es: ${VAR_NAME}
VAR_RE = re.compile(r"\$\{([^}]+)\}")

# Regular expression for references inside .shpd.yaml
# es: #{REF_NAME}
REF_RE = re.compile(r"#\{([^}]+)\}")

# Reference constants
REF_CFG: str = "cfg"
REF_ENV: str = "env"
REF_SVC: str = "svc"
REF_VOL: str = "vol"
REF_NET: str = "net"
REF_CNT: str = "cnt"


REF_MAP: dict[str, str] = {
    "Config": REF_CFG,
    "EnvironmentCfg": REF_ENV,
    "ServiceCfg": REF_SVC,
    "VolumeCfg": REF_VOL,
    "NetworkCfg": REF_NET,
    "ContainerCfg": REF_CNT,
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
            if f.metadata.get("transient"):
                continue
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
        """
        Propagate resolver/reference context and resolution mode recursively.

        This is the core state-wiring pass used by `set_resolved`,
        `set_unresolved`, and `set_resolver`.
        """
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

    def is_resolved(self) -> bool:
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
        """
        Lazily resolve placeholders/references when resolution mode is enabled.

        Raw values are returned unchanged when unresolved mode is active.
        """
        if (
            name.startswith("_")
            or name
            in (
                "is_resolved",
                "set_resolver",
                "set_resolved",
                "set_unresolved",
            )
            or not self.is_resolved()
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
    Represents the lifecycle and activation status of an entity.

    This class captures runtime-derived information used during
    orchestration.

    Field semantics:

    - `active`:
      Indicates whether this entity is eligible to participate in
      start/stop commands.
      Note: this flag does *not* represent the actual runtime state,
      which is evaluated dynamically by the target engine.

    - `rendered_config`:
      The rendered, engine-specific configuration (e.g. Docker Compose)
      associated with the entity. This field is populated during `start`
      and cleared on `stop`. The rendered configuration reflects the
      configuration selected by the first successful probe.
    """

    active: bool = False
    rendered_config: Optional[dict[str, str]] = None


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
class BuildCfg(Resolvable):
    """
    Represents a build configuration.
    """

    context_path: Optional[str] = None
    dockerfile_path: Optional[str] = None


@dataclass
class InitCfg(Resolvable):
    """
    Represents a service init configuration.
    """

    tag: str
    script: Optional[str] = None
    script_path: Optional[str] = None
    when_probes: Optional[list[str]] = None


@dataclass
class ContainerCfg(Resolvable):
    tag: str
    image: Optional[str] = None
    hostname: Optional[str] = None
    run_hostname: Optional[str] = field(
        default=None, metadata={"transient": True}
    )
    container_name: Optional[str] = None
    run_container_name: Optional[str] = field(
        default=None, metadata={"transient": True}
    )
    workdir: Optional[str] = None
    volumes: Optional[list[str]] = None
    environment: Optional[list[str]] = None
    ports: Optional[list[str]] = None
    networks: Optional[list[str]] = None
    extra_hosts: Optional[list[str]] = None
    build: Optional[BuildCfg] = None
    inits: Optional[list[InitCfg]] = None


@dataclass
class ProbeCfg(Resolvable):
    """
    Represents a service probe configuration.
    """

    tag: str
    container: Optional[ContainerCfg] = None
    script: Optional[str] = None
    script_path: Optional[str] = None


@dataclass
class StartCfg(Resolvable):
    """
    Represents a service start blocking condition.
    """

    when_probes: Optional[list[str]] = None


@dataclass
class ReadyCfg(Resolvable):
    """
    Represents environment readiness conditions.

    Semantics:
    - `when_probes` follows the same all-of behavior used by service/start
      gates.
    - When configured, an environment is considered "up" only after:
      1) containers are running, and
      2) every listed probe currently evaluates to success.
    - When omitted/null/empty, readiness falls back to container-running state
      only (legacy behavior).
    """

    when_probes: Optional[list[str]] = None


@dataclass
class ServiceTemplateCfg(Resolvable):
    """
    Represents a service template configuration.
    """

    tag: str
    factory: str
    labels: Optional[list[str]] = None
    properties: Optional[dict[str, str]] = None
    containers: Optional[list[ContainerCfg]] = None
    start: Optional[StartCfg] = None


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

    tag: str
    factory: str
    template: str
    service_class: Optional[str] = None
    labels: Optional[list[str]] = None
    properties: Optional[dict[str, str]] = None
    upstreams: Optional[list[UpstreamCfg]] = None
    containers: Optional[list[ContainerCfg]] = None
    start: Optional[StartCfg] = None
    status: EntityStatus = field(
        default_factory=lambda: EntityStatus(active=True)
    )

    def get_yaml(self, resolved: bool = False) -> str:
        """
        Returns the YAML representation of the service configuration.

        Args:
        resolved: If True, ensure placeholders are resolved before dumping.
        """
        was_resolved = self.is_resolved()
        changed_state = False

        try:
            if resolved and not was_resolved:
                self.set_resolved()
                changed_state = True
            elif not resolved and was_resolved:
                self.set_unresolved()
                changed_state = True

            return yaml.dump(cfg_asdict(self), sort_keys=False)
        finally:
            if changed_state:
                if was_resolved:
                    self.set_resolved()
                else:
                    self.set_unresolved()

    def get_json(self, resolved: bool = False) -> str:
        """
        Return the JSON representation of the service configuration.

        Args:
            resolved: If True, ensure placeholders are resolved before dumping.
        """
        was_resolved = self.is_resolved()

        try:
            if resolved and not was_resolved:
                self.set_resolved()
            elif not resolved and was_resolved:
                self.set_unresolved()

            return json.dumps(cfg_asdict(self), indent=2)
        finally:
            if was_resolved:
                self.set_resolved()
            else:
                self.set_unresolved()

    def get_container_by_tag(self, cnt_tag: str) -> Optional[ContainerCfg]:
        """
        Retrieves a container configuration by its tag.

        :param cnt_tag: The runtime name of the container to retrieve.
        :return: The container configuration if found, else None.
        """
        if not self.containers:
            return None
        for cnt in self.containers:
            if cnt.tag == cnt_tag:
                return cnt
        return None


@dataclass
class EnvTemplateFragmentCfg(Resolvable):
    """
    A named, reusable bundle grouping a service template reference with its
    associated probes, volumes, and networks.  Fragments are declared in
    ``plugin.yaml`` or ``shpd.yaml`` and imported into ``env_templates`` via
    the ``fragments:`` list.
    """

    tag: str
    service_template: ServiceTemplateRefCfg
    probes: Optional[list[ProbeCfg]] = None
    volumes: Optional[list[VolumeCfg]] = None
    networks: Optional[list[NetworkCfg]] = None


@dataclass
class FragmentRefCfg(Resolvable):
    """
    A reference to an ``EnvTemplateFragmentCfg`` inside an
    ``EnvironmentTemplateCfg``.  The optional ``with_values`` map provides
    fragment-local ``${KEY}`` placeholder overrides applied at merge time.
    """

    id: str
    with_values: Optional[dict[str, str]] = None


@dataclass
class EnvironmentTemplateCfg(Resolvable):
    """
    Represents an environment template configuration.
    """

    tag: str
    factory: str
    service_templates: Optional[list[ServiceTemplateRefCfg]]
    probes: Optional[list[ProbeCfg]]
    networks: Optional[list[NetworkCfg]]
    volumes: Optional[list[VolumeCfg]]
    ready: Optional[ReadyCfg] = None
    fragments: Optional[list[FragmentRefCfg]] = None


@dataclass
class EnvironmentCfg(Resolvable):
    """
    Represents an environment configuration.
    """

    template: str
    factory: str
    tag: str
    services: Optional[list[ServiceCfg]]
    probes: Optional[list[ProbeCfg]]
    networks: Optional[list[NetworkCfg]]
    volumes: Optional[list[VolumeCfg]]
    ready: Optional[ReadyCfg] = None
    tracking_remote: Optional[str] = None
    dehydrated: Optional[bool] = None
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

    def get_yaml(self, resolved: bool = False) -> str:
        """
        Return the YAML representation of the environment configuration.

        Args:
            resolved: If True, ensure placeholders are resolved before dumping.
        """
        was_resolved = self.is_resolved()

        try:
            if resolved and not was_resolved:
                self.set_resolved()
            elif not resolved and was_resolved:
                self.set_unresolved()

            return yaml.dump(cfg_asdict(self), sort_keys=False)
        finally:
            if was_resolved:
                self.set_resolved()
            else:
                self.set_unresolved()

    def get_json(self, resolved: bool = False) -> str:
        """
        Return the JSON representation of the environment configuration.

        Args:
            resolved: If True, ensure placeholders are resolved before dumping.
        """
        was_resolved = self.is_resolved()

        try:
            if resolved and not was_resolved:
                self.set_resolved()
            elif not resolved and was_resolved:
                self.set_unresolved()

            return json.dumps(cfg_asdict(self), indent=2)
        finally:
            if was_resolved:
                self.set_resolved()
            else:
                self.set_unresolved()

    def get_probes_yaml(
        self, probe_tag: Optional[str] = None, resolved: bool = False
    ) -> Optional[str]:
        """
        Return the YAML representation of the environment probes configuration.

        Args:
            probe_tag: Optional probe tag to filter probes.
            resolved:  If True, ensure placeholders are resolved before dumping.

        Returns:
            YAML string or None if no probes (or no matching probes) exist.
        """
        if not self.probes:
            return None

        was_resolved = self.is_resolved()

        try:
            if resolved and not was_resolved:
                self.set_resolved()
            elif not resolved and was_resolved:
                self.set_unresolved()

            probes = self.probes
            if probe_tag is not None:
                probes = [p for p in probes if p.tag == probe_tag]
                if not probes:
                    return None

            data = cfg_asdict(probes)
            if not data:
                return None

            config: dict[str, Any] = {
                "probes": data,
            }

            return yaml.dump(config, sort_keys=False)

        finally:
            if was_resolved:
                self.set_resolved()
            else:
                self.set_unresolved()


@dataclass
class StagingAreaCfg(Resolvable):
    """
    Represents the configuration for the staging area.
    """

    volumes_path: str
    images_path: str


@dataclass
class PluginCfg(Resolvable):
    """Represents one installed plugin entry in the main config."""

    id: str
    enabled: str = field(default="true", metadata={"boolify": True})
    version: Optional[str] = None
    config: Optional[dict[str, Any]] = None

    def is_enabled(self) -> bool:
        return str_to_bool(self.enabled)


@dataclass
class PluginEntrypointCfg(Resolvable):
    """Represents the importable entrypoint declared by a plugin."""

    module: str
    class_name: str


@dataclass
class DependsOnCfg(Resolvable):
    """
    Declares a dependency on another Shepherd plugin.  ``version`` is an
    optional PEP 440 version specifier (e.g. ``">=1.0.0"``).
    """

    id: str
    version: Optional[str] = None


@dataclass
class PluginDescriptorCfg(Resolvable):
    """Represents the install-time plugin descriptor."""

    id: str
    name: str
    version: str
    plugin_api_version: int
    entrypoint: PluginEntrypointCfg
    description: Optional[str] = None
    capabilities: Optional[dict[str, bool]] = None
    default_config: Optional[dict[str, Any]] = None
    env_templates: Optional[list[EnvironmentTemplateCfg]] = None
    service_templates: Optional[list[ServiceTemplateCfg]] = None
    env_template_fragments: Optional[list[EnvTemplateFragmentCfg]] = None
    depends_on: Optional[list[DependsOnCfg]] = None


@dataclass
class RemoteChunkCfg(Resolvable):
    """Tunable FastCDC chunk size parameters for a remote."""

    min_size_kb: int = 512
    avg_size_kb: int = 2048
    max_size_kb: int = 8192


@dataclass
class RemoteLocalCacheCfg(Resolvable):
    """Optional on-disk LRU cache for downloaded chunk bytes."""

    path: str = ""
    max_size_gb: int = 20


@dataclass
class RemoteCfg(Resolvable):
    """Represents one registered remote storage backend.

    ``type`` is the discriminator: ``"ftp"`` and ``"sftp"`` are built-in;
    any other value is resolved against the plugin-registered backend
    registry.  FTP and SFTP share the same connection field names since
    ``type`` already distinguishes them.  Plugin backends can pass
    transport-specific parameters via ``properties``.
    """

    name: str
    type: str
    host: Optional[str] = None
    port: Optional[int] = None
    user: Optional[str] = None
    password: Optional[str] = None
    root_path: Optional[str] = None
    identity_file: Optional[str] = None
    default: str = field(default="false", metadata={"boolify": True})
    chunk: RemoteChunkCfg = field(default_factory=RemoteChunkCfg)
    local_cache: Optional[RemoteLocalCacheCfg] = None
    properties: Optional[dict[str, Any]] = None

    def is_default(self) -> bool:
        return str_to_bool(self.default)


@dataclass
class Config(Resolvable):
    """
    Represents the shepherd configuration.
    """

    templates_path: str
    envs_path: str
    volumes_path: str
    staging_area: StagingAreaCfg
    env_templates: Optional[list[EnvironmentTemplateCfg]] = None
    service_templates: Optional[list[ServiceTemplateCfg]] = None
    env_template_fragments: Optional[list[EnvTemplateFragmentCfg]] = None
    plugins: Optional[list[PluginCfg]] = None
    remotes: Optional[list[RemoteCfg]] = None
    envs: list[EnvironmentCfg] = field(default_factory=list[EnvironmentCfg])


def _parse_build(item: Any) -> BuildCfg:
    return BuildCfg(
        context_path=item.get("context_path"),
        dockerfile_path=item.get("dockerfile_path"),
    )


def _parse_init(item: Any) -> InitCfg:
    return InitCfg(
        tag=item["tag"],
        script=item.get("script"),
        script_path=item.get("script_path"),
        when_probes=item.get("when_probes", []),
    )


def _parse_start(item: Any) -> StartCfg:
    return StartCfg(
        when_probes=item.get("when_probes", []),
    )


def _parse_ready(item: Any) -> ReadyCfg:
    return ReadyCfg(
        when_probes=item.get("when_probes", []),
    )


def _parse_container(item: Any) -> ContainerCfg:
    inits = (
        [_parse_init(init) for init in item.get("inits", [])]
        if item.get("inits") is not None
        else None
    )
    return ContainerCfg(
        tag=item.get("tag"),
        image=item.get("image"),
        hostname=item.get("hostname"),
        container_name=item.get("container_name"),
        workdir=item.get("workdir"),
        volumes=item.get("volumes", []),
        environment=item.get("environment", []),
        ports=item.get("ports", []),
        networks=item.get("networks", []),
        extra_hosts=item.get("extra_hosts", []),
        build=_parse_build(item["build"]) if item.get("build") else None,
        inits=inits,
    )


def _parse_probe(item: Any) -> ProbeCfg:
    return ProbeCfg(
        tag=item["tag"],
        container=(
            _parse_container(item["container"])
            if item.get("container")
            else None
        ),
        script=item.get("script"),
        script_path=item.get("script_path"),
    )


def _parse_network(item: Any) -> NetworkCfg:
    external_value = item.get("external", False)
    attachable_value = item.get("attachable")
    enable_ipv6_value = item.get("enable_ipv6")
    return NetworkCfg(
        tag=item["tag"],
        name=item.get("name", None),
        external=(
            bool_to_str(external_value)
            if isinstance(external_value, bool)
            else external_value
        ),
        driver=item.get("driver", None),
        attachable=(
            bool_to_str(attachable_value)
            if isinstance(attachable_value, bool)
            else attachable_value
        ),
        enable_ipv6=(
            bool_to_str(enable_ipv6_value)
            if isinstance(enable_ipv6_value, bool)
            else enable_ipv6_value
        ),
        driver_opts=item.get("driver_opts"),
        ipam=item.get("ipam"),
    )


def _parse_volume(item: Any) -> VolumeCfg:
    external_value = item.get("external", False)
    return VolumeCfg(
        tag=item["tag"],
        external=(
            bool_to_str(external_value)
            if isinstance(external_value, bool)
            else external_value
        ),
        name=item.get("name"),
        driver=item.get("driver"),
        driver_opts=item.get("driver_opts"),
        labels=item.get("labels"),
    )


def _parse_service_template_ref(item: Any) -> ServiceTemplateRefCfg:
    return ServiceTemplateRefCfg(
        template=item["template"],
        tag=item["tag"],
    )


def _parse_service_template(item: Any) -> ServiceTemplateCfg:
    containers_data = cast(list[dict[str, Any]], item.get("containers") or [])
    return ServiceTemplateCfg(
        tag=item["tag"],
        factory=item["factory"],
        labels=item.get("labels", []),
        properties=item.get("properties", {}),
        containers=[
            _parse_container(container) for container in containers_data
        ],
        start=_parse_start(item["start"]) if item.get("start") else None,
    )


def _parse_depends_on(item: Any) -> DependsOnCfg:
    if not isinstance(item, dict) or "id" not in item:
        raise ValueError(
            f"Each depends_on entry must be a mapping with an 'id' field, "
            f"got: {item!r}"
        )
    d = cast(dict[str, Any], item)
    return DependsOnCfg(
        id=str(d["id"]),
        version=str(d["version"]) if d.get("version") else None,
    )


def _parse_fragment_ref(item: Any) -> FragmentRefCfg:
    if isinstance(item, str):
        return FragmentRefCfg(id=item)
    if not isinstance(item, dict) or "id" not in item:
        raise ValueError(
            f"Each fragments entry must be a string or a mapping with an "
            f"'id' field, got: {item!r}"
        )
    d = cast(dict[str, Any], item)
    with_raw = cast(dict[str, Any] | None, d.get("with"))
    return FragmentRefCfg(
        id=str(d["id"]),
        with_values=dict(with_raw) if with_raw else None,
    )


def _parse_env_template_fragment(item: Any) -> EnvTemplateFragmentCfg:
    probes_data = cast(list[dict[str, Any]], item.get("probes") or [])
    volumes_data = cast(list[dict[str, Any]], item.get("volumes") or [])
    networks_data = cast(list[dict[str, Any]], item.get("networks") or [])
    return EnvTemplateFragmentCfg(
        tag=item["tag"],
        service_template=_parse_service_template_ref(item["service_template"]),
        probes=[_parse_probe(p) for p in probes_data],
        volumes=[_parse_volume(v) for v in volumes_data],
        networks=[_parse_network(n) for n in networks_data],
    )


def _parse_environment_template(item: Any) -> EnvironmentTemplateCfg:
    service_templates_data = cast(
        list[dict[str, Any]], item.get("service_templates") or []
    )
    probes_data = cast(list[dict[str, Any]], item.get("probes") or [])
    networks_data = cast(list[dict[str, Any]], item.get("networks") or [])
    volumes_data = cast(list[dict[str, Any]], item.get("volumes") or [])
    fragments_data = item.get("fragments")
    return EnvironmentTemplateCfg(
        tag=item["tag"],
        factory=item["factory"],
        service_templates=[
            _parse_service_template_ref(service_template)
            for service_template in service_templates_data
        ],
        probes=[_parse_probe(probe) for probe in probes_data],
        ready=_parse_ready(item["ready"]) if item.get("ready") else None,
        networks=[_parse_network(network) for network in networks_data],
        volumes=[_parse_volume(volume) for volume in volumes_data],
        fragments=(
            [_parse_fragment_ref(f) for f in fragments_data]
            if fragments_data
            else None
        ),
    )


def _parse_status(item: Any) -> EntityStatus:
    return EntityStatus(
        active=item.get("active", False),
        rendered_config=item.get("rendered_config"),
    )


def _parse_upstream(item: Any) -> UpstreamCfg:
    enabled_value = item["enabled"]
    return UpstreamCfg(
        type=item["type"],
        tag=item["tag"],
        properties=item.get("properties", {}),
        enabled=(
            bool_to_str(enabled_value)
            if isinstance(enabled_value, bool)
            else enabled_value
        ),
    )


def _parse_service(item: Any) -> ServiceCfg:
    containers_data = cast(list[dict[str, Any]], item.get("containers") or [])
    upstreams_data = cast(list[dict[str, Any]], item.get("upstreams") or [])
    return ServiceCfg(
        tag=item["tag"],
        factory=item["factory"],
        template=item["template"],
        service_class=item.get("service_class"),
        labels=item.get("labels", []),
        properties=item.get("properties", {}),
        upstreams=[_parse_upstream(upstream) for upstream in upstreams_data],
        containers=[
            _parse_container(container) for container in containers_data
        ],
        start=_parse_start(item["start"]) if item.get("start") else None,
        status=_parse_status(item["status"]),
    )


def _parse_staging_area(item: Any) -> StagingAreaCfg:
    return StagingAreaCfg(
        volumes_path=item["volumes_path"],
        images_path=item["images_path"],
    )


def _parse_plugin(item: Any) -> PluginCfg:
    enabled_value = item.get("enabled", True)
    return PluginCfg(
        id=item["id"],
        enabled=(
            bool_to_str(enabled_value)
            if isinstance(enabled_value, bool)
            else enabled_value
        ),
        version=item.get("version"),
        config=item.get("config"),
    )


def _parse_remote_chunk_cfg(item: Any) -> RemoteChunkCfg:
    return RemoteChunkCfg(
        min_size_kb=item.get("min_size_kb", 512),
        avg_size_kb=item.get("avg_size_kb", 2048),
        max_size_kb=item.get("max_size_kb", 8192),
    )


def _parse_remote_local_cache_cfg(item: Any) -> RemoteLocalCacheCfg:
    return RemoteLocalCacheCfg(
        path=item.get("path", ""),
        max_size_gb=item.get("max_size_gb", 20),
    )


def _parse_remote(item: Any) -> RemoteCfg:
    default_value = item.get("default", False)
    return RemoteCfg(
        name=item["name"],
        type=item["type"],
        host=item.get("host"),
        port=item.get("port"),
        user=item.get("user"),
        password=item.get("password"),
        root_path=item.get("root_path"),
        identity_file=item.get("identity_file"),
        default=(
            bool_to_str(default_value)
            if isinstance(default_value, bool)
            else default_value
        ),
        chunk=(
            _parse_remote_chunk_cfg(item["chunk"])
            if item.get("chunk")
            else RemoteChunkCfg()
        ),
        local_cache=(
            _parse_remote_local_cache_cfg(item["local_cache"])
            if item.get("local_cache")
            else None
        ),
        properties=item.get("properties"),
    )


def _parse_environment(item: Any) -> EnvironmentCfg:
    services_data = cast(list[dict[str, Any]], item.get("services") or [])
    probes_data = cast(list[dict[str, Any]], item.get("probes") or [])
    networks_data = cast(list[dict[str, Any]], item.get("networks") or [])
    volumes_data = cast(list[dict[str, Any]], item.get("volumes") or [])
    return EnvironmentCfg(
        template=item["template"],
        factory=item["factory"],
        tag=item["tag"],
        services=[_parse_service(service) for service in services_data],
        probes=[_parse_probe(probe) for probe in probes_data],
        ready=_parse_ready(item["ready"]) if item.get("ready") else None,
        networks=[_parse_network(network) for network in networks_data],
        volumes=[_parse_volume(volume) for volume in volumes_data],
        tracking_remote=item.get("tracking_remote"),
        dehydrated=item.get("dehydrated"),
        status=_parse_status(item["status"]),
    )


def parse_plugin_descriptor(yaml_str: str) -> PluginDescriptorCfg:
    """
    Parse a plugin descriptor YAML into the strongly typed descriptor model.
    """

    data = yaml.safe_load(yaml_str)
    if not isinstance(data, dict):
        raise ValueError("Plugin descriptor must be a YAML mapping.")
    descriptor = cast(dict[str, Any], data)

    entrypoint = descriptor.get("entrypoint")
    if not isinstance(entrypoint, dict):
        raise ValueError("Plugin descriptor must declare an entrypoint.")
    entrypoint_cfg = cast(dict[str, Any], entrypoint)

    normalized_capabilities: Optional[dict[str, bool]]
    capabilities = descriptor.get("capabilities")
    if capabilities is not None:
        if not isinstance(capabilities, dict):
            raise ValueError("Plugin capabilities must be a mapping.")
        capabilities_cfg = cast(dict[str, Any], capabilities)
        capabilities_map: dict[str, bool] = {}
        for key, value in capabilities_cfg.items():
            if not isinstance(value, bool):
                raise ValueError("Plugin capability values must be booleans.")
            capabilities_map[str(key)] = value
        normalized_capabilities = capabilities_map
    else:
        normalized_capabilities = None

    default_config = descriptor.get("default_config")
    if default_config is not None and not isinstance(default_config, dict):
        raise ValueError("Plugin default_config must be a mapping.")

    env_templates_data = descriptor.get("env_templates")
    if env_templates_data is not None and not isinstance(
        env_templates_data, list
    ):
        raise ValueError("Plugin env_templates must be a list.")

    service_templates_data = descriptor.get("service_templates")
    if service_templates_data is not None and not isinstance(
        service_templates_data, list
    ):
        raise ValueError("Plugin service_templates must be a list.")

    fragments_data = descriptor.get("env_template_fragments")
    if fragments_data is not None and not isinstance(fragments_data, list):
        raise ValueError("Plugin env_template_fragments must be a list.")

    depends_on_data = descriptor.get("depends_on")
    if depends_on_data is not None and not isinstance(depends_on_data, list):
        raise ValueError("Plugin depends_on must be a list.")

    env_templates = (
        [
            _parse_environment_template(template)
            for template in cast(list[dict[str, Any]], env_templates_data)
        ]
        if env_templates_data is not None
        else None
    )
    service_templates = (
        [
            _parse_service_template(template)
            for template in cast(list[dict[str, Any]], service_templates_data)
        ]
        if service_templates_data is not None
        else None
    )
    env_template_fragments = (
        [
            _parse_env_template_fragment(f)
            for f in cast(list[dict[str, Any]], fragments_data)
        ]
        if fragments_data is not None
        else None
    )
    depends_on = (
        [
            _parse_depends_on(d)
            for d in cast(list[dict[str, Any]], depends_on_data)
        ]
        if depends_on_data is not None
        else None
    )

    return PluginDescriptorCfg(
        id=str(descriptor["id"]),
        name=str(descriptor["name"]),
        version=str(descriptor["version"]),
        plugin_api_version=int(descriptor["plugin_api_version"]),
        entrypoint=PluginEntrypointCfg(
            module=str(entrypoint_cfg["module"]),
            class_name=str(entrypoint_cfg["class"]),
        ),
        description=(
            str(description)
            if (description := descriptor.get("description")) is not None
            else None
        ),
        capabilities=normalized_capabilities,
        default_config=cast(Optional[dict[str, Any]], default_config),
        env_templates=env_templates,
        service_templates=service_templates,
        env_template_fragments=env_template_fragments,
        depends_on=depends_on,
    )


def parse_config(yaml_str: str) -> Config:
    """
    Parse YAML into the strongly typed configuration model.

    Parsing normalizes schema-level defaults and converts bool YAML scalars
    into canonical string flags for fields managed via `boolify`.
    """

    data = yaml.safe_load(yaml_str)

    return Config(
        env_templates=[
            _parse_environment_template(environment_template)
            for environment_template in data.get("env_templates", [])
        ],
        service_templates=[
            _parse_service_template(service_template)
            for service_template in data.get("service_templates", [])
        ],
        env_template_fragments=(
            [
                _parse_env_template_fragment(f)
                for f in data["env_template_fragments"]
            ]
            if data.get("env_template_fragments") is not None
            else None
        ),
        templates_path=data["templates_path"],
        envs_path=data["envs_path"],
        volumes_path=data["volumes_path"],
        staging_area=_parse_staging_area(data["staging_area"]),
        plugins=(
            [_parse_plugin(plugin) for plugin in data.get("plugins", [])]
            if data.get("plugins") is not None
            else None
        ),
        remotes=(
            [_parse_remote(r) for r in data.get("remotes", [])]
            if data.get("remotes") is not None
            else None
        ),
        envs=[_parse_environment(env) for env in data["envs"]],
    )


class ConfigMng:
    """
    Manages the loading and storage of configuration data.

    This class handles:
    - Reading user-defined key-value pairs from a configuration values file.
    - Loading a YAML configuration file.
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
            LOG_FILE=os.path.expanduser(self.user_values["log_file"]),
            LOG_LEVEL=self.user_values["log_level"],
            RAW_LOG_STDOUT=self.user_values["log_stdout"],
            LOG_FORMAT=self.user_values["log_format"],
        )
        self.pluginRuntimeMng = None

    def set_plugin_runtime_mng(self, pluginRuntimeMng: Any) -> None:
        """Attach the optional runtime plugin manager for lookup helpers."""
        self.pluginRuntimeMng = pluginRuntimeMng

    def ensure_dirs(self):
        dirs = {
            "TEMPLATES": self.config.templates_path,
            "TEMPLATES_ENV": os.path.join(
                self.config.templates_path, Constants.ENV_TEMPLATES_DIR
            ),
            "TEMPLATES_SVC": os.path.join(
                self.config.templates_path, Constants.SVC_TEMPLATES_DIR
            ),
            "ENVS": self.config.envs_path,
            "VOLUMES": self.config.volumes_path,
            "VOLUMES_SA": self.config.staging_area.volumes_path,
            "IMAGES_SA": self.config.staging_area.images_path,
        }

        for template in self.config.env_templates or []:
            dirs[f"TEMPLATE_ENV_{template.tag}"] = os.path.join(
                self.config.templates_path,
                Constants.ENV_TEMPLATES_DIR,
                template.tag,
            )

        for template in self.config.service_templates or []:
            dirs[f"TEMPLATE_SVC_{template.tag}"] = os.path.join(
                self.config.templates_path,
                Constants.SVC_TEMPLATES_DIR,
                template.tag,
            )

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

        Notes:
            Expansion is one-pass in file order. A key can reference only
            values already defined above it (plus environment variables).
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
        Reads the YAML configuration file.

        :raises FileNotFoundError: If the configuration file is missing.
        :raises ValueError: If the configuration file is malformed.
        """
        with open(self.constants.SHPD_CONFIG_FILE, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        # Reparse through model constructors to normalize defaults/types.
        config = parse_config(yaml.dump(config_data, sort_keys=False))
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
        Writes the final configuration back to a YAML file.

        :param config: The `Config` object to be saved.
        """
        # Persist unresolved values so placeholders remain in the file.
        config.set_unresolved()
        config_dict = cfg_asdict(config)
        config.set_resolved()

        with open(self.constants.SHPD_CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(config_dict, f, sort_keys=False)

    def store(self):
        """
        Stores the current configuration by calling `store_config`.
        """
        self.store_config(self.config)

    def get_canonical_id(self, identifier: str) -> str:
        """
        Return the internal canonical identifier for core or plugin-owned ids.

        Built-in resources keep their short user-facing ids in config and CLI,
        but internal registry-oriented lookup uses the explicit `core/...`
        namespace just like plugin-owned resources use `<plugin-id>/...`.
        """
        if "/" in identifier:
            return identifier
        return f"{self.constants.CORE_PLUGIN_ID}/{identifier}"

    def _is_core_id(self, identifier: str) -> bool:
        """Return whether the canonical identifier belongs to core."""
        return identifier.startswith(f"{self.constants.CORE_PLUGIN_ID}/")

    def _local_id(self, identifier: str) -> str:
        """Return the local identifier portion from a canonical id."""
        if "/" in identifier:
            return identifier.split("/", 1)[1]
        return identifier

    def _core_environment_template_registry(
        self,
    ) -> dict[str, EnvironmentTemplateCfg]:
        """Build the canonical lookup registry for built-in env templates."""
        return {
            self.get_canonical_id(env_template.tag): env_template
            for env_template in self.config.env_templates or []
        }

    def _core_service_template_registry(
        self,
    ) -> dict[str, ServiceTemplateCfg]:
        """
        Build the canonical lookup registry for built-in service templates.
        """
        return {
            self.get_canonical_id(service_template.tag): service_template
            for service_template in self.config.service_templates or []
        }

    def get_environment_template_registry(
        self,
    ) -> dict[str, EnvironmentTemplateCfg]:
        """Return the merged canonical registry of env templates."""
        registry = self._core_environment_template_registry()
        if self.pluginRuntimeMng is not None:
            registry.update(self.pluginRuntimeMng.registry.env_templates)
        return registry

    def get_service_template_registry(
        self,
    ) -> dict[str, ServiceTemplateCfg]:
        """Return the merged canonical registry of service templates."""
        registry = self._core_service_template_registry()
        if self.pluginRuntimeMng is not None:
            registry.update(self.pluginRuntimeMng.registry.service_templates)
        return registry

    def _core_env_template_fragment_registry(
        self,
    ) -> dict[str, EnvTemplateFragmentCfg]:
        """Build the canonical lookup registry for built-in fragments."""
        registry: dict[str, EnvTemplateFragmentCfg] = {}
        for f in self.config.env_template_fragments or []:
            canonical = self.get_canonical_id(f.tag)
            if canonical in registry:
                Util.print_error_and_die(
                    f"Duplicate env_template_fragment tag '{f.tag}' in "
                    "shpd.yaml."
                )
            registry[canonical] = f
        return registry

    def get_env_template_fragment_registry(
        self,
    ) -> dict[str, EnvTemplateFragmentCfg]:
        """Return the merged canonical registry of env template fragments."""
        registry = self._core_env_template_fragment_registry()
        if self.pluginRuntimeMng is not None:
            registry.update(
                self.pluginRuntimeMng.registry.env_template_fragments
            )
        return registry

    def get_env_template_fragment(
        self, fragment_id: str
    ) -> Optional[EnvTemplateFragmentCfg]:
        """Return the fragment for *fragment_id*, or ``None`` if not found."""
        canonical = self.get_canonical_id(fragment_id)
        return self.get_env_template_fragment_registry().get(canonical)

    def get_canonical_env_factory_id(self, factory_id: str) -> str:
        """Return the canonical environment factory id."""
        return self.get_canonical_id(factory_id)

    def get_canonical_svc_factory_id(self, factory_id: str) -> str:
        """Return the canonical service factory id."""
        return self.get_canonical_id(factory_id)

    def is_core_env_factory_id(self, factory_id: str) -> bool:
        """Return whether the environment factory id resolves to core."""
        return self.get_canonical_env_factory_id(
            factory_id
        ) == self.get_canonical_env_factory_id(
            self.constants.ENV_FACTORY_DEFAULT
        )

    def is_core_svc_factory_id(self, factory_id: str) -> bool:
        """Return whether the service factory id resolves to core."""
        return self.get_canonical_svc_factory_id(
            factory_id
        ) == self.get_canonical_svc_factory_id(
            self.constants.SVC_FACTORY_DEFAULT
        )

    def get_service_template_path(self, serviceTemplate: str) -> Optional[str]:
        """
        Retrieves the service template path by id.

        :param serviceTemplate: The service template id.
        :return: The service template path.
        """
        canonical_id = self.get_canonical_id(serviceTemplate)
        if self._is_core_id(canonical_id):
            local_template_id = self._local_id(canonical_id)
            if self._core_service_template_registry().get(canonical_id):
                return os.path.join(
                    self.config.templates_path,
                    Constants.SVC_TEMPLATES_DIR,
                    local_template_id,
                )
        elif (
            self.pluginRuntimeMng is not None
            and (
                plugin_template_path := (
                    self.pluginRuntimeMng.get_service_template_path(
                        canonical_id
                    )
                )
            )
            is not None
        ):
            return plugin_template_path
        return None

    def get_environment_template(
        self, envTemplate: str
    ) -> Optional[EnvironmentTemplateCfg]:
        """
        Retrieves an environment template configuration by id.

        Accepts both short core ids like `default` and canonical ids like
        `core/default` or `plugin-id/template`.
        """
        return self.get_environment_template_registry().get(
            self.get_canonical_id(envTemplate)
        )

    def get_environment_templates(
        self,
    ) -> Optional[list[EnvironmentTemplateCfg]]:
        """
        Retrieves all environment templates.

        :return: A list of all environment templates.
        """
        templates = list(self.get_environment_template_registry().values())
        return templates or None

    def get_environment_template_tags(self) -> list[str]:
        if env_templates := self.get_environment_templates():
            return sorted([env_template.tag for env_template in env_templates])
        return []

    def get_service_template(
        self, serviceTemplate: str
    ) -> Optional[ServiceTemplateCfg]:
        """
        Retrieves a service template configuration by id.

        Accepts both short core ids like `default` and canonical ids like
        `core/default` or `plugin-id/template`.
        """
        return self.get_service_template_registry().get(
            self.get_canonical_id(serviceTemplate)
        )

    def get_service_templates(self) -> Optional[list[ServiceTemplateCfg]]:
        """
        Retrieves all service templates.

        :return: A list of all service templates.
        """
        templates = list(self.get_service_template_registry().values())
        return templates or None

    def get_resource_templates(self, resource_type: str) -> list[str]:
        match resource_type:
            case self.constants.RESOURCE_TYPE_SVC:
                if service_templates := self.get_service_templates():
                    return sorted(
                        [svc_template.tag for svc_template in service_templates]
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

    def get_plugins(self) -> list[PluginCfg]:
        """Return the configured plugin inventory."""
        return list(self.config.plugins or [])

    def get_plugin(self, plugin_id: str) -> Optional[PluginCfg]:
        """Return one configured plugin by id."""
        for plugin in self.get_plugins():
            if plugin.id == plugin_id:
                return plugin
        return None

    def get_remotes(self) -> list[RemoteCfg]:
        """Return all configured remotes."""
        return list(self.config.remotes or [])

    def get_remote(self, name: str) -> Optional[RemoteCfg]:
        """Return a configured remote by name."""
        return next((r for r in self.get_remotes() if r.name == name), None)

    def get_default_remote(self) -> Optional[RemoteCfg]:
        """Return the remote marked as default, if any."""
        return next((r for r in self.get_remotes() if r.is_default()), None)

    def add_remote(self, remote: RemoteCfg) -> None:
        """Append a new remote entry and persist the config.

        :raises ValueError: If a remote with the same name already exists.
        """
        remotes = list(self.config.remotes or [])
        if any(r.name == remote.name for r in remotes):
            raise ValueError(f"Remote '{remote.name}' already exists.")
        remotes.append(remote)
        self.config.remotes = remotes
        self.store()

    def remove_remote(self, name: str) -> None:
        """Remove a remote entry by name and persist the config."""
        if self.config.remotes:
            self.config.remotes = [
                r for r in self.config.remotes if r.name != name
            ]
        self.store()

    def get_plugin_dir(self, plugin_id: str) -> str:
        """Return the managed install directory for one plugin id."""
        return os.path.join(self.constants.SHPD_PLUGINS_DIR, plugin_id)

    def set_plugin(self, plugin_cfg: PluginCfg) -> None:
        """Add or replace one plugin entry and persist the config."""
        plugins = list(self.config.plugins or [])
        for index, plugin in enumerate(plugins):
            if plugin.id == plugin_cfg.id:
                plugins[index] = plugin_cfg
                self.config.plugins = plugins
                self.store()
                return
        plugins.append(plugin_cfg)
        self.config.plugins = plugins
        self.store()

    def set_plugin_enabled(self, plugin_id: str, enabled: bool) -> PluginCfg:
        """Update one plugin enabled flag and persist the config."""
        plugin = self.get_plugin(plugin_id)
        if plugin is None:
            raise ValueError(f"Plugin '{plugin_id}' not found.")
        plugin.enabled = bool_to_str(enabled)
        self.store()
        return plugin

    def remove_plugin(self, plugin_id: str) -> PluginCfg:
        """Remove one plugin entry from config and persist the change."""
        plugins = list(self.config.plugins or [])
        for index, plugin in enumerate(plugins):
            if plugin.id == plugin_id:
                del plugins[index]
                self.config.plugins = plugins
                self.store()
                return plugin
        raise ValueError(f"Plugin '{plugin_id}' not found.")

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
        # Ensure we mutate/store the canonical unresolved config tree.
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

    def get_probe_tags(self, env: EnvironmentCfg) -> list[str]:
        """
        Retrieves all unique probe tags from the probe configurations.

        :return: A list of unique probe tags.
        """
        if env.probes:
            return sorted({probe.tag for probe in env.probes if probe.tag})
        return []

    def get_service(
        self, env: EnvironmentCfg, svc_tag: str
    ) -> Optional[ServiceCfg]:
        if env.services:
            for svc in env.services:
                if svc.tag == svc_tag:
                    return svc
        return None

    def get_container_tags(self, svc: ServiceCfg) -> list[str]:
        """
        Retrieves all unique container tags from the container configurations.

        :return: A list of unique container tags.
        """
        if svc.containers:
            return sorted({cnt.tag for cnt in svc.containers if cnt.tag})
        return []

    def _apply_fragment_values(
        self,
        fragment: EnvTemplateFragmentCfg,
        with_values: dict[str, str],
    ) -> EnvTemplateFragmentCfg:
        """Return a copy of *fragment* with ``${KEY}`` placeholders substituted.

        Only keys present in *with_values* are substituted; unknown keys are
        left as-is so the global ``${VAR}`` resolution phase can handle them.
        ``#{ref}`` object-reference patterns are never touched here.
        """

        def subst(obj: Any) -> Any:
            if isinstance(obj, str):
                return VAR_RE.sub(
                    lambda m: with_values.get(m.group(1), m.group(0)), obj
                )
            if isinstance(obj, dict):
                obj_d = cast(dict[str, Any], obj)
                return {k: subst(v) for k, v in obj_d.items()}
            if isinstance(obj, list):
                obj_l = cast(list[Any], obj)
                return [subst(i) for i in obj_l]
            return obj

        raw = cast(dict[str, Any], cfg_asdict(deepcopy(fragment)))
        original_tag: str = raw["tag"]
        substituted = cast(dict[str, Any], subst(raw))
        substituted["tag"] = original_tag
        return _parse_env_template_fragment(substituted)

    def env_cfg_from_tag(
        self,
        env_tmpl_cfg: EnvironmentTemplateCfg,
        env_tag: str,
    ):
        """
        Creates an EnvironmentCfg object from a tag.
        """

        # Collect explicit service refs and inline probes/volumes/networks.
        svc_refs: list[ServiceTemplateRefCfg] = list(
            env_tmpl_cfg.service_templates or []
        )
        probes: list[ProbeCfg] = list(env_tmpl_cfg.probes or [])
        volumes: list[VolumeCfg] = list(env_tmpl_cfg.volumes or [])
        networks: list[NetworkCfg] = list(env_tmpl_cfg.networks or [])

        # Merge fragment contributions (additive, tag-conflict → hard fail).
        fragment_registry = self.get_env_template_fragment_registry()
        seen_svc_tags: set[str] = {r.tag for r in svc_refs}
        for frag_ref in env_tmpl_cfg.fragments or []:
            canonical = self.get_canonical_id(frag_ref.id)
            frag = fragment_registry.get(canonical)
            if frag is None:
                Util.print_error_and_die(
                    f"Unknown fragment '{frag_ref.id}' referenced in "
                    f"env template '{env_tmpl_cfg.tag}'."
                )
                raise AssertionError("unreachable")
            if frag_ref.with_values:
                frag = self._apply_fragment_values(frag, frag_ref.with_values)
            if frag.service_template.tag in seen_svc_tags:
                Util.print_error_and_die(
                    f"Fragment '{frag_ref.id}' declares service tag "
                    f"'{frag.service_template.tag}' which conflicts with an "
                    f"existing tag in env template '{env_tmpl_cfg.tag}'."
                )
            seen_svc_tags.add(frag.service_template.tag)
            svc_refs.append(frag.service_template)
            probes.extend(frag.probes or [])
            volumes.extend(frag.volumes or [])
            networks.extend(frag.networks or [])

        services: list[ServiceCfg] = [
            self.svc_cfg_from_service_template(template, ref.tag, None)
            for ref in svc_refs
            if (template := self.get_service_template(ref.template)) is not None
        ]

        return EnvironmentCfg(
            template=env_tmpl_cfg.tag,
            factory=env_tmpl_cfg.factory,
            tag=env_tag,
            services=services or None,
            probes=probes or None,
            ready=deepcopy(env_tmpl_cfg.ready),
            networks=networks or None,
            volumes=volumes or None,
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
            probes=deepcopy(other.probes),
            ready=deepcopy(other.ready),
            networks=deepcopy(other.networks),
            volumes=deepcopy(other.volumes),
            tracking_remote=other.tracking_remote,
            dehydrated=other.dehydrated,
        )

    def svc_tmpl_cfg_from_other(self, other: ServiceTemplateCfg):
        """
        Creates a copy of an existing ServiceTemplateCfg object.
        """
        return ServiceTemplateCfg(
            tag=other.tag,
            factory=other.factory,
            labels=deepcopy(other.labels),
            properties=deepcopy(other.properties),
            containers=deepcopy(other.containers),
            start=deepcopy(other.start),
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
            labels=[],
            properties={},
            upstreams=[],
            containers=[],
            start=None,
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
            labels=deepcopy(service_template.labels),
            properties=deepcopy(service_template.properties),
            upstreams=[],
            containers=deepcopy(service_template.containers),
            start=deepcopy(service_template.start),
        )
