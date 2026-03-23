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
import shutil
import tarfile
import tempfile
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner
from pytest_mock import MockerFixture
from test_util import read_fixture

from shepctl import ShepherdMng, cli


@pytest.fixture
def shpd_conf(tmp_path: Path, mocker: MockerFixture) -> tuple[Path, Path]:
    temp_home = tmp_path / "home"
    temp_home.mkdir()

    config_file = temp_home / ".shpd.conf"
    values = read_fixture("shpd", "values.conf")
    config_file.write_text(values.replace("${test_path}", str(temp_home)))

    os.environ["SHPD_CONF"] = str(config_file)
    return temp_home, config_file


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _write_plugin_inventory(
    config_path: Path, plugins: list[dict[str, object]]
) -> None:
    shpd_config = yaml.safe_load(read_fixture("shpd", "shpd.yaml"))
    shpd_config["plugins"] = plugins
    config_path.write_text(yaml.dump(shpd_config, sort_keys=False))


def _make_plugin_archive(
    plugin_id: str = "runtime-plugin",
    version: str = "1.0.0",
) -> str:
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "plugins"
        / "runtime_plugin"
    )
    tmp_dir = tempfile.mkdtemp()
    plugin_copy = os.path.join(tmp_dir, plugin_id)
    shutil.copytree(fixture_root, plugin_copy)

    descriptor_path = os.path.join(plugin_copy, "plugin.yaml")
    descriptor = yaml.safe_load(Path(descriptor_path).read_text())
    descriptor["id"] = plugin_id
    descriptor["version"] = version
    Path(descriptor_path).write_text(yaml.dump(descriptor, sort_keys=False))

    archive_path = os.path.join(tmp_dir, f"{plugin_id}.tar.gz")
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(plugin_copy, arcname=plugin_id)
    return archive_path


def _install_fixture_plugin(
    shpd_path: Path,
    plugin_id: str = "runtime-plugin",
    *,
    version: str = "1.0.0",
    main_content: str | None = None,
) -> Path:
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "plugins"
        / "runtime_plugin"
    )
    plugin_dir = shpd_path / "plugins" / plugin_id
    shutil.copytree(fixture_root, plugin_dir)

    descriptor_path = plugin_dir / "plugin.yaml"
    descriptor = yaml.safe_load(descriptor_path.read_text())
    descriptor["id"] = plugin_id
    descriptor["version"] = version
    descriptor_path.write_text(yaml.dump(descriptor, sort_keys=False))

    if main_content is not None:
        (plugin_dir / "fixture_plugin" / "main.py").write_text(main_content)

    return plugin_dir


@pytest.mark.shpd
def test_shepherd_loads_enabled_plugin_runtime_registry(
    shpd_conf: tuple[Path, Path], mocker: MockerFixture
):
    """
    Load the fixture plugin through a real package-absolute import.

    The fixture plugin imports `fixture_plugin.helpers` from its `main.py`.
    Without the real-module import strategy in the loader, that sibling import
    would fail during startup because only a synthetic module name would exist.
    """
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    _install_fixture_plugin(shpd_path)
    _write_plugin_inventory(
        shpd_yaml,
        [
            {
                "id": "runtime-plugin",
                "enabled": True,
                "version": "1.0.0",
                "config": {"region": "eu-west-1"},
            }
        ],
    )

    shepherd = ShepherdMng()

    assert shepherd.pluginRuntimeMng is not None
    registry = shepherd.pluginRuntimeMng.registry
    assert "runtime-plugin" in registry.plugins
    assert registry.commands["observability"]["tail"].plugin_id == (
        "runtime-plugin"
    )
    assert registry.commands["env"]["doctor"].plugin_id == "runtime-plugin"
    assert "runtime-plugin/baseline" in registry.env_templates
    assert "runtime-plugin/api" in registry.service_templates
    assert "runtime-plugin/baseline-factory" in registry.env_factories
    assert "runtime-plugin/api-factory" in registry.service_factories
    assert callable(registry.completion_providers["observability"][0].provider)
    env_template = shepherd.configMng.get_environment_template(
        "runtime-plugin/baseline"
    )
    assert env_template is not None
    assert env_template.factory == "runtime-plugin/baseline-factory"
    svc_template = shepherd.configMng.get_service_template("runtime-plugin/api")
    assert svc_template is not None
    assert svc_template.factory == "runtime-plugin/api-factory"
    svc_template_path = shepherd.configMng.get_service_template_path(
        "runtime-plugin/api"
    )
    assert svc_template_path is not None
    assert svc_template_path.endswith(
        "/plugins/runtime-plugin/templates/svcs/api"
    )


