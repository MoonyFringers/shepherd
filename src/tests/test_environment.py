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

import os
from pathlib import Path

import pytest
from click.testing import CliRunner
from pytest_mock import MockerFixture
from test_util import values

from shepctl import ShepherdMng, cli

shpd_config = """
logging:
  file: ${log_file}
  level: ${log_level}
  stdout: ${log_stdout}
  format: ${log_format}
shpd_registry:
  ftp_server: ${shpd_registry}
  ftp_user: ${shpd_registry_ftp_usr}
  ftp_psw: ${shpd_registry_ftp_psw}
  ftp_shpd_path: ${shpd_registry_ftp_shpd_path}
  ftp_env_imgs_path: ${shpd_registry_ftp_imgs_path}
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
    volumes:
      - tag: app_data
        external: false
        driver: local
        driver_opts:
          type: none
          o: bind
          device: /srv/data
        labels:
          env: production
service_templates:
  - tag: default
    factory: docker
    image: test-image:latest
    labels:
      - com.example.label1=value1
      - com.example.label2=value2
    workdir: /test
    volumes:
      - /home/test/.ssh:/home/test/.ssh
      - /etc/ssh:/etc/ssh
    ingress: false
    empty_env: null
    environment: []
    ports:
      - 80:80
      - 443:443
      - 8080:8080
    properties: {}
    networks:
      - default
    extra_hosts:
      - host.docker.internal:host-gateway
    subject_alternative_name: null
envs:
  - template: default
    factory: docker-compose
    tag: test-1
    services:
      - template: default
        factory: docker
        tag: test-1
        image: test-1-image:latest
        labels:
          - com.example.label1=value1
          - com.example.label2=value2
        workdir: /test
        volumes:
          - /home/test/.ssh:/home/test/.ssh
          - /etc/ssh:/etc/ssh
        ingress: false
        empty_env: null
        environment: []
        ports:
          - 80:80
          - 443:443
          - 8080:8080
        properties: {}
        networks:
          - default
        extra_hosts:
          - host.docker.internal:host-gateway
        subject_alternative_name: null
        status:
          active: true
          archived: false
          triggered_config: null
      - template: default
        factory: docker
        tag: test-2
        image: test-2-image:latest
        labels:
          - com.example.label1=value1
          - com.example.label2=value2
        workdir: /test
        volumes:
          - /home/test/.ssh:/home/test/.ssh
          - /etc/ssh:/etc/ssh
        ingress: false
        empty_env: null
        environment: []
        ports:
          - 80:80
          - 443:443
          - 8080:8080
        properties: {}
        networks:
          - default
        extra_hosts:
          - host.docker.internal:host-gateway
        subject_alternative_name: null
        status:
          active: true
          archived: false
          triggered_config: null
    networks:
      - tag: default
        name: envnet
        external: true
    volumes:
      - tag: app_data_ext
        external: true
        name: nfs-1
    status:
      active: true
      archived: false
      triggered_config: null
  - template: default
    factory: docker-compose
    tag: test-2
    services:
      - template: default
        factory: docker
        tag: test-1
        image: test-1-image:latest
        labels:
          - com.example.label1=value1
          - com.example.label2=value2
        workdir: /test
        volumes:
          - /home/test/.ssh:/home/test/.ssh
          - /etc/ssh:/etc/ssh
        ingress: false
        empty_env: null
        environment: []
        ports:
          - 80:80
          - 443:443
          - 8080:8080
        properties: {}
        networks:
          - internal_net
        extra_hosts:
          - host.docker.internal:host-gateway
        subject_alternative_name: null
        status:
          active: true
          archived: false
          triggered_config: null
      - template: default
        factory: docker
        tag: test-2
        image: test-2-image:latest
        labels:
          - com.example.label1=value1
          - com.example.label2=value2
        workdir: /test
        volumes:
          - /home/test/.ssh:/home/test/.ssh
          - /etc/ssh:/etc/ssh
        ingress: false
        empty_env: null
        environment: []
        ports:
          - 80:80
          - 443:443
          - 8080:8080
        properties: {}
        networks:
          - internal_net
        extra_hosts:
          - host.docker.internal:host-gateway
        subject_alternative_name: null
        status:
          active: true
          archived: false
          triggered_config: null
    networks:
      - tag: internal_net
        external: false
        driver: bridge
        attachable: true
        enable_ipv6: false
        driver_opts:
          com.docker.network.bridge.name: br-internal
        ipam:
          driver: default
          config:
            - subnet: 172.30.0.0/16
              gateway: 172.30.0.1
    volumes:
      - tag: app_data
        external: false
        driver: local
        driver_opts:
          type: none
          o: bind
          device: /srv/data
        labels:
          env: production
    status:
      active: false
      archived: false
      triggered_config: null
"""


