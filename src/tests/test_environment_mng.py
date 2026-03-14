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

import time
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pytest_mock import MockerFixture
from rich.console import Group
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree

from environment.environment import EnvironmentMng, ProbeRunResult
from environment.render import (
    build_env_details_tree,
    build_env_status_tree,
    build_probe_status_tree,
)
from environment.status_wait import (
    WaitForEnvStateHooks,
    render_moving_shadow_text,
    wait_for_env_state,
)
from util.util import Util


def _new_environment_mng(
    mocker: MockerFixture, cli_flags: dict[str, bool] | None = None
) -> EnvironmentMng:
    return EnvironmentMng(
        cli_flags=cli_flags or {},
        configMng=mocker.Mock(),
        envFactory=mocker.Mock(),
        svcFactory=mocker.Mock(),
    )


def test_wait_for_env_up_does_not_exit_while_starting(mocker: MockerFixture):
    mng = _new_environment_mng(mocker)
    setattr(mng, "_status_poll_seconds", 0.001)

    env = mocker.Mock()
    env.envCfg = SimpleNamespace(tag="test-env")

    status_samples: list[
        tuple[dict[str, list[list[str]]], bool, bool, bool]
    ] = [
        ({}, False, False, False),
        ({}, False, False, False),
        (
            {"svc": [["cnt", "[bold green]running[/bold green]"]]},
            True,
            True,
            True,
        ),
    ]
    status_idx = {"value": 0}

    def collect_status(
        _env: Any,
        gate_status: Any = None,
    ) -> tuple[dict[str, list[list[str]]], bool, bool, bool]:
        idx = min(status_idx["value"], len(status_samples) - 1)
        status_idx["value"] += 1
        return status_samples[idx]

    start_calls = {"count": 0}

    def start_action():
        start_calls["count"] += 1
        time.sleep(0.02)

    fake_console = mocker.Mock()
    fake_console.is_terminal = False
    env.get_services.return_value = []
    mocker.patch.object(Util, "console", fake_console)
    mocker.patch.object(mng, "_collect_env_status", side_effect=collect_status)
    mocker.patch.object(mng, "_build_env_status_tree", return_value="tree")

    mng.wait_for_env_up(env, timeout_seconds=2, start_action=start_action)

    assert start_calls["count"] == 1
    assert status_idx["value"] >= 2
    fake_console.print.assert_called_once_with("tree")


def test_wait_for_env_up_propagates_action_error(mocker: MockerFixture):
    mng = _new_environment_mng(mocker)
    setattr(mng, "_status_poll_seconds", 0.001)

    env = mocker.Mock()
    env.envCfg = SimpleNamespace(tag="test-env")
    env.get_services.return_value = []
    mocker.patch.object(
        mng, "_collect_env_status", return_value=({}, False, False, False)
    )

    fake_console = mocker.Mock()
    fake_console.is_terminal = False
    mocker.patch.object(Util, "console", fake_console)

    def start_action():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        mng.wait_for_env_up(env, timeout_seconds=2, start_action=start_action)


def test_wait_for_env_up_timeout_calls_print_error(mocker: MockerFixture):
    mng = _new_environment_mng(mocker)
    setattr(mng, "_status_poll_seconds", 0.001)

    env = mocker.Mock()
    env.envCfg = SimpleNamespace(tag="test-env")
    env.get_services.return_value = []

    fake_console = mocker.Mock()
    fake_console.is_terminal = False
    mocker.patch.object(Util, "console", fake_console)
    print_error = mocker.patch.object(
        Util, "print_error_and_die", side_effect=RuntimeError("timeout")
    )

    def start_action():
        time.sleep(0.05)

    with pytest.raises(RuntimeError, match="timeout"):
        mng.wait_for_env_up(env, timeout_seconds=0, start_action=start_action)

    print_error.assert_called_once()


def test_wait_for_env_down_timeout_calls_print_error(mocker: MockerFixture):
    mng = _new_environment_mng(mocker)
    setattr(mng, "_status_poll_seconds", 0.001)

    env = mocker.Mock()
    env.envCfg = SimpleNamespace(tag="test-env")
    env.get_services.return_value = []

    fake_console = mocker.Mock()
    fake_console.is_terminal = False
    mocker.patch.object(Util, "console", fake_console)
    print_error = mocker.patch.object(
        Util, "print_error_and_die", side_effect=RuntimeError("timeout")
    )

    def stop_action():
        time.sleep(0.05)

    with pytest.raises(RuntimeError, match="timeout"):
        mng.wait_for_env_down(env, timeout_seconds=0, stop_action=stop_action)

    print_error.assert_called_once()


def test_wait_for_env_down_hides_gates_column(mocker: MockerFixture):
    mng = _new_environment_mng(mocker)
    setattr(mng, "_status_poll_seconds", 0.001)
    env = mocker.Mock()
    env.envCfg = SimpleNamespace(tag="test-env")
    env.get_services.return_value = []

    fake_console = mocker.Mock()
    fake_console.is_terminal = False
    mocker.patch.object(Util, "console", fake_console)

    mocker.patch.object(
        mng,
        "_collect_env_status",
        return_value=(
            {
                "svc-1": [
                    [
                        "[dim]-[/dim]",
                        "cnt-1",
                        "[dim]stopped[/dim]",
                    ]
                ]
            },
            False,
            False,
            True,
        ),
    )
    build_mock = mocker.patch.object(
        mng, "_build_env_status_tree", return_value="tree"
    )

    mng.wait_for_env_down(env, timeout_seconds=1, stop_action=None)

    assert build_mock.call_count == 1
    assert build_mock.call_args.kwargs["hidden_columns"] == {"Gates"}


