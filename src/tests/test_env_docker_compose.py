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
from types import SimpleNamespace
from typing import Any, cast

import pytest
import yaml
from click.testing import CliRunner
from pytest_mock import MockerFixture
from test_util import read_fixture

from docker.docker_compose_env import DockerComposeEnv
from environment.environment import NonRecoverableStartError, ProbeRunResult
from shepctl import ShepherdMng, cli

docker_compose_ps_output = """
{"Command":"\\\"docker-entrypoint.s…\\\"","CreatedAt":"2025-09-08 12:22:01 +0200 CEST","ExitCode":0,"Health":"","ID":"cc1200024a2a","Image":"postgres:14","Labels":"com.docker.compose.oneoff=False","LocalVolumes":"1","Mounts":"beppe_postgres","Name":"db-instance","Names":"db-instance","Networks":"beppe_beppe","Ports":"0.0.0.0:5432-\u003e5432/tcp, [::]:5432-\u003e5432/tcp","Project":"beppe","Publishers":[{"URL":"0.0.0.0","TargetPort":5432,"PublishedPort":5432,"Protocol":"tcp"},{"URL":"::","TargetPort":5432,"PublishedPort":5432,"Protocol":"tcp"}],"RunningFor":"About a minute ago","Service":"test-1-test-1","Size":"0B","State":"running","Status":"Up About a minute"}
{"Command":"\"docker-entrypoint.s…\"","Status":"Wrong JSON"}
"""

test_env_running_ps_output = (
    '{"Service":"container-1-test-1-test-1","State":"running"}\n'
    '{"Service":"container-1-test-2-test-1","State":"running"}\n'
)


def mock_subprocess_with_running_ps(mocker: MockerFixture):
    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        cmd = cast(list[str], args[0]) if args else []
        if "ps" in cmd:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout=test_env_running_ps_output,
                stderr="",
            )
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        )

    return mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        side_effect=fake_run,
    )


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
    inits: null
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
    rendered_config: null
- template: default
  factory: docker
  tag: test-2
  service_class: null
  upstreams: []
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
    inits: null
  labels:
  - com.example.label1=value1
  - com.example.label2=value2
  ingress: false
  empty_env: null
  properties: {}
  status:
    active: true
    archived: false
    rendered_config: null
probes:
  - tag: db-ready
    container:
      tag: db-ready
      image: postgres:17-3.5
      hostname: null
      container_name: null
      workdir: null
      volumes: []
      environment: []
      ports: []
      networks:
        - "#{env.tag}"
      extra_hosts: []
      subject_alternative_name: null
      inits: null
      build: null
    script: sh -c 'pg_isready -h db -p 5432 -U sys -d docker'
    script_path: null
  - tag: db-live
    container:
      tag: db-live
      image: postgres:17-3.5
      hostname: null
      container_name: null
      workdir: null
      volumes: []
      environment: []
      ports: []
      networks:
        - "#{env.tag}"
      extra_hosts: []
      subject_alternative_name: null
      inits: null
      build: null
    script: sh -c 'pg_isready -h db -p 5432 -U docker -d docker'
    script_path: null
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
  rendered_config: null
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
    inits: null
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
    rendered_config: null
- template: default
  factory: docker
  tag: test-2
  service_class: null
  upstreams: []
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
    inits: null
  labels:
  - com.example.label1=value1
  - com.example.label2=value2
  ingress: false
  empty_env: null
  properties: {}
  status:
    active: true
    archived: false
    rendered_config: null
probes:
  - tag: db-ready
    container:
      tag: db-ready
      image: postgres:17-3.5
      hostname: null
      container_name: null
      workdir: null
      volumes: []
      environment: []
      ports: []
      networks:
        - test-1
      extra_hosts: []
      subject_alternative_name: null
      inits: null
      build: null
    script: sh -c 'pg_isready -h db -p 5432 -U sys -d docker'
    script_path: null
  - tag: db-live
    container:
      tag: db-live
      image: postgres:17-3.5
      hostname: null
      container_name: null
      workdir: null
      volumes: []
      environment: []
      ports: []
      networks:
        - test-1
      extra_hosts: []
      subject_alternative_name: null
      inits: null
      build: null
    script: sh -c 'pg_isready -h db -p 5432 -U docker -d docker'
    script_path: null
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
  rendered_config: null
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
    mock_subproc = mock_subprocess_with_running_ps(mocker)

    result = runner.invoke(cli, ["up", "env"])
    assert result.exit_code == 0
    assert mock_subproc.call_count >= 2
    assert any(
        "ps" in (call.args[0] if call.args else [])
        for call in mock_subproc.call_args_list
    )

    sm = ShepherdMng()
    env = sm.configMng.get_environment("test-1")
    assert env
    assert env.status.active is True
    assert env.status.archived is False
    assert env.status.rendered_config


