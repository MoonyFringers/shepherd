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

from shepctl import ShepherdMng, cli

values = """
  # Oracle (ora) Configuration
  ora_image=ghcr.io/MoonyFringers/shepherd/oracle:19.3.0.0_TZ40
  ora_empty_env=fresh-ora-19300
  ora_pump_dir=PUMP_DIR
  ora_root_db_name=ORCLCDB
  ora_plug_db_name=ORCLPDB1
  ora_listener_port=1521

  # PostgreSQL (pg) Configuration
  pg_image=ghcr.io/MoonyFringers/shepherd/postgres:17-3.5
  pg_empty_env=fresh-pg-1735
  pg_listener_port=5432

  # SHPD Registry Configuration
  shpd_registry=ftp.example.com
  shpd_registry_ftp_usr=
  shpd_registry_ftp_psw=
  shpd_registry_ftp_shpd_path=shpd
  shpd_registry_ftp_imgs_path=imgs

  # Host and Domain Configuration
  host_inet_ip=127.0.0.1
  domain=sslip.io
  dns_type=autoresolving

  # Certificate Authority (CA) Configuration
  ca_country=IT
  ca_state=MS
  ca_locality=Carrara
  ca_org=MoonyFringe
  ca_org_unit=Development
  ca_cn=sslip.io
  ca_email=lf@sslip.io
  ca_passphrase=test

  # Certificate Configuration
  cert_country=IT
  cert_state=MS
  cert_locality=Carrara
  cert_org=MoonyFringe
  cert_org_unit=Development
  cert_cn=sslip.io
  cert_email=lf@sslip.io
  cert_subject_alternative_names=

  shpd_dir=~/shpd
  shpd_volumes_dir=${shpd_dir}/volumes

  # Database Default Configuration
  db_sys_usr=sys
  db_sys_psw=sys
  db_usr=docker
  db_psw=docker

  # Logging Configuration
  log_file=~/shpd/shepctl.log
  log_level=WARNING
  log_stdout=false
  log_format=%(asctime)s - %(levelname)s - %(message)s
  """