def test_stop_env_no_wait_skips_wait_for_down(mocker: MockerFixture):
    mng = _new_environment_mng(mocker)
    env_cfg = SimpleNamespace(tag="test-env", status=SimpleNamespace())
    env = mocker.Mock()
    env.envCfg = env_cfg
    wait_mock = mocker.patch.object(mng, "wait_for_env_down")
    mocker.patch.object(mng, "get_environment_from_cfg", return_value=env)

    mng.stop_env(cast(Any, env_cfg), wait=False)

    wait_mock.assert_not_called()
    env.stop.assert_called_once_with()
    env.sync_config.assert_called_once_with()
    assert env.envCfg.status.rendered_config is None


def test_wait_for_env_up_non_terminal_waits_for_running_state(
    mocker: MockerFixture,
):
    mng = _new_environment_mng(mocker)
    setattr(mng, "_status_poll_seconds", 0.001)
    env = mocker.Mock()
    env.envCfg = SimpleNamespace(tag="test-env")
    env.get_services.return_value = []

    status_samples: list[
        tuple[dict[str, list[list[str]]], bool, bool, bool]
    ] = [
        (
            {"svc": [["-", "cnt", "[dim]stopped[/dim]"]]},
            False,
            False,
            True,
        ),
        (
            {"svc": [["-", "cnt", "[bold green]running[/bold green]"]]},
            True,
            True,
            True,
        ),
    ]
    idx = {"value": 0}

    def collect_status(
        _env: Any,
        gate_status: Any = None,
    ) -> tuple[dict[str, list[list[str]]], bool, bool, bool]:
        i = min(idx["value"], len(status_samples) - 1)
        idx["value"] += 1
        return status_samples[i]

    fake_console = mocker.Mock()
    fake_console.is_terminal = False
    mocker.patch.object(Util, "console", fake_console)
    mocker.patch.object(mng, "_collect_env_status", side_effect=collect_status)
    mocker.patch.object(mng, "_build_env_status_tree", return_value="tree")

    mng.wait_for_env_up(env, timeout_seconds=2, start_action=None)

    assert idx["value"] >= 2
    fake_console.print.assert_called_once_with("tree")


def test_wait_for_env_down_non_terminal_waits_for_stopped_state(
    mocker: MockerFixture,
):
    mng = _new_environment_mng(mocker)
    setattr(mng, "_status_poll_seconds", 0.001)
    env = mocker.Mock()
    env.envCfg = SimpleNamespace(tag="test-env")
    env.get_services.return_value = []

    status_samples: list[
        tuple[dict[str, list[list[str]]], bool, bool, bool]
    ] = [
        (
            {"svc": [["-", "cnt", "[bold green]running[/bold green]"]]},
            False,
            True,
            True,
        ),
        (
            {"svc": [["-", "cnt", "[dim]stopped[/dim]"]]},
            False,
            False,
            True,
        ),
    ]
    idx = {"value": 0}

    def collect_status(
        _env: Any,
        gate_status: Any = None,
    ) -> tuple[dict[str, list[list[str]]], bool, bool, bool]:
        i = min(idx["value"], len(status_samples) - 1)
        idx["value"] += 1
        return status_samples[i]

    fake_console = mocker.Mock()
    fake_console.is_terminal = False
    mocker.patch.object(Util, "console", fake_console)
    mocker.patch.object(mng, "_collect_env_status", side_effect=collect_status)
    mocker.patch.object(mng, "_build_env_status_tree", return_value="tree")

    mng.wait_for_env_down(env, timeout_seconds=2, stop_action=None)

    assert idx["value"] >= 2
    fake_console.print.assert_called_once_with("tree")


def test_wait_for_env_up_quiet_still_polls_until_running(
    mocker: MockerFixture,
):
    mng = _new_environment_mng(mocker, cli_flags={"quiet": True})
    setattr(mng, "_status_poll_seconds", 0.001)
    env = mocker.Mock()
    env.envCfg = SimpleNamespace(tag="test-env")
    env.get_services.return_value = []

    status_samples: list[
        tuple[dict[str, list[list[str]]], bool, bool, bool]
    ] = [
        (
            {"svc": [["-", "cnt", "[dim]stopped[/dim]"]]},
            False,
            False,
            True,
        ),
        (
            {"svc": [["-", "cnt", "[bold green]running[/bold green]"]]},
            True,
            True,
            True,
        ),
    ]
    idx = {"value": 0}

    def collect_status(
        _env: Any,
        gate_status: Any = None,
    ) -> tuple[dict[str, list[list[str]]], bool, bool, bool]:
        i = min(idx["value"], len(status_samples) - 1)
        idx["value"] += 1
        return status_samples[i]

    fake_console = mocker.Mock()
    fake_console.is_terminal = True
    mocker.patch.object(Util, "console", fake_console)
    mocker.patch.object(mng, "_collect_env_status", side_effect=collect_status)

    mng.wait_for_env_up(env, timeout_seconds=2, start_action=None)

    assert idx["value"] >= 2
    fake_console.print.assert_not_called()