@pytest.mark.docker
def test_start_impl_starts_only_available_gates(mocker: MockerFixture):
    env_cfg = SimpleNamespace(
        tag="gated-env",
        services=[],
        volumes=[],
        status=SimpleNamespace(
            rendered_config={
                "ungated": "name: gated-env\nservices: {}\n",
                "db-ready": "name: gated-env\nservices:\n  db: {}\n",
                "db-ready|db-live": "name: gated-env\nservices:\n  api: {}\n",
            }
        ),
    )
    env = DockerComposeEnv(mocker.Mock(), mocker.Mock(), cast(Any, env_cfg))

    run_compose_mock = mocker.patch(
        "docker.docker_compose_env.run_compose",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "up", "-d"],
            returncode=0,
            stdout="",
            stderr="",
        ),
    )

    started = env.start_impl(started_gate_keys=set(), probe_results=None)
    assert started == {"ungated"}
    assert run_compose_mock.call_count == 1
    assert run_compose_mock.call_args_list[0].args[0] == [
        "name: gated-env\nservices: {}\n"
    ]

    started = env.start_impl(
        started_gate_keys={"ungated"},
        probe_results=[
            ProbeRunResult(tag="db-ready", exit_code=0),
            ProbeRunResult(tag="db-live", exit_code=1),
        ],
    )
    assert started == {"db-ready"}
    assert run_compose_mock.call_count == 2
    assert run_compose_mock.call_args_list[1].args[0] == [
        "name: gated-env\nservices: {}\n",
        "name: gated-env\nservices:\n  db: {}\n",
    ]


@pytest.mark.docker
def test_start_impl_logs_compose_command_with_category(mocker: MockerFixture):
    env_cfg = SimpleNamespace(
        tag="log-env",
        services=[],
        volumes=[],
        status=SimpleNamespace(
            rendered_config={
                "ungated": "name: log-env\nservices: {}\n",
            }
        ),
    )
    env = DockerComposeEnv(
        mocker.Mock(),
        mocker.Mock(),
        cast(Any, env_cfg),
        cli_flags={"show_commands": True, "show_commands_limit": 5},
    )

    mocker.patch(
        "docker.docker_compose_env.run_compose",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "up", "-d"],
            returncode=0,
            stdout="",
            stderr="",
        ),
    )

    env.start_impl(started_gate_keys=set(), probe_results=None)
    log = env.get_command_log()
    assert len(log) == 1
    assert "[bold green]●[/bold green]" in log[0]
    assert "start:ungated" in log[0]
    assert "exit 0" in log[0]


@pytest.mark.docker
def test_start_impl_records_compose_failure_output(mocker: MockerFixture):
    env_cfg = SimpleNamespace(
        tag="log-env",
        services=[],
        volumes=[],
        status=SimpleNamespace(
            rendered_config={
                "ungated": "name: log-env\nservices: {}\n",
            }
        ),
    )
    env = DockerComposeEnv(
        mocker.Mock(),
        mocker.Mock(),
        cast(Any, env_cfg),
        cli_flags={"show_commands": True, "show_commands_limit": 5},
    )

    mocker.patch(
        "docker.docker_compose_env.run_compose",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "up", "-d"],
            returncode=1,
            stdout="out",
            stderr="err",
        ),
    )

    with pytest.raises(NonRecoverableStartError):
        env.start_impl(started_gate_keys=set(), probe_results=None)
    err = env.get_command_error()
    assert err is not None
    assert "Docker compose start:ungated failed" == err["title"]
    assert "--- stdout ---" in err["body"]
    assert "--- stderr ---" in err["body"]


