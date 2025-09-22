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

from database import DatabaseMng
from environment import EnvironmentMng
from service import ServiceMng
from shepctl import ShepherdMng, cli

shpd_config_svc_default = """
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
        tag: test
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
        status:
          active: true
          archived: false
          triggered_config: null
    status:
      active: true
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


@pytest.mark.shpd
def test_shepherdmng_creates_dirs(
    shpd_conf: tuple[Path, Path], mocker: MockerFixture
):
    """Test that ShepherdMng creates the required directories."""
    sm = ShepherdMng()

    expected_dirs = [
        sm.configMng.config.envs_path,
        sm.configMng.config.volumes_path,
        sm.configMng.constants.SHPD_CERTS_DIR,
        sm.configMng.constants.SHPD_SSH_DIR,
        sm.configMng.constants.SHPD_SSHD_DIR,
        sm.configMng.config.staging_area.volumes_path,
        sm.configMng.config.staging_area.images_path,
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
def test_cli_flags_no_flags(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_init = mocker.patch.object(ShepherdMng, "__init__", return_value=None)

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
def test_cli_flags_verbose(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_init = mocker.patch.object(ShepherdMng, "__init__", return_value=None)

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
def test_cli_flags_yes(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_init = mocker.patch.object(ShepherdMng, "__init__", return_value=None)

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
def test_cli_flags_all(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_init = mocker.patch.object(ShepherdMng, "__init__", return_value=None)

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
def test_cli_flags_follow(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_init = mocker.patch.object(ShepherdMng, "__init__", return_value=None)

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
def test_cli_flags_porcelain(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_init = mocker.patch.object(ShepherdMng, "__init__", return_value=None)

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
def test_cli_flags_keep(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_init = mocker.patch.object(ShepherdMng, "__init__", return_value=None)

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
def test_cli_flags_replace(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_init = mocker.patch.object(ShepherdMng, "__init__", return_value=None)

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
def test_cli_flags_checkout(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_init = mocker.patch.object(ShepherdMng, "__init__", return_value=None)

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
def test_cli_complete(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    result = runner.invoke(cli, ["__complete", "env"])
    assert result.exit_code == 0


# service tests


@pytest.mark.shpd
def test_cli_srv_build(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_build = mocker.patch.object(ServiceMng, "build_image_svc")

    result = runner.invoke(cli, ["svc", "build", "service_template"])
    assert result.exit_code == 0
    mock_build.assert_called_once_with("service_template")


@pytest.mark.shpd
def test_cli_srv_up(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_start = mocker.patch.object(ServiceMng, "start_svc")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["svc", "up", "service_tag"])
    assert result.exit_code == 0
    mock_start.assert_called_once()


@pytest.mark.shpd
def test_cli_srv_halt(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_halt = mocker.patch.object(ServiceMng, "halt_svc")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["svc", "halt", "service_tag"])
    assert result.exit_code == 0
    mock_halt.assert_called_once()


@pytest.mark.shpd
def test_cli_srv_reload(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_reload = mocker.patch.object(ServiceMng, "reload_svc")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["svc", "reload", "service_tag"])
    assert result.exit_code == 0
    mock_reload.assert_called_once()


@pytest.mark.shpd
def test_cli_srv_stdout(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_stdout = mocker.patch.object(ServiceMng, "stdout_svc")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["svc", "stdout", "service_tag"])
    assert result.exit_code == 0
    mock_stdout.assert_called_once()


@pytest.mark.shpd
def test_cli_srv_shell(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_shell = mocker.patch.object(ServiceMng, "shell_svc")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["svc", "shell", "service_tag"])
    assert result.exit_code == 0
    mock_shell.assert_called_once()


# database service tests


@pytest.mark.shpd
def test_cli_db_sql_shell(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_sql_shell = mocker.patch.object(DatabaseMng, "sql_shell_svc")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["db", "sql-shell", "db-tag"])
    assert result.exit_code == 0
    mock_sql_shell.assert_called_once()


# environment tests


@pytest.mark.shpd
def test_cli_env_init(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_init = mocker.patch.object(EnvironmentMng, "init_env")

    result = runner.invoke(cli, ["env", "init", "docker-compose", "env_tag"])
    assert result.exit_code == 0
    mock_init.assert_called_once_with("docker-compose", "env_tag")


@pytest.mark.shpd
def test_cli_env_clone(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_clone = mocker.patch.object(EnvironmentMng, "clone_env")

    result = runner.invoke(cli, ["env", "clone", "src_env_tag", "dst_env_tag"])
    assert result.exit_code == 0
    mock_clone.assert_called_once_with("src_env_tag", "dst_env_tag")


@pytest.mark.shpd
def test_cli_env_checkout(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_checkout = mocker.patch.object(EnvironmentMng, "checkout_env")

    result = runner.invoke(cli, ["env", "checkout", "env_tag"])
    assert result.exit_code == 0
    mock_checkout.assert_called_once_with("env_tag")


@pytest.mark.shpd
def test_cli_env_list(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_list = mocker.patch.object(EnvironmentMng, "list_envs")

    result = runner.invoke(cli, ["env", "list"])
    assert result.exit_code == 0
    mock_list.assert_called_once()


@pytest.mark.shpd
def test_cli_env_up(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_start = mocker.patch.object(EnvironmentMng, "start_env")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["env", "up"])
    assert result.exit_code == 0
    mock_start.assert_called_once()


@pytest.mark.shpd
def test_cli_env_halt(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_halt = mocker.patch.object(EnvironmentMng, "halt_env")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["env", "halt"])
    assert result.exit_code == 0
    mock_halt.assert_called_once()


@pytest.mark.shpd
def test_cli_env_reload(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_reload = mocker.patch.object(EnvironmentMng, "reload_env")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["env", "reload"])
    assert result.exit_code == 0
    mock_reload.assert_called_once()


@pytest.mark.shpd
def test_cli_env_status(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_status = mocker.patch.object(EnvironmentMng, "status_env")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config_svc_default)

    result = runner.invoke(cli, ["env", "status"])
    assert result.exit_code == 0
    mock_status.assert_called_once()
