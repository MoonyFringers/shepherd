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

from shepctl import ShepherdMng, cli

shpd_config = """
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
      ],
      "volumes":[
        {
          "tag": "app_data",
          "external": false,
          "driver": "local",
          "driver_opts": {
            "type": "none",
            "o": "bind",
            "device": "/srv/data"
          },
          "labels": {
            "env": "production"
          }
        }
      ]
    }
  ],
  "service_templates": [
    {
      "tag": "default",
      "factory": "docker",
      "image": "busybox:stable-glibc",
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
          "tag": "test-1",
          "image": "busybox:stable-glibc",
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
        },
        {
          "template": "default",
          "factory": "docker",
          "tag": "test-2",
          "image": "busybox:stable-glibc",
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
      "networks": [
        {
          "tag": "default",
          "name": "envnet",
          "external": true
        }
      ],
      "volumes":[
        {
          "tag": "app_data_ext",
          "external": true,
          "name": "nfs-1"
        }
      ],
      "status": {
        "active": true,
        "archived": false,
        "triggered_config": null
      }
    },
    {
      "template": "default",
      "factory": "docker-compose",
      "tag": "test-2",
      "services": [
        {
          "template": "default",
          "factory": "docker",
          "tag": "test-1",
          "image": "busybox:stable-glibc",
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
            "internal_net"
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
        },
        {
          "template": "default",
          "factory": "docker",
          "tag": "test-2",
          "image": "busybox:stable-glibc",
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
            "internal_net"
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
      "networks": [
        {
          "tag": "internal_net",
          "external": false,
          "driver": "bridge",
          "attachable": true,
          "enable_ipv6": false,
          "driver_opts": {
            "com.docker.network.bridge.name": "br-internal"
          },
          "ipam": {
            "driver": "default",
            "config": [
              {
                "subnet": "172.30.0.0/16",
                "gateway": "172.30.0.1"
              }
            ]
          }
        }
      ],
      "volumes":[
        {
          "tag": "app_data",
          "external": false,
          "driver": "local",
          "driver_opts": {
            "type": "none",
            "o": "bind",
            "device": "/srv/data"
          },
          "labels": {
            "env": "production"
          }
        }
      ],
      "status": {
        "active": false,
        "archived": false,
        "triggered_config": null
      }
    }
  ]
}
"""

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
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    result = runner.invoke(cli, ["env", "render", "test-1"])
    assert result.exit_code == 0

    assert result.output == (
        "name: test-1\n"
        "services:\n"
        "  test-1-test-1:\n"
        "    image: busybox:stable-glibc\n"
        "    hostname: test-1-test-1\n"
        "    container_name: test-1-test-1\n"
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
        "  test-2-test-1:\n"
        "    image: busybox:stable-glibc\n"
        "    hostname: test-2-test-1\n"
        "    container_name: test-2-test-1\n"
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


@pytest.mark.docker
def test_env_render_compose_env_int_net(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    result = runner.invoke(cli, ["env", "render", "test-2"])
    assert result.exit_code == 0

    assert result.output == (
        "name: test-2\n"
        "services:\n"
        "  test-1-test-2:\n"
        "    image: busybox:stable-glibc\n"
        "    hostname: test-1-test-2\n"
        "    container_name: test-1-test-2\n"
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
        "  test-2-test-2:\n"
        "    image: busybox:stable-glibc\n"
        "    hostname: test-2-test-2\n"
        "    container_name: test-2-test-2\n"
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


@pytest.mark.docker
def test_env_start(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

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
    assert result.exit_code == 0
    mock_subproc.assert_called_once()

    sm = ShepherdMng()
    env = sm.configMng.get_environment("test-1")
    assert env
    assert env.status.active is True
    assert env.status.archived is False
    assert env.status.triggered_config


@pytest.mark.docker
def test_env_stop(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "restart"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["env", "up"])

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "down"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["env", "halt"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()

    sm = ShepherdMng()
    env = sm.configMng.get_environment("test-1")
    assert env
    assert env.status.active is True
    assert env.status.archived is False
    assert env.status.triggered_config is None


@pytest.mark.docker
def test_env_restart(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "restart"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["env", "up"])

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "restart"],
            returncode=0,
            stdout="mocked docker compose output",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["env", "reload"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()

    sm = ShepherdMng()
    env = sm.configMng.get_environment("test-1")
    assert env
    assert env.status.active is True
    assert env.status.archived is False
    assert env.status.triggered_config


@pytest.mark.docker
def test_env_status(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    mock_subproc = mocker.patch(
        "docker.docker_compose_util.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["docker", "compose", "ps", "--format", "json"],
            returncode=0,
            stdout=docker_compose_ps_output,
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["env", "status"])
    assert result.exit_code == 0
    mock_subproc.assert_called_once()