@pytest.mark.docker
def test_start_rolls_back_with_stop_on_non_recoverable_gate_failure(
    mocker: MockerFixture,
):
    env_cfg = SimpleNamespace(
        tag="rollback-env",
        services=[],
        volumes=[],
        status=SimpleNamespace(rendered_config=None),
    )
    env = DockerComposeEnv(mocker.Mock(), mocker.Mock(), cast(Any, env_cfg))
    rendered_map = {
        "ungated": "name: rollback-env\nservices:\n  app: {}\n",
    }
    mocker.patch.object(env, "render_target", return_value=rendered_map)
    mocker.patch.object(env, "ensure_resources_impl")

    run_compose_mock = mocker.patch(
        "docker.docker_compose_env.run_compose",
        side_effect=[
            subprocess.CompletedProcess(
                args=["docker", "compose", "up", "-d"],
                returncode=1,
                stdout="up-out",
                stderr="up-err",
            ),
            subprocess.CompletedProcess(
                args=["docker", "compose", "down"],
                returncode=0,
                stdout="",
                stderr="",
            ),
        ],
    )

    die_mock = mocker.patch(
        "environment.environment.Util.print_error_and_die",
        side_effect=RuntimeError("die"),
    )
    with pytest.raises(RuntimeError, match="die"):
        env.start(timeout_seconds=5)

    assert run_compose_mock.call_count == 2
    assert run_compose_mock.call_args_list[0].args[1:3] == ("up", "-d")
    assert run_compose_mock.call_args_list[1].args[1:2] == ("down",)
    die_mock.assert_called_once_with(
        "Failed to start gate 'ungated' for environment 'rollback-env'."
    )


@pytest.mark.docker
def test_start_runs_init_when_probe_turns_true(mocker: MockerFixture):
    env_cfg = SimpleNamespace(
        tag="init-env",
        services=[],
        volumes=[],
        status=SimpleNamespace(rendered_config=None),
    )
    env = DockerComposeEnv(mocker.Mock(), mocker.Mock(), cast(Any, env_cfg))
    env.services = cast(
        list[Any],
        [
            SimpleNamespace(
                svcCfg=SimpleNamespace(
                    tag="db",
                    start=None,
                    containers=[
                        SimpleNamespace(
                            tag="pg",
                            run_container_name="db-init-env",
                            inits=[
                                SimpleNamespace(
                                    tag="create-user",
                                    script="echo init ok",
                                    script_path=None,
                                    when_probes=["ready"],
                                )
                            ],
                        )
                    ],
                )
            )
        ],
    )
    rendered_map = {
        "ungated": "name: init-env\nservices:\n  db-init-env: {}\n",
        "ready": "name: init-env\nservices:\n  ready-svc: {}\n",
    }
    mocker.patch.object(env, "render_target", return_value=rendered_map)
    mocker.patch.object(
        env,
        "check_probes",
        return_value=[
            ProbeRunResult(tag="ready", exit_code=0),
        ],
    )
    mocker.patch.object(env, "ensure_resources_impl")

    run_compose_mock = mocker.patch(
        "docker.docker_compose_env.run_compose",
        side_effect=[
            subprocess.CompletedProcess(
                args=["docker", "compose", "up", "-d"],
                returncode=0,
                stdout="",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["docker", "compose", "exec", "-T"],
                returncode=0,
                stdout="",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["docker", "compose", "exec", "-T"],
                returncode=0,
                stdout="",
                stderr="",
            ),
        ],
    )

    env.start(timeout_seconds=5)
    assert run_compose_mock.call_count == 3
    assert run_compose_mock.call_args_list[2].args[1:] == (
        "exec",
        "-T",
        "db-init-env",
        "sh",
        "-lc",
        "echo init ok",
    )