@pytest.mark.shpd
def test_shepherd_reloads_same_plugin_root_in_same_process(
    shpd_conf: tuple[Path, Path], mocker: MockerFixture
):
    """
    Reload the same plugin root cleanly in one Python process.

    Without purging the owned module root before reload, Python would keep the
    first import cached in `sys.modules` and the second Shepherd bootstrap
    would see stale plugin code.
    """
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    plugin_dir = _install_fixture_plugin(shpd_path)
    _write_plugin_inventory(
        shpd_yaml,
        [
            {
                "id": "runtime-plugin",
                "enabled": True,
                "version": "1.0.0",
                "config": {"region": "eu-west-1"},
            }
        ],
    )

    shepherd = ShepherdMng()
    assert shepherd.pluginRuntimeMng is not None

    updated_main = plugin_dir / "fixture_plugin" / "main.py"
    updated_main.write_text(
        (
            "from fixture_plugin.helpers import complete_observability\n"
            "from plugin import ShepherdPlugin\n\n"
            "class RuntimeFixturePlugin(ShepherdPlugin):\n"
            "    def get_completion_providers(self):\n"
            "        return [\n"
            "            type(\n"
            "                'CompletionSpec',\n"
            "                (),\n"
            "                {\n"
            "                    'scope': 'observability',\n"
            "                    'provider': staticmethod(\n"
            "                        lambda args: [\n"
            "                            complete_observability(args)[0]\n"
            "                            + '-reloaded'\n"
            "                        ]\n"
            "                    ),\n"
            "                },\n"
            "            )(),\n"
            "        ]\n"
        )
    )

    reloaded = ShepherdMng()
    assert reloaded.pluginRuntimeMng is not None
    providers = reloaded.pluginRuntimeMng.registry.completion_providers
    assert providers["observability"][0].provider(
        ["observability", "tail"]
    ) == ["logs-reloaded"]


