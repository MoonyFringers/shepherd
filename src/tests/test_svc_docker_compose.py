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
from click.testing import CliRunner
from pytest_mock import MockerFixture
from test_util import values

from shepctl import cli

shpd_config_svc_default = """
{
  "logging": {
    "file": "${log_file}",
    "level": "${log_level}",
    "stdout": "${log_stdout}",
    "format": "${log_format}"
  },
  "shpd_registry": {
    "ftp_server": "${shpd_registry}",
    "ftp_user": "${shpd_registry_ftp_usr}",
    "ftp_psw": "${shpd_registry_ftp_psw}",
    "ftp_shpd_path": "${shpd_registry_ftp_shpd_path}",
    "ftp_env_imgs_path": "${shpd_registry_ftp_imgs_path}"
  },
  "envs_path": "${envs_path}",
  "volumes_path": "${volumes_path}",
  "host_inet_ip": "${host_inet_ip}",
  "domain": "${domain}",
  "dns_type": "${dns_type}",
  "ca": {
    "country": "${ca_country}",
    "state": "${ca_state}",
    "locality": "${ca_locality}",
    "organization": "${ca_org}",
    "organizational_unit": "${ca_org_unit}",
    "common_name": "${ca_cn}",
    "email": "${ca_email}",
    "passphrase": "${ca_passphrase}"
  },
  "cert": {
    "country": "${cert_country}",
    "state": "${cert_state}",
    "locality": "${cert_locality}",
    "organization": "${cert_org}",
    "organizational_unit": "${cert_org_unit}",
    "common_name": "${cert_cn}",
    "email": "${cert_email}",
    "subject_alternative_names": []
  },
  "staging_area": {
    "volumes_path": "${staging_area_volumes_path}",
    "images_path": "${staging_area_images_path}"
  },
  "env_templates": [
    {
      "tag": "default",
      "factory": "docker-compose",
      "service_templates": [
        {
          "template": "default",
          "tag": "service-default"
        }
      ],
      "networks": [
        {
          "tag": "shpdnet",
          "name": "envnet",
          "external": true
        }
      ]
    }
  ],
  "service_templates": [
    {
      "tag": "default",
      "factory": "docker",
      "image": "test-image:latest",
      "labels": [
        "com.example.label1=value1",
        "com.example.label2=value2"
      ],
      "workdir": "/test",
      "volumes": [
          "/home/test/.ssh:/home/test/.ssh",
          "/etc/ssh:/etc/ssh"
      ],
      "ingress": false,
      "empty_env": null,
      "environment": [],
      "ports": [
        "80:80",
        "443:443",
        "8080:8080"
      ],
      "properties": {},
      "networks": [
        "default"
      ],
      "extra_hosts": [
        "host.docker.internal:host-gateway"
      ],
      "subject_alternative_name": null
    }
  ],
  "envs": [
    {
      "template": "default",
      "factory": "docker-compose",
      "tag": "test-1",
      "services": [
        {
          "template": "default",
          "factory": "docker",
          "tag": "test",
          "image": "test-image:latest",
          "labels": [
            "com.example.label1=value1",
            "com.example.label2=value2"
          ],
          "workdir": "/test",
          "volumes": [
              "/home/test/.ssh:/home/test/.ssh",
              "/etc/ssh:/etc/ssh"
          ],
          "ingress": false,
          "empty_env": null,
          "environment": [],
          "ports": [
            "80:80",
            "443:443",
            "8080:8080"
          ],
          "properties": {},
          "networks": [
            "default"
          ],
          "extra_hosts": [
            "host.docker.internal:host-gateway"
          ],
          "subject_alternative_name": null,
          "status": {
            "active": true,
            "archived": false,
            "triggered_config": null
          }
        }
      ],
      "status": {
        "active": true,
        "archived": false,
        "triggered_config": null
      }
    }
  ]
}
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


@pytest.mark.docker
def test_svc_render_compose_service(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["svc", "get", "test"])
    assert result.exit_code == 0

    assert result.output == (
        "services:\n"
        "  test-test-1:\n"
        "    image: test-image:latest\n"
        "    hostname: test-test-1\n"
        "    container_name: test-test-1\n"
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
        "    - default\n\n"
    )


@pytest.mark.docker
def test_svc_start(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config_svc_default)

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "up", "-d"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

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
def test_svc_stop(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config_svc_default)

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "start", "-d"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

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
def test_svc_reload(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config_svc_default)

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "start", "-d"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

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
def test_svc_stdout(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config_svc_default)

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "start", "-d"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

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

    result = runner.invoke(cli, ["svc", "stdout", "test"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()


@pytest.mark.docker
def test_svc_shell(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config_svc_default)

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "start", "-d"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

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
