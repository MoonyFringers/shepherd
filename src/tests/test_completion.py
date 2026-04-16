# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner
from pytest_mock import MockerFixture
from test_util import read_fixture

from shepctl import ShepherdMng


@pytest.fixture
def shpd_conf(tmp_path: Path, mocker: MockerFixture) -> tuple[Path, Path]:
    """Fixture to create a temporary home directory and .shpd.conf file."""
    temp_home = tmp_path / "home"
    temp_home.mkdir()

    config_file = temp_home / ".shpd.conf"
    values = read_fixture("completion", "values.conf")
    config_file.write_text(values.replace("${test_path}", str(temp_home)))

    os.environ["SHPD_CONF"] = str(config_file)
    return temp_home, config_file


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _write_completion_config_with_plugins(config_path: Path) -> None:
    shpd_config = yaml.safe_load(read_fixture("completion", "shpd.yaml"))
    shpd_config["plugins"] = [
        {
            "id": "acme",
            "enabled": True,
            "version": "1.2.3",
            "config": {"region": "eu-west-1"},
        },
        {
            "id": "acme-extra",
            "enabled": False,
            "version": "1.0.0",
            "config": None,
        },
    ]
    config_path.write_text(yaml.dump(shpd_config, sort_keys=False))


def _install_runtime_fixture_plugin(shpd_path: Path) -> None:
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "plugins"
        / "runtime_plugin"
    )
    plugin_dir = shpd_path / "plugins" / "runtime-plugin"
    shutil.copytree(fixture_root, plugin_dir)