@pytest.mark.shpd
def test_cli_executes_plugin_scope_and_verb(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    _install_fixture_plugin(shpd_path)
    _write_plugin_inventory(
        shpd_yaml,
        [
            {
                "id": "runtime-plugin",
                "enabled": True,
                "version": "1.0.0",
                "config": None,
            }
        ],
    )

    result = runner.invoke(cli, ["observability", "tail", "logs"])

    assert result.exit_code == 0
    assert "plugin-tail:logs" in result.output


@pytest.mark.shpd
def test_cli_executes_plugin_verb_under_core_scope(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    _install_fixture_plugin(shpd_path)
    _write_plugin_inventory(
        shpd_yaml,
        [
            {
                "id": "runtime-plugin",
                "enabled": True,
                "version": "1.0.0",
                "config": None,
            }
        ],
    )

    result = runner.invoke(cli, ["env", "doctor", "network"])

    assert result.exit_code == 0
    assert "plugin-doctor:network" in result.output


@pytest.mark.shpd
def test_cli_adds_environment_from_plugin_template(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    _install_fixture_plugin(shpd_path)
    _write_plugin_inventory(
        shpd_yaml,
        [
            {
                "id": "runtime-plugin",
                "enabled": True,
                "version": "1.0.0",
                "config": None,
            }
        ],
    )

    result = runner.invoke(
        cli, ["env", "add", "runtime-plugin/baseline", "plugin-env"]
    )

    assert result.exit_code == 0

    shepherd = ShepherdMng()
    env_cfg = shepherd.configMng.get_environment("plugin-env")
    assert env_cfg is not None
    assert env_cfg.template == "runtime-plugin/baseline"
    assert env_cfg.factory == "runtime-plugin/baseline-factory"
    assert env_cfg.services is not None
    assert env_cfg.services[0].template == "runtime-plugin/api"
    assert env_cfg.services[0].factory == "runtime-plugin/api-factory"
    assert (shpd_path / "envs" / "plugin-env").is_dir()
    assert (shpd_path / "envs" / "plugin-env" / "plugin-api").is_dir()


@pytest.mark.shpd
def test_cli_adds_service_from_plugin_template(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    _install_fixture_plugin(shpd_path)
    _write_plugin_inventory(
        shpd_yaml,
        [
            {
                "id": "runtime-plugin",
                "enabled": True,
                "version": "1.0.0",
                "config": None,
            }
        ],
    )

    result = runner.invoke(cli, ["env", "add", "default", "plugin-svc-env"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["env", "checkout", "plugin-svc-env"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["svc", "add", "runtime-plugin/api", "api-1"])
    assert result.exit_code == 0

    shepherd = ShepherdMng()
    env_cfg = shepherd.configMng.get_active_environment()
    assert env_cfg is not None
    svc_cfg = env_cfg.get_service("api-1")
    assert svc_cfg is not None
    assert svc_cfg.template == "runtime-plugin/api"
    assert svc_cfg.factory == "runtime-plugin/api-factory"
    assert svc_cfg.properties == {"source": "plugin"}


@pytest.mark.shpd
def test_startup_rejects_plugin_commands_under_reserved_plugin_scope(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    _install_fixture_plugin(
        shpd_path,
        main_content=(
            "import click\n"
            "from plugin import PluginCommandSpec, ShepherdPlugin\n\n"
            "class RuntimeFixturePlugin(ShepherdPlugin):\n"
            "    def get_commands(self):\n"
            "        @click.command(name='doctor')\n"
            "        def doctor():\n"
            "            click.echo('reserved')\n"
            "        return [\n"
            "            PluginCommandSpec(\n"
            "                scope='plugin',\n"
            "                verb='doctor',\n"
            "                command=doctor,\n"
            "            )\n"
            "        ]\n"
        ),
    )
    _write_plugin_inventory(
        shpd_yaml,
        [
            {
                "id": "runtime-plugin",
                "enabled": True,
                "version": "1.0.0",
                "config": None,
            }
        ],
    )

    result = runner.invoke(cli, ["test"])

    assert result.exit_code == 1
    assert "uses reserved" in result.output
    assert "administrative scope 'plugin'" in result.output


@pytest.mark.shpd
def test_plugin_scope_skips_runtime_loading_for_broken_plugin(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    _write_plugin_inventory(
        shpd_yaml,
        [
            {
                "id": "broken-plugin",
                "enabled": True,
                "version": "1.0.0",
                "config": None,
            }
        ],
    )

    result = runner.invoke(cli, ["plugin", "disable", "broken-plugin"])

    assert result.exit_code == 0
    assert "Plugin 'broken-plugin' disabled." in result.output
    stored = yaml.safe_load(shpd_yaml.read_text())
    assert stored["plugins"][0]["enabled"] is False


@pytest.mark.shpd
def test_normal_startup_fails_for_missing_enabled_plugin(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    _write_plugin_inventory(
        shpd_yaml,
        [
            {
                "id": "broken-plugin",
                "enabled": True,
                "version": "1.0.0",
                "config": None,
            }
        ],
    )

    result = runner.invoke(cli, ["test"])

    assert result.exit_code == 1
    assert "Enabled plugin 'broken-plugin' is missing" in result.output


@pytest.mark.shpd
def test_normal_startup_rejects_reserved_core_plugin_id(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    _install_fixture_plugin(shpd_path, plugin_id="core")
    _write_plugin_inventory(
        shpd_yaml,
        [
            {
                "id": "core",
                "enabled": True,
                "version": "1.0.0",
                "config": None,
            }
        ],
    )

    result = runner.invoke(cli, ["test"])

    assert result.exit_code == 1
    assert "Plugin id 'core' is reserved" in result.output


@pytest.mark.shpd
def test_startup_fails_for_plugin_command_collision(
    shpd_conf: tuple[Path, Path], mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    _install_fixture_plugin(shpd_path, plugin_id="runtime-plugin")
    _install_fixture_plugin(shpd_path, plugin_id="collision-plugin")
    _write_plugin_inventory(
        shpd_yaml,
        [
            {
                "id": "runtime-plugin",
                "enabled": True,
                "version": "1.0.0",
                "config": None,
            },
            {
                "id": "collision-plugin",
                "enabled": True,
                "version": "1.0.0",
                "config": None,
            },
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        ShepherdMng()

    assert excinfo.value.code == 1


@pytest.mark.shpd
def test_startup_fails_for_invalid_plugin_entrypoint(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    _install_fixture_plugin(
        shpd_path,
        main_content="class RuntimeFixturePlugin:\n    pass\n",
    )
    _write_plugin_inventory(
        shpd_yaml,
        [
            {
                "id": "runtime-plugin",
                "enabled": True,
                "version": "1.0.0",
                "config": None,
            }
        ],
    )

    result = runner.invoke(cli, ["test"])

    assert result.exit_code == 1
    assert "must implement ShepherdPlugin" in result.output


@pytest.mark.shpd
def test_plugin_install_rejects_duplicate_without_force(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    """Installing an already-installed plugin without --force is an error."""
    archive = _make_plugin_archive()
    runner.invoke(cli, ["plugin", "install", archive])

    result = runner.invoke(cli, ["plugin", "install", archive])

    assert result.exit_code == 1
    assert "already installed" in result.output
    assert "--force" in result.output


@pytest.mark.shpd
def test_plugin_install_force_replaces_existing_plugin(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    """--force replaces the plugin directory and updates the version."""
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    archive_v1 = _make_plugin_archive(version="1.0.0")
    runner.invoke(cli, ["plugin", "install", archive_v1])

    archive_v2 = _make_plugin_archive(version="2.0.0")
    result = runner.invoke(cli, ["plugin", "install", "--force", archive_v2])

    assert result.exit_code == 0
    assert "installed" in result.output
    stored = yaml.safe_load(shpd_yaml.read_text())
    plugin = next(p for p in stored["plugins"] if p["id"] == "runtime-plugin")
    assert plugin["version"] == "2.0.0"


@pytest.mark.shpd
def test_plugin_install_force_preserves_enabled_state_and_config(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    """--force keeps the existing enabled flag and user config intact."""
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    archive = _make_plugin_archive()
    runner.invoke(cli, ["plugin", "install", archive])
    runner.invoke(cli, ["plugin", "disable", "runtime-plugin"])
    stored = yaml.safe_load(shpd_yaml.read_text())
    stored["plugins"][0]["config"] = {"region": "us-east-1"}
    shpd_yaml.write_text(yaml.dump(stored, sort_keys=False))

    result = runner.invoke(cli, ["plugin", "install", "--force", archive])

    assert result.exit_code == 0
    stored = yaml.safe_load(shpd_yaml.read_text())
    plugin = next(p for p in stored["plugins"] if p["id"] == "runtime-plugin")
    assert plugin["enabled"] is False
    assert plugin["config"] == {"region": "us-east-1"}
