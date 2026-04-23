# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.


import os
from copy import deepcopy
from unittest.mock import mock_open

import pytest
import yaml
from pytest_mock import MockerFixture
from test_util import read_fixture

from config import (
    Config,
    ConfigMng,
    EnvTemplateFragmentCfg,
    FragmentRefCfg,
    RemoteCfg,
    RemoteChunkCfg,
    ServiceTemplateRefCfg,
    parse_config,
    parse_plugin_descriptor,
)
from docker import DockerComposeEnv, DockerComposeSvc
from factory import ShpdEnvironmentFactory, ShpdServiceFactory
from util import Constants


def _load_config_manager(mocker: MockerFixture) -> ConfigMng:
    values = read_fixture("cfg", "values.conf")
    config_yaml = read_fixture("cfg", "shpd.yaml")

    mock_open1 = mock_open(read_data=values)
    mock_open2 = mock_open(read_data=config_yaml)

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch(
        "builtins.open",
        side_effect=[mock_open1.return_value, mock_open2.return_value],
    )

    cMng = ConfigMng(".shpd.conf")
    cMng.load()
    return cMng


@pytest.mark.cfg
def test_load_config(mocker: MockerFixture):
    """Test regular parsing"""

    mocker.patch.dict(
        os.environ,
        {
            "ora_container_name": "ora-cnt-1",
            "ora_hostname": "ora-host",
        },
    )

    values = read_fixture("cfg", "values.conf")
    config_yaml = read_fixture("cfg", "shpd.yaml")

    mock_open1 = mock_open(read_data=values)
    mock_open2 = mock_open(read_data=config_yaml)

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch(
        "builtins.open",
        side_effect=[mock_open1.return_value, mock_open2.return_value],
    )

    cMng = ConfigMng(".shpd.conf")
    config: Config = cMng.load_config()
    config.set_resolved()

    env_templates = config.env_templates
    assert env_templates and env_templates[0].tag == "default"
    assert env_templates[0].factory == "docker-compose"
    assert env_templates[0].service_templates
    assert env_templates[0].service_templates[0].tag == "service-default"
    assert env_templates[0].service_templates[0].template == "default"
    assert env_templates[0].networks
    assert env_templates[0].networks[0].tag == "shpdnet"
    assert env_templates[0].networks[0].name == "envnet"
    assert env_templates[0].networks[0].is_external()
    assert env_templates[0].volumes
    assert env_templates[0].volumes[0].tag == "app_data"
    assert env_templates[0].volumes[0].driver == "local"
    assert not env_templates[0].volumes[0].is_external()
    assert env_templates[0].volumes[0].driver_opts
    assert (
        env_templates[0].volumes[0].driver_opts["device"]
        == "${test_path}/envs/srv/data"
    )

    service_templates = config.service_templates
    assert service_templates and service_templates[0].tag == "oracle"
    assert service_templates[0].factory == "docker"
    assert service_templates[0].containers
    assert service_templates[0].containers[0].tag == "container-ora"
    assert service_templates[0].containers[0].image == (
        "ghcr.io/MoonyFringers/shepherd/oracle:19.3.0.0_TZ40"
    )
    assert service_templates[0].containers[0].build is None
    assert service_templates[0].containers[0].hostname == "ora-host"
    assert service_templates[0].containers[0].container_name == "ora-cnt-1"
    assert service_templates[0].containers[0].environment == []
    assert (
        service_templates[0].containers[0].ports
        and service_templates[0].containers[0].ports[0] == "1521:1521"
    )
    assert (
        service_templates[0].containers[0].volumes
        and service_templates[0].containers[0].volumes[0]
        == "app_data:/mnt/test"
    )
    assert (
        service_templates[0].properties
        and service_templates[0].properties["pump_dir_name"] == "PUMP_DIR"
    )
    assert service_templates[0].properties["root_db_name"] == "ORCLCDB"
    assert service_templates[0].properties["plug_db_name"] == "ORCLPDB1"
    assert service_templates[0].properties["sys_user"] == "sys"
    assert service_templates[0].properties["sys_psw"] == "sys"
    assert service_templates[0].properties["user"] == "docker"
    assert service_templates[0].properties["psw"] == "docker"
    assert service_templates[1].tag == "postgres"
    assert service_templates[1].factory == "docker"
    assert service_templates[1].containers
    assert service_templates[1].containers[0].image == (
        "ghcr.io/MoonyFringers/shepherd/postgres:17-3.5"
    )
    assert service_templates[1].containers[0].build
    assert service_templates[1].containers[0].build.context_path == (
        "${test_path}/envs/#{env.tag}/build"
    )
    assert service_templates[1].containers[0].build.dockerfile_path == (
        "${test_path}/envs/#{env.tag}/build/Dockerfile"
    )
    assert service_templates[1].containers[0].environment == []
    assert (
        service_templates[1].containers[0].ports
        and service_templates[1].containers[0].ports[0] == "5432:5432"
    )
    assert (
        service_templates[1].properties
        and service_templates[1].properties["sys_user"] == "sys"
    )
    assert service_templates[1].properties["sys_psw"] == "sys"
    assert service_templates[1].properties["user"] == "docker"
    assert service_templates[1].properties["psw"] == "docker"
    assert config.envs[0].template == "default"
    assert config.envs[0].factory == Constants.ENV_FACTORY_DEFAULT
    assert config.envs[0].tag == "sample-1"
    services = config.envs[0].services
    assert services and services[0].template == "postgres"
    assert services[0].factory == "docker"
    assert services[0].tag == "pg-1"
    assert services[0].containers
    assert services[0].containers[0].image == (
        "ghcr.io/MoonyFringers/shepherd/postgres:17-3.5"
    )
    properties = services[0].properties
    assert properties and properties["sys_user"] == "syspg1"
    assert properties["sys_psw"] == "syspg1"
    assert properties["user"] == "pg1"
    assert properties["psw"] == "pg1"
    upstreams = services[0].upstreams
    assert upstreams and upstreams[0].tag == "upstream-1"
    properties = upstreams[0].properties
    assert properties and properties["user"] == "pg1up"
    assert properties["psw"] == "pg1up"
    assert properties["host"] == "localhost"
    assert properties["port"] == "5432"
    assert properties["database"] == "d_pg1"
    assert properties["unix_user"] == "postgres"
    assert properties["dump_dir"] == "/dumps"
    assert upstreams[0].is_enabled()
    assert upstreams[1].tag == "upstream-2"
    properties = upstreams[1].properties
    assert properties and properties["user"] == "pg2up"
    assert properties["psw"] == "pg2up"
    assert properties["host"] == "moon"
    assert properties["port"] == "5432"
    assert properties["database"] == "d_pg2"
    assert properties["unix_user"] == "postgres"
    assert properties["dump_dir"] == "/dumps/2"
    assert not upstreams[1].is_enabled()
    assert services[1].template == "traefik"
    assert services[1].factory == "docker"
    assert services[2].template == "custom-1"
    assert services[2].tag == "primary"
    assert services[3].template == "nodejs"
    assert services[3].tag == "poke"
    assert services[3].containers
    environment = services[3].containers[0].environment
    assert environment and environment[0] == "USER=user"
    assert environment and environment[1] == "PSW=psw"
    ports = services[3].containers[0].ports
    assert config.envs[0].networks
    assert config.envs[0].networks[0].tag == "shpdnet"
    assert config.envs[0].networks[0].name == "envnet"
    assert config.envs[0].networks[0].is_external()
    assert config.envs[0].volumes
    assert config.envs[0].volumes[0].tag == "app_data"
    assert config.envs[0].volumes[0].driver == "local"
    assert not config.envs[0].volumes[0].is_external()

    assert ports and ports[0] == "3000:3000"
    assert config.templates_path == "${test_path}/templates"
    assert config.envs_path == "${test_path}/envs"
    assert config.plugins is not None
    assert config.plugins[0].id == "acme"
    assert config.plugins[0].enabled == "true"
    assert config.plugins[0].is_enabled() is True
    assert config.plugins[0].version == "1.2.3"
    assert config.plugins[0].config == {
        "region": "eu-west-1",
        "enabled_feature": True,
    }
    assert config.envs[0].status.active is True
    assert config.envs[0].status.rendered_config is None