def test_wait_for_env_up_quiet_still_enforces_timeout(mocker: MockerFixture):
    mng = _new_environment_mng(mocker, cli_flags={"quiet": True})
    setattr(mng, "_status_poll_seconds", 0.001)
    env = mocker.Mock()
    env.envCfg = SimpleNamespace(tag="test-env")
    env.get_services.return_value = []

    mocker.patch.object(
        mng,
        "_collect_env_status",
        return_value=(
            {"svc": [["-", "cnt", "[dim]stopped[/dim]"]]},
            False,
            True,
            True,
        ),
    )
    fake_console = mocker.Mock()
    fake_console.is_terminal = True
    mocker.patch.object(Util, "console", fake_console)
    print_error = mocker.patch.object(
        Util, "print_error_and_die", side_effect=RuntimeError("timeout")
    )

    with pytest.raises(RuntimeError, match="timeout"):
        mng.wait_for_env_up(env, timeout_seconds=0, start_action=None)

    print_error.assert_called_once()


def test_status_env_watch_delegates_to_waiter(mocker: MockerFixture):
    mng = _new_environment_mng(mocker)
    env = mocker.Mock()
    env_cfg = SimpleNamespace(tag="test-env")
    mocker.patch.object(mng, "get_environment_from_cfg", return_value=env)
    wait_mock = mocker.patch.object(mng, "wait_for_env_up")

    mng.status_env(cast(Any, env_cfg), watch=True)

    wait_mock.assert_called_once_with(
        env,
        timeout_seconds=None,
        start_action=None,
        watch_after=True,
        progress_label="Checking",
    )


def test_status_env_renders_tree(mocker: MockerFixture):
    mng = _new_environment_mng(mocker)
    env_cfg = SimpleNamespace(tag="env-1")
    env = mocker.Mock()
    mocker.patch.object(mng, "get_environment_from_cfg", return_value=env)
    mocker.patch.object(
        mng,
        "_collect_env_status",
        return_value=(
            {
                "svc-1": [
                    [
                        "[dim]-[/dim]",
                        "cnt-1",
                        "[bold green]running[/bold green]",
                    ]
                ]
            },
            True,
            True,
            True,
        ),
    )
    fake_console = mocker.Mock()
    mocker.patch.object(Util, "console", fake_console)

    mng.status_env(cast(Any, env_cfg), watch=False)

    printed_group = cast(Group, fake_console.print.call_args.args[0])
    printed_tree = cast(Tree, printed_group.renderables[0])
    summary = cast(Text, printed_group.renderables[1])
    assert str(printed_tree.label) == "[bold white]env-1[/bold white]"
    service_node = printed_tree.children[0]
    assert str(service_node.label) == "[bold cyan]svc-1[/bold cyan]"
    assert "RUNNING: 1" in summary.plain


def test_format_service_gate_glyphs_states(mocker: MockerFixture):
    mng = _new_environment_mng(mocker)
    mng_any = cast(Any, mng)

    gated = SimpleNamespace(
        svcCfg=SimpleNamespace(start=SimpleNamespace(when_probes=["p2", "p1"]))
    )
    ungated = SimpleNamespace(svcCfg=SimpleNamespace(start=None))

    assert (
        mng_any._format_service_gate_glyphs(cast(Any, ungated))
        == "[dim]-[/dim]"
    )
    assert (
        mng_any._format_service_gate_glyphs(cast(Any, gated))
        == "[dim]·[/dim][dim]·[/dim]"
    )

    glyphs = mng_any._format_service_gate_glyphs(
        cast(Any, gated),
        gate_status={"p1": True, "p2": False},
    )
    assert "[bold red]✗[/bold red]" in glyphs
    assert "[bold green]✓[/bold green]" in glyphs


def test_format_service_gate_details_sorted_and_colored(mocker: MockerFixture):
    mng = _new_environment_mng(mocker)
    mng_any = cast(Any, mng)

    gated = SimpleNamespace(
        svcCfg=SimpleNamespace(
            start=SimpleNamespace(when_probes=["zeta", "alpha", "beta"])
        )
    )
    ungated = SimpleNamespace(svcCfg=SimpleNamespace(start=None))

    assert (
        mng_any._format_service_gate_details(cast(Any, ungated))
        == "[dim]-[/dim]"
    )

    details = mng_any._format_service_gate_details(
        cast(Any, gated),
        gate_status={"alpha": True, "beta": False, "zeta": None},
    )
    assert details.find("alpha") < details.find("beta") < details.find("zeta")
    assert "[green]alpha[/green]" in details
    assert "[red]beta[/red]" in details
    assert "[dim]zeta[/dim]" in details


def test_evaluate_gate_status_success_and_exception(mocker: MockerFixture):
    mng = _new_environment_mng(mocker)
    mng_any = cast(Any, mng)
    env = mocker.Mock()
    env.envCfg = SimpleNamespace(tag="test-env")

    env.check_probes.return_value = [
        ProbeRunResult(tag="a", exit_code=0, timed_out=False),
        ProbeRunResult(tag="b", exit_code=1, timed_out=False),
        ProbeRunResult(tag="c", exit_code=0, timed_out=True),
    ]

    status = mng_any._evaluate_gate_status(env, {"a", "b", "c", "d"})
    assert status["a"] is True
    assert status["b"] is False
    assert status["c"] is False
    assert status["d"] is None

    env.check_probes.side_effect = RuntimeError("probe error")
    status_err = mng_any._evaluate_gate_status(env, {"a", "b"})
    assert status_err == {"a": None, "b": None}


