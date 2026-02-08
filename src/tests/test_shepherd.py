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
from test_util import read_fixture

from environment import EnvironmentMng
from service import ServiceMng
from shepctl import ShepherdMng, cli
from util.constants import Constants


@pytest.fixture
def shpd_conf(tmp_path: Path, mocker: MockerFixture) -> tuple[Path, Path]:
    """Fixture to create a temporary home directory and .shpd.conf file."""
    temp_home = tmp_path / "home"
    temp_home.mkdir()

    config_file = temp_home / ".shpd.conf"
    values = read_fixture("shpd", "values.conf")
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
        sm.configMng.config.templates_path,
        sm.configMng.config.templates_path + "/" + Constants.ENV_TEMPLATES_DIR,
        sm.configMng.config.templates_path + "/" + Constants.SVC_TEMPLATES_DIR,
        sm.configMng.config.envs_path,
        sm.configMng.config.volumes_path,
        sm.configMng.constants.SHPD_CERTS_DIR,
        sm.configMng.constants.SHPD_SSH_DIR,
        sm.configMng.constants.SHPD_SSHD_DIR,
        sm.configMng.config.staging_area.volumes_path,
        sm.configMng.config.staging_area.images_path,
    ]

    for template in sm.configMng.get_environment_templates() or []:
        expected_dirs.append(
            sm.configMng.config.templates_path
            + "/"
            + Constants.ENV_TEMPLATES_DIR
            + "/"
            + template.tag
        )

    for template in sm.configMng.get_service_templates() or []:
        expected_dirs.append(
            sm.configMng.config.templates_path
            + "/"
            + Constants.SVC_TEMPLATES_DIR
            + "/"
            + template.tag
        )

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
    mock_init.assert_called_once_with({"verbose": False, "yes": False})