@pytest.mark.cfg
def test_core_canonical_template_lookup(mocker: MockerFixture):
    cMng = _load_config_manager(mocker)

    env_template = cMng.get_environment_template("default")
    assert env_template is not None
    assert cMng.get_environment_template("core/default") == env_template

    svc_template = cMng.get_service_template("oracle")
    assert svc_template is not None
    assert cMng.get_service_template("core/oracle") == svc_template

    assert cMng.get_service_template_path("oracle") == os.path.join(
        cMng.config.templates_path,
        Constants.SVC_TEMPLATES_DIR,
        "oracle",
    )
    assert cMng.get_service_template_path("core/oracle") == os.path.join(
        cMng.config.templates_path,
        Constants.SVC_TEMPLATES_DIR,
        "oracle",
    )


@pytest.mark.cfg
def test_core_canonical_factory_dispatch(mocker: MockerFixture):
    cMng = _load_config_manager(mocker)
    svc_factory = ShpdServiceFactory(cMng)
    env_factory = ShpdEnvironmentFactory(cMng, svc_factory)

    env_template = deepcopy(cMng.get_environment_template("default"))
    assert env_template is not None
    env_template.factory = cMng.get_canonical_env_factory_id(
        Constants.ENV_FACTORY_DEFAULT
    )

    service_template = cMng.get_service_template("oracle")
    assert service_template is not None
    service_cfg = cMng.svc_cfg_from_service_template(
        service_template, "svc-core", None
    )
    service_cfg.factory = cMng.get_canonical_svc_factory_id(
        Constants.SVC_FACTORY_DEFAULT
    )

    env_cfg = deepcopy(cMng.config.envs[0])

    assert isinstance(
        env_factory.new_environment(env_template, "sample-core"),
        DockerComposeEnv,
    )
    assert isinstance(
        svc_factory.new_service_from_cfg(env_cfg, service_cfg),
        DockerComposeSvc,
    )


@pytest.mark.cfg
def test_load_user_values_file_not_found(mocker: MockerFixture):
    """Test file_values_path does not exist"""

    mock_open1 = mock_open(read_data="{}")
    mocker.patch(
        "builtins.open",
        side_effect=[OSError("File not found"), mock_open1.return_value],
    )

    with pytest.raises(SystemExit) as exc_info:
        ConfigMng(".shpd.conf")
        assert exc_info.value.code == 1