def test_build_probe_status_tree_returns_colored_probe_nodes():
    results = [
        ProbeRunResult(tag="ok-probe", exit_code=0, timed_out=False),
        ProbeRunResult(tag="failed-probe", exit_code=1, timed_out=False),
        ProbeRunResult(tag="slow-probe", exit_code=0, timed_out=True),
    ]
    renderable = build_probe_status_tree(
        results,
        title="[white]env-1[/white] probes",
    )
    assert isinstance(renderable, Group)
    tree = cast(Tree, renderable.renderables[0])
    summary = cast(Text, renderable.renderables[1])
    assert str(tree.label) == "[white]env-1[/white] probes"
    child_labels = [str(child.label) for child in tree.children]
    assert "[green]ok-probe[/green]" in child_labels
    assert "[red]failed-probe[/red]" in child_labels
    assert "[yellow]slow-probe[/yellow]" in child_labels
    assert summary.plain == "Summary:  OK: 1  FAILED: 1  TIMEOUT: 1"


def test_check_probes_renders_probe_status_tree(mocker: MockerFixture):
    mng = _new_environment_mng(mocker)
    env_cfg = SimpleNamespace(tag="env-1")
    env = mocker.Mock()
    env.envCfg = SimpleNamespace(
        tag="env-1",
        status=SimpleNamespace(rendered_config={"ungated": "cfg"}),
    )
    env.check_probes.return_value = [
        ProbeRunResult(tag="db-ready", exit_code=0, timed_out=False)
    ]
    mocker.patch.object(mng, "get_environment_from_cfg", return_value=env)
    build_tree = mocker.patch.object(
        mng, "_build_probe_status_tree", return_value="probe-tree"
    )
    fake_console = mocker.Mock()
    mocker.patch.object(Util, "console", fake_console)

    exit_code = mng.check_probes(cast(Any, env_cfg), probe_tag=None)

    assert exit_code == 0
    build_tree.assert_called_once()
    fake_console.print.assert_called_once_with("probe-tree")


def test_build_env_status_tree_with_command_log_panel(mocker: MockerFixture):
    mng = _new_environment_mng(mocker)
    mng_any = cast(Any, mng)
    grouped = {
        "svc-1": [
            [
                "[dim]-[/dim]",
                "cnt-1",
                "[bold green]running[/bold green]",
                "[dim]-[/dim]",
            ]
        ]
    }

    renderable = mng_any._build_env_status_tree(
        "env-1",
        grouped,
        command_log=["[green]ok[/green]", "[red]fail[/red]"],
        command_log_limit=4,
    )
    assert isinstance(renderable, Group)
    assert isinstance(renderable.renderables[0], Tree)
    assert isinstance(renderable.renderables[1], Text)
    assert isinstance(renderable.renderables[2], Panel)
    panel = renderable.renderables[2]
    assert panel.title == "Recent Commands"
    assert panel.border_style == "blue"
    assert panel.expand is True
    assert panel.box is not None
    assert len(str(panel.renderable).splitlines()) == 4


def test_build_env_status_tree_with_error_panel(mocker: MockerFixture):
    mng = _new_environment_mng(mocker)
    mng_any = cast(Any, mng)
    grouped = {
        "svc-1": [
            [
                "[dim]-[/dim]",
                "cnt-1",
                "[bold green]running[/bold green]",
                "[dim]-[/dim]",
            ]
        ]
    }

    renderable = mng_any._build_env_status_tree(
        "env-1",
        grouped,
        command_log=["[green]ok[/green]"],
        command_log_limit=2,
        command_error={
            "title": "Command start:db failed",
            "body": "--- stderr ---\nboom",
        },
        command_error_limit=2,
    )
    assert isinstance(renderable, Group)
    assert len(renderable.renderables) == 4
    assert isinstance(renderable.renderables[1], Text)
    error_panel = renderable.renderables[3]
    assert isinstance(error_panel, Panel)
    assert error_panel.title == "Command start:db failed"
    assert error_panel.border_style == "red"
    assert len(str(error_panel.renderable).splitlines()) == 2


def test_build_env_status_tree_returns_tree_with_service_metadata():
    grouped = {
        "svc-1": [
            [
                "[bold green]✓[/bold green]",
                "cnt-1",
                "[bold green]running[/bold green]",
                "[bold green]probe-a[/bold green]",
            ],
            ["", "cnt-2", "[dim]stopped[/dim]", ""],
        ]
    }

    renderable = build_env_status_tree(
        "env-1",
        grouped,
        details_enabled=True,
    )

    assert isinstance(renderable, Group)
    tree = cast(Tree, renderable.renderables[0])
    summary = cast(Text, renderable.renderables[1])
    assert str(tree.label) == "[bold white]env-1[/bold white]"
    service_node = tree.children[0]
    assert str(service_node.label) == "[bold cyan]svc-1[/bold cyan]"
    assert (
        Text.from_markup(str(service_node.children[0].label)).plain == "gates"
    )
    gate_labels = [
        str(child.label) for child in service_node.children[0].children
    ]
    assert "[bold green]probe-a[/bold green]" in gate_labels
    child_labels = [str(child.label) for child in service_node.children[1:]]
    assert (
        "[white]cnt-1[/white]: [bold green]running[/bold green]" in child_labels
    )
    assert "[white]cnt-2[/white]: [dim]stopped[/dim]" in child_labels
    assert "SERVICES: 1" in summary.plain
    assert "CONTAINERS: 2" in summary.plain


