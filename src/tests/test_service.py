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
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from pytest_mock import MockerFixture
from rich.tree import Tree
from test_util import read_fixture

from service import ServiceMng
from service.render import build_svc_details_tree
from shepctl import ShepherdMng, cli
from util.util import Util


@pytest.fixture
def shpd_conf(tmp_path: Path, mocker: MockerFixture) -> tuple[Path, Path]:
    """Fixture to create a temporary home directory and .shpd.conf file."""
    temp_home = tmp_path / "home"
    temp_home.mkdir()

    config_file = temp_home / ".shpd.conf"
    values = read_fixture("svc", "values.conf")
    config_file.write_text(values.replace("${test_path}", str(temp_home)))

    os.environ["SHPD_CONF"] = str(config_file)
    return temp_home, config_file


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.svc
def test_add_svc_one_default(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    result = runner.invoke(cli, ["add", "env", "default", "test-svc-add"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["checkout", "test-svc-add"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["add", "svc", "default", "svc-1"])
    assert result.exit_code == 0

    sm = ShepherdMng()
    env = sm.configMng.get_active_environment()

    assert env is not None, "Active environment should not be None"
    assert env.services is not None, "Services should not be None"
    assert len(env.services) == 2, "There should be exactly two services"

    assert (
        env.services[0].tag == "service-default"
    ), "Service tag should be 'service-default'"
    assert (
        env.services[0].template == "default"
    ), "Service type should be 'default'"
    assert (
        env.services[0].factory == "docker"
    ), "Service factory should be 'docker'"
    assert env.services[0].containers
    assert (
        env.services[0].containers[0].image == ""
    ), "Service image should be ''"
    assert (
        env.services[0].containers[0].environment == []
    ), "Service environment should be empty"
    assert (
        env.services[0].containers[0].ports == []
    ), "Service ports should be empty"
    assert (
        env.services[0].properties == {}
    ), "Service properties should be empty"

    assert env.services[1].tag == "svc-1", "Service tag should be 'svc-1'"
    assert (
        env.services[1].template == "default"
    ), "Service type should be 'default'"
    assert (
        env.services[1].factory == "docker"
    ), "Service factory should be 'docker'"
    assert env.services[1].containers
    assert (
        env.services[1].containers[0].image == ""
    ), "Service image should be ''"
    assert (
        env.services[1].containers[0].environment == []
    ), "Service environment should be empty"
    assert (
        env.services[1].containers[0].ports == []
    ), "Service ports should be empty"
    assert (
        env.services[1].properties == {}
    ), "Service properties should be empty"


@pytest.mark.svc
def test_add_svc_two_default(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    result = runner.invoke(cli, ["add", "env", "default", "test-svc-add"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["checkout", "test-svc-add"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["add", "svc", "default", "svc-1"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["add", "svc", "default", "svc-2"])
    assert result.exit_code == 0

    sm = ShepherdMng()
    env = sm.configMng.get_active_environment()
    assert env is not None, "Active environment should not be None"
    assert env.services is not None, "Services should not be None"
    assert len(env.services) == 3, "There should be exactly three services"

    assert env.services[1].tag == "svc-1", "Service tag should be 'svc-1'"
    assert (
        env.services[1].template == "default"
    ), "Service type should be 'default'"
    assert (
        env.services[1].factory == "docker"
    ), "Service factory should be 'docker'"
    assert env.services[1].containers
    assert (
        env.services[1].containers[0].image == ""
    ), "Service image should be ''"
    assert (
        env.services[1].containers[0].environment == []
    ), "Service environment should be empty"
    assert (
        env.services[1].containers[0].ports == []
    ), "Service ports should be empty"
    assert (
        env.services[1].properties == {}
    ), "Service properties should be empty"

    assert env.services[2].tag == "svc-2", "Service tag should be 'svc-2'"
    assert (
        env.services[2].template == "default"
    ), "Service type should be 'default'"
    assert (
        env.services[2].factory == "docker"
    ), "Service factory should be 'docker'"
    assert env.services[2].containers
    assert (
        env.services[2].containers[0].image == ""
    ), "Service image should be ''"
    assert (
        env.services[2].containers[0].environment == []
    ), "Service environment should be empty"
    assert (
        env.services[2].containers[0].ports == []
    ), "Service ports should be empty"
    assert (
        env.services[2].properties == {}
    ), "Service properties should be empty"


@pytest.mark.svc
def test_add_svc_two_same_tag_default(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    result = runner.invoke(cli, ["add", "env", "default", "test-svc-add"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["checkout", "test-svc-add"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["add", "svc", "default", "svc-1"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["add", "svc", "default", "svc-1"])
    assert result.exit_code == 1

    sm = ShepherdMng()
    env = sm.configMng.get_active_environment()
    assert env is not None, "Active environment should not be None"
    assert env.services is not None, "Services should not be None"
    assert len(env.services) == 2, "There should be exactly one service"
    assert env.services[1].tag == "svc-1", "Service tag should be 'svc-1'"
    assert (
        env.services[1].template == "default"
    ), "Service type should be 'default'"
    assert (
        env.services[1].factory == "docker"
    ), "Service factory should be 'docker'"
    assert env.services[1].containers
    assert (
        env.services[1].containers[0].image == ""
    ), "Service image should be ''"
    assert (
        env.services[1].containers[0].environment == []
    ), "Service environment should be empty"
    assert (
        env.services[1].containers[0].ports == []
    ), "Service ports should be empty"
    assert (
        env.services[1].properties == {}
    ), "Service properties should be empty"


@pytest.mark.svc
def test_add_svc_one_with_template(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("svc", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    result = runner.invoke(cli, ["add", "env", "default", "test-svc-add"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["checkout", "test-svc-add"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["add", "svc", "postgres", "pg-1", "database"])

    # no 'postgres' factory, so this should fail
    assert result.exit_code == 1

    sm = ShepherdMng()
    env = sm.configMng.get_active_environment()
    assert env is not None, "Active environment should not be None"
    assert env.services is not None, "Services should not be None"
    assert (
        len(env.services) == 1
    ), "There should be exactly one (default) service"

    assert (
        env.services[0].tag == "service-default"
    ), "Service tag should be 'service-default'"


def test_describe_svc_renders_summary_table(mocker: MockerFixture):
    mng = ServiceMng(
        cli_flags={},
        configMng=mocker.Mock(),
        svcFactory=mocker.Mock(),
    )
    env_cfg = mocker.Mock()
    service = mocker.Mock()
    service.svcCfg = SimpleNamespace(
        tag="svc-1",
        template="default",
        service_class="database",
        factory="docker",
        containers=[object(), object()],
        status=SimpleNamespace(active=True),
    )
    mocker.patch.object(mng, "get_service", return_value=service)
    render_table = mocker.patch.object(Util, "render_table")

    mng.describe_svc(env_cfg, "svc-1")

    render_table.assert_called_once_with(
        title=None,
        columns=[
            {"header": "NAME", "style": "cyan"},
            {"header": "TEMPLATE", "style": "magenta"},
            {"header": "CONTAINERS", "style": "white", "justify": "right"},
            {"header": "ACTIVE", "style": "white"},
        ],
        rows=[["svc-1", "default", "2", "yes"]],
    )


def test_build_svc_details_tree(mocker: MockerFixture):
    service = mocker.Mock()
    service.svcCfg = SimpleNamespace(
        tag="svc-1",
        containers=[
            SimpleNamespace(tag="web", run_container_name="web-svc-1-test"),
            SimpleNamespace(
                tag="worker", run_container_name="worker-svc-1-test"
            ),
        ],
    )

    tree = build_svc_details_tree(service)

    assert isinstance(tree, Tree)
    assert tree.label == "[bold]svc-1[/bold]"
    assert len(tree.children) == 2
    assert tree.children[0].label == "[white]web-svc-1-test[/white]"
    assert tree.children[1].label == "[white]worker-svc-1-test[/white]"


def test_describe_svc_with_details_renders_tree(mocker: MockerFixture):
    mng = ServiceMng(
        cli_flags={"details": True},
        configMng=mocker.Mock(),
        svcFactory=mocker.Mock(),
    )
    env_cfg = mocker.Mock()
    service = mocker.Mock()
    service.svcCfg = SimpleNamespace(
        tag="svc-1",
        template="default",
        containers=[object()],
        status=SimpleNamespace(active=True),
    )
    mocker.patch.object(mng, "get_service", return_value=service)
    mocker.patch.object(mng, "_build_svc_details_tree", return_value="tree")
    render_table = mocker.patch.object(Util, "render_table")
    console_print = mocker.patch.object(Util.console, "print")

    mng.describe_svc(env_cfg, "svc-1")

    render_table.assert_called_once()
    console_print.assert_called_once_with("tree")