@pytest.mark.cfg
def test_load_invalid_user_values(mocker: MockerFixture):
    """Test invalid user values"""

    mock_open1 = mock_open(read_data="key")
    mock_open2 = mock_open(read_data="{}")

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch(
        "builtins.open",
        side_effect=[mock_open1.return_value, mock_open2.return_value],
    )

    with pytest.raises(SystemExit) as exc_info:
        ConfigMng(".shpd.conf")
        assert exc_info.value.code == 1


@pytest.mark.cfg
def test_store_config_with_real_files():
    """Test storing config using real files in ./"""

    try:
        with (
            open(".shpd.yaml", "w") as config_file,
            open(".shpd.conf", "w") as values_file,
        ):
            values = read_fixture("cfg", "values.conf")
            config_yaml = read_fixture("cfg", "shpd.yaml")
            config_file.write(config_yaml)
            values_file.write(values.replace("${test_path}", "."))

        cMng = ConfigMng(values_file.name)
        config: Config = cMng.load_config()
        cMng.store_config(config)

        with open(".shpd.yaml", "r") as output_file:
            content = output_file.read()
            y1: str = yaml.dump(yaml.safe_load(content), sort_keys=True)
            expected = yaml.safe_load(config_yaml)
            expected.setdefault("env_template_fragments", None)
            expected.setdefault("remotes", None)
            for item in expected.get("env_templates", []):
                item.setdefault("ready", None)
                item.setdefault("fragments", None)
            for item in expected.get("envs", []):
                item.setdefault("ready", None)
                item.setdefault("tracking_remote", None)
                item.setdefault("dehydrated", None)
            for remote in expected.get("remotes") or []:
                remote.setdefault("host", None)
                remote.setdefault("port", None)
                remote.setdefault("user", None)
                remote.setdefault("password", None)
                remote.setdefault("root_path", None)
                remote.setdefault("identity_file", None)
                remote.setdefault("local_cache", None)
                remote.setdefault("properties", None)
            y2: str = yaml.dump(expected, sort_keys=True)
            assert y1 == y2

    finally:
        for file_path in (".shpd.yaml", ".shpd.conf"):
            if os.path.exists(file_path):
                os.remove(file_path)


@pytest.mark.cfg
def test_load_config_change_resolve_status(mocker: MockerFixture):
    """Test regular parsing"""

    mocker.patch.dict(
        os.environ,
        {
            "ora_container_name": "ora-cnt-1",
            "ora_hostname": "ora-host",
        },
    )

    values = read_fixture("cfg", "values.conf")
    config_yaml = read_fixture("cfg", "shpd.yaml")
    mock_open1 = mock_open(read_data=values)
    mock_open2 = mock_open(read_data=config_yaml)

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch(
        "builtins.open",
        side_effect=[mock_open1.return_value, mock_open2.return_value],
    )

    cMng = ConfigMng(".shpd.conf")
    config: Config = cMng.load_config()
    config.set_unresolved()
    assert config.envs
    assert config.envs[0].services
    config.envs[0].get_yaml(True)
    config.envs[0].services[0].get_yaml(True)
    config.set_resolved()
    config.envs[0].get_yaml(False)
    config.envs[0].services[0].get_yaml(False)


@pytest.mark.cfg
def test_parse_plugin_descriptor():
    descriptor_yaml = """
id: acme
name: Acme Plugin
version: 1.2.3
plugin_api_version: 1
entrypoint:
  module: plugin.main
  class: AcmePlugin
description: Example plugin
capabilities:
  templates: true
  commands: false
default_config:
  region: eu-west-1
env_templates:
  - tag: baseline
    factory: baseline-factory
    service_templates:
      - template: api
        tag: plugin-api
    probes: null
    networks: null
    volumes: null
service_templates:
  - tag: api
    factory: api-factory
    labels: []
    properties:
      source: plugin
    containers:
      - image: busybox
        tag: app
        container_name: null
        hostname: null
        workdir: null
        volumes: []
        environment: []
        ports: []
        networks: []
        extra_hosts: []
        inits: null
        build: null
    start: null
"""

    descriptor = parse_plugin_descriptor(descriptor_yaml)

    assert descriptor.id == "acme"
    assert descriptor.name == "Acme Plugin"
    assert descriptor.version == "1.2.3"
    assert descriptor.plugin_api_version == 1
    assert descriptor.entrypoint.module == "plugin.main"
    assert descriptor.entrypoint.class_name == "AcmePlugin"
    assert descriptor.description == "Example plugin"
    assert descriptor.capabilities == {
        "templates": True,
        "commands": False,
    }
    assert descriptor.default_config == {"region": "eu-west-1"}
    assert descriptor.env_templates is not None
    assert descriptor.env_templates[0].tag == "baseline"
    assert descriptor.env_templates[0].factory == "baseline-factory"
    assert descriptor.env_templates[0].service_templates is not None
    assert descriptor.env_templates[0].service_templates[0].template == "api"
    assert descriptor.service_templates is not None
    assert descriptor.service_templates[0].tag == "api"
    assert descriptor.service_templates[0].factory == "api-factory"


@pytest.mark.cfg
def test_parse_plugin_descriptor_requires_entrypoint():
    descriptor_yaml = """
id: acme
name: Acme Plugin
version: 1.2.3
plugin_api_version: 1
"""

    with pytest.raises(ValueError):
        parse_plugin_descriptor(descriptor_yaml)


