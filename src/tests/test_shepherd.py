# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

from __future__ import annotations

import io
import os
import tarfile
from pathlib import Path
from types import SimpleNamespace

import click
import pytest
import yaml
from click.testing import CliRunner
from pytest_mock import MockerFixture
from test_util import read_fixture

from config import EnvironmentCfg
from environment import EnvironmentMng
from plugin import PluginCommandSpec
from plugin.runtime import RegisteredPluginCommand
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
        },
        load_runtime_plugins=True,
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
    mock_init.assert_called_once_with(flags, load_runtime_plugins=True)

    result = runner.invoke(cli, ["-v", "test"])

    assert result.exit_code == 0
    mock_init.assert_called_with(flags, load_runtime_plugins=True)


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
    mock_init.assert_called_once_with(flags, load_runtime_plugins=True)

    result = runner.invoke(cli, ["-y", "test"])

    assert result.exit_code == 0
    mock_init.assert_called_with(flags, load_runtime_plugins=True)


@pytest.mark.shpd
def test_cli_plugin_scope_uses_safe_bootstrap(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    def fake_init(
        self: ShepherdMng,
        cli_flags: dict[str, object],
        *,
        load_runtime_plugins: bool,
    ) -> None:
        self.pluginMng = mocker.Mock()

    mock_init = mocker.patch.object(
        ShepherdMng,
        "__init__",
        autospec=True,
        side_effect=fake_init,
    )

    result = runner.invoke(cli, ["plugin", "list"])

    assert result.exit_code == 0
    mock_init.assert_called_once_with(
        mocker.ANY,
        {
            "verbose": False,
            "quiet": False,
            "details": False,
            "show_commands": False,
            "show_commands_limit": 5,
            "yes": False,
        },
        load_runtime_plugins=False,
    )


@pytest.mark.shpd
def test_cli_reuses_preloaded_runtime_for_plugin_commands(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    @click.command(name="tail")
    def tail() -> None:
        click.echo("plugin-tail")

    fake_runtime = SimpleNamespace(
        registry=SimpleNamespace(
            commands={
                "observability": {
                    "tail": RegisteredPluginCommand(
                        plugin_id="runtime-plugin",
                        spec=PluginCommandSpec(
                            scope="observability",
                            verb="tail",
                            command=tail,
                        ),
                    )
                }
            }
        )
    )

    def fake_loader(ctx: click.Context) -> SimpleNamespace:
        ctx.find_root().meta["plugin_runtime_mng"] = fake_runtime
        return fake_runtime

    mock_loader = mocker.patch(
        "shepctl._load_plugin_runtime_for_click",
        side_effect=fake_loader,
    )
    mock_init = mocker.patch.object(ShepherdMng, "__init__", return_value=None)

    result = runner.invoke(cli, ["observability", "tail"])

    assert result.exit_code == 0
    mock_loader.assert_called()
    mock_init.assert_called_once_with(
        {
            "verbose": False,
            "quiet": False,
            "details": False,
            "show_commands": False,
            "show_commands_limit": 5,
            "yes": False,
        },
        load_runtime_plugins=True,
        plugin_runtime_mng=fake_runtime,
    )


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


@pytest.mark.shpd
def test_cli_root_help(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "Usage: cli [OPTIONS] COMMAND [ARGS]..." in result.output
    assert "env" in result.output
    assert "svc" in result.output


@pytest.mark.shpd
def test_cli_root_help_bootstraps_default_config_values(
    tmp_path: Path,
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
):
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.delenv("SHPD_CONF", raising=False)
    monkeypatch.setenv("HOME", str(home_dir))

    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "Usage: cli [OPTIONS] COMMAND [ARGS]..." in result.output
    config_values = home_dir / ".shpd.conf"
    assert config_values.exists()
    assert "shpd_path=~/shpd" in config_values.read_text()
    assert (home_dir / "shpd" / ".shpd.yaml").exists()


@pytest.mark.shpd
def test_cli_env_help(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    result = runner.invoke(cli, ["env", "--help"])

    assert result.exit_code == 0
    assert "Usage: cli env [OPTIONS] COMMAND [ARGS]..." in result.output
    assert "list" in result.output
    assert "get" in result.output


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


def _write_plugin_archive(
    archive_path: Path,
    plugin_id: str = "acme-extra",
    version: str = "1.0.0",
    descriptor_content: str | None = None,
) -> None:
    with tarfile.open(archive_path, "w:gz") as archive:
        descriptor = descriptor_content or f"""id: {plugin_id}
name: Acme Extra
version: {version}
plugin_api_version: 1
entrypoint:
  module: plugin.main
  class: AcmePlugin
capabilities:
  commands: true
default_config:
  region: eu-west-1
"""
        descriptor_bytes = descriptor.encode("utf-8")
        descriptor_info = tarfile.TarInfo("acme-extra/plugin.yaml")
        descriptor_info.size = len(descriptor_bytes)
        archive.addfile(descriptor_info, fileobj=io.BytesIO(descriptor_bytes))

        module_bytes = b"class AcmePlugin:\n    pass\n"
        module_info = tarfile.TarInfo("acme-extra/plugin/main.py")
        module_info.size = len(module_bytes)
        archive.addfile(module_info, fileobj=io.BytesIO(module_bytes))


def _write_cli_config_with_plugins(config_path: Path) -> None:
    shpd_config = yaml.safe_load(read_fixture("shpd", "shpd.yaml"))
    shpd_config["plugins"] = [
        {
            "id": "acme",
            "enabled": True,
            "version": "1.2.3",
            "config": {
                "region": "eu-west-1",
                "enabled_feature": True,
            },
        }
    ]
    config_path.write_text(yaml.dump(shpd_config, sort_keys=False))


@pytest.mark.shpd
def test_cli_plugin_list(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    _write_cli_config_with_plugins(shpd_yaml)

    result = runner.invoke(cli, ["plugin", "list"])

    assert result.exit_code == 0
    assert "acme" in result.output
    assert "1.2.3" in result.output


@pytest.mark.shpd
def test_cli_plugin_get_yaml(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    _write_cli_config_with_plugins(shpd_yaml)

    result = runner.invoke(cli, ["plugin", "get", "acme"])

    assert result.exit_code == 0
    rendered = yaml.safe_load(result.output)
    assert rendered["id"] == "acme"
    assert rendered["enabled"] is True
    assert rendered["version"] == "1.2.3"


@pytest.mark.shpd
def test_cli_plugin_enable_disable(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    _write_cli_config_with_plugins(shpd_yaml)

    result = runner.invoke(cli, ["plugin", "disable", "acme"])
    assert result.exit_code == 0
    assert "Plugin 'acme' disabled." in result.output

    stored = yaml.safe_load(shpd_yaml.read_text())
    assert stored["plugins"][0]["enabled"] is False

    result = runner.invoke(cli, ["plugin", "enable", "acme"])
    assert result.exit_code == 0
    assert "Plugin 'acme' enabled." in result.output

    stored = yaml.safe_load(shpd_yaml.read_text())
    assert stored["plugins"][0]["enabled"] is True


@pytest.mark.shpd
@pytest.mark.parametrize(
    "args",
    [
        ["plugin", "enable", "missing"],
        ["plugin", "disable", "missing"],
    ],
)
def test_cli_plugin_enable_disable_missing_plugin(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
    args: list[str],
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    _write_cli_config_with_plugins(shpd_yaml)

    result = runner.invoke(cli, args)

    assert result.exit_code == 1
    assert "Error: Plugin 'missing' not found." in result.output


@pytest.mark.shpd
def test_cli_plugin_install_and_remove(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    _write_cli_config_with_plugins(shpd_yaml)

    archive_path = shpd_path / "acme-extra.tar.gz"
    _write_plugin_archive(archive_path)

    result = runner.invoke(cli, ["plugin", "install", str(archive_path)])
    assert result.exit_code == 0
    assert "Plugin 'acme-extra' installed." in result.output

    plugin_dir = shpd_path / "plugins" / "acme-extra"
    assert plugin_dir.is_dir()
    assert (plugin_dir / "plugin.yaml").is_file()
    stored = yaml.safe_load(shpd_yaml.read_text())
    plugin_cfg = next(
        plugin for plugin in stored["plugins"] if plugin["id"] == "acme-extra"
    )
    assert plugin_cfg["enabled"] is True
    assert plugin_cfg["version"] == "1.0.0"
    assert plugin_cfg["config"] == {"region": "eu-west-1"}

    result = runner.invoke(cli, ["plugin", "remove", "acme-extra"])
    assert result.exit_code == 0
    assert "Plugin 'acme-extra' removed." in result.output
    assert not plugin_dir.exists()
    stored = yaml.safe_load(shpd_yaml.read_text())
    assert all(plugin["id"] != "acme-extra" for plugin in stored["plugins"])


@pytest.mark.shpd
def test_cli_plugin_install_invalid_descriptor(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    _write_cli_config_with_plugins(shpd_yaml)

    archive_path = shpd_path / "invalid-plugin.tar.gz"
    _write_plugin_archive(
        archive_path,
        descriptor_content="""id: broken
name: Broken Plugin
version: 1.0.0
plugin_api_version: 1
entrypoint:
  module: plugin.main
  class: BrokenPlugin
capabilities:
  commands: "false"
""",
    )

    result = runner.invoke(cli, ["plugin", "install", str(archive_path)])

    assert result.exit_code == 1
    assert "Error: Invalid plugin descriptor" in result.output
    assert "Plugin capability values must" in result.output
    assert "be booleans." in result.output
    assert not (shpd_path / "plugins" / "broken").exists()


@pytest.mark.shpd
def test_cli_plugin_install_rejects_reserved_core_plugin_id(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    _write_cli_config_with_plugins(shpd_yaml)

    archive_path = shpd_path / "core-plugin.tar.gz"
    _write_plugin_archive(archive_path, plugin_id="core")

    result = runner.invoke(cli, ["plugin", "install", str(archive_path)])

    assert result.exit_code == 1
    assert "Plugin id 'core' is reserved" in result.output
    assert not (shpd_path / "plugins" / "core").exists()


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
        mocker.ANY, timeout_seconds=120, watch=False, keep_output=False
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
        mocker.ANY, timeout_seconds=120, watch=True, keep_output=False
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
        "keep_output": False,
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


@pytest.mark.shpd
def test_cli_check_probe_watch(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    watch_probes = mocker.patch.object(EnvironmentMng, "watch_probes")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(read_fixture("shpd", "shpd.yaml"))

    result = runner.invoke(cli, ["probe", "check", "--watch"])
    assert result.exit_code == 0
    watch_probes.assert_called_once()
    _, probe_tag = watch_probes.call_args.args
    assert probe_tag is None


@pytest.mark.shpd
def test_cli_check_probe_watch_with_probe_tag(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    watch_probes = mocker.patch.object(EnvironmentMng, "watch_probes")
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(read_fixture("shpd", "shpd.yaml"))

    result = runner.invoke(cli, ["probe", "check", "db-ready", "--watch"])
    assert result.exit_code == 0
    watch_probes.assert_called_once()
    _, probe_tag = watch_probes.call_args.args
    assert probe_tag == "db-ready"


# =============================================================================
# REMOTE commands
# =============================================================================


def _write_cli_config_with_remotes(config_path: Path) -> None:
    """Write a shpd.yaml that already contains two registered remotes."""
    shpd_config = yaml.safe_load(read_fixture("shpd", "shpd.yaml"))
    shpd_config["remotes"] = [
        {
            "name": "ftp-prod",
            "type": "ftp",
            "host": "ftp.example.com",
            "user": "deploy",
            "root_path": "/shpd",
            "default": "true",
        },
        {
            "name": "sftp-backup",
            "type": "sftp",
            "host": "sftp.example.com",
            "user": "backup",
            "root_path": "/shpd",
            "default": "false",
        },
    ]
    config_path.write_text(yaml.dump(shpd_config, sort_keys=False))


def _setup_remote(shpd_conf: tuple[Path, Path]) -> Path:
    """Create dir + write config with remotes; return shpd_yaml path."""
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    _write_cli_config_with_remotes(shpd_yaml)
    return shpd_yaml


# ------------------------------------------------------------------
# remote add
# ------------------------------------------------------------------


@pytest.mark.shpd
def test_cli_remote_add_ftp(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
) -> None:
    """'remote add' with FTP transport registers the remote and persists it."""
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(read_fixture("shpd", "shpd.yaml"))

    result = runner.invoke(
        cli,
        [
            "remote",
            "add",
            "my-ftp",
            "--ftp",
            "--host",
            "ftp.example.com",
            "--user",
            "deploy",
            "--password",
            "secret",
            "--root-path",
            "/shpd",
        ],
    )

    assert result.exit_code == 0
    assert "Remote 'my-ftp' registered." in result.output
    stored = yaml.safe_load(shpd_yaml.read_text())
    remotes = stored.get("remotes", [])
    assert any(r["name"] == "my-ftp" and r["type"] == "ftp" for r in remotes)


@pytest.mark.shpd
def test_cli_remote_add_sftp(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
) -> None:
    """'remote add' with SFTP transport registers the remote."""
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(read_fixture("shpd", "shpd.yaml"))

    result = runner.invoke(
        cli,
        [
            "remote",
            "add",
            "my-sftp",
            "--sftp",
            "--host",
            "sftp.example.com",
            "--user",
            "backup",
            "--identity-file",
            "/home/backup/.ssh/id_ed25519",
            "--root-path",
            "/shpd",
        ],
    )

    assert result.exit_code == 0
    assert "Remote 'my-sftp' registered." in result.output
    stored = yaml.safe_load(shpd_yaml.read_text())
    remotes = stored.get("remotes", [])
    assert any(r["name"] == "my-sftp" and r["type"] == "sftp" for r in remotes)


@pytest.mark.shpd
def test_cli_remote_add_set_default(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
) -> None:
    """'remote add --set-default' marks the remote as the default."""
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(read_fixture("shpd", "shpd.yaml"))

    runner.invoke(
        cli,
        [
            "remote",
            "add",
            "my-ftp",
            "--ftp",
            "--host",
            "ftp.example.com",
            "--user",
            "u",
            "--password",
            "p",
            "--root-path",
            "/shpd",
            "--set-default",
        ],
    )

    stored = yaml.safe_load(shpd_yaml.read_text())
    remote = next(r for r in stored["remotes"] if r["name"] == "my-ftp")
    assert remote["default"] is True


@pytest.mark.shpd
def test_cli_remote_add_missing_transport(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
) -> None:
    """'remote add' without --ftp/--sftp fails with a usage error."""
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(read_fixture("shpd", "shpd.yaml"))

    result = runner.invoke(
        cli,
        [
            "remote",
            "add",
            "my-remote",
            "--host",
            "h",
            "--user",
            "u",
            "--root-path",
            "/",
        ],
    )

    assert result.exit_code != 0
    assert "Specify a transport" in result.output


@pytest.mark.shpd
def test_cli_remote_add_duplicate_name(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
) -> None:
    """'remote add' with a name that already exists fails cleanly."""
    shpd_yaml = _setup_remote(shpd_conf)

    result = runner.invoke(
        cli,
        [
            "remote",
            "add",
            "ftp-prod",
            "--ftp",
            "--host",
            "h",
            "--user",
            "u",
            "--password",
            "p",
            "--root-path",
            "/",
        ],
    )

    assert result.exit_code != 0
    assert "already exists" in result.output


# ------------------------------------------------------------------
# remote list
# ------------------------------------------------------------------


@pytest.mark.shpd
def test_cli_remote_list_empty(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
) -> None:
    """'remote list' with no remotes configured prints a helpful message."""
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(read_fixture("shpd", "shpd.yaml"))

    result = runner.invoke(cli, ["remote", "list"])

    assert result.exit_code == 0
    assert "No remotes configured" in result.output


@pytest.mark.shpd
def test_cli_remote_list(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
) -> None:
    """'remote list' shows all registered remotes."""
    _setup_remote(shpd_conf)

    result = runner.invoke(cli, ["remote", "list"])

    assert result.exit_code == 0
    assert "ftp-prod" in result.output
    assert "sftp-backup" in result.output


# ------------------------------------------------------------------
# remote delete
# ------------------------------------------------------------------


@pytest.mark.shpd
def test_cli_remote_delete(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
) -> None:
    """'remote delete' removes the remote from the config."""
    shpd_yaml = _setup_remote(shpd_conf)

    result = runner.invoke(cli, ["remote", "delete", "sftp-backup"])

    assert result.exit_code == 0
    assert "Remote 'sftp-backup' removed." in result.output
    stored = yaml.safe_load(shpd_yaml.read_text())
    remotes = stored.get("remotes", [])
    assert all(r["name"] != "sftp-backup" for r in remotes)


@pytest.mark.shpd
def test_cli_remote_delete_missing(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
) -> None:
    """'remote delete' on an unknown name fails with a usage error."""
    _setup_remote(shpd_conf)

    result = runner.invoke(cli, ["remote", "delete", "does-not-exist"])

    assert result.exit_code != 0
    assert "not configured" in result.output


# ------------------------------------------------------------------
# remote envs
# ------------------------------------------------------------------


@pytest.mark.shpd
def test_cli_remote_envs(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
) -> None:
    """'remote envs' delegates to remoteMng.display_envs with no remote name."""
    from remote import RemoteMng

    _setup_remote(shpd_conf)
    mock_display = mocker.patch.object(RemoteMng, "display_envs")

    result = runner.invoke(cli, ["remote", "envs"])

    assert result.exit_code == 0
    mock_display.assert_called_once_with(None)


@pytest.mark.shpd
def test_cli_remote_envs_with_remote(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
) -> None:
    """'remote envs --remote=<name>' passes the name to display_envs."""
    from remote import RemoteMng

    _setup_remote(shpd_conf)
    mock_display = mocker.patch.object(RemoteMng, "display_envs")

    result = runner.invoke(cli, ["remote", "envs", "--remote", "ftp-prod"])

    assert result.exit_code == 0
    mock_display.assert_called_once_with("ftp-prod")


# ------------------------------------------------------------------
# remote get
# ------------------------------------------------------------------


@pytest.mark.shpd
def test_cli_remote_get(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
) -> None:
    """'remote get <env>' delegates to remoteMng.display_snapshots."""
    from remote import RemoteMng

    _setup_remote(shpd_conf)
    mock_display = mocker.patch.object(RemoteMng, "display_snapshots")

    result = runner.invoke(cli, ["remote", "get", "my-env"])

    assert result.exit_code == 0
    mock_display.assert_called_once_with("my-env", None)


@pytest.mark.shpd
def test_cli_remote_get_with_remote(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
) -> None:
    """'remote get <env> --remote=<name>' passes both args to display_snapshots."""
    from remote import RemoteMng

    _setup_remote(shpd_conf)
    mock_display = mocker.patch.object(RemoteMng, "display_snapshots")

    result = runner.invoke(
        cli, ["remote", "get", "my-env", "--remote", "ftp-prod"]
    )

    assert result.exit_code == 0
    mock_display.assert_called_once_with("my-env", "ftp-prod")


@pytest.mark.shpd
def test_cli_remote_add_ftp_missing_password(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
) -> None:
    """'remote add --ftp' without --password fails with a usage error."""
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    (shpd_path / ".shpd.yaml").write_text(read_fixture("shpd", "shpd.yaml"))

    result = runner.invoke(
        cli,
        [
            "remote",
            "add",
            "my-ftp",
            "--ftp",
            "--host",
            "ftp.example.com",
            "--user",
            "u",
            "--root-path",
            "/shpd",
        ],
    )

    assert result.exit_code != 0
    assert "FTP remotes require --password" in result.output


@pytest.mark.shpd
def test_cli_remote_add_sftp_missing_credentials(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
) -> None:
    """'remote add --sftp' without --password or --identity-file fails."""
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    (shpd_path / ".shpd.yaml").write_text(read_fixture("shpd", "shpd.yaml"))

    result = runner.invoke(
        cli,
        [
            "remote",
            "add",
            "my-sftp",
            "--sftp",
            "--host",
            "sftp.example.com",
            "--user",
            "u",
            "--root-path",
            "/shpd",
        ],
    )

    assert result.exit_code != 0
    assert "SFTP remotes require --password or --identity-file" in result.output