@pytest.mark.compl
def test_completion_no_args(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    sm = ShepherdMng(load_runtime_plugins=False)
    completions = sm.completionMng.get_completions([])
    assert completions == sm.completionMng.SCOPES, "Expected scopes only"


@pytest.mark.compl
def test_completion_global_flags_prefix(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    sm = ShepherdMng(load_runtime_plugins=False)
    completions = sm.completionMng.get_completions(["--q"])
    assert completions == ["--quiet"], "Expected filtered global flag"


@pytest.mark.compl
@pytest.mark.parametrize("args", [["env", "-"], ["svc", "-"], ["probe", "-"]])
def test_completion_scope_prefix_does_not_suggest_root_flags(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
    args: list[str],
):
    sm = ShepherdMng(load_runtime_plugins=False)
    completions = sm.completionMng.get_completions(args)
    assert completions == [], "Expected no root flags after choosing a scope"


@pytest.mark.compl
def test_completion_add(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"

    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng(load_runtime_plugins=False)
    completions = sm.completionMng.get_completions(["env"])
    assert (
        completions == sm.completionMng.scope_verbs["env"]
    ), "Expected env verbs"


@pytest.mark.compl
def test_completion_plugin_scope(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    sm = ShepherdMng(load_runtime_plugins=False)
    completions = sm.completionMng.get_completions(["plugin"])
    assert (
        completions == sm.completionMng.scope_verbs["plugin"]
    ), "Expected plugin verbs"


@pytest.mark.compl
def test_completion_includes_plugin_scope_and_scope_extension(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    _write_completion_config_with_plugins(shpd_yaml)
    _install_runtime_fixture_plugin(shpd_path)
    shpd_config = yaml.safe_load(shpd_yaml.read_text())
    shpd_config["plugins"] = [
        {
            "id": "runtime-plugin",
            "enabled": True,
            "version": "1.0.0",
            "config": None,
        }
    ]
    shpd_yaml.write_text(yaml.dump(shpd_config, sort_keys=False))

    sm = ShepherdMng()

    assert "observability" in sm.completionMng.get_completions([])
    assert "doctor" in sm.completionMng.get_completions(["env"])


@pytest.mark.compl
def test_completion_executes_runtime_plugin_provider(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = yaml.safe_load(read_fixture("completion", "shpd.yaml"))
    shpd_config["plugins"] = [
        {
            "id": "runtime-plugin",
            "enabled": True,
            "version": "1.0.0",
            "config": None,
        }
    ]
    shpd_yaml.write_text(yaml.dump(shpd_config, sort_keys=False))
    _install_runtime_fixture_plugin(shpd_path)

    sm = ShepherdMng()

    assert sm.completionMng.get_completions(["observability", "tail"]) == [
        "logs",
        "metrics",
        "traces",
    ]
    assert sm.completionMng.get_completions(["env", "doctor"]) == [
        "containers",
        "network",
        "volumes",
    ]


@pytest.mark.compl
@pytest.mark.parametrize(
    "args",
    [
        ["plugin", "get"],
        ["plugin", "enable"],
        ["plugin", "disable"],
        ["plugin", "remove"],
    ],
)
def test_completion_plugin_id_verbs(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
    args: list[str],
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    _write_completion_config_with_plugins(shpd_yaml)

    sm = ShepherdMng(load_runtime_plugins=False)
    completions = sm.completionMng.get_completions(args)
    assert completions == [
        "acme",
        "acme-extra",
    ], "Expected plugin id completion"


@pytest.mark.compl
def test_completion_plugin_id_prefix(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    _write_completion_config_with_plugins(shpd_yaml)

    sm = ShepherdMng(load_runtime_plugins=False)
    completions = sm.completionMng.get_completions(["plugin", "get", "ac"])
    assert completions == [
        "acme",
        "acme-extra",
    ], "Expected filtered plugin id completion"


@pytest.mark.compl
def test_completion_add_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "add"])
    assert (
        completions == sm.configMng.get_environment_template_tags()
    ), "Expected add-env completion"


@pytest.mark.compl
def test_completion_add_env_includes_plugin_templates(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = yaml.safe_load(read_fixture("completion", "shpd.yaml"))
    shpd_config["plugins"] = [
        {
            "id": "runtime-plugin",
            "enabled": True,
            "version": "1.0.0",
            "config": None,
        }
    ]
    shpd_yaml.write_text(yaml.dump(shpd_config, sort_keys=False))
    _install_runtime_fixture_plugin(shpd_path)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "add"])
    assert "runtime-plugin/baseline" in completions


@pytest.mark.compl
def test_completion_add_svc_1(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "add"])
    assert completions == ["t1", "t2"], "Expected add svc -1- completion"


@pytest.mark.compl
def test_completion_add_svc_includes_plugin_templates(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = yaml.safe_load(read_fixture("completion", "shpd.yaml"))
    shpd_config["plugins"] = [
        {
            "id": "runtime-plugin",
            "enabled": True,
            "version": "1.0.0",
            "config": None,
        }
    ]
    shpd_yaml.write_text(yaml.dump(shpd_config, sort_keys=False))
    _install_runtime_fixture_plugin(shpd_path)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "add"])
    assert "runtime-plugin/api" in completions


@pytest.mark.compl
def test_completion_add_svc_2(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "add", "t1"])
    assert completions == [], "Expected add svc -2- completion"


@pytest.mark.compl
def test_completion_add_svc_3(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(
        ["svc", "add", "t1", "svc-tag"]
    )
    assert completions == ["foo-class"], "Expected add svc -3- completion"


@pytest.mark.compl
def test_completion_clone(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env"])
    assert (
        completions == sm.completionMng.SCOPE_VERBS["env"]
    ), "Expected env verbs"


@pytest.mark.compl
def test_completion_clone_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "clone"])
    assert completions == ["test-1", "test-2"], "Expected env clone completion"


@pytest.mark.compl
def test_completion_rename(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env"])
    assert (
        completions == sm.completionMng.SCOPE_VERBS["env"]
    ), "Expected env verbs"


@pytest.mark.compl
def test_completion_rename_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "rename"])
    assert completions == ["test-1", "test-2"], "Expected env rename completion"


@pytest.mark.compl
def test_completion_checkout_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "checkout"])
    assert completions == [
        "test-2",
    ], "Expected env checkout completion"