@pytest.mark.cfg
def test_parse_plugin_descriptor_rejects_non_boolean_capabilities():
    descriptor_yaml = """
id: acme
name: Acme Plugin
version: 1.2.3
plugin_api_version: 1
entrypoint:
  module: plugin.main
  class: AcmePlugin
capabilities:
  commands: "false"
  completion: "0"
"""

    with pytest.raises(ValueError):
        parse_plugin_descriptor(descriptor_yaml)


@pytest.mark.cfg
def test_parse_plugin_descriptor_allows_omitted_network_and_volume_external():
    descriptor_yaml = """
id: acme
name: Acme Plugin
version: 1.2.3
plugin_api_version: 1
entrypoint:
  module: plugin.main
  class: AcmePlugin
env_templates:
  - tag: baseline
    factory: docker-compose
    service_templates: []
    probes: []
    networks:
      - tag: default
    volumes:
      - tag: data
"""

    descriptor = parse_plugin_descriptor(descriptor_yaml)

    assert descriptor.env_templates is not None
    assert descriptor.env_templates[0].networks is not None
    assert descriptor.env_templates[0].networks[0].external == "false"
    assert descriptor.env_templates[0].volumes is not None
    assert descriptor.env_templates[0].volumes[0].external == "false"


@pytest.mark.cfg
def test_parse_plugin_enabled_supports_bool_and_placeholder():
    config_yaml = """
templates_path: ${templates_path}
envs_path: ${envs_path}
plugins:
  - id: acme
    enabled: false
    version: 1.2.3
  - id: beta
    enabled: ${plugin_enabled}
    version: 2.0.0
envs: []
"""

    config = parse_config(config_yaml)

    assert config.plugins is not None
    assert config.plugins[0].enabled == "false"
    assert config.plugins[0].is_enabled() is False
    assert config.plugins[1].enabled == "${plugin_enabled}"


@pytest.mark.cfg
def test_copy_config(mocker: MockerFixture):
    """Test copying config with mock"""

    values = read_fixture("cfg", "values.conf")
    config_yaml = read_fixture("cfg", "shpd.yaml")
    mock_open1 = mock_open(read_data=values)
    mock_open2 = mock_open(read_data=config_yaml)

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch(
        "builtins.open",
        side_effect=[mock_open1.return_value, mock_open2.return_value],
    )

    cMng = ConfigMng(".shpd.conf")
    config: Config = cMng.load_config()

    service_templates = config.service_templates
    assert service_templates
    svc_templ = service_templates[0]
    svc_templ_cloned = cMng.svc_tmpl_cfg_from_other(svc_templ)
    assert svc_templ_cloned == svc_templ

    env = config.envs[0]
    assert env
    env_cloned = cMng.env_cfg_from_other(env)
    assert env_cloned != env
    env_cloned.status = env.status
    assert env_cloned == env

    services = config.envs[0].services
    assert services
    svc = services[0]
    assert svc


@pytest.mark.cfg
def test_load_config_with_refs(mocker: MockerFixture):
    """Test loading config with references"""

    values = read_fixture("cfg", "values.conf")
    config_yaml_with_refs = read_fixture("cfg", "shpd_with_refs.yaml")
    mock_open1 = mock_open(read_data=values.replace("${test_path}", "."))
    mock_open2 = mock_open(read_data=config_yaml_with_refs)

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch(
        "builtins.open",
        side_effect=[mock_open1.return_value, mock_open2.return_value],
    )

    cMng = ConfigMng(".shpd.conf")
    config: Config = cMng.load_config()

    assert config.envs
    assert config.envs[0].template == "nginx-postgres"
    assert config.envs[0].factory == Constants.ENV_FACTORY_DEFAULT
    assert config.envs[0].tag == "foo"
    assert config.envs[0].services
    assert config.envs[0].services[0].template == "nginx"
    assert config.envs[0].services[0].factory == Constants.SVC_FACTORY_DEFAULT
    assert config.envs[0].services[0].containers
    assert config.envs[0].services[0].containers[0].image == "nginx:latest"
    assert config.envs[0].services[0].containers[0].networks
    assert config.envs[0].services[0].containers[0].networks[0] == "foo"
    assert config.envs[0].services[0].properties
    assert config.envs[0].services[0].properties["com.example.type"] == "web"
    assert config.envs[0].volumes
    assert config.envs[0].volumes[0].tag == "nginx"
    assert config.envs[0].volumes[0].driver_opts
    assert config.envs[0].volumes[0].driver_opts["device"] == "./envs/foo/nginx"
    assert config.envs[0].volumes[1].tag == "postgres"
    assert config.envs[0].volumes[1].driver_opts
    assert (
        config.envs[0].volumes[1].driver_opts["device"] == "./envs/foo/postgres"
    )
    assert config.envs[0].networks
    assert config.envs[0].networks[0].tag == "foo"
    assert config.envs[0].networks[0].name == "foo"
    assert config.envs[0].services[1].template == "postgres"
    assert config.envs[0].services[1].service_class == "#{not.exist}"
    assert config.envs[0].services[1].factory == Constants.SVC_FACTORY_DEFAULT
    assert config.envs[0].services[1].containers
    assert config.envs[0].services[1].containers[0].image == "postgres:14"
    assert config.envs[0].services[1].containers[0].networks
    assert config.envs[0].services[1].containers[0].networks[0] == "foo"
    assert config.envs[0].services[1].properties
    assert config.envs[0].services[1].properties["com.example.type"] == "db"