@pytest.fixture
def shpd_conf(tmp_path: Path, mocker: MockerFixture) -> tuple[Path, Path]:
    """Fixture to create a temporary home directory and .shpd.conf file."""
    temp_home = tmp_path / "home"
    temp_home.mkdir()

    config_file = temp_home / ".shpd.conf"
    config_file.write_text(values.replace("${test_path}", str(temp_home)))

    os.environ["SHPD_CONF"] = str(config_file)
    return temp_home, config_file


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.env
def test_env_init(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    result = runner.invoke(cli, ["env", "init", "default", "test-init-1"])
    assert result.exit_code == 0

    sm = ShepherdMng()
    assert sm.configMng.exists_environment("test-init-1")

    expected_dirs = [os.path.join(sm.configMng.config.envs_path, "test-init-1")]

    for directory in expected_dirs:
        assert os.path.isdir(
            directory
        ), f"Directory {directory} was not created."


@pytest.mark.env
def test_env_clone(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    result = runner.invoke(cli, ["env", "init", "default", "test-clone-1"])
    assert result.exit_code == 0

    result = runner.invoke(
        cli, ["env", "clone", "test-clone-1", "test-clone-2"]
    )
    assert result.exit_code == 0

    sm = ShepherdMng()
    assert sm.configMng.exists_environment("test-clone-1")
    assert sm.configMng.exists_environment("test-clone-2")

    expected_dirs = [
        os.path.join(sm.configMng.config.envs_path, "test-clone-1"),
        os.path.join(sm.configMng.config.envs_path, "test-clone-2"),
    ]

    for directory in expected_dirs:
        assert os.path.isdir(
            directory
        ), f"Directory {directory} was not created."


@pytest.mark.env
def test_env_rename(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    result = runner.invoke(cli, ["env", "init", "default", "test-rename-1"])
    assert result.exit_code == 0

    result = runner.invoke(
        cli, ["env", "rename", "test-rename-1", "test-rename-2"]
    )
    assert result.exit_code == 0

    sm = ShepherdMng()
    assert not sm.configMng.exists_environment("test-rename-1")
    assert sm.configMng.exists_environment("test-rename-2")

    renamed_dir = os.path.join(sm.configMng.config.envs_path, "test-rename-2")
    old_dir = os.path.join(sm.configMng.config.envs_path, "test-rename-1")

    assert os.path.isdir(
        renamed_dir
    ), f"Directory {renamed_dir} was not created."
    assert not os.path.exists(
        old_dir
    ), f"Old directory {old_dir} still exists after rename."


@pytest.mark.env
def test_env_checkout(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    result = runner.invoke(cli, ["env", "init", "default", "test-1"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["env", "init", "default", "test-2"])
    assert result.exit_code == 0

    sm = ShepherdMng()
    env = sm.configMng.get_active_environment()
    assert env is None

    result = runner.invoke(cli, ["env", "checkout", "test-1"])
    assert result.exit_code == 0

    sm = ShepherdMng()
    env = sm.configMng.get_active_environment()
    assert env is not None
    assert env.tag == "test-1"

    result = runner.invoke(cli, ["env", "checkout", "test-2"])
    assert result.exit_code == 0

    sm = ShepherdMng()
    env = sm.configMng.get_active_environment()
    assert env is not None
    assert env.tag == "test-2"


@pytest.mark.env
def test_env_list(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    result = runner.invoke(cli, ["env", "init", "default", "test-1"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["env", "list"])
    assert result.exit_code == 0


@pytest.mark.env
def test_env_delete_yes(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    mocker.patch("builtins.input", return_value="y")

    result = runner.invoke(cli, ["env", "init", "default", "test-1"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["env", "delete", "test-1"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["env", "init", "default", "test-1"])
    assert result.exit_code == 0

    mocker.patch("builtins.input", return_value="y")

    result = runner.invoke(cli, ["env", "delete", "test-1"])
    assert result.exit_code == 0

    sm = ShepherdMng()
    env = sm.configMng.get_environment("test-1")
    assert env is None

    env_dir = os.path.join(sm.configMng.config.envs_path, "test-1")

    assert not os.path.exists(
        env_dir
    ), f"directory {env_dir} still exists after delete."


@pytest.mark.env
def test_env_delete_no(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    mocker.patch("builtins.input", return_value="n")

    result = runner.invoke(cli, ["env", "init", "default", "test-1"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["env", "delete", "test-1"])
    assert result.exit_code == 0

    sm = ShepherdMng()
    env = sm.configMng.get_environment("test-1")
    assert env is not None

    env_dir = os.path.join(sm.configMng.config.envs_path, "test-1")

    assert os.path.exists(
        env_dir
    ), f"directory {env_dir} does not exist after delete-no."


@pytest.mark.env
def test_env_add_nonexisting_resource(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    result = runner.invoke(cli, ["env", "init", "default", "test-svc-add"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["env", "checkout", "test-svc-add"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["env", "add", "foo", "foo-1"])
    assert result.exit_code == 2
