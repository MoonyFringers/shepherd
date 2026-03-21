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


import os
from unittest.mock import mock_open

import pytest
import yaml
from pytest_mock import MockerFixture
from test_util import read_fixture

from config import Config, ConfigMng, parse_config, parse_plugin_descriptor
from util import Constants


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
        == "${test_path}/volumes/srv/data"
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
    assert config.envs[0].template == Constants.ENV_TEMPLATE_DEFAULT
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
    assert config.volumes_path == "${test_path}/volumes"
    assert config.staging_area.volumes_path == "${test_path}/sa_volumes"
    assert config.staging_area.images_path == "${test_path}/sa_images"
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
            for item in expected.get("env_templates", []):
                item.setdefault("ready", None)
            for item in expected.get("envs", []):
                item.setdefault("ready", None)
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
def test_parse_plugin_enabled_supports_bool_and_placeholder():
    config_yaml = """
templates_path: ${templates_path}
envs_path: ${envs_path}
volumes_path: ${volumes_path}
staging_area:
  volumes_path: ${staging_area_volumes_path}
  images_path: ${staging_area_images_path}
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
    assert (
        config.envs[0].volumes[0].driver_opts["device"] == "./volumes/foo/nginx"
    )
    assert config.envs[0].volumes[1].tag == "postgres"
    assert config.envs[0].volumes[1].driver_opts
    assert (
        config.envs[0].volumes[1].driver_opts["device"]
        == "./volumes/foo/postgres"
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
            for item in expected.get("env_templates", []):
                item.setdefault("ready", None)
            for item in expected.get("envs", []):
                item.setdefault("ready", None)
            expected.setdefault("plugins", None)
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