@pytest.mark.cfg
def test_store_config_with_refs_with_real_files():
    """Test storing config using real files in ./"""

    try:
        with (
            open(".shpd.yaml", "w") as config_file,
            open(".shpd.conf", "w") as values_file,
        ):
            values = read_fixture("cfg", "values.conf")
            config_yaml_with_refs = read_fixture("cfg", "shpd_with_refs.yaml")
            config_file.write(config_yaml_with_refs)
            values_file.write(values.replace("${test_path}", "."))

        cMng = ConfigMng(values_file.name)
        config: Config = cMng.load_config()
        cMng.store_config(config)

        with open(".shpd.yaml", "r") as output_file:
            content = output_file.read()
            y1: str = yaml.dump(yaml.safe_load(content), sort_keys=True)
            expected = yaml.safe_load(config_yaml_with_refs)
            expected.setdefault("env_template_fragments", None)
            expected.setdefault("plugins", None)
            expected.setdefault("remotes", None)
            for item in expected.get("env_templates", []):
                item.setdefault("ready", None)
                item.setdefault("fragments", None)
            for item in expected.get("envs", []):
                item.setdefault("ready", None)
                item.setdefault("tracking_remote", None)
                item.setdefault("dehydrated", None)
            y2: str = yaml.dump(expected, sort_keys=True)
            assert y1 == y2

    finally:
        for file_path in (".shpd.yaml", ".shpd.conf"):
            if os.path.exists(file_path):
                os.remove(file_path)


@pytest.mark.cfg
def test_load_config_parses_lifecycle_sections(
    mocker: MockerFixture,
):
    """
    Parse coverage for:
      - service_templates[].init / start
      - envs[].services[].start
    """

    mocker.patch.dict(
        os.environ,
        {
            "ora_container_name": "ora-cnt-1",
            "ora_hostname": "ora-host",
        },
    )
    values = read_fixture("cfg", "values.conf")
    config_yaml = read_fixture("cfg", "shpd_lifecycle.yaml")
    mock_open1 = mock_open(read_data=values)
    mock_open2 = mock_open(read_data=config_yaml)

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch(
        "builtins.open",
        side_effect=[mock_open1.return_value, mock_open2.return_value],
    )

    cMng = ConfigMng(".shpd.conf")
    config: Config = cMng.load_config()
    config.set_resolved()

    env_templates = config.env_templates
    assert env_templates

    # probes
    pg_env_tpl = env_templates[0]
    assert pg_env_tpl.probes is not None
    assert len(pg_env_tpl.probes) == 3

    created = next((p for p in pg_env_tpl.probes if p.tag == "created"), None)
    ready = next((p for p in pg_env_tpl.probes if p.tag == "ready"), None)
    live = next((p for p in pg_env_tpl.probes if p.tag == "live"), None)

    assert created is not None
    assert created.container is not None
    assert created.container.image == "busybox:1.36"
    assert created.script is not None
    assert created.script_path is None

    assert ready is not None
    assert ready.container is not None
    assert ready.script == "sh -c 'pg_isready -h db -p 5432 -U sys -d docker'"

    assert live is not None
    assert live.container is None
    assert live.script is None
    assert live.script_path is None

    svc_templates = config.service_templates
    assert svc_templates
    pg_tpl = next((s for s in svc_templates if s.tag == "postgres"), None)
    assert pg_tpl is not None

    # inits
    assert pg_tpl.containers is not None
    assert len(pg_tpl.containers) == 1
    assert pg_tpl.containers[0].inits is not None
    assert len(pg_tpl.containers[0].inits) == 1
    init0 = pg_tpl.containers[0].inits[0]
    assert init0.tag == "create-docker-user"
    assert init0.script == "sh -c 'echo init ok'"
    assert init0.script_path is None
    assert init0.when_probes == ["ready"]

    # start
    assert pg_tpl.start is not None
    assert pg_tpl.start.when_probes == ["sample-1-test-probe"]

    assert config.envs
    env0 = config.envs[0]
    assert env0.services
    db_svc = next((s for s in env0.services if s.tag == "db"), None)
    assert db_svc is not None

    assert db_svc.start is not None
    assert db_svc.start.when_probes == ["sample-1-test-probe"]


# ---------------------------------------------------------------------------
# env_template_fragments — parse_plugin_descriptor tests
# ---------------------------------------------------------------------------


@pytest.mark.cfg
def test_parse_plugin_descriptor_with_fragments_and_depends_on():
    descriptor_yaml = """
id: acme
name: Acme Plugin
version: 1.2.3
plugin_api_version: 1
entrypoint:
  module: plugin.main
  class: AcmePlugin
env_template_fragments:
  - tag: db-bundle
    service_template:
      template: api
      tag: db
    probes:
      - tag: db-ready
        container:
          tag: db-probe
          image: busybox:stable-glibc
          networks: []
        script: "sh -c 'sleep 1'"
    volumes:
      - tag: db_data
        external: false
        driver: local
    networks: []
depends_on:
  - id: other-plugin
    version: ">=1.0.0"
"""

    descriptor = parse_plugin_descriptor(descriptor_yaml)

    assert descriptor.env_template_fragments is not None
    assert len(descriptor.env_template_fragments) == 1
    frag = descriptor.env_template_fragments[0]
    assert frag.tag == "db-bundle"
    assert frag.service_template.template == "api"
    assert frag.service_template.tag == "db"
    assert frag.probes is not None
    assert frag.probes[0].tag == "db-ready"
    assert frag.volumes is not None
    assert frag.volumes[0].tag == "db_data"

    assert descriptor.depends_on is not None
    assert len(descriptor.depends_on) == 1
    dep = descriptor.depends_on[0]
    assert dep.id == "other-plugin"
    assert dep.version == ">=1.0.0"