@pytest.mark.docker
def test_start_runs_init_in_enclosing_container(mocker: MockerFixture):
    env_cfg = SimpleNamespace(
        tag="enclosing-env",
        services=[],
        volumes=[],
        status=SimpleNamespace(rendered_config=None),
    )
    env = DockerComposeEnv(mocker.Mock(), mocker.Mock(), cast(Any, env_cfg))
    env.services = cast(
        list[Any],
        [
            SimpleNamespace(
                svcCfg=SimpleNamespace(
                    tag="svc",
                    start=None,
                    containers=[
                        SimpleNamespace(
                            tag="api",
                            run_container_name="api-enclosing-env",
                            inits=[
                                SimpleNamespace(
                                    tag="init-api",
                                    script="echo api",
                                    script_path=None,
                                    when_probes=[],
                                )
                            ],
                        ),
                        SimpleNamespace(
                            tag="worker",
                            run_container_name="worker-enclosing-env",
                            inits=[
                                SimpleNamespace(
                                    tag="init-worker",
                                    script="echo worker",
                                    script_path=None,
                                    when_probes=[],
                                )
                            ],
                        ),
                    ],
                )
            )
        ],
    )
    rendered_map = {
        "ungated": (
            "name: enclosing-env\n"
            "services:\n"
            "  api-enclosing-env: {}\n"
            "  worker-enclosing-env: {}\n"
        ),
    }
    mocker.patch.object(env, "render_target", return_value=rendered_map)
    mocker.patch.object(env, "ensure_resources_impl")

    run_compose_mock = mocker.patch(
        "docker.docker_compose_env.run_compose",
        side_effect=[
            subprocess.CompletedProcess(
                args=["docker", "compose", "up", "-d"],
                returncode=0,
                stdout="",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["docker", "compose", "exec", "-T"],
                returncode=0,
                stdout="",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["docker", "compose", "exec", "-T"],
                returncode=0,
                stdout="",
                stderr="",
            ),
        ],
    )

    env.start(timeout_seconds=5)
    assert run_compose_mock.call_count == 3
    assert run_compose_mock.call_args_list[1].args[1:4] == (
        "exec",
        "-T",
        "api-enclosing-env",
    )
    assert run_compose_mock.call_args_list[2].args[1:4] == (
        "exec",
        "-T",
        "worker-enclosing-env",
    )


@pytest.mark.docker
def test_start_records_init_compose_failure_output(mocker: MockerFixture):
    env_cfg = SimpleNamespace(
        tag="init-fail-env",
        services=[],
        volumes=[],
        status=SimpleNamespace(rendered_config=None),
    )
    env = DockerComposeEnv(
        mocker.Mock(),
        mocker.Mock(),
        cast(Any, env_cfg),
        cli_flags={"show_commands": True, "show_commands_limit": 5},
    )
    env.services = cast(
        list[Any],
        [
            SimpleNamespace(
                svcCfg=SimpleNamespace(
                    tag="svc",
                    start=None,
                    containers=[
                        SimpleNamespace(
                            tag="api",
                            run_container_name="api-init-fail-env",
                            inits=[
                                SimpleNamespace(
                                    tag="seed",
                                    script="echo seed",
                                    script_path=None,
                                    when_probes=[],
                                )
                            ],
                        )
                    ],
                )
            )
        ],
    )
    rendered_map = {
        "ungated": "name: init-fail-env\nservices:\n  api-init-fail-env: {}\n",
    }
    mocker.patch.object(env, "render_target", return_value=rendered_map)
    mocker.patch.object(env, "ensure_resources_impl")

    run_compose_mock = mocker.patch(
        "docker.docker_compose_env.run_compose",
        side_effect=[
            subprocess.CompletedProcess(
                args=["docker", "compose", "up", "-d"],
                returncode=0,
                stdout="",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["docker", "compose", "exec", "-T"],
                returncode=1,
                stdout="init-out",
                stderr="init-err",
            ),
            subprocess.CompletedProcess(
                args=["docker", "compose", "down"],
                returncode=0,
                stdout="",
                stderr="",
            ),
        ],
    )

    die_mock = mocker.patch(
        "environment.environment.Util.print_error_and_die",
        side_effect=RuntimeError("die"),
    )
    with pytest.raises(RuntimeError, match="die"):
        env.start(timeout_seconds=5)

    assert run_compose_mock.call_count == 3
    err = env.get_command_error()
    assert err is not None
    assert "Docker compose init:svc|api|seed failed" == err["title"]
    assert "--- stdout ---" in err["body"]
    assert "init-out" in err["body"]
    assert "--- stderr ---" in err["body"]
    assert "init-err" in err["body"]
    assert run_compose_mock.call_args_list[2].args[1:2] == ("down",)
    die_mock.assert_called_once_with(
        "Failed to run init 'seed' for container 'api' in environment "
        "'init-fail-env'."
    )