def test_build_env_status_tree_manager_method_returns_tree(
    mocker: MockerFixture,
):
    mng = _new_environment_mng(mocker)
    mng_any = cast(Any, mng)
    grouped = {
        "svc-1": [
            [
                "[dim]-[/dim]",
                "cnt-1",
                "[bold green]running[/bold green]",
                "[dim]probe-a[/dim]",
            ]
        ]
    }

    renderable = mng_any._build_env_status_tree("env-1", grouped)

    assert isinstance(renderable, Group)
    assert isinstance(renderable.renderables[0], Tree)


def test_build_env_status_tree_omits_gates_node_without_probes():
    grouped = {
        "svc-1": [
            [
                "[dim]-[/dim]",
                "cnt-1",
                "[bold green]running[/bold green]",
                "[dim]-[/dim]",
            ]
        ]
    }

    renderable = build_env_status_tree(
        "env-1",
        grouped,
        details_enabled=True,
    )

    assert isinstance(renderable, Group)
    tree = cast(Tree, renderable.renderables[0])
    service_node = tree.children[0]
    child_labels = [str(child.label) for child in service_node.children]
    assert "[cyan]gates[/cyan]" not in child_labels
    assert (
        "[white]cnt-1[/white]: [bold green]running[/bold green]" in child_labels
    )


def test_build_env_status_tree_applies_flash_to_changed_nodes():
    grouped = {
        "svc-1": [
            [
                "[dim]-[/dim]",
                "cnt-1",
                "[bold green]running[/bold green]",
                "[green]probe-a[/green], [dim]probe-b[/dim]",
            ]
        ]
    }

    renderable = build_env_status_tree(
        "env-1",
        grouped,
        details_enabled=True,
        flashing_containers={"svc-1/cnt-1"},
        flashing_probes={("svc-1", "probe-a")},
    )

    tree = cast(Tree, cast(Group, renderable).renderables[0])
    service_node = tree.children[0]
    gates_node = service_node.children[0]
    gate_labels = [str(child.label) for child in gates_node.children]
    child_labels = [str(child.label) for child in service_node.children[1:]]

    assert "[bold black on green]probe-a[/bold black on green]" in gate_labels
    assert (
        "[white]cnt-1[/white]: "
        "[bold black on green]running[/bold black on green]" in child_labels
    )


def test_build_env_status_tree_applies_flash_to_changed_summary_values():
    grouped = {
        "svc-1": [
            [
                "[dim]-[/dim]",
                "cnt-1",
                "[bold green]running[/bold green]",
                "[green]probe-a[/green]",
            ]
        ]
    }

    renderable = build_env_status_tree(
        "env-1",
        grouped,
        details_enabled=True,
        flashing_summary_keys={"RUNNING", "GATES OK"},
    )

    summary = cast(Text, cast(Group, renderable).renderables[1])
    assert "RUNNING: 1" in summary.plain
    assert "GATES OK: 1" in summary.plain
    assert len(summary.spans) >= 2
    assert any(
        span.style == "bold black on green"
        and summary.plain[span.start : span.end] == "1"
        for span in summary.spans
    )


def test_collect_env_status_includes_probe_details_for_tree_view(
    mocker: MockerFixture,
):
    mng = _new_environment_mng(mocker)
    mng_any = cast(Any, mng)

    container = SimpleNamespace(tag="cnt-a", run_container_name="svc-a-cnt")
    svc = SimpleNamespace(
        svcCfg=SimpleNamespace(
            tag="svc-a",
            containers=[container],
            start=SimpleNamespace(when_probes=["p1", "p2"]),
        )
    )
    env = mocker.Mock()
    env.status.return_value = [{"Service": "svc-a-cnt", "State": "running"}]
    env.get_services.return_value = [svc]

    grouped, _, _, _ = mng_any._collect_env_status(
        env,
        gate_status={"p1": True, "p2": None},
    )

    assert grouped["svc-a"][0][3] == "[green]p1[/green], [dim]p2[/dim]"


def test_collect_env_status_details_row_shape(mocker: MockerFixture):
    mng = _new_environment_mng(mocker, cli_flags={"details": True})
    mng_any = cast(Any, mng)

    container = SimpleNamespace(tag="cnt-a", run_container_name="svc-a-cnt")
    svc = SimpleNamespace(
        svcCfg=SimpleNamespace(
            tag="svc-a",
            containers=[container],
            start=SimpleNamespace(when_probes=["p1", "p2"]),
        )
    )
    env = mocker.Mock()
    env.status.return_value = [{"Service": "svc-a-cnt", "State": "running"}]
    env.get_services.return_value = [svc]

    grouped, all_running, any_running, has_containers = (
        mng_any._collect_env_status(
            env,
            gate_status={"p1": True, "p2": None},
        )
    )
    assert all_running is True
    assert any_running is True
    assert has_containers is True
    row = grouped["svc-a"][0]
    assert len(row) == 4
    assert row[1] == "cnt-a"