@pytest.mark.cfg
def test_parse_plugin_descriptor_rejects_non_list_fragments():
    descriptor_yaml = """
id: acme
name: Acme Plugin
version: 1.2.3
plugin_api_version: 1
entrypoint:
  module: plugin.main
  class: AcmePlugin
env_template_fragments: not-a-list
"""

    with pytest.raises(
        ValueError, match="env_template_fragments must be a list"
    ):
        parse_plugin_descriptor(descriptor_yaml)


@pytest.mark.cfg
def test_parse_plugin_descriptor_rejects_non_list_depends_on():
    descriptor_yaml = """
id: acme
name: Acme Plugin
version: 1.2.3
plugin_api_version: 1
entrypoint:
  module: plugin.main
  class: AcmePlugin
depends_on: not-a-list
"""

    with pytest.raises(ValueError, match="depends_on must be a list"):
        parse_plugin_descriptor(descriptor_yaml)


# ---------------------------------------------------------------------------
# env_template_fragments — FragmentRefCfg parse tests
# ---------------------------------------------------------------------------


@pytest.mark.cfg
def test_parse_fragment_ref_string_shorthand():
    """A plain string in fragments: is parsed as FragmentRefCfg with no with."""
    config_yaml = """
templates_path: /tmp
envs_path: /tmp
env_templates:
  - tag: demo
    factory: docker-compose
    service_templates: []
    probes: []
    networks: []
    volumes: []
    fragments:
      - my-plugin/base
envs: []
"""
    config = parse_config(config_yaml)

    assert config.env_templates is not None
    tmpl = config.env_templates[0]
    assert tmpl.fragments is not None
    assert len(tmpl.fragments) == 1
    ref = tmpl.fragments[0]
    assert ref.id == "my-plugin/base"
    assert ref.with_values is None


@pytest.mark.cfg
def test_parse_fragment_ref_with_values():
    """Fragment ref dict form with a with: block is parsed into with_values."""
    config_yaml = """
templates_path: /tmp
envs_path: /tmp
env_templates:
  - tag: demo
    factory: docker-compose
    service_templates: []
    probes: []
    networks: []
    volumes: []
    fragments:
      - id: my-plugin/base
        with:
          key1: value1
          key2: value2
envs: []
"""
    config = parse_config(config_yaml)

    assert config.env_templates is not None
    frags = config.env_templates[0].fragments
    assert frags is not None
    ref = frags[0]
    assert ref.id == "my-plugin/base"
    assert ref.with_values == {"key1": "value1", "key2": "value2"}


# ---------------------------------------------------------------------------
# env_template_fragments — parse_config tests
# ---------------------------------------------------------------------------


@pytest.mark.cfg
def test_parse_config_with_env_template_fragments(mocker: MockerFixture):
    """Top-level env_template_fragments section is parsed and accessible."""
    values = read_fixture("cfg", "values.conf")
    config_yaml = read_fixture("cfg", "shpd_with_fragments.yaml")

    mock_open1 = mock_open(read_data=values)
    mock_open2 = mock_open(read_data=config_yaml)
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch(
        "builtins.open",
        side_effect=[mock_open1.return_value, mock_open2.return_value],
    )
    cMng = ConfigMng(".shpd.conf")

    config = cMng.load_config()

    assert config.env_template_fragments is not None
    assert len(config.env_template_fragments) == 1
    frag = config.env_template_fragments[0]
    assert frag.tag == "worker-base"
    assert frag.service_template.template == "worker"
    assert frag.service_template.tag == "job"
    assert frag.probes is not None and len(frag.probes) == 1
    assert frag.probes[0].tag == "job-ready"
    assert frag.volumes is not None and len(frag.volumes) == 1
    assert frag.volumes[0].tag == "job_data"
    assert frag.networks is not None and len(frag.networks) == 1
    assert frag.networks[0].tag == "default"

    assert config.env_templates is not None
    tmpl = config.env_templates[0]
    assert tmpl.fragments is not None and len(tmpl.fragments) == 1
    ref = tmpl.fragments[0]
    assert ref.id == "worker-base"
    assert ref.with_values == {"job_name": "my-job"}


# ---------------------------------------------------------------------------
# _apply_fragment_values tests
# ---------------------------------------------------------------------------


def _make_minimal_config_mng(mocker: MockerFixture) -> ConfigMng:
    """Return a ConfigMng backed by the fragment fixture."""
    values = read_fixture("cfg", "values.conf")
    config_yaml = read_fixture("cfg", "shpd_with_fragments.yaml")
    mock_open1 = mock_open(read_data=values)
    mock_open2 = mock_open(read_data=config_yaml)
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch(
        "builtins.open",
        side_effect=[mock_open1.return_value, mock_open2.return_value],
    )
    cMng = ConfigMng(".shpd.conf")
    cMng.load()
    return cMng