@pytest.mark.docker
def test_start_does_not_rerun_init_across_probe_poll_cycles(
    mocker: MockerFixture,
):
    env_cfg = SimpleNamespace(
        tag="init-dedup-env",
        services=[],
        volumes=[],
        status=SimpleNamespace(rendered_config=None),
    )
    env = DockerComposeEnv(mocker.Mock(), mocker.Mock(), cast(Any, env_cfg))
    env.services = cast(
        list[Any],
        [
            SimpleNamespace(
                svcCfg=SimpleNamespace(
                    tag="svc",
                    start=SimpleNamespace(when_probes=["ready"]),
                    containers=[
                        SimpleNamespace(
                            tag="api",
                            run_container_name="api-init-dedup-env",
                            inits=[
                                SimpleNamespace(
                                    tag="seed",
                                    script="echo seed once",
                                    script_path=None,
                                    when_probes=["ready"],
                                )
                            ],
                        )
                    ],
                )
            )
        ],
    )
    rendered_map = {
        "ungated": "name: init-dedup-env\nservices:\n  base: {}\n",
        "ready": "name: init-dedup-env\nservices:\n  api-init-dedup-env: {}\n",
        "never": "name: init-dedup-env\nservices:\n  never-up: {}\n",
    }
    mocker.patch.object(env, "render_target", return_value=rendered_map)
    check_probes_mock = mocker.patch.object(
        env,
        "check_probes",
        side_effect=[
            [
                ProbeRunResult(tag="ready", exit_code=0),
                ProbeRunResult(tag="never", exit_code=1),
            ],
            [
                ProbeRunResult(tag="ready", exit_code=0),
                ProbeRunResult(tag="never", exit_code=1),
            ],
            [],
        ],
    )
    mocker.patch.object(env, "ensure_resources_impl")
    sleep_mock = mocker.patch("environment.environment.time.sleep")

    run_compose_mock = mocker.patch(
        "docker.docker_compose_env.run_compose",
        side_effect=[
            subprocess.CompletedProcess(
                args=["docker", "compose", "up", "-d"],
                returncode=0,
                stdout="",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["docker", "compose", "up", "-d"],
                returncode=0,
                stdout="",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["docker", "compose", "exec", "-T"],
                returncode=0,
                stdout="",
                stderr="",
            ),
        ],
    )

    env.start(timeout_seconds=5)

    assert check_probes_mock.call_count == 3
    sleep_mock.assert_called_once_with(1.0)
    assert run_compose_mock.call_count == 3
    assert run_compose_mock.call_args_list[2].args[1:] == (
        "exec",
        "-T",
        "api-init-dedup-env",
        "sh",
        "-lc",
        "echo seed once",
    )


@pytest.mark.docker
def test_render_target_merged_includes_gated_services(mocker: MockerFixture):
    env_cfg = SimpleNamespace(
        tag="merge-env",
        services=[],
        volumes=[],
        status=SimpleNamespace(rendered_config=None),
    )
    env = DockerComposeEnv(mocker.Mock(), mocker.Mock(), cast(Any, env_cfg))

    rendered_map = {
        "ungated": "name: merge-env\nservices: {base: {}}\n",
        "db-ready": "name: merge-env\nservices: {db: {}}\n",
    }
    mocker.patch.object(env, "render_target", return_value=rendered_map)

    merged_yaml = env.render_target_merged()
    merged = yaml.safe_load(merged_yaml)
    assert "services" in merged
    assert "base" in merged["services"]
    assert "db" in merged["services"]


@pytest.mark.docker
def test_render_target_grouped_uses_literal_blocks(mocker: MockerFixture):
    env_cfg = SimpleNamespace(
        tag="group-env",
        services=[],
        volumes=[],
        status=SimpleNamespace(rendered_config=None),
    )
    env = DockerComposeEnv(mocker.Mock(), mocker.Mock(), cast(Any, env_cfg))

    rendered_map = {
        "ungated": "name: group-env\nservices: {base: {}}\n",
        "db-ready": "name: group-env\nservices: {db: {}}\n",
    }
    mocker.patch.object(env, "render_target", return_value=rendered_map)

    grouped_yaml = env.render_target_grouped()
    assert "ungated: |" in grouped_yaml
    assert "\\n" not in grouped_yaml


