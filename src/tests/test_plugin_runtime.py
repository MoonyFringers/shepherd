# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

from __future__ import annotations

import os
import shutil
import tarfile
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner
from pytest_mock import MockerFixture
from test_util import read_fixture

from plugin import PluginRuntimeMng
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
    tmp_dir: str,
    plugin_id: str = "runtime-plugin",
    version: str = "1.0.0",
) -> str:
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "plugins"
        / "runtime_plugin"
    )
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
def test_attach_managers_populates_plugin_contexts(
    shpd_conf: tuple[Path, Path], mocker: MockerFixture
):
    """attach_managers() injects env/svc managers into pre-loaded contexts.

    Simulates the tab-completion pre-bootstrap path: PluginRuntimeMng is
    created without managers (environment=None, service=None), then
    attach_managers() is called with mock managers and every loaded plugin
    context must be updated.
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
                "config": None,
            }
        ],
    )

    shepherd = ShepherdMng()
    runtime_mng: PluginRuntimeMng = (
        shepherd.pluginRuntimeMng  # type: ignore[assignment]
    )

    # Pre-bootstrap: build a fresh runtime with no managers passed in.
    runtime_no_managers = PluginRuntimeMng(shepherd.configMng)
    loaded = runtime_no_managers.registry.plugins.get("runtime-plugin")
    assert loaded is not None
    assert loaded.instance.context.environment is None
    assert loaded.instance.context.service is None

    # Inject managers — simulates what ShepherdMng does after full bootstrap.
    runtime_no_managers.attach_managers(
        shepherd.environmentMng, shepherd.serviceMng
    )
    assert loaded.instance.context.environment is shepherd.environmentMng
    assert loaded.instance.context.service is shepherd.serviceMng

    _ = runtime_mng  # silence unused-variable warning


@pytest.mark.shpd
def test_plugin_install_rejects_duplicate_without_force(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
    tmp_path: Path,
):
    """Installing an already-installed plugin without --force is an error."""
    archive = _make_plugin_archive(str(tmp_path))
    runner.invoke(cli, ["plugin", "install", archive])

    result = runner.invoke(cli, ["plugin", "install", archive])

    assert result.exit_code == 1
    assert "already installed" in result.output
    assert "--force" in result.output


@pytest.mark.shpd
def test_plugin_install_force_replaces_existing_plugin(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
    tmp_path: Path,
):
    """--force replaces the plugin directory and updates the version."""
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    archive_v1 = _make_plugin_archive(str(tmp_path / "v1"), version="1.0.0")
    runner.invoke(cli, ["plugin", "install", archive_v1])

    archive_v2 = _make_plugin_archive(str(tmp_path / "v2"), version="2.0.0")
    result = runner.invoke(cli, ["plugin", "install", "--force", archive_v2])

    assert result.exit_code == 0
    assert "installed" in result.output
    stored = yaml.safe_load(shpd_yaml.read_text())
    plugin = next(p for p in stored["plugins"] if p["id"] == "runtime-plugin")
    assert plugin["version"] == "2.0.0"


@pytest.mark.shpd
def test_plugin_install_force_preserves_enabled_state_and_config(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
    tmp_path: Path,
):
    """--force keeps the existing enabled flag and user config intact."""
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    archive = _make_plugin_archive(str(tmp_path))
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


# ---------------------------------------------------------------------------
# env_template_fragments — registration tests
# ---------------------------------------------------------------------------


@pytest.mark.shpd
def test_shepherd_loads_plugin_fragments_into_registry(
    shpd_conf: tuple[Path, Path], mocker: MockerFixture
):
    """Plugin fragments are registered in the runtime registry."""
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

    assert "runtime-plugin/db-bundle" in registry.env_template_fragments
    frag = registry.env_template_fragments["runtime-plugin/db-bundle"]
    # Local "api" ref is auto-namespaced to "runtime-plugin/api"
    assert frag.service_template.template == "runtime-plugin/api"
    assert frag.service_template.tag == "db"
    assert frag.probes is not None
    assert frag.probes[0].tag == "db-ready"
    assert frag.volumes is not None
    assert frag.volumes[0].tag == "db_data"


@pytest.mark.shpd
def test_fragment_namespace_rejects_slash_in_tag(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    """A fragment tag containing '/' is rejected at load time."""
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    plugin_dir = _install_fixture_plugin(shpd_path)
    _write_plugin_inventory(
        shpd_yaml,
        [{"id": "runtime-plugin", "enabled": True, "version": "1.0.0"}],
    )

    descriptor_path = plugin_dir / "plugin.yaml"
    descriptor = yaml.safe_load(descriptor_path.read_text())
    descriptor["env_template_fragments"] = [
        {
            "tag": "bad/tag",
            "service_template": {"template": "api", "tag": "db"},
            "probes": [],
            "volumes": [],
            "networks": [],
        }
    ]
    descriptor_path.write_text(yaml.dump(descriptor, sort_keys=False))

    result = runner.invoke(cli, ["test"])

    assert result.exit_code == 1
    assert "must not contain '/'" in result.output


@pytest.mark.shpd
def test_fragment_duplicate_in_same_plugin_fails(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    """Two fragments with the same tag in one plugin descriptor fail at load."""
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    plugin_dir = _install_fixture_plugin(shpd_path)
    _write_plugin_inventory(
        shpd_yaml,
        [{"id": "runtime-plugin", "enabled": True, "version": "1.0.0"}],
    )

    descriptor_path = plugin_dir / "plugin.yaml"
    descriptor: dict[str, object] = yaml.safe_load(descriptor_path.read_text())
    frag: dict[str, object] = {
        "tag": "dup-frag",
        "service_template": {"template": "api", "tag": "db"},
        "probes": [],
        "volumes": [],
        "networks": [],
    }
    descriptor["env_template_fragments"] = [frag, frag.copy()]
    descriptor_path.write_text(yaml.dump(descriptor, sort_keys=False))

    result = runner.invoke(cli, ["test"])

    assert result.exit_code == 1
    assert "duplicate fragment" in result.output


# ---------------------------------------------------------------------------
# depends_on — plugin dependency tests
# ---------------------------------------------------------------------------


def _install_minimal_plugin(
    shpd_path: Path,
    plugin_id: str,
    *,
    version: str = "1.0.0",
    extra_descriptor: dict[str, object] | None = None,
) -> Path:
    """Install a self-contained stub plugin with a unique module root.

    Unlike :func:`_install_fixture_plugin`, each call creates a fresh Python
    package so multiple minimal plugins can be loaded in the same process
    without module-root collisions.
    """
    module_name = plugin_id.replace("-", "_") + "_impl"
    plugin_dir = shpd_path / "plugins" / plugin_id
    pkg_dir = plugin_dir / module_name
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "main.py").write_text(
        "from plugin import ShepherdPlugin\n\n\n"
        "class Plugin(ShepherdPlugin):\n    pass\n"
    )
    (plugin_dir / "templates" / "svcs").mkdir(parents=True)

    descriptor: dict[str, object] = {
        "id": plugin_id,
        "name": plugin_id,
        "version": version,
        "plugin_api_version": 1,
        "entrypoint": {
            "module": f"{module_name}.main",
            "class": "Plugin",
        },
    }
    if extra_descriptor:
        descriptor.update(extra_descriptor)
    (plugin_dir / "plugin.yaml").write_text(
        yaml.dump(descriptor, sort_keys=False)
    )
    return plugin_dir


@pytest.mark.shpd
def test_depends_on_fails_for_missing_dependency(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    """A plugin that depends on an absent plugin fails at startup."""
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    _install_minimal_plugin(
        shpd_path,
        "plugin-b",
        extra_descriptor={"depends_on": [{"id": "missing-plugin"}]},
    )
    _write_plugin_inventory(
        shpd_yaml,
        [{"id": "plugin-b", "enabled": True, "version": "1.0.0"}],
    )

    result = runner.invoke(cli, ["test"])

    assert result.exit_code == 1
    assert "missing-plugin" in result.output


@pytest.mark.shpd
def test_depends_on_version_constraint_satisfied(
    shpd_conf: tuple[Path, Path], mocker: MockerFixture
):
    """A satisfied version constraint loads both plugins successfully."""
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    _install_minimal_plugin(shpd_path, "plugin-a", version="1.2.0")
    _install_minimal_plugin(
        shpd_path,
        "plugin-b",
        extra_descriptor={
            "depends_on": [{"id": "plugin-a", "version": ">=1.0.0"}]
        },
    )
    _write_plugin_inventory(
        shpd_yaml,
        [
            {"id": "plugin-a", "enabled": True, "version": "1.2.0"},
            {"id": "plugin-b", "enabled": True, "version": "1.0.0"},
        ],
    )

    shepherd = ShepherdMng()

    assert shepherd.pluginRuntimeMng is not None
    registry = shepherd.pluginRuntimeMng.registry
    assert "plugin-a" in registry.plugins
    assert "plugin-b" in registry.plugins


@pytest.mark.shpd
def test_depends_on_version_constraint_violated(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    """An unsatisfied version constraint causes a hard failure at startup."""
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    _install_minimal_plugin(shpd_path, "plugin-a", version="1.2.0")
    _install_minimal_plugin(
        shpd_path,
        "plugin-b",
        extra_descriptor={
            "depends_on": [{"id": "plugin-a", "version": ">=2.0.0"}]
        },
    )
    _write_plugin_inventory(
        shpd_yaml,
        [
            {"id": "plugin-a", "enabled": True, "version": "1.2.0"},
            {"id": "plugin-b", "enabled": True, "version": "1.0.0"},
        ],
    )

    result = runner.invoke(cli, ["test"])

    assert result.exit_code == 1
    assert "1.2.0" in result.output


@pytest.mark.shpd
def test_depends_on_cycle_fails(
    shpd_conf: tuple[Path, Path], runner: CliRunner, mocker: MockerFixture
):
    """A dependency cycle between two plugins is detected and reported."""
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    _install_minimal_plugin(
        shpd_path,
        "plugin-a",
        extra_descriptor={"depends_on": [{"id": "plugin-b"}]},
    )
    _install_minimal_plugin(
        shpd_path,
        "plugin-b",
        extra_descriptor={"depends_on": [{"id": "plugin-a"}]},
    )
    _write_plugin_inventory(
        shpd_yaml,
        [
            {"id": "plugin-a", "enabled": True, "version": "1.0.0"},
            {"id": "plugin-b", "enabled": True, "version": "1.0.0"},
        ],
    )

    result = runner.invoke(cli, ["test"])

    assert result.exit_code == 1
    assert "Circular dependency" in result.output


@pytest.mark.shpd
def test_plugins_loaded_in_dependency_order(
    shpd_conf: tuple[Path, Path], mocker: MockerFixture
):
    """A dependent plugin loads after its dependency."""
    shpd_path = shpd_conf[0]
    shpd_yaml = shpd_path / ".shpd.yaml"
    _install_minimal_plugin(shpd_path, "plugin-a", version="1.0.0")
    _install_minimal_plugin(
        shpd_path,
        "plugin-b",
        extra_descriptor={
            "depends_on": [{"id": "plugin-a", "version": ">=1.0.0"}]
        },
    )
    # List plugin-b first to confirm topo sort overrides list order.
    _write_plugin_inventory(
        shpd_yaml,
        [
            {"id": "plugin-b", "enabled": True, "version": "1.0.0"},
            {"id": "plugin-a", "enabled": True, "version": "1.0.0"},
        ],
    )

    shepherd = ShepherdMng()

    assert shepherd.pluginRuntimeMng is not None
    registry = shepherd.pluginRuntimeMng.registry
    loaded_order = list(registry.plugins.keys())
    assert "plugin-a" in loaded_order
    assert "plugin-b" in loaded_order
    # plugin-a must appear before plugin-b in the insertion-ordered dict
    assert loaded_order.index("plugin-a") < loaded_order.index("plugin-b")