def _make_test_fragment(
    script: str = "sh -c 'echo ${db_name}'",
) -> EnvTemplateFragmentCfg:
    from config.config import (
        ContainerCfg,
        ProbeCfg,
        VolumeCfg,
    )

    return EnvTemplateFragmentCfg(
        tag="test-frag",
        service_template=ServiceTemplateRefCfg(template="svc/main", tag="svc"),
        probes=[
            ProbeCfg(
                tag="svc-ready",
                container=ContainerCfg(
                    tag="probe",
                    image="busybox:stable-glibc",
                    networks=["#{env.tag}-net"],
                ),
                script=script,
            )
        ],
        volumes=[VolumeCfg(tag="svc_data", external="false")],
        networks=[],
    )


@pytest.mark.cfg
def test_apply_fragment_values_substitutes_known_keys(mocker: MockerFixture):
    """${KEY} present in with_values is replaced in fragment content."""
    cMng = _make_minimal_config_mng(mocker)
    frag = _make_test_fragment("sh -c 'echo ${db_name}'")

    result = getattr(cMng, "_apply_fragment_values")(frag, {"db_name": "myapp"})

    assert result.probes is not None
    assert result.probes[0].script == "sh -c 'echo myapp'"


@pytest.mark.cfg
def test_apply_fragment_values_leaves_unknown_keys_intact(
    mocker: MockerFixture,
):
    """${KEY} absent from with_values is left as-is for global resolution."""
    cMng = _make_minimal_config_mng(mocker)
    frag = _make_test_fragment("sh -c 'echo ${unknown_var}'")

    result = getattr(cMng, "_apply_fragment_values")(
        frag, {"other_key": "value"}
    )

    assert result.probes is not None
    assert result.probes[0].script == "sh -c 'echo ${unknown_var}'"


@pytest.mark.cfg
def test_apply_fragment_values_leaves_ref_patterns_intact(
    mocker: MockerFixture,
):
    """#{ref.path} patterns pass through _apply_fragment_values unchanged."""
    cMng = _make_minimal_config_mng(mocker)
    frag = _make_test_fragment("sh -c 'echo ok'")
    # networks=["#{env.tag}-net"] is set in _make_test_fragment.

    result = getattr(cMng, "_apply_fragment_values")(frag, {"db_name": "myapp"})

    assert result.probes is not None
    cnt = result.probes[0].container
    assert cnt is not None
    assert cnt.networks is not None
    assert "#{env.tag}-net" in cnt.networks


# ---------------------------------------------------------------------------
# env_cfg_from_tag fragment merge tests
# ---------------------------------------------------------------------------


def _load_fragment_config_mng(mocker: MockerFixture) -> ConfigMng:
    """Return a fully loaded ConfigMng from the fragment fixture."""
    values = read_fixture("cfg", "values.conf")
    config_yaml = read_fixture("cfg", "shpd_with_fragments.yaml")
    mock_open1 = mock_open(read_data=values)
    mock_open2 = mock_open(read_data=config_yaml)
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch(
        "builtins.open",
        side_effect=[mock_open1.return_value, mock_open2.return_value],
    )
    cMng = ConfigMng(".shpd.conf")
    cMng.load()
    return cMng


@pytest.mark.cfg
def test_env_cfg_from_tag_merges_core_fragment(mocker: MockerFixture):
    """Importing a core fragment adds its service, probe, volume, network."""
    cMng = _load_fragment_config_mng(mocker)

    demo_tmpl = cMng.get_environment_template("demo")
    assert demo_tmpl is not None

    env = cMng.env_cfg_from_tag(demo_tmpl, "test-env")

    # Service contributed by the fragment
    assert env.services is not None
    tags = {s.tag for s in env.services}
    assert "job" in tags

    # Probe contributed by the fragment
    assert env.probes is not None
    probe_tags = {p.tag for p in env.probes}
    assert "job-ready" in probe_tags

    # Volume contributed by the fragment
    assert env.volumes is not None
    vol_tags = {v.tag for v in env.volumes}
    assert "job_data" in vol_tags

    # Network contributed by the fragment
    assert env.networks is not None
    net_tags = {n.tag for n in env.networks}
    assert "default" in net_tags


@pytest.mark.cfg
def test_env_cfg_from_tag_applies_with_values_in_fragment(
    mocker: MockerFixture,
):
    """with: values are substituted into fragment content at merge time."""
    cMng = _load_fragment_config_mng(mocker)

    demo_tmpl = cMng.get_environment_template("demo")
    assert demo_tmpl is not None

    env = cMng.env_cfg_from_tag(demo_tmpl, "test-env")

    # The fixture fragment probe script is "sh -c 'echo ${job_name} && sleep 1'"
    # and with: {job_name: my-job}, so after merge it must be substituted.
    assert env.probes is not None
    probe = next(p for p in env.probes if p.tag == "job-ready")
    assert probe.script is not None
    assert "${job_name}" not in probe.script
    assert "my-job" in probe.script


@pytest.mark.cfg
def test_env_cfg_from_tag_fails_on_unknown_fragment(mocker: MockerFixture):
    """Referencing an unknown fragment ID causes a hard failure."""
    from config.config import EnvironmentTemplateCfg

    cMng = _load_fragment_config_mng(mocker)

    bad_tmpl = EnvironmentTemplateCfg(
        tag="bad",
        factory="docker-compose",
        service_templates=[],
        probes=[],
        networks=[],
        volumes=[],
        fragments=[FragmentRefCfg(id="does-not-exist")],
    )

    with pytest.raises(SystemExit):
        cMng.env_cfg_from_tag(bad_tmpl, "test-env")