def test_wait_for_env_down_terminal_main_loop(mocker: MockerFixture):
    mng = _new_environment_mng(mocker)
    setattr(mng, "_status_poll_seconds", 0.001)

    env = mocker.Mock()
    env.envCfg = SimpleNamespace(tag="test-env")
    env.get_services.return_value = []

    status_samples: list[
        tuple[dict[str, list[list[str]]], bool, bool, bool]
    ] = [
        (
            {"svc": [["-", "cnt", "[bold green]running[/bold green]"]]},
            False,
            True,
            True,
        ),
        (
            {"svc": [["-", "cnt", "[dim]stopped[/dim]"]]},
            False,
            False,
            True,
        ),
    ]
    idx = {"value": 0}

    def collect_status(
        _env: Any, gate_status: Any = None
    ) -> tuple[dict[str, list[list[str]]], bool, bool, bool]:
        i = min(idx["value"], len(status_samples) - 1)
        idx["value"] += 1
        return status_samples[i]

    fake_console = mocker.Mock()
    fake_console.is_terminal = True
    mocker.patch.object(Util, "console", fake_console)
    mocker.patch.object(mng, "_collect_env_status", side_effect=collect_status)
    mocker.patch.object(mng, "_build_env_status_tree", return_value="tree")

    live_updates: list[Any] = []
    live_stops = {"count": 0}

    class FakeLive:
        def __init__(self, *args: Any, **kwargs: Any):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            return False

        def update(self, renderable: Any):
            live_updates.append(renderable)

        def stop(self):
            live_stops["count"] += 1

    mocker.patch("environment.status_wait.Live", FakeLive)

    stop_calls = {"count": 0}

    def stop_action():
        stop_calls["count"] += 1

    mng.wait_for_env_down(env, timeout_seconds=2, stop_action=stop_action)

    assert stop_calls["count"] == 1
    assert idx["value"] >= 2
    assert live_updates
    assert live_stops["count"] == 0


def test_wait_for_env_up_terminal_no_action_waits_for_first_snapshot(
    mocker: MockerFixture,
):
    mng = _new_environment_mng(mocker)
    setattr(mng, "_status_poll_seconds", 0.001)

    env = mocker.Mock()
    env.envCfg = SimpleNamespace(tag="test-env")
    env.get_services.return_value = []

    calls = {"count": 0}

    def collect_status(
        _env: Any, gate_status: Any = None
    ) -> tuple[dict[str, list[list[str]]], bool, bool, bool]:
        calls["count"] += 1
        if calls["count"] == 1:
            time.sleep(0.03)
        return (
            {"svc": [["-", "cnt", "[bold green]running[/bold green]"]]},
            True,
            True,
            True,
        )

    fake_console = mocker.Mock()
    fake_console.is_terminal = True
    mocker.patch.object(Util, "console", fake_console)
    mocker.patch.object(mng, "_collect_env_status", side_effect=collect_status)
    mocker.patch.object(mng, "_build_env_status_tree", return_value="tree")

    class FakeLive:
        def __init__(self, *args: Any, **kwargs: Any):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            return False

        def update(self, renderable: Any):
            pass

        def stop(self):
            pass

    mocker.patch("environment.status_wait.Live", FakeLive)

    mng.wait_for_env_up(
        env,
        timeout_seconds=2,
        start_action=None,
        watch_after=False,
    )

    assert calls["count"] >= 1
    fake_console.print.assert_not_called()


def test_wait_for_env_up_watch_clears_ready_badge_on_regression(
    mocker: MockerFixture,
):
    env = mocker.Mock()
    env.envCfg = SimpleNamespace(tag="test-env")

    status_samples: list[
        tuple[dict[str, list[list[str]]], bool, bool, bool]
    ] = [
        (
            {"svc": [["-", "cnt", "[yellow]starting[/yellow]"]]},
            False,
            True,
            True,
        ),
        (
            {"svc": [["-", "cnt", "[bold green]running[/bold green]"]]},
            True,
            True,
            True,
        ),
        (
            {"svc": [["-", "cnt", "[yellow]degraded[/yellow]"]]},
            False,
            True,
            True,
        ),
    ]
    idx = {"value": 0}

    def collect_status(
        _env: Any, _gate_status: Any = None
    ) -> tuple[dict[str, list[list[str]]], bool, bool, bool]:
        i = min(idx["value"], len(status_samples) - 1)
        idx["value"] += 1
        if idx["value"] > 6:
            raise RuntimeError("stop-watch")
        time.sleep(0.01)
        return status_samples[i]

    build_tree = mocker.Mock(return_value="tree")
    hooks = WaitForEnvStateHooks(
        status_poll_seconds=0.005,
        is_quiet=lambda: False,
        get_required_gate_tags=lambda _env: set(),
        evaluate_gate_status=lambda _env, _tags: {},
        collect_env_status=collect_status,
        build_env_status=build_tree,
        remaining_timeout_seconds=lambda _started, _timeout: None,
    )

    class FakeLive:
        def __init__(self, *args: Any, **kwargs: Any):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            return False

        def update(self, renderable: Any):
            del renderable

        def stop(self):
            pass

    mocker.patch("environment.status_wait.Live", FakeLive)
    fake_console = mocker.Mock()
    fake_console.is_terminal = True
    mocker.patch.object(Util, "console", fake_console)

    with pytest.raises(RuntimeError, match="stop-watch"):
        wait_for_env_state(
            env,
            timeout_seconds=None,
            action=None,
            wait_until_up=True,
            watch_after=True,
            hooks=hooks,
        )

    suffixes = [
        Text.from_markup(call.kwargs["status_suffix"]).plain
        for call in build_tree.call_args_list
        if "status_suffix" in call.kwargs
    ]
    ready_indexes = [
        i for i, suffix in enumerate(suffixes) if suffix == "Ready"
    ]
    assert ready_indexes
    assert any(suffix != "Ready" for suffix in suffixes[ready_indexes[0] + 1 :])