@pytest.mark.docker
def test_start_loops_and_unblocks_gated_compose(mocker: MockerFixture):
    env_cfg = SimpleNamespace(
        tag="loop-env",
        services=[],
        volumes=[],
        status=SimpleNamespace(rendered_config=None),
    )
    config_mng = mocker.Mock()
    env = DockerComposeEnv(config_mng, mocker.Mock(), cast(Any, env_cfg))

    rendered_map = {
        "ungated": "name: loop-env\nservices: {}\n",
        "db-ready": "name: loop-env\nservices:\n  db: {}\n",
    }
    mocker.patch.object(env, "render_target", return_value=rendered_map)
    check_probes_mock = mocker.patch.object(env, "check_probes")
    check_probes_mock.return_value = [
        ProbeRunResult(tag="db-ready", exit_code=0),
    ]
    mocker.patch.object(env, "ensure_resources_impl")

    run_compose_mock = mocker.patch(
        "docker.docker_compose_env.run_compose",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "up", "-d"],
            returncode=0,
            stdout="",
            stderr="",
        ),
    )

    env.start()

    assert env_cfg.status.rendered_config == rendered_map
    assert run_compose_mock.call_count == 2
    assert run_compose_mock.call_args_list[0].args[0] == [
        rendered_map["ungated"]
    ]
    assert run_compose_mock.call_args_list[1].args[0] == [
        rendered_map["ungated"],
        rendered_map["db-ready"],
    ]
    check_probes_mock.assert_called_once_with(
        probe_tag=None,
        fail_fast=False,
        timeout_seconds=120,
    )


@pytest.mark.docker
def test_start_retries_gates_until_probe_turns_true(mocker: MockerFixture):
    env_cfg = SimpleNamespace(
        tag="retry-env",
        services=[],
        volumes=[],
        status=SimpleNamespace(rendered_config=None),
    )
    env = DockerComposeEnv(mocker.Mock(), mocker.Mock(), cast(Any, env_cfg))

    rendered_map = {
        "ungated": "name: retry-env\nservices: {}\n",
        "db-ready": "name: retry-env\nservices:\n  db: {}\n",
    }
    mocker.patch.object(env, "render_target", return_value=rendered_map)
    check_probes_mock = mocker.patch.object(
        env,
        "check_probes",
        side_effect=[
            [ProbeRunResult(tag="db-ready", exit_code=1)],
            [ProbeRunResult(tag="db-ready", exit_code=0)],
        ],
    )
    mocker.patch.object(env, "ensure_resources_impl")
    sleep_mock = mocker.patch("environment.environment.time.sleep")

    run_compose_mock = mocker.patch(
        "docker.docker_compose_env.run_compose",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "up", "-d"],
            returncode=0,
            stdout="",
            stderr="",
        ),
    )

    env.start(timeout_seconds=5)

    assert run_compose_mock.call_count == 2
    assert run_compose_mock.call_args_list[0].args[0] == [
        rendered_map["ungated"]
    ]
    assert run_compose_mock.call_args_list[1].args[0] == [
        rendered_map["ungated"],
        rendered_map["db-ready"],
    ]
    assert check_probes_mock.call_count == 2
    sleep_mock.assert_called_once_with(1.0)


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

    mock_subproc = mock_subprocess_with_running_ps(mocker)

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
    assert mock_subproc.call_count >= 2
    assert any(
        "ps" in (call.args[0] if call.args else [])
        for call in mock_subproc.call_args_list
    )

    sm = ShepherdMng()
    env = sm.configMng.get_environment("test-1")
    assert env
    assert env.status.active is True
    assert env.status.archived is False
    assert env.status.rendered_config is None


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

    mock_subproc = mock_subprocess_with_running_ps(mocker)

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
    assert env.status.rendered_config


