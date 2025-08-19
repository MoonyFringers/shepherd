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

from database import DatabaseMng
from environment import EnvironmentMng
from service import ServiceMng
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

  shpd_dir=.
  shpd_volumes_dir=${shpd_dir}/volumes

  # Database Default Configuration
  db_sys_usr=sys
  db_sys_psw=sys
  db_usr=docker
  db_psw=docker

  # Logging Configuration
  log_file=shepctl.log
  log_level=WARNING
  log_stdout=false
  log_format=%(asctime)s - %(levelname)s - %(message)s
  """

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
          "subject_alternative_name": null
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


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_shepherdmng_creates_dirs(
    temp_home: Path, mocker: MockerFixture, expanduser_side_effects: int
):
    """Test that ShepherdMng creates the required directories."""
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    sm = ShepherdMng()

    expected_dirs = [
        sm.configMng.constants.SHPD_ENVS_DIR,
        sm.configMng.constants.SHPD_ENV_IMGS_DIR,
        sm.configMng.constants.SHPD_CERTS_DIR,
        sm.configMng.constants.SHPD_SSH_DIR,
        sm.configMng.constants.SHPD_SSHD_DIR,
    ]

    for directory in expected_dirs:
        assert os.path.isdir(
            directory
        ), f"Directory {directory} was not created."

    shpd_config_file = sm.configMng.constants.SHPD_CONFIG_FILE
    assert os.path.isfile(
        shpd_config_file
    ), f"Config file {shpd_config_file} does not exist or is not a file."


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_flags_no_flags(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_init = mocker.patch.object(ShepherdMng, "__init__", return_value=None)
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    result = runner.invoke(cli, ["test"])

    assert result.exit_code == 0
    mock_init.assert_called_once_with(
        {
            "verbose": False,
            "yes": False,
            "all": False,
            "follow": False,
            "porcelain": False,
            "keep": False,
            "replace": False,
            "checkout": False,
        }
    )


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_flags_verbose(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_init = mocker.patch.object(ShepherdMng, "__init__", return_value=None)
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    result = runner.invoke(cli, ["--verbose", "test"])

    flags = {
        "verbose": True,
        "yes": False,
        "all": False,
        "follow": False,
        "porcelain": False,
        "keep": False,
        "replace": False,
        "checkout": False,
    }

    assert result.exit_code == 0
    mock_init.assert_called_once_with(flags)

    result = runner.invoke(cli, ["-v", "test"])

    assert result.exit_code == 0
    mock_init.assert_called_with(flags)


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_flags_yes(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_init = mocker.patch.object(ShepherdMng, "__init__", return_value=None)
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    result = runner.invoke(cli, ["--yes", "test"])

    flags = {
        "verbose": False,
        "yes": True,
        "all": False,
        "follow": False,
        "porcelain": False,
        "keep": False,
        "replace": False,
        "checkout": False,
    }

    assert result.exit_code == 0
    mock_init.assert_called_once_with(flags)

    result = runner.invoke(cli, ["-y", "test"])

    assert result.exit_code == 0
    mock_init.assert_called_with(flags)


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_flags_all(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_init = mocker.patch.object(ShepherdMng, "__init__", return_value=None)
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    result = runner.invoke(cli, ["--all", "test"])

    flags = {
        "verbose": False,
        "yes": False,
        "all": True,
        "follow": False,
        "porcelain": False,
        "keep": False,
        "replace": False,
        "checkout": False,
    }

    assert result.exit_code == 0
    mock_init.assert_called_once_with(flags)

    result = runner.invoke(cli, ["-a", "test"])

    assert result.exit_code == 0
    mock_init.assert_called_with(flags)


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_flags_follow(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_init = mocker.patch.object(ShepherdMng, "__init__", return_value=None)
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    result = runner.invoke(cli, ["--follow", "test"])

    flags = {
        "verbose": False,
        "yes": False,
        "all": False,
        "follow": True,
        "porcelain": False,
        "keep": False,
        "replace": False,
        "checkout": False,
    }

    assert result.exit_code == 0
    mock_init.assert_called_once_with(flags)

    result = runner.invoke(cli, ["-f", "test"])

    assert result.exit_code == 0
    mock_init.assert_called_with(flags)


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_flags_porcelain(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_init = mocker.patch.object(ShepherdMng, "__init__", return_value=None)
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    result = runner.invoke(cli, ["--porcelain", "test"])

    flags = {
        "verbose": False,
        "yes": False,
        "all": False,
        "follow": False,
        "porcelain": True,
        "keep": False,
        "replace": False,
        "checkout": False,
    }

    assert result.exit_code == 0
    mock_init.assert_called_once_with(flags)

    result = runner.invoke(cli, ["-p", "test"])

    assert result.exit_code == 0
    mock_init.assert_called_with(flags)


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_flags_keep(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_init = mocker.patch.object(ShepherdMng, "__init__", return_value=None)
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    result = runner.invoke(cli, ["--keep", "test"])

    flags = {
        "verbose": False,
        "yes": False,
        "all": False,
        "follow": False,
        "porcelain": False,
        "keep": True,
        "replace": False,
        "checkout": False,
    }

    assert result.exit_code == 0
    mock_init.assert_called_once_with(flags)

    result = runner.invoke(cli, ["-k", "test"])

    assert result.exit_code == 0
    mock_init.assert_called_with(flags)


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_flags_replace(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_init = mocker.patch.object(ShepherdMng, "__init__", return_value=None)
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    result = runner.invoke(cli, ["--replace", "test"])

    flags = {
        "verbose": False,
        "yes": False,
        "all": False,
        "follow": False,
        "porcelain": False,
        "keep": False,
        "replace": True,
        "checkout": False,
    }

    assert result.exit_code == 0
    mock_init.assert_called_once_with(flags)

    result = runner.invoke(cli, ["-r", "test"])

    assert result.exit_code == 0
    mock_init.assert_called_with(flags)


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_flags_checkout(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_init = mocker.patch.object(ShepherdMng, "__init__", return_value=None)
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    result = runner.invoke(cli, ["--checkout", "test"])

    flags = {
        "verbose": False,
        "yes": False,
        "all": False,
        "follow": False,
        "porcelain": False,
        "keep": False,
        "replace": False,
        "checkout": True,
    }

    assert result.exit_code == 0
    mock_init.assert_called_once_with(flags)

    result = runner.invoke(cli, ["-c", "test"])

    assert result.exit_code == 0
    mock_init.assert_called_with(flags)


# completion tests


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_complete(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    result = runner.invoke(cli, ["__complete", "env"])
    assert result.exit_code == 0


# service tests


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_srv_build(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_build = mocker.patch.object(ServiceMng, "build_image_svc")
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    result = runner.invoke(cli, ["svc", "build", "service_template"])
    assert result.exit_code == 0
    mock_build.assert_called_once_with("service_template")


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_srv_up(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_start = mocker.patch.object(ServiceMng, "start_svc")
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_dir = temp_home / "shpd"
    shpd_dir.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_dir / ".shpd.json"
    shpd_json.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["svc", "up", "service_tag"])
    assert result.exit_code == 0
    mock_start.assert_called_once()


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_srv_halt(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_halt = mocker.patch.object(ServiceMng, "halt_svc")
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_dir = temp_home / "shpd"
    shpd_dir.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_dir / ".shpd.json"
    shpd_json.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["svc", "halt", "service_tag"])
    assert result.exit_code == 0
    mock_halt.assert_called_once()


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_srv_reload(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_reload = mocker.patch.object(ServiceMng, "reload_svc")
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_dir = temp_home / "shpd"
    shpd_dir.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_dir / ".shpd.json"
    shpd_json.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["svc", "reload", "service_tag"])
    assert result.exit_code == 0
    mock_reload.assert_called_once()


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_srv_stdout(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_stdout = mocker.patch.object(ServiceMng, "stdout_svc")
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_dir = temp_home / "shpd"
    shpd_dir.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_dir / ".shpd.json"
    shpd_json.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["svc", "stdout", "service_tag"])
    assert result.exit_code == 0
    mock_stdout.assert_called_once()


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_srv_shell(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_shell = mocker.patch.object(ServiceMng, "shell_svc")
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_dir = temp_home / "shpd"
    shpd_dir.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_dir / ".shpd.json"
    shpd_json.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["svc", "shell", "service_tag"])
    assert result.exit_code == 0
    mock_shell.assert_called_once()


# database service tests


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_db_sql_shell(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_sql_shell = mocker.patch.object(DatabaseMng, "sql_shell_svc")
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_dir = temp_home / "shpd"
    shpd_dir.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_dir / ".shpd.json"
    shpd_json.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["db", "sql-shell", "db-tag"])
    assert result.exit_code == 0
    mock_sql_shell.assert_called_once()


# environment tests


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_env_init(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_init = mocker.patch.object(EnvironmentMng, "init_env")
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    result = runner.invoke(cli, ["env", "init", "docker-compose", "env_tag"])
    assert result.exit_code == 0
    mock_init.assert_called_once_with("docker-compose", "env_tag")


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_env_clone(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_clone = mocker.patch.object(EnvironmentMng, "clone_env")
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    result = runner.invoke(cli, ["env", "clone", "src_env_tag", "dst_env_tag"])
    assert result.exit_code == 0
    mock_clone.assert_called_once_with("src_env_tag", "dst_env_tag")


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_env_checkout(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_checkout = mocker.patch.object(EnvironmentMng, "checkout_env")
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    result = runner.invoke(cli, ["env", "checkout", "env_tag"])
    assert result.exit_code == 0
    mock_checkout.assert_called_once_with("env_tag")


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_env_list(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_list = mocker.patch.object(EnvironmentMng, "list_envs")
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    result = runner.invoke(cli, ["env", "list"])
    assert result.exit_code == 0
    mock_list.assert_called_once()


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_env_up(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_start = mocker.patch.object(EnvironmentMng, "start_env")
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_dir = temp_home / "shpd"
    shpd_dir.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_dir / ".shpd.json"
    shpd_json.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["env", "up"])
    assert result.exit_code == 0
    mock_start.assert_called_once()


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_env_halt(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_halt = mocker.patch.object(EnvironmentMng, "halt_env")
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_dir = temp_home / "shpd"
    shpd_dir.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_dir / ".shpd.json"
    shpd_json.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["env", "halt"])
    assert result.exit_code == 0
    mock_halt.assert_called_once()


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_env_reload(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_reload = mocker.patch.object(EnvironmentMng, "reload_env")
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_dir = temp_home / "shpd"
    shpd_dir.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_dir / ".shpd.json"
    shpd_json.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["env", "reload"])
    assert result.exit_code == 0
    mock_reload.assert_called_once()


@pytest.mark.shpd
@pytest.mark.parametrize("expanduser_side_effects", [1])
def test_cli_env_status(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
    expanduser_side_effects: int,
):
    mock_status = mocker.patch.object(EnvironmentMng, "status_env")
    side_effect = make_expanduser_side_effect(
        temp_home, expanduser_side_effects
    )
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_dir = temp_home / "shpd"
    shpd_dir.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_dir / ".shpd.json"
    shpd_json.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["env", "status"])
    assert result.exit_code == 0
    mock_status.assert_called_once()