@pytest.mark.shpd
def test_cli_flags_verbose(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_init = mocker.patch.object(ShepherdMng, "__init__", return_value=None)

    result = runner.invoke(cli, ["--verbose", "test"])

    flags = {"verbose": True, "yes": False}

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

    flags = {"verbose": False, "yes": True}

    assert result.exit_code == 0
    mock_init.assert_called_once_with(flags)

    result = runner.invoke(cli, ["-y", "test"])

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
def test_cli_build_svc(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_build = mocker.patch.object(ServiceMng, "build_svc")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["build", "service_tag"])
    assert result.exit_code == 0
    mock_build.assert_called_once()


@pytest.mark.shpd
def test_cli_start_svc(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_start = mocker.patch.object(ServiceMng, "start_svc")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["up", "svc", "service_tag"])
    assert result.exit_code == 0
    mock_start.assert_called_once()


@pytest.mark.shpd
def test_cli_stop_svc(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_stop = mocker.patch.object(ServiceMng, "stop_svc")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["halt", "svc", "service_tag"])
    assert result.exit_code == 0
    mock_stop.assert_called_once()


@pytest.mark.shpd
def test_cli_reload_svc(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_reload = mocker.patch.object(ServiceMng, "reload_svc")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["reload", "svc", "service_tag"])
    assert result.exit_code == 0
    mock_reload.assert_called_once()


@pytest.mark.shpd
def test_cli_logs_svc(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_logs = mocker.patch.object(ServiceMng, "logs_svc")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["logs", "service_tag"])
    assert result.exit_code == 0
    mock_logs.assert_called_once()


@pytest.mark.shpd
def test_cli_shell_svc(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_shell = mocker.patch.object(ServiceMng, "shell_svc")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["shell", "service_tag"])
    assert result.exit_code == 0
    mock_shell.assert_called_once()


# environment tests


@pytest.mark.shpd
def test_cli_add_env(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_add = mocker.patch.object(EnvironmentMng, "add_env")

    result = runner.invoke(cli, ["add", "env", "docker-compose", "env_tag"])
    assert result.exit_code == 0
    mock_add.assert_called_once_with("docker-compose", "env_tag")


@pytest.mark.shpd
def test_cli_clone_env(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_clone = mocker.patch.object(EnvironmentMng, "clone_env")

    result = runner.invoke(cli, ["clone", "env", "src_env_tag", "dst_env_tag"])
    assert result.exit_code == 0
    mock_clone.assert_called_once_with("src_env_tag", "dst_env_tag")


@pytest.mark.shpd
def test_cli_checkout_env(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_checkout = mocker.patch.object(EnvironmentMng, "checkout_env")

    result = runner.invoke(cli, ["checkout", "env_tag"])
    assert result.exit_code == 0
    mock_checkout.assert_called_once_with("env_tag")


@pytest.mark.shpd
def test_cli_list_env(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_list = mocker.patch.object(EnvironmentMng, "list_envs")

    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    mock_list.assert_called_once()


@pytest.mark.shpd
def test_cli_start_env(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_start = mocker.patch.object(EnvironmentMng, "start_env")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["up", "env"])
    assert result.exit_code == 0
    mock_start.assert_called_once()


@pytest.mark.shpd
def test_cli_stop_env(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_stop = mocker.patch.object(EnvironmentMng, "stop_env")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["halt", "env"])
    assert result.exit_code == 0
    mock_stop.assert_called_once()


@pytest.mark.shpd
def test_cli_reload_env(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_reload = mocker.patch.object(EnvironmentMng, "reload_env")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["reload", "env"])
    assert result.exit_code == 0
    mock_reload.assert_called_once()


@pytest.mark.shpd
def test_cli_status_env(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_status = mocker.patch.object(EnvironmentMng, "status_env")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["status", "env"])
    assert result.exit_code == 0
    mock_status.assert_called_once()


# probe tests


@pytest.mark.shpd
def test_cli_get_probe_no_args(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    render_probes = mocker.patch.object(EnvironmentMng, "render_probes")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["get", "probe"])
    assert result.exit_code == 0
    render_probes.assert_called_once()


@pytest.mark.shpd
def test_cli_get_probe_flag_output(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    render_probes = mocker.patch.object(EnvironmentMng, "render_probes")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["get", "probe", "--output", "json"])
    assert result.exit_code == 0
    render_probes.assert_called_once()


@pytest.mark.shpd
def test_cli_get_probe_flag_target(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    render_probes = mocker.patch.object(EnvironmentMng, "render_probes")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(
        cli, ["get", "probe", "--output", "json", "--target"]
    )
    assert result.exit_code == 0
    render_probes.assert_called_once()


@pytest.mark.shpd
def test_cli_get_probe_flag_resolved(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    render_probes = mocker.patch.object(EnvironmentMng, "render_probes")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(
        cli, ["get", "probe", "--output", "json", "--resolved"]
    )
    assert result.exit_code == 0
    render_probes.assert_called_once()


@pytest.mark.shpd
def test_cli_get_probe_flag_all(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    render_probes = mocker.patch.object(EnvironmentMng, "render_probes")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["get", "probe", "--all"])
    assert result.exit_code == 0
    render_probes.assert_called_once()


@pytest.mark.shpd
def test_cli_get_probe_flag_all_with_probe_tag(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    render_probes = mocker.patch.object(EnvironmentMng, "render_probes")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["get", "probe", "db-ready", "--all"])
    assert result.exit_code == 0
    render_probes.assert_called_once()


@pytest.mark.shpd
def test_cli_get_probe_with_probe_tag(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    render_probes = mocker.patch.object(EnvironmentMng, "render_probes")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["get", "probe", "db-ready"])
    assert result.exit_code == 0
    render_probes.assert_called_once()


@pytest.mark.shpd
def test_cli_check_probe_no_args(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    check_probes = mocker.patch.object(
        EnvironmentMng, "check_probes", return_value=0
    )
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["check", "probe"])
    assert result.exit_code == 0
    check_probes.assert_called_once()


@pytest.mark.shpd
def test_cli_check_probe_with_probe_tag(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    check_probes = mocker.patch.object(
        EnvironmentMng, "check_probes", return_value=0
    )
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["check", "probe", "db-ready"])
    assert result.exit_code == 0
    check_probes.assert_called_once()


@pytest.mark.shpd
def test_cli_check_probe_with_probe_tag_failed(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    check_probes = mocker.patch.object(
        EnvironmentMng, "check_probes", return_value=1
    )
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["check", "probe", "db-ready"])
    assert result.exit_code == 1
    check_probes.assert_called_once()


@pytest.mark.shpd
def test_cli_check_probe_flag_all(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    check_probes = mocker.patch.object(
        EnvironmentMng, "check_probes", return_value=0
    )
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["check", "probe", "--all"])
    assert result.exit_code == 0
    check_probes.assert_called_once()


@pytest.mark.shpd
def test_cli_check_probe_flag_all_with_probe_tag(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    check_probes = mocker.patch.object(
        EnvironmentMng, "check_probes", return_value=0
    )
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["check", "probe", "db-ready", "--all"])
    assert result.exit_code == 0
    check_probes.assert_called_once()
