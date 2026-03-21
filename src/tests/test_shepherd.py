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

from config import EnvironmentCfg
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
        sm.configMng.constants.SHPD_PLUGINS_DIR,
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
    mock_init.assert_called_once_with(
        {
            "verbose": False,
            "quiet": False,
            "details": False,
            "show_commands": False,
            "show_commands_limit": 5,
            "yes": False,
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
        "quiet": False,
        "details": False,
        "show_commands": False,
        "show_commands_limit": 5,
        "yes": False,
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
        "quiet": False,
        "details": False,
        "show_commands": False,
        "show_commands_limit": 5,
        "yes": True,
    }

    assert result.exit_code == 0
    mock_init.assert_called_once_with(flags)

    result = runner.invoke(cli, ["-y", "test"])

    assert result.exit_code == 0
    mock_init.assert_called_with(flags)


@pytest.mark.shpd
def test_get_env_flags_details(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    def assert_flags(
        env_mng: EnvironmentMng,
        env_tag: str,
    ) -> None:
        assert env_mng.cli_flags["details"] is True
        assert env_tag == "test-1"

    mocker.patch.object(
        EnvironmentMng, "describe_env", autospec=True, side_effect=assert_flags
    )
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["env", "get", "test-1", "--details"])
    assert result.exit_code == 0


@pytest.mark.shpd
def test_get_svc_flags_details(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    def assert_flags(
        svc_mng: ServiceMng,
        env_cfg: EnvironmentCfg,
        svc_tag: str,
    ) -> None:
        assert svc_mng.cli_flags["details"] is True
        assert env_cfg.tag == "test-1"
        assert svc_tag == "test"

    mocker.patch.object(
        ServiceMng, "describe_svc", autospec=True, side_effect=assert_flags
    )
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["svc", "get", "test", "--details"])
    assert result.exit_code == 0


@pytest.mark.shpd
def test_status_flags_show_commands(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    def assert_flags(
        env_mng: EnvironmentMng,
        env_cfg: EnvironmentCfg,
        **kwargs: object,
    ) -> None:
        assert env_mng.cli_flags["show_commands"] is True
        assert env_mng.cli_flags["show_commands_limit"] == 5

    mocker.patch.object(
        EnvironmentMng, "status_env", autospec=True, side_effect=assert_flags
    )
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["env", "status", "--show-commands"])
    assert result.exit_code == 0


@pytest.mark.shpd
def test_reload_flags_show_commands_limit(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    def assert_flags(
        env_mng: EnvironmentMng,
        env_cfg: EnvironmentCfg,
        **kwargs: object,
    ) -> None:
        assert env_mng.cli_flags["show_commands"] is False
        assert env_mng.cli_flags["show_commands_limit"] == 8

    mocker.patch.object(
        EnvironmentMng, "reload_env", autospec=True, side_effect=assert_flags
    )
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["env", "reload", "--show-commands-limit", "8"])
    assert result.exit_code == 0


@pytest.mark.shpd
def test_cli_get_env_by_gate_requires_output(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mocker.patch.object(ShepherdMng, "__init__", return_value=None)

    result = runner.invoke(cli, ["env", "get", "--by-gate"])

    assert result.exit_code != 0
    assert (
        "--target, --resolved, and --by-gate require --output" in result.output
    )


@pytest.mark.shpd
def test_cli_get_env_by_gate_requires_target_when_output_present(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mocker.patch.object(ShepherdMng, "__init__", return_value=None)

    result = runner.invoke(cli, ["env", "get", "--output", "yaml", "--by-gate"])

    assert result.exit_code != 0
    assert "--by-gate requires --target" in result.output


@pytest.mark.shpd
@pytest.mark.parametrize(
    ("args", "expected_message"),
    [
        (
            ["env", "get", "test-1", "--target"],
            "--target, --resolved, and --by-gate require --output",
        ),
        (
            ["env", "get", "test-1", "--resolved"],
            "--target, --resolved, and --by-gate require --output",
        ),
        (
            ["env", "get", "test-1", "--target", "--by-gate"],
            "--target, --resolved, and --by-gate require --output",
        ),
    ],
)
def test_cli_get_env_render_flags_require_output(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
    args: list[str],
    expected_message: str,
):
    mocker.patch.object(ShepherdMng, "__init__", return_value=None)

    result = runner.invoke(cli, args)

    assert result.exit_code != 0
    assert expected_message in result.output


@pytest.mark.shpd
def test_cli_get_env_without_output_describes_env(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    describe_env = mocker.patch.object(EnvironmentMng, "describe_env")
    render_env = mocker.patch.object(EnvironmentMng, "render_env")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["env", "get", "test-1"])

    assert result.exit_code == 0
    describe_env.assert_called_once_with("test-1")
    render_env.assert_not_called()


@pytest.mark.shpd
def test_cli_get_env_with_output_renders_env(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    describe_env = mocker.patch.object(EnvironmentMng, "describe_env")
    render_env = mocker.patch.object(
        EnvironmentMng, "render_env", return_value="env-yaml"
    )
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["env", "get", "test-1", "--output", "yaml"])

    assert result.exit_code == 0
    assert "env-yaml" in result.output
    render_env.assert_called_once_with(
        "test-1", False, False, output="yaml", grouped=False
    )
    describe_env.assert_not_called()


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

    result = runner.invoke(cli, ["svc", "build", "service_tag"])
    assert result.exit_code == 0
    mock_build.assert_called_once()


@pytest.mark.shpd
def test_cli_get_svc_without_output_describes_svc(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    describe_svc = mocker.patch.object(ServiceMng, "describe_svc")
    render_svc = mocker.patch.object(ServiceMng, "render_svc")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["svc", "get", "test"])

    assert result.exit_code == 0
    describe_svc.assert_called_once()
    render_svc.assert_not_called()


@pytest.mark.shpd
@pytest.mark.parametrize(
    "args",
    [
        ["svc", "get", "test", "--target"],
        ["svc", "get", "test", "--resolved"],
    ],
)
def test_cli_get_svc_render_flags_require_output(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
    args: list[str],
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, args)

    assert result.exit_code != 0
    assert "--target and --resolved require --output" in result.output


@pytest.mark.shpd
def test_cli_get_svc_with_output_renders_svc(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    describe_svc = mocker.patch.object(ServiceMng, "describe_svc")
    render_svc = mocker.patch.object(
        ServiceMng, "render_svc", return_value="svc-yaml"
    )
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["svc", "get", "test", "--output", "yaml"])

    assert result.exit_code == 0
    assert "svc-yaml" in result.output
    render_svc.assert_called_once_with(
        mocker.ANY, "test", False, False, output="yaml"
    )
    describe_svc.assert_not_called()


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

    result = runner.invoke(cli, ["svc", "up", "service_tag"])
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

    result = runner.invoke(cli, ["svc", "halt", "service_tag"])
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

    result = runner.invoke(cli, ["svc", "reload", "service_tag"])
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

    result = runner.invoke(cli, ["svc", "logs", "service_tag"])
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

    result = runner.invoke(cli, ["svc", "shell", "service_tag"])
    assert result.exit_code == 0
    mock_shell.assert_called_once()


# environment tests


@pytest.mark.shpd
def test_cli_add_env(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_add = mocker.patch.object(EnvironmentMng, "add_env")

    result = runner.invoke(cli, ["env", "add", "docker-compose", "env_tag"])
    assert result.exit_code == 0
    mock_add.assert_called_once_with("docker-compose", "env_tag")


@pytest.mark.shpd
def test_cli_clone_env(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_clone = mocker.patch.object(EnvironmentMng, "clone_env")

    result = runner.invoke(cli, ["env", "clone", "src_env_tag", "dst_env_tag"])
    assert result.exit_code == 0
    mock_clone.assert_called_once_with("src_env_tag", "dst_env_tag")


@pytest.mark.shpd
def test_cli_checkout_env(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_checkout = mocker.patch.object(EnvironmentMng, "checkout_env")

    result = runner.invoke(cli, ["env", "checkout", "env_tag"])
    assert result.exit_code == 0
    mock_checkout.assert_called_once_with("env_tag")


@pytest.mark.shpd
def test_cli_list_env(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_list = mocker.patch.object(EnvironmentMng, "list_envs")

    result = runner.invoke(cli, ["env", "list"])
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

    result = runner.invoke(cli, ["env", "up"])
    assert result.exit_code == 0
    mock_start.assert_called_once_with(
        mocker.ANY, timeout_seconds=60, watch=False
    )


@pytest.mark.shpd
def test_cli_start_env_watch(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_start = mocker.patch.object(EnvironmentMng, "start_env")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["env", "up", "--watch"])
    assert result.exit_code == 0
    mock_start.assert_called_once_with(
        mocker.ANY, timeout_seconds=60, watch=True
    )


@pytest.mark.shpd
def test_cli_start_env_with_timeout(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_start = mocker.patch.object(EnvironmentMng, "start_env")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["env", "up", "--timeout", "30"])
    assert result.exit_code == 0
    mock_start.assert_called_once()
    assert mock_start.call_args.kwargs == {
        "timeout_seconds": 30,
        "watch": False,
    }


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

    result = runner.invoke(cli, ["env", "halt"])
    assert result.exit_code == 0
    mock_stop.assert_called_once_with(mocker.ANY, wait=True)


@pytest.mark.shpd
def test_cli_stop_env_no_wait(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_stop = mocker.patch.object(EnvironmentMng, "stop_env")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["env", "halt", "--no-wait"])
    assert result.exit_code == 0
    mock_stop.assert_called_once_with(mocker.ANY, wait=False)


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

    result = runner.invoke(cli, ["env", "reload"])
    assert result.exit_code == 0
    mock_reload.assert_called_once_with(mocker.ANY, watch=False)


@pytest.mark.shpd
def test_cli_reload_env_watch(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_reload = mocker.patch.object(EnvironmentMng, "reload_env")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["env", "reload", "--watch"])
    assert result.exit_code == 0
    mock_reload.assert_called_once_with(mocker.ANY, watch=True)


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

    result = runner.invoke(cli, ["env", "status"])
    assert result.exit_code == 0
    mock_status.assert_called_once_with(mocker.ANY, watch=False)


@pytest.mark.shpd
def test_cli_status_env_watch(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_status = mocker.patch.object(EnvironmentMng, "status_env")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["env", "status", "--watch"])
    assert result.exit_code == 0
    mock_status.assert_called_once_with(mocker.ANY, watch=True)


@pytest.mark.shpd
def test_cli_status_watch_default(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    mock_status = mocker.patch.object(EnvironmentMng, "status_env")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("shpd", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["env", "status", "--watch"])
    assert result.exit_code == 0
    mock_status.assert_called_once_with(mocker.ANY, watch=True)


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

    result = runner.invoke(cli, ["probe", "get"])
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

    result = runner.invoke(cli, ["probe", "get", "--output", "json"])
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
        cli, ["probe", "get", "--output", "json", "--target"]
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
        cli, ["probe", "get", "--output", "json", "--resolved"]
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

    result = runner.invoke(cli, ["probe", "get", "--all"])
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

    result = runner.invoke(cli, ["probe", "get", "db-ready", "--all"])
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

    result = runner.invoke(cli, ["probe", "get", "db-ready"])
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

    result = runner.invoke(cli, ["probe", "check"])
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

    result = runner.invoke(cli, ["probe", "check", "db-ready"])
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

    result = runner.invoke(cli, ["probe", "check", "db-ready"])
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

    result = runner.invoke(cli, ["probe", "check", "--all"])
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

    result = runner.invoke(cli, ["probe", "check", "db-ready", "--all"])
    assert result.exit_code == 0
    check_probes.assert_called_once()
