# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.io.

# flake8: noqa E501

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import cast

import pytest
import yaml
from click.testing import CliRunner
from pytest_mock import MockerFixture
from test_util import read_fixture

from shepctl import cli

svc_env_running_ps_output = (
    '{"Service":"container-1-test-test-1","State":"running"}\n'
    '{"Service":"container-1-test-1-test-1","State":"running"}\n'
    '{"Service":"container-2-test-1-test-1","State":"running"}\n'
    '{"Service":"container-1-test-2-test-1","State":"running"}\n'
    '{"Service":"container-1-test-3-test-1","State":"running"}\n'
    '{"Service":"container-1-test-4-test-1","State":"running"}\n'
)


def mock_subprocess_with_running_ps(mocker: MockerFixture):
    def fake_run(
        *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        cmd = (
            cast(list[str], args[0])
            if args and isinstance(args[0], list)
            else []
        )
        if "ps" in cmd:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout=svc_env_running_ps_output,
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
    values = read_fixture("svc_docker", "values.conf")
    config_file.write_text(values.replace("${test_path}", str(temp_home)))

    envs = temp_home / "envs"
    envs.mkdir()
    (envs / "test-1" / "build").mkdir(parents=True)
    (envs / "test-1" / "build" / "Dockerfile").write_text("FROM alpine:latest")

    os.environ["SHPD_CONF"] = str(config_file)
    return temp_home, config_file


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.docker
def test_svc_render_default_compose_service(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("svc_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["svc", "get", "test", "-oyaml"])
    assert result.exit_code == 0

    expected = (
        "template: default\n"
        "factory: docker\n"
        "tag: test\n"
        "start: null\n"
        "containers:\n"
        "  - image: test-image:latest\n"
        "    tag: container-1\n"
        "    workdir: /test\n"
        "    container_name: null\n"
        "    hostname: null\n"
        "    volumes:\n"
        "      - /home/test/.ssh:/home/test/.ssh\n"
        "      - /etc/ssh:/etc/ssh\n"
        "    environment:\n"
        "     - POSTGRES_PASSWORD=psw\n"
        "     - POSTGRES_USER=sys\n"
        "     - POSTGRES_DB=docker\n"
        "    ports:\n"
        "      - 80:80\n"
        "      - 443:443\n"
        "      - 8080:8080\n"
        "    networks:\n"
        "      - default\n"
        "    extra_hosts:\n"
        "      - host.docker.internal:host-gateway\n"
        "    inits: null\n"
        "    build:\n"
        "      context_path: '#{cfg.envs_path}/#{env.tag}/build'\n"
        "      dockerfile_path: '#{cnt.build.context_path}/Dockerfile'\n"
        "service_class: null\n"
        "labels:\n"
        "- com.example.label1=value1\n"
        "- com.example.label2=value2\n"
        "properties: {}\n"
        "upstreams: []\n"
        "status:\n"
        "  active: true\n"
        "  rendered_config: null\n\n"
    )

    y1: str = yaml.dump(yaml.safe_load(result.output), sort_keys=True)
    y2: str = yaml.dump(yaml.safe_load(expected), sort_keys=True)
    assert y1 == y2


@pytest.mark.docker
def test_svc_render_default_compose_service_resolved(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("svc_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["svc", "get", "test", "-oyaml", "-r"])
    assert result.exit_code == 0

    expected = (
        "template: default\n"
        "factory: docker\n"
        "tag: test\n"
        "start: null\n"
        "service_class: null\n"
        "containers:\n"
        "  - image: test-image:latest\n"
        "    tag: container-1\n"
        "    workdir: /test\n"
        "    container_name: null\n"
        "    hostname: null\n"
        "    volumes:\n"
        "      - /home/test/.ssh:/home/test/.ssh\n"
        "      - /etc/ssh:/etc/ssh\n"
        "    environment:\n"
        "     - POSTGRES_PASSWORD=psw\n"
        "     - POSTGRES_USER=sys\n"
        "     - POSTGRES_DB=docker\n"
        "    ports:\n"
        "      - 80:80\n"
        "      - 443:443\n"
        "      - 8080:8080\n"
        "    networks:\n"
        "      - default\n"
        "    extra_hosts:\n"
        "      - host.docker.internal:host-gateway\n"
        "    inits: null\n"
        "    build:\n"
        f"     context_path: {str(shpd_path)}/envs/test-1/build\n"
        f"     dockerfile_path: {str(shpd_path)}/envs/test-1/build/Dockerfile\n"
        "labels:\n"
        "- com.example.label1=value1\n"
        "- com.example.label2=value2\n"
        "properties: {}\n"
        "upstreams: []\n"
        "status:\n"
        "  active: true\n"
        "  rendered_config: null\n\n"
    )

    y1: str = yaml.dump(yaml.safe_load(result.output), sort_keys=True)
    y2: str = yaml.dump(yaml.safe_load(expected), sort_keys=True)
    assert y1 == y2


@pytest.mark.docker
def test_svc_render_target_compose_service(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("svc_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["svc", "get", "test", "-oyaml", "-t"])
    assert result.exit_code == 0

    expected = (
        "services:\n"
        "   container-1-test-test-1:\n"
        "     image: test-image:latest\n"
        "     hostname: container-1-test-test-1\n"
        "     working_dir: /test\n"
        "     container_name: container-1-test-test-1\n"
        "     labels:\n"
        "     - com.example.label1=value1\n"
        "     - com.example.label2=value2\n"
        "     environment:\n"
        "     - POSTGRES_PASSWORD=psw\n"
        "     - POSTGRES_USER=sys\n"
        "     - POSTGRES_DB=docker\n"
        "     volumes:\n"
        "     - /home/test/.ssh:/home/test/.ssh\n"
        "     - /etc/ssh:/etc/ssh\n"
        "     ports:\n"
        "     - 80:80\n"
        "     - 443:443\n"
        "     - 8080:8080\n"
        "     extra_hosts:\n"
        "     - host.docker.internal:host-gateway\n"
        "     networks:\n"
        "     - default\n\n"
    )

    y1: str = yaml.dump(yaml.safe_load(result.output), sort_keys=True)
    y2: str = yaml.dump(yaml.safe_load(expected), sort_keys=True)
    assert y1 == y2


@pytest.mark.docker
def test_start_svc(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("svc_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mock_subprocess_with_running_ps(mocker)

    result = runner.invoke(cli, ["env", "up"])

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "up", "-d", "test-test-1"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["svc", "up", "test"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()


@pytest.mark.docker
def test_start_svc_cnt_2(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("svc_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mock_subprocess_with_running_ps(mocker)

    result = runner.invoke(cli, ["env", "up"])

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "up", "-d", "test-test-1"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["svc", "up", "test-1", "container-2"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()


@pytest.mark.docker
def test_stop_svc(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("svc_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mock_subprocess_with_running_ps(mocker)

    result = runner.invoke(cli, ["env", "up"])

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "stop", "test-test-1"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["svc", "halt", "test"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()


@pytest.mark.docker
def test_stop_svc_cnt_2(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("svc_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mock_subprocess_with_running_ps(mocker)

    result = runner.invoke(cli, ["env", "up"])

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "stop", "test-test-1"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["svc", "halt", "test-1", "container-2"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()


@pytest.mark.docker
def test_reload_svc(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("svc_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mock_subprocess_with_running_ps(mocker)

    result = runner.invoke(cli, ["env", "up"])

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "restart", "test-test-1"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["svc", "reload", "test"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()


@pytest.mark.docker
def test_reload_svc_cnt_2(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("svc_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mock_subprocess_with_running_ps(mocker)

    result = runner.invoke(cli, ["env", "up"])

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "restart", "test-test-1"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["svc", "reload", "test-1", "container-2"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()


@pytest.mark.docker
def test_logs_svc(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("svc_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mock_subprocess_with_running_ps(mocker)

    result = runner.invoke(cli, ["env", "up"])

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "logs", "test-test-1"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["svc", "logs", "test"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()


@pytest.mark.docker
def test_logs_svc_cnt_2(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("svc_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mock_subprocess_with_running_ps(mocker)

    result = runner.invoke(cli, ["env", "up"])

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "logs", "test-test-1"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["svc", "logs", "test-1", "container-2"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()


@pytest.mark.docker
def test_shell_svc(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("svc_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mock_subprocess_with_running_ps(mocker)

    result = runner.invoke(cli, ["env", "up"])

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "shell", "test-test-1"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["svc", "shell", "test"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()


@pytest.mark.docker
def test_shell_svc_cnt_2(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("svc_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mock_subprocess_with_running_ps(mocker)

    result = runner.invoke(cli, ["env", "up"])

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "shell", "test-test-1"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["svc", "shell", "test-1", "container-2"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()


@pytest.mark.docker
def test_build_svc(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("svc_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "build", "test-test-1"],
            returncode=0,
            stdout="mocked docker build output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["svc", "build", "test"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()


@pytest.mark.docker
def test_build_svc_cnt_2(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("svc_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "build", "test-test-1"],
            returncode=0,
            stdout="mocked docker build output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["svc", "build", "test-1", "container-2"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()


@pytest.mark.docker
def test_build_svc_missing_build(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("svc_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "build", "test-1-test-1"],
            returncode=0,
            stdout="mocked docker build output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["svc", "build", "test-1"])
    assert result.exit_code == 1
    mock_subproc.assert_not_called()


@pytest.mark.docker
def test_build_svc_missing_build_dockerfile(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("svc_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "build", "test-2-test-1"],
            returncode=0,
            stdout="mocked docker build output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["svc", "build", "test-2"])
    assert result.exit_code == 1
    mock_subproc.assert_not_called()


@pytest.mark.docker
def test_build_svc_missing_build_context_path(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("svc_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "build", "test-3-test-1"],
            returncode=0,
            stdout="mocked docker build output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["svc", "build", "test-3"])
    assert result.exit_code == 1
    mock_subproc.assert_not_called()


@pytest.mark.docker
def test_build_svc_dockerfile_does_not_exist(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("svc_docker", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "build", "test-4-test-1"],
            returncode=0,
            stdout="mocked docker build output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["svc", "build", "test-4"])
    assert result.exit_code == 1
    mock_subproc.assert_not_called()