@pytest.mark.compl
def test_completion_delete(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env"])
    assert (
        completions == sm.completionMng.SCOPE_VERBS["env"]
    ), "Expected env verbs"


@pytest.mark.compl
def test_completion_delete_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "delete"])
    assert completions == [
        "test-1",
        "test-2",
    ], "Expected env delete completion"


@pytest.mark.compl
def test_completion_list(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "list"])
    assert completions == [], "Expected list completion"


@pytest.mark.compl
def test_completion_start(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env"])
    assert (
        completions == sm.completionMng.SCOPE_VERBS["env"]
    ), "Expected env verbs"


@pytest.mark.compl
def test_completion_start_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "up"])
    assert completions == [
        "--show-commands",
        "--show-commands-limit",
        "-t",
        "--timeout",
        "-w",
        "--watch",
        "--keep-output",
    ], "Expected env up flags"


@pytest.mark.compl
def test_completion_start_env_with_option_prefix(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "up", "--sh"])
    assert completions == [
        "--show-commands",
        "--show-commands-limit",
    ], "Expected filtered env up flags"


@pytest.mark.compl
def test_completion_start_svc(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "up"])
    assert completions == ["red", "white"], "Expected up svc completion"


@pytest.mark.compl
def test_completion_start_svc_cnt_1(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "up", "red"])
    assert completions == [
        "container-1",
        "container-2",
    ], "Expected up svc completion"


@pytest.mark.compl
def test_completion_stop(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env"])
    assert (
        completions == sm.completionMng.SCOPE_VERBS["env"]
    ), "Expected env verbs"


@pytest.mark.compl
def test_completion_stop_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "halt"])
    assert completions == ["--no-wait"], "Expected env halt flags"


@pytest.mark.compl
def test_completion_stop_svc(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "halt"])
    assert completions == ["red", "white"], "Expected halt svc completion"


@pytest.mark.compl
def test_completion_stop_svc_cnt_1(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "halt", "red"])
    assert completions == [
        "container-1",
        "container-2",
    ], "Expected halt svc completion"


@pytest.mark.compl
def test_completion_reload(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env"])
    assert (
        completions == sm.completionMng.SCOPE_VERBS["env"]
    ), "Expected env verbs"


@pytest.mark.compl
def test_completion_reload_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "reload"])
    assert completions == [
        "--show-commands",
        "--show-commands-limit",
        "-w",
        "--watch",
    ], "Expected env reload flags"


@pytest.mark.compl
def test_completion_reload_svc(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "reload"])
    assert completions == ["red", "white"], "Expected reload svc completion"


@pytest.mark.compl
def test_completion_reload_svc_cnt_1(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "reload", "red"])
    assert completions == [
        "container-1",
        "container-2",
    ], "Expected reload svc completion"


@pytest.mark.compl
@pytest.mark.parametrize(
    "args",
    [
        ["svc", "up", "red", "container-1"],
        ["svc", "halt", "red", "container-1"],
        ["svc", "reload", "red", "container-1"],
    ],
)
def test_completion_svc_after_final_positional_has_no_more_suggestions(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
    args: list[str],
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(args)
    assert completions == []


@pytest.mark.compl
def test_completion_get(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env"])
    assert (
        completions == sm.completionMng.SCOPE_VERBS["env"]
    ), "Expected env verbs"


@pytest.mark.compl
def test_completion_get_env_oyaml(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "get", "-oyaml"])
    assert completions == [
        "test-1",
        "test-2",
    ], "Expected get env -oyaml completion"


@pytest.mark.compl
def test_completion_get_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "get"])
    assert completions == ["test-1", "test-2"], "Expected get env completion"


@pytest.mark.compl
def test_completion_get_svc_oyaml(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "get", "-oyaml"])
    assert completions == ["red", "white"], "Expected get svc -oyaml completion"