def test_wait_for_env_up_watch_flashes_ready_badge_briefly(
    mocker: MockerFixture,
):
    env = mocker.Mock()
    env.envCfg = SimpleNamespace(tag="test-env")

    status_samples: list[
        tuple[dict[str, list[list[str]]], bool, bool, bool]
    ] = [
        (
            {"svc": [["-", "cnt", "[yellow]starting[/yellow]"]]},
            False,
            True,
            True,
        ),
        (
            {"svc": [["-", "cnt", "[bold green]running[/bold green]"]]},
            True,
            True,
            True,
        ),
    ]
    idx = {"value": 0}

    def collect_status(
        _env: Any, _gate_status: Any = None
    ) -> tuple[dict[str, list[list[str]]], bool, bool, bool]:
        idx["value"] += 1
        if idx["value"] > 130:
            raise RuntimeError("stop-watch")
        sample_idx = 0 if idx["value"] == 1 else 1
        time.sleep(0.005)
        return status_samples[sample_idx]

    build_tree = mocker.Mock(return_value="tree")
    hooks = WaitForEnvStateHooks(
        status_poll_seconds=0.005,
        is_quiet=lambda: False,
        get_required_gate_tags=lambda _env: set(),
        evaluate_gate_status=lambda _env, _tags: {},
        collect_env_status=collect_status,
        build_env_status=build_tree,
        remaining_timeout_seconds=lambda _started, _timeout: None,
    )

    class FakeLive:
        def __init__(self, *args: Any, **kwargs: Any):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            return False

        def update(self, renderable: Any):
            del renderable

        def stop(self):
            pass

    mocker.patch("environment.status_wait.Live", FakeLive)
    fake_console = mocker.Mock()
    fake_console.is_terminal = True
    mocker.patch.object(Util, "console", fake_console)

    with pytest.raises(RuntimeError, match="stop-watch"):
        wait_for_env_state(
            env,
            timeout_seconds=None,
            action=None,
            wait_until_up=True,
            watch_after=True,
            hooks=hooks,
        )

    suffixes = [
        call.kwargs["status_suffix"]
        for call in build_tree.call_args_list
        if "status_suffix" in call.kwargs
    ]
    assert "[bold black on green]Ready[/bold black on green]" in suffixes


def test_wait_for_env_up_watch_marks_changed_container_and_probe_for_flash(
    mocker: MockerFixture,
):
    env = mocker.Mock()
    env.envCfg = SimpleNamespace(tag="test-env")

    status_samples: list[
        tuple[dict[str, list[list[str]]], bool, bool, bool]
    ] = [
        (
            {
                "svc": [
                    [
                        "[dim]-[/dim]",
                        "cnt",
                        "[yellow]starting[/yellow]",
                        "[dim]probe-a[/dim]",
                    ]
                ]
            },
            False,
            True,
            True,
        ),
        (
            {
                "svc": [
                    [
                        "[dim]-[/dim]",
                        "cnt",
                        "[bold green]running[/bold green]",
                        "[green]probe-a[/green]",
                    ]
                ]
            },
            True,
            True,
            True,
        ),
    ]
    idx = {"value": 0}

    def collect_status(
        _env: Any, _gate_status: Any = None
    ) -> tuple[dict[str, list[list[str]]], bool, bool, bool]:
        idx["value"] += 1
        if idx["value"] > 12:
            raise RuntimeError("stop-watch")
        sample_idx = 0 if idx["value"] == 1 else 1
        time.sleep(0.005)
        return status_samples[sample_idx]

    build_tree = mocker.Mock(return_value="tree")
    hooks = WaitForEnvStateHooks(
        status_poll_seconds=0.005,
        is_quiet=lambda: False,
        get_required_gate_tags=lambda _env: set(),
        evaluate_gate_status=lambda _env, _tags: {},
        collect_env_status=collect_status,
        build_env_status=build_tree,
        remaining_timeout_seconds=lambda _started, _timeout: None,
    )

    class FakeLive:
        def __init__(self, *args: Any, **kwargs: Any):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            return False

        def update(self, renderable: Any):
            del renderable

        def stop(self):
            pass

    mocker.patch("environment.status_wait.Live", FakeLive)
    fake_console = mocker.Mock()
    fake_console.is_terminal = True
    mocker.patch.object(Util, "console", fake_console)

    with pytest.raises(RuntimeError, match="stop-watch"):
        wait_for_env_state(
            env,
            timeout_seconds=None,
            action=None,
            wait_until_up=True,
            watch_after=True,
            hooks=hooks,
        )

    flashing_calls = [
        call.kwargs
        for call in build_tree.call_args_list
        if call.kwargs.get("flashing_containers")
        or call.kwargs.get("flashing_probes")
    ]
    assert any(
        "svc/cnt" in kwargs["flashing_containers"] for kwargs in flashing_calls
    )
    assert any(
        ("svc", "probe-a") in kwargs["flashing_probes"]
        for kwargs in flashing_calls
    )
    assert any(
        "RUNNING" in kwargs["flashing_summary_keys"]
        for kwargs in flashing_calls
    )


def test_render_moving_shadow_text_is_deterministic_per_tick():
    frame0 = render_moving_shadow_text("Starting", tick=0)
    frame1 = render_moving_shadow_text("Starting", tick=1)
    frame8 = render_moving_shadow_text("Starting", tick=8)

    assert frame0 != frame1
    assert frame0 == frame8
    assert "[bold white]" in frame0
    assert "[white]" in frame0
    assert "[grey50]" in frame0


