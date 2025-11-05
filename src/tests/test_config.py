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
from test_util import values

from config import Config, ConfigMng
from util import Constants

config_yaml = """
shpd_registry:
  ftp_server: ${shpd_registry}
  ftp_user: ${shpd_registry_ftp_usr}
  ftp_psw: ${shpd_registry_ftp_psw}
  ftp_shpd_path: ${shpd_registry_ftp_shpd_path}
  ftp_env_imgs_path: ${shpd_registry_ftp_imgs_path}
templates_path: ${templates_path}
envs_path: ${envs_path}
volumes_path: ${volumes_path}
host_inet_ip: ${host_inet_ip}
domain: ${domain}
dns_type: ${dns_type}
ca:
  country: ${ca_country}
  state: ${ca_state}
  locality: ${ca_locality}
  organization: ${ca_org}
  organizational_unit: ${ca_org_unit}
  common_name: ${ca_cn}
  email: ${ca_email}
  passphrase: ${ca_passphrase}
cert:
  country: ${cert_country}
  state: ${cert_state}
  locality: ${cert_locality}
  organization: ${cert_org}
  organizational_unit: ${cert_org_unit}
  common_name: ${cert_cn}
  email: ${cert_email}
  subject_alternative_names: []
staging_area:
  volumes_path: ${staging_area_volumes_path}
  images_path: ${staging_area_images_path}
env_templates:
  - tag: default
    factory: docker-compose
    service_templates:
      - template: default
        tag: service-default
    networks:
      - tag: shpdnet
        name: envnet
        external: true
        driver: null
        attachable: null
        enable_ipv6: null
        driver_opts: null
        ipam: null
    volumes:
      - tag: app_data
        external: false
        name: null
        driver: local
        driver_opts:
          type: none
          o: bind
          device: ${volumes_path}/srv/data
        labels:
          env: production
service_templates:
  - tag: oracle
    factory: docker
    containers:
      - image: ${ora_image}
        tag: container-ora
        hostname: ${ora_hostname}
        container_name: ${ora_container_name}
        workdir: null
        environment: []
        volumes:
          - app_data:/mnt/test
        ports:
          - 1521:${ora_listener_port}
        networks: []
        extra_hosts: []
        subject_alternative_name: null
    build: null
    labels: []
    ingress: false
    empty_env: ${ora_empty_env}
    properties:
      pump_dir_name: ${ora_pump_dir}
      root_db_name: ${ora_root_db_name}
      plug_db_name: ${ora_plug_db_name}
      sys_user: ${db_sys_usr}
      sys_psw: ${db_sys_psw}
      user: ${db_usr}
      psw: ${db_psw}
  - tag: postgres
    factory: docker
    containers:
      - image: ${pg_image}
        tag: container-pg
        hostname: ${pg_hostname}
        container_name: ${pg_container_name}
        workdir: null
        environment: []
        volumes: []
        ports:
          - 5432:${pg_listener_port}
        networks: []
        extra_hosts: []
        subject_alternative_name: null
    build:
      context_path: '#{cfg.envs_path}/#{env.tag}/build'
      dockerfile_path: '#{svc.build.context_path}/Dockerfile'
    labels: []
    ingress: false
    empty_env: ${pg_empty_env}
    properties:
      sys_user: ${db_sys_usr}
      sys_psw: ${db_sys_psw}
      user: ${db_usr}
      psw: ${db_psw}
envs:
  - template: default
    factory: docker-compose
    tag: sample-1
    services:
      - template: postgres
        factory: docker
        containers:
          - image: ghcr.io/MoonyFringers/shepherd/postgres:17-3.5
            tag: container-pg
            hostname: null
            container_name: null
            workdir: null
            volumes: []
            environment: null
            ports: []
            networks: []
            extra_hosts: []
            subject_alternative_name: null
        tag: pg-1
        service_class: null
        build:
          context_path: '#{cfg.envs_path}/#{env.tag}/build'
          dockerfile_path: '#{svc.build.context_path}/Dockerfile'
        labels: []
        ingress: null
        empty_env: null
        properties:
          sys_user: syspg1
          sys_psw: syspg1
          user: pg1
          psw: pg1
        upstreams:
          - type: postgres
            tag: upstream-1
            enabled: true
            properties:
              user: pg1up
              psw: pg1up
              host: localhost
              port: '5432'
              database: d_pg1
              unix_user: postgres
              dump_dir: /dumps
          - type: postgres
            tag: upstream-2
            enabled: false
            properties:
              user: pg2up
              psw: pg2up
              host: moon
              port: '5432'
              database: d_pg2
              unix_user: postgres
              dump_dir: /dumps/2
        status:
          active: true
          archived: false
          triggered_config: null
      - template: traefik
        factory: docker
        tag: traefik-1
        service_class: null
        containers:
          - image: ''
            tag: 1
            hostname: null
            container_name: null
            workdir: null
            volumes: []
            environment: null
            ports: []
            networks: []
            extra_hosts: []
            subject_alternative_name: null
        build: null
        labels: []
        ingress: true
        empty_env: null
        properties: {}
        upstreams: []
        status:
          active: true
          archived: false
          triggered_config: null
      - template: custom-1
        factory: docker
        tag: primary
        service_class: null
        containers:
          - image: ''
            tag: 1
            hostname: null
            container_name: null
            workdir: null
            volumes: []
            environment: null
            ports: []
            networks: []
            extra_hosts: []
            subject_alternative_name: null
        build: null
        labels: []
        ingress: true
        empty_env: null
        properties:
          instance.name: primary
          instance.id: 1
        upstreams: []
        status:
          active: true
          archived: false
          triggered_config: null
      - template: nodejs
        build: null
        factory: docker
        tag: poke
        service_class: null
        containers:
          - image: ''
            tag: 1
            hostname: null
            container_name: null
            workdir: null
            volumes: []
            environment:
              - USER=user
              - PSW=psw
            ports:
              - 3000:3000
            networks: []
            extra_hosts: []
            subject_alternative_name: null
        labels: []
        ingress: null
        empty_env: null
        properties: {}
        upstreams: []
        status:
          active: true
          archived: false
          triggered_config: null
    networks:
      - tag: shpdnet
        name: envnet
        external: true
        driver: null
        attachable: null
        enable_ipv6: null
        driver_opts: null
        ipam: null
    volumes:
      - tag: app_data
        external: false
        name: null
        driver: local
        driver_opts:
          type: none
          o: bind
          device: /srv/data
        labels:
          env: production
    status:
      active: true
      archived: false
      triggered_config: null
"""