@pytest.mark.compl
def test_completion_build_svc(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "build"])
    assert completions == ["red", "white"], "Expected build svc completion"


@pytest.mark.compl
def test_completion_build_svc_cnt_1(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "build", "red"])
    assert completions == [
        "container-1",
        "container-2",
    ], "Expected build svc completion"


@pytest.mark.compl
def test_completion_logs_svc(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "logs"])
    assert completions == ["red", "white"], "Expected logs svc completion"


@pytest.mark.compl
def test_completion_logs_svc_cnt_1(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "logs", "red"])
    assert completions == [
        "container-1",
        "container-2",
    ], "Expected logs svc completion"


@pytest.mark.compl
def test_completion_shell_svc(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "shell"])
    assert completions == ["red", "white"], "Expected shell svc completion"


@pytest.mark.compl
def test_completion_shell_svc_cnt_1(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "shell", "red"])
    assert completions == [
        "container-1",
        "container-2",
    ], "Expected shell svc completion"


@pytest.mark.compl
def test_completion_status_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "status"])
    assert completions == [
        "--show-commands",
        "--show-commands-limit",
        "-w",
        "--watch",
    ], "Expected status env flags"


@pytest.mark.compl
def test_completion_get_env_shows_tags_only(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "get"])
    assert completions == ["test-1", "test-2"], "Expected get env tags only"


@pytest.mark.compl
def test_completion_get_env_after_output_value_keeps_env_tags(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(
        ["env", "get", "--output", "yaml"]
    )
    assert completions == [
        "test-1",
        "test-2",
    ], "Expected get env tags after output value"


@pytest.mark.compl
@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (
            ["env", "get", "test-1"],
            [
                "-o",
                "--output",
                "-t",
                "--target",
                "--by-gate",
                "-r",
                "--resolved",
                "--details",
            ],
        ),
        (
            ["svc", "get", "red"],
            [
                "-o",
                "--output",
                "-t",
                "--target",
                "-r",
                "--resolved",
                "--details",
            ],
        ),
        (
            ["probe", "get", "db-live"],
            [
                "-o",
                "--output",
                "-t",
                "--target",
                "-r",
                "--resolved",
                "-a",
                "--all",
            ],
        ),
    ],
)
def test_completion_get_resource_after_positional_shows_flags(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
    args: list[str],
    expected: list[str],
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(args)
    assert completions == expected


@pytest.mark.compl
def test_completion_get_env_output_value_choices(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "get", "--output"])
    assert completions == ["yaml", "json"], "Expected output value choices"