@pytest.mark.cfg
def test_env_cfg_from_tag_fails_on_duplicate_service_tag(mocker: MockerFixture):
    """Two fragment refs with the same service tag cause a hard failure."""
    from config.config import EnvironmentTemplateCfg

    cMng = _load_fragment_config_mng(mocker)

    # Both fragments use service tag "job" (the fixture fragment does)
    dup_tmpl = EnvironmentTemplateCfg(
        tag="dup",
        factory="docker-compose",
        service_templates=[],
        probes=[],
        networks=[],
        volumes=[],
        fragments=[
            FragmentRefCfg(id="worker-base", with_values={"job_name": "a"}),
            FragmentRefCfg(id="worker-base", with_values={"job_name": "b"}),
        ],
    )

    with pytest.raises(SystemExit):
        cMng.env_cfg_from_tag(dup_tmpl, "test-env")


# ---------------------------------------------------------------------------
# Remote storage config tests
# ---------------------------------------------------------------------------


@pytest.mark.cfg
def test_load_config_with_remotes(mocker: MockerFixture):
    """Fixture remotes block parses correctly; fields and defaults round-trip."""
    cMng = _load_config_manager(mocker)
    config = cMng.config

    remotes = config.remotes
    assert remotes is not None
    assert len(remotes) == 2

    prod = remotes[0]
    assert prod.name == "prod-backup"
    assert prod.type == "ftp"
    assert prod.host == "storage.example.com"
    assert prod.port == 21
    assert prod.user == "backup"
    assert prod.password == "${BACKUP_PWD}"
    assert prod.root_path == "/shepherd"
    assert prod.is_default() is True
    assert prod.chunk.min_size_kb == 512
    assert prod.chunk.avg_size_kb == 2048
    assert prod.chunk.max_size_kb == 8192
    assert prod.local_cache is not None
    assert prod.local_cache.max_size_gb == 10

    dev = remotes[1]
    assert dev.name == "dev-backup"
    assert dev.type == "sftp"
    assert dev.identity_file == "~/.ssh/id_ed25519"
    assert dev.is_default() is False


@pytest.mark.cfg
def test_load_config_remote_chunk_defaults():
    """A remote with no chunk: block gets the default chunk parameters."""
    config_yaml = """
templates_path: /tmp
envs_path: /tmp
remotes:
  - name: minimal
    type: ftp
    host: ftp.example.com
envs: []
"""
    config = parse_config(config_yaml)

    assert config.remotes is not None
    remote = config.remotes[0]
    assert remote.chunk == RemoteChunkCfg()
    assert remote.chunk.min_size_kb == 512
    assert remote.chunk.avg_size_kb == 2048
    assert remote.chunk.max_size_kb == 8192
    assert remote.local_cache is None
    assert remote.is_default() is False


@pytest.mark.cfg
def test_store_and_reload_remotes():
    """Remotes survive a store_config → re-parse round-trip."""
    try:
        with (
            open(".shpd.yaml", "w") as config_file,
            open(".shpd.conf", "w") as values_file,
        ):
            values = read_fixture("cfg", "values.conf")
            config_yaml = read_fixture("cfg", "shpd.yaml")
            config_file.write(config_yaml)
            values_file.write(values.replace("${test_path}", "."))

        cMng = ConfigMng(values_file.name)
        config: Config = cMng.load_config()
        cMng.store_config(config)

        with open(".shpd.yaml", "r") as f:
            stored_yaml = f.read()

        reloaded = parse_config(stored_yaml)
        assert reloaded.remotes is not None
        assert len(reloaded.remotes) == 2

        prod = reloaded.remotes[0]
        assert prod.name == "prod-backup"
        assert prod.is_default() is True

        dev = reloaded.remotes[1]
        assert dev.name == "dev-backup"
        assert dev.is_default() is False

    finally:
        for path in (".shpd.yaml", ".shpd.conf"):
            if os.path.exists(path):
                os.remove(path)


@pytest.mark.cfg
def test_tracking_remote_parses(mocker: MockerFixture):
    """tracking_remote on an env is parsed from the fixture."""
    cMng = _load_config_manager(mocker)
    env = cMng.config.envs[0]
    assert env.tracking_remote == "prod-backup"


@pytest.mark.cfg
def test_tracking_remote_round_trip():
    """tracking_remote survives a store_config → re-parse round-trip."""
    try:
        with (
            open(".shpd.yaml", "w") as config_file,
            open(".shpd.conf", "w") as values_file,
        ):
            values = read_fixture("cfg", "values.conf")
            config_yaml = read_fixture("cfg", "shpd.yaml")
            config_file.write(config_yaml)
            values_file.write(values.replace("${test_path}", "."))

        cMng = ConfigMng(values_file.name)
        config: Config = cMng.load_config()
        cMng.store_config(config)

        with open(".shpd.yaml", "r") as f:
            stored_yaml = f.read()

        reloaded = parse_config(stored_yaml)
        assert reloaded.envs[0].tracking_remote == "prod-backup"

    finally:
        for path in (".shpd.yaml", ".shpd.conf"):
            if os.path.exists(path):
                os.remove(path)


@pytest.mark.cfg
def test_add_remote_rejects_duplicate_name(mocker: MockerFixture):
    """add_remote raises ValueError when a remote with the same name exists."""
    cMng = _load_config_manager(mocker)

    duplicate = RemoteCfg(name="prod-backup", type="ftp")
    with pytest.raises(ValueError, match="prod-backup"):
        cMng.add_remote(duplicate)