values = """
  # PostgreSQL (pg) Configuration
  pg_image=ghcr.io/MoonyFringers/shepherd/postgres:17-3.5
  pg_empty_env=fresh-pg-1735
  pg_listener_port=5432

  # SHPD Registry Configuration
  shpd_registry=ftp.example.com
  shpd_registry_ftp_usr=
  shpd_registry_ftp_psw=
  shpd_registry_ftp_shpd_path=shpd
  shpd_registry_ftp_imgs_path=imgs

  # Host and Domain Configuration
  host_inet_ip=127.0.0.1
  domain=sslip.io
  dns_type=autoresolving

  # Certificate Authority (CA) Configuration
  ca_country=IT
  ca_state=MS
  ca_locality=Carrara
  ca_org=MoonyFringe
  ca_org_unit=Development
  ca_cn=sslip.io
  ca_email=lf@sslip.io
  ca_passphrase=test

  # Certificate Configuration
  cert_country=IT
  cert_state=MS
  cert_locality=Carrara
  cert_org=MoonyFringe
  cert_org_unit=Development
  cert_cn=sslip.io
  cert_email=lf@sslip.io
  cert_subject_alternative_names=

  shpd_dir=~/shpd

  # Database Default Configuration
  db_sys_usr=sys
  db_sys_psw=sys
  db_usr=docker
  db_psw=docker

  # Logging Configuration
  log_file=~/shpd/shepctl.log
  log_level=WARNING
  log_stdout=false
  log_format=%(asctime)s - %(levelname)s - %(message)s
  """

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
          "key": "shpdnet",
          "name": "envnet",
          "external": true
        }
      ],
      "volumes":[
        {
          "key": "app_data",
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
          "tag": "test-1",
          "image": "test-1-image:latest",
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
        },
        {
          "template": "default",
          "factory": "docker",
          "tag": "test-2",
          "image": "test-2-image:latest",
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
      "networks": [
        {
          "key": "default",
          "name": "envnet",
          "external": true
        }
      ],
      "volumes":[
        {
          "key": "app_data_ext",
          "external": true,
          "name": "nfs-1"
        }
      ],
      "archived": false,
      "active": true
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
          "image": "test-1-image:latest",
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
          "subject_alternative_name": null
        },
        {
          "template": "default",
          "factory": "docker",
          "tag": "test-2",
          "image": "test-2-image:latest",
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
          "subject_alternative_name": null
        }
      ],
      "networks": [
        {
          "key": "internal_net",
          "external": false,
          "driver": "bridge",
          "internal": true,
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
          "key": "app_data",
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
      "archived": false,
      "active": true
    }
  ]
}
"""


@pytest.fixture
def temp_home(tmp_path: Path, mocker: MockerFixture) -> Path:
    """Fixture to create a temporary home directory and .shpd.conf file."""
    temp_home = tmp_path / "home"
    temp_home.mkdir()

    config_file = temp_home / ".shpd.conf"
    config_file.write_text(values)

    return temp_home


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def make_expanduser_side_effect(path: Path, calls: int):
    """Generate a list of `os.path.expanduser` return
    values repeating [shpd, .shpd.conf, shpd/shepctl.log]."""
    return [
        (
            path / ".shpd.conf"
            if i % 3 == 0
            else (
                path / "shpd" if i % 3 == 1 else path / "shpd" / "shepctl.log"
            )
        )
        for i in range(calls * 3)
    ]


@pytest.mark.env
@pytest.mark.parametrize("expanduser_side_effects", [2])
def test_env_init(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    result = runner.invoke(cli, ["env", "init", "default", "test-init-1"])
    assert result.exit_code == 0

    sm = ShepherdMng()
    assert sm.configMng.exists_environment("test-init-1")

    expected_dirs = [
        os.path.join(sm.configMng.constants.SHPD_ENVS_DIR, "test-init-1")
    ]

    for directory in expected_dirs:
        assert os.path.isdir(
            directory
        ), f"Directory {directory} was not created."


@pytest.mark.env
@pytest.mark.parametrize("expanduser_side_effects", [3])
def test_env_clone(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

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
        os.path.join(sm.configMng.constants.SHPD_ENVS_DIR, "test-clone-1"),
        os.path.join(sm.configMng.constants.SHPD_ENVS_DIR, "test-clone-2"),
    ]

    for directory in expected_dirs:
        assert os.path.isdir(
            directory
        ), f"Directory {directory} was not created."


@pytest.mark.env
@pytest.mark.parametrize("expanduser_side_effects", [3])
def test_env_rename(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    result = runner.invoke(cli, ["env", "init", "default", "test-rename-1"])
    assert result.exit_code == 0

    result = runner.invoke(
        cli, ["env", "rename", "test-rename-1", "test-rename-2"]
    )
    assert result.exit_code == 0

    sm = ShepherdMng()
    assert not sm.configMng.exists_environment("test-rename-1")
    assert sm.configMng.exists_environment("test-rename-2")

    renamed_dir = os.path.join(
        sm.configMng.constants.SHPD_ENVS_DIR, "test-rename-2"
    )
    old_dir = os.path.join(
        sm.configMng.constants.SHPD_ENVS_DIR, "test-rename-1"
    )

    assert os.path.isdir(
        renamed_dir
    ), f"Directory {renamed_dir} was not created."
    assert not os.path.exists(
        old_dir
    ), f"Old directory {old_dir} still exists after rename."


@pytest.mark.env
@pytest.mark.parametrize("expanduser_side_effects", [7])
def test_env_checkout(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

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
@pytest.mark.parametrize("expanduser_side_effects", [2])
def test_env_list(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    result = runner.invoke(cli, ["env", "init", "default", "test-1"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["env", "list"])
    assert result.exit_code == 0


@pytest.mark.env
@pytest.mark.parametrize("expanduser_side_effects", [3])
def test_env_delete_yes(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    mocker.patch("builtins.input", return_value="y")

    result = runner.invoke(cli, ["env", "init", "default", "test-1"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["env", "delete", "test-1"])
    assert result.exit_code == 0

    sm = ShepherdMng()
    env = sm.configMng.get_environment("test-1")
    assert env is None

    env_dir = os.path.join(sm.configMng.constants.SHPD_ENVS_DIR, "test-1")

    assert not os.path.exists(
        env_dir
    ), f"directory {env_dir} still exists after delete."


@pytest.mark.env
@pytest.mark.parametrize("expanduser_side_effects", [3])
def test_env_delete_no(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    mocker.patch("builtins.input", return_value="n")

    result = runner.invoke(cli, ["env", "init", "default", "test-1"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["env", "delete", "test-1"])
    assert result.exit_code == 0

    sm = ShepherdMng()
    env = sm.configMng.get_environment("test-1")
    assert env is not None

    env_dir = os.path.join(sm.configMng.constants.SHPD_ENVS_DIR, "test-1")

    assert os.path.exists(
        env_dir
    ), f"directory {env_dir} does not exist after delete-no."


@pytest.mark.env
@pytest.mark.parametrize("expanduser_side_effects", [3])
def test_env_add_nonexisting_resource(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    result = runner.invoke(cli, ["env", "init", "default", "test-svc-add"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["env", "checkout", "test-svc-add"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["env", "add", "foo", "foo-1"])
    assert result.exit_code == 2


@pytest.mark.env
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_env_render_compose_env_ext_net(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_dir = temp_home / "shpd"
    shpd_dir.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_dir / ".shpd.json"
    shpd_json.write_text(shpd_config)

    result = runner.invoke(cli, ["env", "render", "test-1"])
    assert result.exit_code == 0

    assert result.output == (
        "name: test-1\n"
        "services:\n"
        "  test-1-test-1:\n"
        "    image: test-1-image:latest\n"
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
        "    image: test-2-image:latest\n"
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


@pytest.mark.env
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_env_render_compose_env_int_net(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_dir = temp_home / "shpd"
    shpd_dir.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_dir / ".shpd.json"
    shpd_json.write_text(shpd_config)

    result = runner.invoke(cli, ["env", "render", "test-2"])
    assert result.exit_code == 0

    assert result.output == (
        "name: test-2\n"
        "services:\n"
        "  test-1-test-2:\n"
        "    image: test-1-image:latest\n"
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
        "    image: test-2-image:latest\n"
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
        "    internal: true\n"
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