def test_render_moving_shadow_text_preserves_spaces_and_escapes_markup():
    frame = render_moving_shadow_text("Go [now]", tick=2)

    assert " " in frame
    assert "[" in frame
    assert "]" in frame


def test_wait_for_env_state_uses_custom_progress_label(
    mocker: MockerFixture,
):
    env = mocker.Mock()
    env.envCfg = SimpleNamespace(tag="test-env")
    status_samples: list[
        tuple[dict[str, list[list[str]]], bool, bool, bool]
    ] = [
        (
            {
                "svc": [
                    [
                        "[dim]-[/dim]",
                        "cnt",
                        "[yellow]starting[/yellow]",
                    ]
                ]
            },
            False,
            True,
            True,
        ),
        (
            {
                "svc": [
                    [
                        "[dim]-[/dim]",
                        "cnt",
                        "[bold green]running[/bold green]",
                    ]
                ]
            },
            True,
            True,
            True,
        ),
    ]
    status_idx = {"value": 0}

    def collect_status(
        _env: Any,
        _gate_status: Any = None,
    ) -> tuple[dict[str, list[list[str]]], bool, bool, bool]:
        idx = min(status_idx["value"], len(status_samples) - 1)
        status_idx["value"] += 1
        return status_samples[idx]

    build_tree = mocker.Mock(return_value="tree")
    hooks = WaitForEnvStateHooks(
        status_poll_seconds=0.001,
        is_quiet=lambda: False,
        get_required_gate_tags=lambda _env: set(),
        evaluate_gate_status=lambda _env, _tags: {},
        collect_env_status=collect_status,
        build_env_status=build_tree,
        remaining_timeout_seconds=lambda _started, _timeout: None,
    )

    class FakeLive:
        def __init__(self, *args: Any, **kwargs: Any):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            return False

        def update(self, renderable: Any):
            pass

        def stop(self):
            pass

    mocker.patch("environment.status_wait.Live", FakeLive)
    fake_console = mocker.Mock()
    fake_console.is_terminal = True
    mocker.patch.object(Util, "console", fake_console)

    def action() -> None:
        time.sleep(0.02)

    wait_for_env_state(
        env,
        timeout_seconds=None,
        action=action,
        wait_until_up=True,
        watch_after=False,
        progress_label="Checking",
        hooks=hooks,
    )

    suffixes = [
        Text.from_markup(call.kwargs["status_suffix"]).plain
        for call in build_tree.call_args_list
        if "status_suffix" in call.kwargs
    ]
    assert "Checking" in suffixes


def test_describe_env_renders_summary_table(mocker: MockerFixture):
    mng = _new_environment_mng(mocker)
    env = mocker.Mock()
    env.envCfg = SimpleNamespace(
        tag="env-1",
        template="default",
        factory="docker-compose",
        services=[object(), object()],
        probes=[object()],
        status=SimpleNamespace(active=True),
    )
    mocker.patch.object(mng, "get_environment_from_tag", return_value=env)
    render_table = mocker.patch.object(Util, "render_table")

    mng.describe_env("env-1")

    render_table.assert_called_once_with(
        title=None,
        columns=[
            {"header": "NAME", "style": "cyan"},
            {"header": "TEMPLATE", "style": "magenta"},
            {"header": "ENGINE", "style": "yellow"},
            {"header": "ACTIVE", "style": "white"},
            {"header": "SERVICES", "style": "white", "justify": "right"},
            {"header": "PROBES", "style": "white", "justify": "right"},
        ],
        rows=[["env-1", "default", "docker-compose", "yes", "2", "1"]],
    )


def test_build_env_details_tree(mocker: MockerFixture):
    svc_1 = SimpleNamespace(
        svcCfg=SimpleNamespace(
            tag="api",
            containers=[
                SimpleNamespace(
                    tag="web", run_container_name="web-api-test-env"
                )
            ],
        )
    )
    svc_2 = SimpleNamespace(
        svcCfg=SimpleNamespace(
            tag="db",
            containers=[
                SimpleNamespace(
                    tag="postgres",
                    run_container_name="postgres-db-test-env",
                )
            ],
        )
    )
    env = mocker.Mock()
    env.envCfg = SimpleNamespace(tag="test-env")
    env.get_services.return_value = [svc_1, svc_2]

    tree = build_env_details_tree(env)

    assert isinstance(tree, Tree)
    assert tree.label == "[bold]test-env[/bold]"
    assert len(tree.children) == 2
    assert tree.children[0].label == "[cyan]api[/cyan]"
    assert (
        tree.children[0].children[0].label == "[white]web-api-test-env[/white]"
    )
    assert tree.children[1].label == "[cyan]db[/cyan]"
    assert (
        tree.children[1].children[0].label
        == "[white]postgres-db-test-env[/white]"
    )


def test_describe_env_with_details_renders_tree(mocker: MockerFixture):
    mng = _new_environment_mng(mocker, cli_flags={"details": True})
    env = mocker.Mock()
    env.envCfg = SimpleNamespace(
        tag="env-1",
        template="default",
        factory="docker-compose",
        services=[object()],
        probes=[],
        status=SimpleNamespace(active=True),
    )
    mocker.patch.object(mng, "get_environment_from_tag", return_value=env)
    mocker.patch.object(mng, "_build_env_details_tree", return_value="tree")
    render_table = mocker.patch.object(Util, "render_table")
    console_print = mocker.patch.object(Util.console, "print")

    mng.describe_env("env-1")

    render_table.assert_called_once()
    console_print.assert_called_once_with("tree")