@pytest.mark.compl
def test_completion_get_svc_output_value_choices_with_empty_current_arg(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(
        ["svc", "get", "cache", "-o", ""]
    )
    assert completions == ["yaml", "json"], "Expected output choices after -o "


@pytest.mark.compl
def test_completion_get_svc_output_value_choices_with_prefix(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(
        ["svc", "get", "cache", "-o", "y"]
    )
    assert completions == ["yaml"], "Expected filtered output value choices"


@pytest.mark.compl
@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (
            ["env", "get", "-"],
            [
                "-o",
                "--output",
                "-t",
                "--target",
                "--by-gate",
                "-r",
                "--resolved",
                "--details",
            ],
        ),
        (
            ["svc", "get", "-"],
            [
                "-o",
                "--output",
                "-t",
                "--target",
                "-r",
                "--resolved",
                "--details",
            ],
        ),
        (
            ["probe", "get", "-"],
            [
                "-o",
                "--output",
                "-t",
                "--target",
                "-r",
                "--resolved",
                "-a",
                "--all",
            ],
        ),
    ],
)
def test_completion_get_resource_flag_prefix_only_shows_flags(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
    args: list[str],
    expected: list[str],
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(args)
    assert completions == expected


@pytest.mark.compl
def test_completion_get_probe_oyaml(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["probe", "get", "-oyaml"])
    assert completions == [
        "db-live",
        "db-ready",
    ], "Expected get probe -oyaml completion"


@pytest.mark.compl
def test_completion_get_probe(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_config = read_fixture("completion", "shpd.yaml")
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["probe", "get"])
    assert completions == [
        "db-live",
        "db-ready",
    ], "Expected get probe completion"


@pytest.mark.compl
def test_completion_plugin_install_shows_force_flag(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    sm = ShepherdMng(load_runtime_plugins=False)
    completions = sm.completionMng.get_completions(["plugin", "install", ""])
    assert "--force" in completions


@pytest.mark.compl
def test_completion_env_up_shows_keep_output_flag(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    sm = ShepherdMng(load_runtime_plugins=False)
    completions = sm.completionMng.get_completions(["env", "up", ""])
    assert "--keep-output" in completions


@pytest.mark.compl
def test_completion_probe_check_shows_watch_flag(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    sm = ShepherdMng(load_runtime_plugins=False)
    completions = sm.completionMng.get_completions(["probe", "check", ""])
    assert "-w" in completions
    assert "--watch" in completions
    assert "--show-commands-limit" in completions


# =============================================================================
# REMOTE completion
# =============================================================================


def _write_shpd_yaml(shpd_path: Path) -> None:
    """Write the completion fixture yaml (includes two remotes) to *shpd_path*."""
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(read_fixture("completion", "shpd.yaml"))


def _remote_sm(shpd_conf: tuple[Path, Path]) -> "ShepherdMng":
    """Return a ShepherdMng with the completion fixture yaml loaded."""
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    _write_shpd_yaml(shpd_path)
    return ShepherdMng(load_runtime_plugins=False)


@pytest.mark.compl
def test_completion_remote_scope_in_scopes(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
) -> None:
    """'remote' scope is included in the top-level scope list."""
    sm = ShepherdMng(load_runtime_plugins=False)
    assert "remote" in sm.completionMng.get_completions([])


@pytest.mark.compl
def test_completion_remote_verbs(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
) -> None:
    """Completing 'remote' returns the expected verb list."""
    sm = ShepherdMng(load_runtime_plugins=False)
    completions = sm.completionMng.get_completions(["remote"])
    assert completions == ["add", "list", "delete", "envs", "get"]


@pytest.mark.compl
def test_completion_remote_delete_remote_names(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
) -> None:
    """'remote delete' completes to all registered remote names."""
    sm = _remote_sm(shpd_conf)
    completions = sm.completionMng.get_completions(["remote", "delete"])
    assert completions == ["ftp-prod", "sftp-backup"]


@pytest.mark.compl
def test_completion_remote_delete_prefix_filter(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
) -> None:
    """'remote delete ftp' completes only names starting with 'ftp'."""
    sm = _remote_sm(shpd_conf)
    completions = sm.completionMng.get_completions(["remote", "delete", "ftp"])
    assert completions == ["ftp-prod"]


@pytest.mark.compl
def test_completion_remote_delete_after_valid_name(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
) -> None:
    """No completions after a full remote name has been provided."""
    sm = _remote_sm(shpd_conf)
    completions = sm.completionMng.get_completions(
        ["remote", "delete", "ftp-prod"]
    )
    assert completions == []


@pytest.mark.compl
def test_completion_remote_envs_no_extra_args(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
) -> None:
    """'remote envs' with no positional args suggests the --remote option."""
    sm = _remote_sm(shpd_conf)
    completions = sm.completionMng.get_completions(["remote", "envs"])
    assert completions == ["--remote"]


@pytest.mark.compl
def test_completion_remote_envs_remote_option_value(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
) -> None:
    """'remote envs --remote' returns all registered remote names."""
    sm = _remote_sm(shpd_conf)
    completions = sm.completionMng.get_completions(
        ["remote", "envs", "--remote"]
    )
    assert completions == ["ftp-prod", "sftp-backup"]


@pytest.mark.compl
def test_completion_remote_envs_remote_option_prefix(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
) -> None:
    """'remote envs --remote ftp-' returns only names starting with 'ftp-'."""
    sm = _remote_sm(shpd_conf)
    completions = sm.completionMng.get_completions(
        ["remote", "envs", "--remote", "ftp-"]
    )
    assert completions == ["ftp-prod"]


@pytest.mark.compl
def test_completion_remote_get_env_names(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
) -> None:
    """'remote get' completes ENV_NAME from the default remote index."""
    from config.config import RemoteCfg
    from storage.snapshot import IndexCatalogue, IndexCatalogueEntry

    sm = _remote_sm(shpd_conf)
    fake_cfg = RemoteCfg(
        name="ftp-prod", type="ftp", host="h", user="u", root_path="/"
    )
    fake_catalogue = IndexCatalogue(
        updated_at="2026-01-01T00:00:00Z",
        environments={
            "my-env": IndexCatalogueEntry(
                latest_snapshot="snap-1",
                snapshot_count=1,
                last_backup="2026-01-01T00:00:00Z",
                labels=[],
                total_size_bytes=0,
                stored_size_bytes=0,
            ),
            "other-env": IndexCatalogueEntry(
                latest_snapshot="snap-2",
                snapshot_count=1,
                last_backup="2026-01-01T00:00:00Z",
                labels=[],
                total_size_bytes=0,
                stored_size_bytes=0,
            ),
        },
    )
    mocker.patch.object(
        sm.remoteMng,
        "list_envs",
        return_value=(fake_cfg, fake_catalogue),
    )

    completions = sm.completionMng.get_completions(["remote", "get"])
    assert sorted(completions) == ["my-env", "other-env"]


@pytest.mark.compl
def test_completion_remote_get_env_names_prefix(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
) -> None:
    """'remote get my-' filters env names by the given prefix."""
    from config.config import RemoteCfg
    from storage.snapshot import IndexCatalogue, IndexCatalogueEntry

    sm = _remote_sm(shpd_conf)
    fake_cfg = RemoteCfg(
        name="ftp-prod", type="ftp", host="h", user="u", root_path="/"
    )
    fake_catalogue = IndexCatalogue(
        updated_at="2026-01-01T00:00:00Z",
        environments={
            "my-env": IndexCatalogueEntry(
                latest_snapshot="snap-1",
                snapshot_count=1,
                last_backup="2026-01-01T00:00:00Z",
                labels=[],
                total_size_bytes=0,
                stored_size_bytes=0,
            ),
            "other-env": IndexCatalogueEntry(
                latest_snapshot="snap-2",
                snapshot_count=1,
                last_backup="2026-01-01T00:00:00Z",
                labels=[],
                total_size_bytes=0,
                stored_size_bytes=0,
            ),
        },
    )
    mocker.patch.object(
        sm.remoteMng,
        "list_envs",
        return_value=(fake_cfg, fake_catalogue),
    )

    completions = sm.completionMng.get_completions(["remote", "get", "my-"])
    assert completions == ["my-env"]


@pytest.mark.compl
def test_completion_remote_get_remote_option_value(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
) -> None:
    """'remote get <env> --remote' returns all registered remote names."""
    sm = _remote_sm(shpd_conf)
    completions = sm.completionMng.get_completions(
        ["remote", "get", "my-env", "--remote"]
    )
    assert completions == ["ftp-prod", "sftp-backup"]


@pytest.mark.compl
def test_completion_remote_add_flags(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
) -> None:
    """'remote add -' suggests all add-command flags."""
    sm = ShepherdMng(load_runtime_plugins=False)
    completions = sm.completionMng.get_completions(["remote", "add", "-"])
    assert "--ftp" in completions
    assert "--sftp" in completions
    assert "--host" in completions
    assert "--user" in completions
    assert "--root-path" in completions
    assert "--set-default" in completions
