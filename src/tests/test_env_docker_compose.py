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

# flake8: noqa E501

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner
from pytest_mock import MockerFixture
from test_util import read_fixture

from shepctl import ShepherdMng, cli

docker_compose_ps_output = """
{"Command":"\\\"docker-entrypoint.s…\\\"","CreatedAt":"2025-09-08 12:22:01 +0200 CEST","ExitCode":0,"Health":"","ID":"cc1200024a2a","Image":"postgres:14","Labels":"com.docker.compose.oneoff=False","LocalVolumes":"1","Mounts":"beppe_postgres","Name":"db-instance","Names":"db-instance","Networks":"beppe_beppe","Ports":"0.0.0.0:5432-\u003e5432/tcp, [::]:5432-\u003e5432/tcp","Project":"beppe","Publishers":[{"URL":"0.0.0.0","TargetPort":5432,"PublishedPort":5432,"Protocol":"tcp"},{"URL":"::","TargetPort":5432,"PublishedPort":5432,"Protocol":"tcp"}],"RunningFor":"About a minute ago","Service":"test-1-test-1","Size":"0B","State":"running","Status":"Up About a minute"}
{"Command":"\"docker-entrypoint.s…\"","Status":"Wrong JSON"}
"""


@pytest.fixture
def shpd_conf(tmp_path: Path, mocker: MockerFixture) -> tuple[Path, Path]:
    """Fixture to create a temporary home directory and .shpd.conf file."""
    temp_home = tmp_path / "home"
    temp_home.mkdir()

    config_file = temp_home / ".shpd.conf"
    values = read_fixture("env_docker", "values.conf")
    config_file.write_text(values.replace("${test_path}", str(temp_home)))

    os.environ["SHPD_CONF"] = str(config_file)
    return temp_home, config_file


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.docker
def test_env_render_compose_env_ext_net(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("env_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["get", "env", "test-1", "-oyaml"])
    assert result.exit_code == 0

    expected = """
template: default
factory: docker-compose
tag: test-1
services:
- template: default
  factory: docker
  tag: test-1
  service_class: null
  upstreams: []
  inits: []
  start: null
  containers:
  - image: busybox:stable-glibc
    build: null
    tag: container-1
    container_name: null
    hostname: null
    workdir: /test
    volumes:
    - /home/test/.ssh:/home/test/.ssh
    - /etc/ssh:/etc/ssh
    environment: []
    ports:
    - 80:80
    - 443:443
    - 8080:8080
    networks:
    - default
    extra_hosts:
    - host.docker.internal:host-gateway
    subject_alternative_name: null
  labels:
  - com.example.label1=value1
  - com.example.label2=value2
  - domain=${domain}
  ingress: false
  empty_env: null
  properties: {}
  status:
    active: true
    archived: false
    triggered_config: null
- template: default
  factory: docker
  tag: test-2
  service_class: null
  upstreams: []
  inits: []
  start: null
  containers:
  - image: busybox:stable-glibc
    tag: container-1
    build: null
    container_name: null
    hostname: null
    workdir: /test
    volumes:
    - /home/test/.ssh:/home/test/.ssh
    - /etc/ssh:/etc/ssh
    environment: []
    ports:
    - 80:80
    - 443:443
    - 8080:8080
    networks:
    - default
    extra_hosts:
    - host.docker.internal:host-gateway
    subject_alternative_name: null
  labels:
  - com.example.label1=value1
  - com.example.label2=value2
  ingress: false
  empty_env: null
  properties: {}
  status:
    active: true
    archived: false
    triggered_config: null
probes: []
networks:
- tag: default
  name: envnet
  external: true
  driver: null
  attachable: null
  enable_ipv6: null
  driver_opts: null
  ipam: null
volumes:
- tag: app_data_ext
  external: true
  name: nfs-1
  driver: null
  driver_opts: null
  labels: null
status:
  active: true
  archived: false
  triggered_config: null
"""

    y1: str = yaml.dump(yaml.safe_load(result.output), sort_keys=True)
    y2: str = yaml.dump(yaml.safe_load(expected), sort_keys=True)
    assert y1 == y2


@pytest.mark.docker
def test_env_render_compose_env_resolved(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("env_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["get", "env", "test-1", "-oyaml", "-r"])
    assert result.exit_code == 0

    expected = """
template: default
factory: docker-compose
tag: test-1
services:
- template: default
  factory: docker
  tag: test-1
  service_class: null
  upstreams: []
  inits: []
  start: null
  containers:
  - image: busybox:stable-glibc
    tag: container-1
    container_name: null
    build: null
    hostname: null
    workdir: /test
    volumes:
    - /home/test/.ssh:/home/test/.ssh
    - /etc/ssh:/etc/ssh
    environment: []
    ports:
    - 80:80
    - 443:443
    - 8080:8080
    networks:
    - default
    extra_hosts:
    - host.docker.internal:host-gateway
    subject_alternative_name: null
  labels:
  - com.example.label1=value1
  - com.example.label2=value2
  - domain=sslip.io
  ingress: false
  empty_env: null
  properties: {}
  status:
    active: true
    archived: false
    triggered_config: null
- template: default
  factory: docker
  tag: test-2
  service_class: null
  upstreams: []
  inits: []
  start: null
  containers:
  - image: busybox:stable-glibc
    build: null
    tag: container-1
    container_name: null
    hostname: null
    workdir: /test
    volumes:
    - /home/test/.ssh:/home/test/.ssh
    - /etc/ssh:/etc/ssh
    environment: []
    ports:
    - 80:80
    - 443:443
    - 8080:8080
    networks:
    - default
    extra_hosts:
    - host.docker.internal:host-gateway
    subject_alternative_name: null
  labels:
  - com.example.label1=value1
  - com.example.label2=value2
  ingress: false
  empty_env: null
  properties: {}
  status:
    active: true
    archived: false
    triggered_config: null
probes: []
networks:
- tag: default
  name: envnet
  external: true
  driver: null
  attachable: null
  enable_ipv6: null
  driver_opts: null
  ipam: null
volumes:
- tag: app_data_ext
  external: true
  name: nfs-1
  driver: null
  driver_opts: null
  labels: null
status:
  active: true
  archived: false
  triggered_config: null
"""

    y1: str = yaml.dump(yaml.safe_load(result.output), sort_keys=True)
    y2: str = yaml.dump(yaml.safe_load(expected), sort_keys=True)
    assert y1 == y2


@pytest.mark.docker
def test_env_render_target_compose_env_ext_net(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("env_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["get", "env", "test-1", "-oyaml", "-t"])
    assert result.exit_code == 0

    expected = (
        "name: test-1\n"
        "services:\n"
        "  container-1-test-1-test-1:\n"
        "    image: busybox:stable-glibc\n"
        "    hostname: container-1-test-1-test-1\n"
        "    container_name: container-1-test-1-test-1\n"
        "    working_dir: /test\n"
        "    labels:\n"
        "    - com.example.label1=value1\n"
        "    - com.example.label2=value2\n"
        "    - domain=${domain}\n"
        "    volumes:\n"
        "    - /home/test/.ssh:/home/test/.ssh\n"
        "    - /etc/ssh:/etc/ssh\n"
        "    ports:\n"
        "    - 80:80\n"
        "    - 443:443\n"
        "    - 8080:8080\n"
        "    extra_hosts:\n"
        "    - host.docker.internal:host-gateway\n"
        "    networks:\n"
        "    - default\n"
        "  container-1-test-2-test-1:\n"
        "    image: busybox:stable-glibc\n"
        "    hostname: container-1-test-2-test-1\n"
        "    container_name: container-1-test-2-test-1\n"
        "    working_dir: /test\n"
        "    labels:\n"
        "    - com.example.label1=value1\n"
        "    - com.example.label2=value2\n"
        "    volumes:\n"
        "    - /home/test/.ssh:/home/test/.ssh\n"
        "    - /etc/ssh:/etc/ssh\n"
        "    ports:\n"
        "    - 80:80\n"
        "    - 443:443\n"
        "    - 8080:8080\n"
        "    extra_hosts:\n"
        "    - host.docker.internal:host-gateway\n"
        "    networks:\n"
        "    - default\n"
        "networks:\n"
        "  default:\n"
        "    name: envnet\n"
        "    external: true\n"
        "volumes:\n"
        "  app_data_ext:\n"
        "    name: nfs-1\n"
        "    external: true\n\n"
    )

    y1: str = yaml.dump(yaml.safe_load(result.output), sort_keys=True)
    y2: str = yaml.dump(yaml.safe_load(expected), sort_keys=True)
    assert y1 == y2


@pytest.mark.docker
def test_env_render_target_compose_env_resolved(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("env_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["get", "env", "test-1", "-oyaml", "-t", "-r"])
    assert result.exit_code == 0

    expected = (
        "name: test-1\n"
        "services:\n"
        "  container-1-test-1-test-1:\n"
        "    image: busybox:stable-glibc\n"
        "    hostname: container-1-test-1-test-1\n"
        "    container_name: container-1-test-1-test-1\n"
        "    working_dir: /test\n"
        "    labels:\n"
        "    - com.example.label1=value1\n"
        "    - com.example.label2=value2\n"
        "    - domain=sslip.io\n"
        "    volumes:\n"
        "    - /home/test/.ssh:/home/test/.ssh\n"
        "    - /etc/ssh:/etc/ssh\n"
        "    ports:\n"
        "    - 80:80\n"
        "    - 443:443\n"
        "    - 8080:8080\n"
        "    extra_hosts:\n"
        "    - host.docker.internal:host-gateway\n"
        "    networks:\n"
        "    - default\n"
        "  container-1-test-2-test-1:\n"
        "    image: busybox:stable-glibc\n"
        "    hostname: container-1-test-2-test-1\n"
        "    container_name: container-1-test-2-test-1\n"
        "    working_dir: /test\n"
        "    labels:\n"
        "    - com.example.label1=value1\n"
        "    - com.example.label2=value2\n"
        "    volumes:\n"
        "    - /home/test/.ssh:/home/test/.ssh\n"
        "    - /etc/ssh:/etc/ssh\n"
        "    ports:\n"
        "    - 80:80\n"
        "    - 443:443\n"
        "    - 8080:8080\n"
        "    extra_hosts:\n"
        "    - host.docker.internal:host-gateway\n"
        "    networks:\n"
        "    - default\n"
        "networks:\n"
        "  default:\n"
        "    name: envnet\n"
        "    external: true\n"
        "volumes:\n"
        "  app_data_ext:\n"
        "    name: nfs-1\n"
        "    external: true\n\n"
    )

    y1: str = yaml.dump(yaml.safe_load(result.output), sort_keys=True)
    y2: str = yaml.dump(yaml.safe_load(expected), sort_keys=True)
    assert y1 == y2


@pytest.mark.docker
def test_env_render_target_compose_env_int_net(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("env_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["get", "env", "test-2", "-oyaml", "-t"])
    assert result.exit_code == 0

    expected = (
        "name: test-2\n"
        "services:\n"
        "  container-1-test-1-test-2:\n"
        "    image: busybox:stable-glibc\n"
        "    hostname: container-1-test-1-test-2\n"
        "    container_name: container-1-test-1-test-2\n"
        "    working_dir: /test\n"
        "    labels:\n"
        "    - com.example.label1=value1\n"
        "    - com.example.label2=value2\n"
        "    volumes:\n"
        "    - /home/test/.ssh:/home/test/.ssh\n"
        "    - /etc/ssh:/etc/ssh\n"
        "    ports:\n"
        "    - 80:80\n"
        "    - 443:443\n"
        "    - 8080:8080\n"
        "    extra_hosts:\n"
        "    - host.docker.internal:host-gateway\n"
        "    networks:\n"
        "    - internal_net\n"
        "  container-1-test-2-test-2:\n"
        "    image: busybox:stable-glibc\n"
        "    hostname: container-1-test-2-test-2\n"
        "    container_name: container-1-test-2-test-2\n"
        "    working_dir: /test\n"
        "    labels:\n"
        "    - com.example.label1=value1\n"
        "    - com.example.label2=value2\n"
        "    volumes:\n"
        "    - /home/test/.ssh:/home/test/.ssh\n"
        "    - /etc/ssh:/etc/ssh\n"
        "    ports:\n"
        "    - 80:80\n"
        "    - 443:443\n"
        "    - 8080:8080\n"
        "    extra_hosts:\n"
        "    - host.docker.internal:host-gateway\n"
        "    networks:\n"
        "    - internal_net\n"
        "networks:\n"
        "  internal_net:\n"
        "    driver: bridge\n"
        "    attachable: true\n"
        "    enable_ipv6: false\n"
        "    driver_opts:\n"
        "      com.docker.network.bridge.name: br-internal\n"
        "    ipam:\n"
        "      driver: default\n"
        "      config:\n"
        "      - subnet: 172.30.0.0/16\n"
        "        gateway: 172.30.0.1\n"
        "volumes:\n"
        "  app_data:\n"
        "    driver: local\n"
        "    driver_opts:\n"
        "      type: none\n"
        "      o: bind\n"
        "      device: /srv/data\n"
        "    labels:\n"
        "      env: production\n\n"
    )

    y1: str = yaml.dump(yaml.safe_load(result.output), sort_keys=True)
    y2: str = yaml.dump(yaml.safe_load(expected), sort_keys=True)
    assert y1 == y2


@pytest.mark.docker
def test_start_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("env_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "up", "-d"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["up", "env"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()

    sm = ShepherdMng()
    env = sm.configMng.get_environment("test-1")
    assert env
    assert env.status.active is True
    assert env.status.archived is False
    assert env.status.triggered_config


@pytest.mark.docker
def test_stop_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("env_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "restart"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["up", "env"])

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "down"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["halt", "env"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()

    sm = ShepherdMng()
    env = sm.configMng.get_environment("test-1")
    assert env
    assert env.status.active is True
    assert env.status.archived is False
    assert env.status.triggered_config is None


@pytest.mark.docker
def test_reload_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("env_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "restart"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["up", "env"])

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "restart"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["reload", "env"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()

    sm = ShepherdMng()
    env = sm.configMng.get_environment("test-1")
    assert env
    assert env.status.active is True
    assert env.status.archived is False
    assert env.status.triggered_config


@pytest.mark.docker
def test_status_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("env_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "ps", "--format", "json"],
            returncode=0,
            stdout=docker_compose_ps_output,
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["status", "env"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()