config_yaml_with_refs: str = """
shpd_registry:
  ftp_server: ${shpd_registry}
  ftp_user: ${shpd_registry_ftp_usr}
  ftp_psw: ${shpd_registry_ftp_psw}
  ftp_shpd_path: ${shpd_registry_ftp_shpd_path}
  ftp_env_imgs_path: ${shpd_registry_ftp_imgs_path}
templates_path: ${templates_path}
envs_path: ${envs_path}
volumes_path: ${volumes_path}
host_inet_ip: ${host_inet_ip}
domain: ${domain}
dns_type: ${dns_type}
ca:
  country: ${ca_country}
  state: ${ca_state}
  locality: ${ca_locality}
  organization: ${ca_org}
  organizational_unit: ${ca_org_unit}
  common_name: ${ca_cn}
  email: ${ca_email}
  passphrase: ${ca_passphrase}
cert:
  country: ${cert_country}
  state: ${cert_state}
  locality: ${cert_locality}
  organization: ${cert_org}
  organizational_unit: ${cert_org_unit}
  common_name: ${cert_cn}
  email: ${cert_email}
  subject_alternative_names: []
staging_area:
  volumes_path: ${staging_area_volumes_path}
  images_path: ${staging_area_images_path}
env_templates:
  - tag: nginx-postgres
    factory: docker-compose
    service_templates:
      - template: nginx
        tag: web
      - template: postgres
        tag: db
    networks:
      - tag: '#{env.tag}'
        name: '#{net.tag}'
        external: false
        driver: bridge
        attachable: null
        enable_ipv6: null
        driver_opts: null
        ipam: null
    volumes:
      - tag: nginx
        external: false
        name: null
        driver: local
        driver_opts:
          type: none
          o: bind
          device: '#{cfg.volumes_path}/#{env.tag}/#{vol.tag}'
        labels:
          env: production
      - tag: postgres
        external: false
        name: null
        driver: local
        driver_opts:
          type: none
          o: bind
          device: '#{cfg.volumes_path}/#{env.tag}/#{vol.tag}'
        labels:
          env: production
service_templates:
  - tag: nginx
    factory: docker
    containers:
      - image: nginx:latest
        tag: nginx
        hostname: web-instance
        container_name: web-instance
        workdir: /usr/share/nginx/html
        volumes:
          - nginx:/usr/share/nginx/html
        environment:
          - NGINX_PORT=80
        ports:
          - 8080:80
        networks:
          - '#{env.tag}'
        extra_hosts: []
        subject_alternative_name: null
    build: null
    labels:
      - com.example.type=web
    ingress: true
    empty_env: ''
    properties: {}
  - tag: postgres
    factory: docker
    containers:
      - image: postgres:14
        tag: postgres
        hostname: db-instance
        container_name: db-instance
        workdir: /var/lib/postgresql/data
        volumes:
          - postgres:/var/lib/postgresql/data
        environment:
          - POSTGRES_PASSWORD=secret
        ports:
          - 5432:5432
        networks:
          - '#{env.tag}'
        extra_hosts: []
        subject_alternative_name: null
    build: null
    labels:
      - com.example.type=db
    ingress: false
    empty_env: ''
    properties: {}
envs:
  - template: nginx-postgres
    factory: docker-compose
    tag: foo
    services:
      - template: nginx
        tag: web
        factory: docker
        containers:
          - image: nginx:latest
            tag: nginx
            hostname: web-instance
            container_name: web-instance
            workdir: /usr/share/nginx/html
            volumes:
              - nginx:/usr/share/nginx/html
            environment:
              - NGINX_PORT=80
            ports:
              - 8080:80
            networks:
              - '#{env.tag}'
            extra_hosts: []
            subject_alternative_name: null
        build: null
        labels:
          - com.example.type=web
        ingress: true
        empty_env: ''
        service_class: '#{not.exist}'
        properties:
          com.example.type: '#{svc.tag}'
        upstreams: []
        status:
          active: true
          archived: false
          triggered_config: null
      - template: postgres
        upstreams: []
        factory: docker
        tag: db
        service_class: '#{not.exist}'
        containers:
          - image: postgres:14
            tag: postgres
            hostname: db-instance
            container_name: db-instance
            workdir: /var/lib/postgresql/data
            volumes:
              - postgres:/var/lib/postgresql/data
            environment:
              - POSTGRES_PASSWORD=secret
            ports:
              - 5432:5432
            networks:
              - '#{env.tag}'
            extra_hosts: []
            subject_alternative_name: null
        build: null
        labels:
          - com.example.type=db
        ingress: false
        empty_env: ''
        properties:
          com.example.type: '#{svc.tag}'
        status:
          active: true
          archived: false
          triggered_config: null
    networks:
      - tag: '#{env.tag}'
        name: '#{net.tag}'
        external: false
        driver: bridge
        attachable: null
        enable_ipv6: null
        driver_opts: null
        ipam: null
    volumes:
      - tag: nginx
        external: false
        name: null
        driver: local
        driver_opts:
          type: none
          o: bind
          device: '#{cfg.volumes_path}/#{env.tag}/#{vol.tag}'
        labels:
          env: production
      - tag: postgres
        external: false
        name: null
        driver: local
        driver_opts:
          type: none
          o: bind
          device: '#{cfg.volumes_path}/#{env.tag}/#{vol.tag}'
        labels:
          env: production
    status:
      active: true
      archived: false
      triggered_config: null
"""


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

    mock_open1 = mock_open(read_data=values)
    mock_open2 = mock_open(read_data=config_yaml)

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch(
        "builtins.open",
        side_effect=[mock_open1.return_value, mock_open2.return_value],
    )

    cMng = ConfigMng(".shpd.conf")
    config: Config = cMng.load_config()

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
    assert service_templates[0].build is None
    assert service_templates[0].containers[0].hostname == "ora-host"
    assert service_templates[0].containers[0].container_name == "ora-cnt-1"
    assert service_templates[0].empty_env == "fresh-ora-19300"
    assert not service_templates[0].is_ingress()
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
    assert service_templates[0].containers[0].subject_alternative_name is None
    assert service_templates[1].tag == "postgres"
    assert service_templates[1].factory == "docker"
    assert service_templates[1].containers
    assert service_templates[1].containers[0].image == (
        "ghcr.io/MoonyFringers/shepherd/postgres:17-3.5"
    )
    assert service_templates[1].build
    assert service_templates[1].build.context_path == (
        "${test_path}/envs/#{env.tag}/build"
    )
    assert service_templates[1].build.dockerfile_path == (
        "#{svc.build.context_path}/Dockerfile"
    )
    assert service_templates[1].empty_env == "fresh-pg-1735"
    assert not service_templates[1].is_ingress()
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
    assert service_templates[1].containers[0].subject_alternative_name is None

    assert config.shpd_registry.ftp_server == "ftp.example.com"
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
    assert services[1].is_ingress
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
    assert config.host_inet_ip == "127.0.0.1"
    assert config.domain == "sslip.io"
    assert config.dns_type == "autoresolving"
    assert config.ca.country == "IT"
    assert config.ca.state == "MS"
    assert config.ca.locality == "Carrara"
    assert config.ca.organization == "MoonyFringe"
    assert config.ca.organizational_unit == "Development"
    assert config.ca.common_name == "sslip.io"
    assert config.ca.email == "lf@sslip.io"
    assert config.ca.passphrase == "test"
    assert config.cert.country == "IT"
    assert config.cert.state == "MS"
    assert config.cert.locality == "Carrara"
    assert config.cert.organization == "MoonyFringe"
    assert config.cert.organizational_unit == "Development"
    assert config.cert.common_name == "sslip.io"
    assert config.cert.email == "lf@sslip.io"
    assert config.cert.subject_alternative_names == []
    assert config.staging_area.volumes_path == "${test_path}/sa_volumes"
    assert config.staging_area.images_path == "${test_path}/sa_images"
    assert config.envs[0].status.archived is False
    assert config.envs[0].status.active is True
    assert config.envs[0].status.triggered_config is None


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
            config_file.write(config_yaml)
            values_file.write(values.replace("${test_path}", "."))

        cMng = ConfigMng(values_file.name)
        config: Config = cMng.load_config()
        cMng.store_config(config)

        with open(".shpd.yaml", "r") as output_file:
            content = output_file.read()
            y1: str = yaml.dump(yaml.safe_load(content), sort_keys=True)
            y2: str = yaml.dump(yaml.safe_load(config_yaml), sort_keys=True)
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
def test_copy_config(mocker: MockerFixture):
    """Test copying config with mock"""

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
            config_file.write(config_yaml_with_refs)
            values_file.write(values.replace("${test_path}", "."))

        cMng = ConfigMng(values_file.name)
        config: Config = cMng.load_config()
        cMng.store_config(config)

        with open(".shpd.yaml", "r") as output_file:
            content = output_file.read()
            y1: str = yaml.dump(yaml.safe_load(content), sort_keys=True)
            y2: str = yaml.dump(
                yaml.safe_load(config_yaml_with_refs), sort_keys=True
            )
            assert y1 == y2

    finally:
        for file_path in (".shpd.yaml", ".shpd.conf"):
            if os.path.exists(file_path):
                os.remove(file_path)
