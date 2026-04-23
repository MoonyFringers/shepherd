# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner
from pytest_mock import MockerFixture
from test_util import read_fixture

from shepctl import ShepherdMng, cli


@pytest.fixture
def shpd_conf(tmp_path: Path, mocker: MockerFixture) -> tuple[Path, Path]:
    """Fixture to create a temporary home directory and .shpd.conf file."""
    temp_home = tmp_path / "home"
    temp_home.mkdir()

    config_file = temp_home / ".shpd.conf"
    values = read_fixture("env", "values.conf")
    config_file.write_text(values.replace("${test_path}", str(temp_home)))

    shpd_yaml = temp_home / ".shpd.yaml"
    shpd_yaml.write_text(read_fixture("svc", "shpd.yaml"))

    os.environ["SHPD_CONF"] = str(config_file)
    return temp_home, config_file


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.env
def test_add_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    result = runner.invoke(cli, ["env", "add", "default", "test-init-1"])
    assert result.exit_code == 0

    sm = ShepherdMng()
    assert sm.configMng.exists_environment("test-init-1")

    expected_dirs = [os.path.join(sm.configMng.config.envs_path, "test-init-1")]

    for directory in expected_dirs:
        assert os.path.isdir(
            directory
        ), f"Directory {directory} was not created."


@pytest.mark.env
def test_clone_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    result = runner.invoke(cli, ["env", "add", "default", "test-clone-1"])
    assert result.exit_code == 0

    result = runner.invoke(
        cli, ["env", "clone", "test-clone-1", "test-clone-2"]
    )
    assert result.exit_code == 0

    sm = ShepherdMng()
    assert sm.configMng.exists_environment("test-clone-1")
    assert sm.configMng.exists_environment("test-clone-2")

    expected_dirs = [
        os.path.join(sm.configMng.config.envs_path, "test-clone-1"),
        os.path.join(sm.configMng.config.envs_path, "test-clone-2"),
    ]

    for directory in expected_dirs:
        assert os.path.isdir(
            directory
        ), f"Directory {directory} was not created."


@pytest.mark.env
def test_rename_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    result = runner.invoke(cli, ["env", "add", "default", "test-rename-1"])
    assert result.exit_code == 0

    result = runner.invoke(
        cli, ["env", "rename", "test-rename-1", "test-rename-2"]
    )
    assert result.exit_code == 0

    sm = ShepherdMng()
    assert not sm.configMng.exists_environment("test-rename-1")
    assert sm.configMng.exists_environment("test-rename-2")

    renamed_dir = os.path.join(sm.configMng.config.envs_path, "test-rename-2")
    old_dir = os.path.join(sm.configMng.config.envs_path, "test-rename-1")

    assert os.path.isdir(
        renamed_dir
    ), f"Directory {renamed_dir} was not created."
    assert not os.path.exists(
        old_dir
    ), f"Old directory {old_dir} still exists after rename."


@pytest.mark.env
def test_checkout_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    result = runner.invoke(cli, ["env", "add", "default", "test-1"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["env", "add", "default", "test-2"])
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
def test_list_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    result = runner.invoke(cli, ["env", "add", "default", "test-1"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["env", "list"])
    assert result.exit_code == 0


@pytest.mark.env
def test_get_env_json(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("env", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["env", "get", "test-1", "--output", "json"])

    assert result.exit_code == 0

    sm = ShepherdMng()
    env_cfg = sm.configMng.get_environment("test-1")
    assert env_cfg is not None
    assert json.loads(result.output) == yaml.safe_load(env_cfg.get_yaml())


@pytest.mark.env
def test_delete_env_yes(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    mocker.patch("builtins.input", return_value="y")

    result = runner.invoke(cli, ["env", "add", "default", "test-1"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["env", "delete", "test-1"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["env", "add", "default", "test-1"])
    assert result.exit_code == 0

    mocker.patch("builtins.input", return_value="y")

    result = runner.invoke(cli, ["env", "delete", "test-1"])
    assert result.exit_code == 0

    sm = ShepherdMng()
    env = sm.configMng.get_environment("test-1")
    assert env is None

    env_dir = os.path.join(sm.configMng.config.envs_path, "test-1")

    assert not os.path.exists(
        env_dir
    ), f"directory {env_dir} still exists after delete."


@pytest.mark.env
def test_delete_env_no(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    mocker.patch("builtins.input", return_value="n")

    result = runner.invoke(cli, ["env", "add", "default", "test-1"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["env", "delete", "test-1"])
    assert result.exit_code == 0

    sm = ShepherdMng()
    env = sm.configMng.get_environment("test-1")
    assert env is not None

    env_dir = os.path.join(sm.configMng.config.envs_path, "test-1")

    assert os.path.exists(
        env_dir
    ), f"directory {env_dir} does not exist after delete-no."


@pytest.mark.env
def test_delete_env_permission_denied_retry_with_sudo(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    result = runner.invoke(cli, ["env", "add", "default", "test-perm-1"])
    assert result.exit_code == 0

    mocker.patch("builtins.input", side_effect=["y", "y"])
    mocker.patch(
        "environment.environment.shutil.rmtree",
        side_effect=[
            PermissionError(13, "Permission denied", "data"),
            None,
        ],
    )
    mocker.patch(
        "environment.environment.shutil.which", return_value="/usr/bin/sudo"
    )
    mock_run = mocker.patch(
        "environment.environment.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["sudo", "chown", "-R", "1000:1000", "/tmp/x"],
            returncode=0,
            stdout="",
            stderr="",
        ),
    )

    result = runner.invoke(cli, ["env", "delete", "test-perm-1"])
    assert result.exit_code == 0
    assert "test-perm-1" in result.output

    sm = ShepherdMng()
    assert sm.configMng.get_environment("test-perm-1") is None
    mock_run.assert_called_once()
    assert mock_run.call_args[0][0][:3] == ["sudo", "chown", "-R"]


@pytest.mark.env
def test_delete_env_permission_denied_retry_declined(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    result = runner.invoke(cli, ["env", "add", "default", "test-perm-2"])
    assert result.exit_code == 0

    mocker.patch("builtins.input", side_effect=["y", "n"])
    mocker.patch(
        "environment.environment.shutil.rmtree",
        side_effect=PermissionError(13, "Permission denied", "data"),
    )
    mocker.patch(
        "environment.environment.shutil.which", return_value="/usr/bin/sudo"
    )
    mock_run = mocker.patch("environment.environment.subprocess.run")

    result = runner.invoke(cli, ["env", "delete", "test-perm-2"])
    assert result.exit_code == 1
    assert "Failed to remove directory" in result.output

    sm = ShepherdMng()
    assert sm.configMng.get_environment("test-perm-2") is not None
    mock_run.assert_not_called()


@pytest.mark.env
def test_add_nonexisting_service(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    result = runner.invoke(cli, ["env", "add", "default", "test-svc-add"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["env", "checkout", "test-svc-add"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["svc", "add", "foo", "foo-1"])
    assert result.exit_code == 1