@pytest.mark.docker
def test_reload_env_env_not_started(
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

    result = runner.invoke(cli, ["reload", "env"])
    assert result.exit_code != 0
    mock_subproc.assert_not_called()


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


@pytest.mark.docker
def test_probe_render(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("env_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["get", "probe", "db-ready", "-oyaml"])
    assert result.exit_code == 0

    expected = """
probes:
- tag: db-ready
  container:
    tag: db-ready
    image: postgres:17-3.5
    hostname: null
    container_name: null
    workdir: null
    volumes: []
    environment: []
    ports: []
    networks:
    - '#{env.tag}'
    extra_hosts: []
    subject_alternative_name: null
    inits: null
    build: null
  script: sh -c 'pg_isready -h db -p 5432 -U sys -d docker'
  script_path: null
"""

    y1: str = yaml.dump(yaml.safe_load(result.output), sort_keys=True)
    y2: str = yaml.dump(yaml.safe_load(expected), sort_keys=True)
    assert y1 == y2


@pytest.mark.docker
def test_probe_render_resolved(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("env_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["get", "probe", "db-ready", "-oyaml", "-r"])
    assert result.exit_code == 0

    expected = """
probes:
- tag: db-ready
  container:
    tag: db-ready
    image: postgres:17-3.5
    hostname: null
    container_name: null
    workdir: null
    volumes: []
    environment: []
    ports: []
    networks:
    - test-1
    extra_hosts: []
    subject_alternative_name: null
    inits: null
    build: null
  script: sh -c 'pg_isready -h db -p 5432 -U sys -d docker'
  script_path: null
"""

    y1: str = yaml.dump(yaml.safe_load(result.output), sort_keys=True)
    y2: str = yaml.dump(yaml.safe_load(expected), sort_keys=True)
    assert y1 == y2


@pytest.mark.docker
def test_probe_render_target(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("env_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["get", "probe", "db-ready", "-oyaml", "-t"])
    assert result.exit_code == 0

    expected = """
name: test-1
services:
  db-ready:
    image: postgres:17-3.5
    networks:
    - '#{env.tag}'
    command: sh -c 'pg_isready -h db -p 5432 -U sys -d docker'
    restart: 'no'

"""

    y1: str = yaml.dump(yaml.safe_load(result.output), sort_keys=True)
    y2: str = yaml.dump(yaml.safe_load(expected), sort_keys=True)
    assert y1 == y2


@pytest.mark.docker
def test_probe_render_target_resolved(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("env_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(
        cli, ["get", "probe", "db-ready", "-oyaml", "-t", "-r"]
    )
    assert result.exit_code == 0

    expected = """
name: test-1
services:
  db-ready:
    image: postgres:17-3.5
    networks:
    - test-1
    command: sh -c 'pg_isready -h db -p 5432 -U sys -d docker'
    restart: 'no'

"""

    y1: str = yaml.dump(yaml.safe_load(result.output), sort_keys=True)
    y2: str = yaml.dump(yaml.safe_load(expected), sort_keys=True)
    assert y1 == y2


@pytest.mark.docker
def test_check_probe(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("env_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mock_subprocess_with_running_ps(mocker)

    result = runner.invoke(cli, ["up", "env"])
    assert result.exit_code == 0

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose"],
            returncode=0,
            stdout="db:5432 - accepting connections",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["check", "probe"])
    assert result.exit_code == 0
    mock_subproc.assert_called()


@pytest.mark.docker
def test_check_prob_env_not_started(
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
            args=["docker", "compose"],
            returncode=0,
            stdout="db:5432 - accepting connections",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["check", "probe"])
    assert result.exit_code != 0
    mock_subproc.assert_not_called()


@pytest.mark.docker
def test_check_probe_flag_verbose(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("env_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mock_subprocess_with_running_ps(mocker)

    result = runner.invoke(cli, ["up", "env"])
    assert result.exit_code == 0

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose"],
            returncode=0,
            stdout="db:5432 - accepting connections",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["-v", "check", "probe"])
    assert result.exit_code == 0
    mock_subproc.assert_called()


@pytest.mark.docker
def test_check_probe_with_probe_tag(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("env_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mock_subprocess_with_running_ps(mocker)

    result = runner.invoke(cli, ["up", "env"])
    assert result.exit_code == 0

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose"],
            returncode=0,
            stdout="db:5432 - accepting connections",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["check", "probe", "db-ready"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()


@pytest.mark.docker
def test_check_probe_with_missing_probe_tag(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("env_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mock_subprocess_with_running_ps(mocker)

    result = runner.invoke(cli, ["up", "env"])
    assert result.exit_code == 0

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose"],
            returncode=0,
            stdout="db:5432 - accepting connections",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["check", "probe", "no-such-probe"])
    assert result.exit_code == 1
    assert "Probe 'no-such-probe' not found" in result.output
    mock_subproc.assert_not_called()


@pytest.mark.docker
def test_check_probe_timeout(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(read_fixture("env_docker", "shpd.yaml"))

    mock_subprocess_with_running_ps(mocker)

    result = runner.invoke(cli, ["up", "env"])
    assert result.exit_code == 0

    # 2) "check probe" triggers timeout
    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        side_effect=subprocess.TimeoutExpired(
            cmd=["sh", "-c", "pg_isready"], timeout=1
        ),
    )

    result = runner.invoke(cli, ["check", "probe", "db-ready"])

    assert result.exit_code != 0
    mock_subproc.assert_called_once()
