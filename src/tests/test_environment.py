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

from shepctl import ShepherdMng, cli


@pytest.fixture
def shpd_conf(tmp_path: Path, mocker: MockerFixture) -> tuple[Path, Path]:
    """Fixture to create a temporary home directory and .shpd.conf file."""
    temp_home = tmp_path / "home"
    temp_home.mkdir()

    config_file = temp_home / ".shpd.conf"
    values = read_fixture("env", "values.conf")
    config_file.write_text(values.replace("${test_path}", str(temp_home)))

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
    result = runner.invoke(cli, ["add", "env", "default", "test-init-1"])
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
    result = runner.invoke(cli, ["add", "env", "default", "test-clone-1"])
    assert result.exit_code == 0

    result = runner.invoke(
        cli, ["clone", "env", "test-clone-1", "test-clone-2"]
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
    result = runner.invoke(cli, ["add", "env", "default", "test-rename-1"])
    assert result.exit_code == 0

    result = runner.invoke(
        cli, ["rename", "env", "test-rename-1", "test-rename-2"]
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
    result = runner.invoke(cli, ["add", "env", "default", "test-1"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["add", "env", "default", "test-2"])
    assert result.exit_code == 0

    sm = ShepherdMng()
    env = sm.configMng.get_active_environment()
    assert env is None

    result = runner.invoke(cli, ["checkout", "test-1"])
    assert result.exit_code == 0

    sm = ShepherdMng()
    env = sm.configMng.get_active_environment()
    assert env is not None
    assert env.tag == "test-1"

    result = runner.invoke(cli, ["checkout", "test-2"])
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
    result = runner.invoke(cli, ["add", "env", "default", "test-1"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0


@pytest.mark.env
def test_delete_env_yes(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    mocker.patch("builtins.input", return_value="y")

    result = runner.invoke(cli, ["add", "env", "default", "test-1"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["delete", "env", "test-1"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["add", "env", "default", "test-1"])
    assert result.exit_code == 0

    mocker.patch("builtins.input", return_value="y")

    result = runner.invoke(cli, ["delete", "env", "test-1"])
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

    result = runner.invoke(cli, ["add", "env", "default", "test-1"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["delete", "env", "test-1"])
    assert result.exit_code == 0

    sm = ShepherdMng()
    env = sm.configMng.get_environment("test-1")
    assert env is not None

    env_dir = os.path.join(sm.configMng.config.envs_path, "test-1")

    assert os.path.exists(
        env_dir
    ), f"directory {env_dir} does not exist after delete-no."


@pytest.mark.env
def test_add_nonexisting_service(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    result = runner.invoke(cli, ["add", "env", "default", "test-svc-add"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["checkout", "test-svc-add"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["add", "svc", "foo", "foo-1"])
    assert result.exit_code == 1
