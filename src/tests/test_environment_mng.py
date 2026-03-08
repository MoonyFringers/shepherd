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
from rich.table import Table
from rich.text import Text

from environment.environment import EnvironmentMng, ProbeRunResult
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
            {"svc": [["cnt", "[white]running[/white]"]]},
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
    mocker.patch.object(mng, "_build_env_status_table", return_value="table")

    mng.wait_for_env_up(env, timeout_seconds=2, start_action=start_action)

    assert start_calls["count"] == 1
    assert status_idx["value"] >= 2
    fake_console.print.assert_called_once_with("table")


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
        mng, "_build_env_status_table", return_value="table"
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
            {"svc": [["-", "cnt", "[white]running[/white]"]]},
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
    mocker.patch.object(mng, "_build_env_status_table", return_value="table")

    mng.wait_for_env_up(env, timeout_seconds=2, start_action=None)

    assert idx["value"] >= 2
    fake_console.print.assert_called_once_with("table")


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
            {"svc": [["-", "cnt", "[white]running[/white]"]]},
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
    mocker.patch.object(mng, "_build_env_status_table", return_value="table")

    mng.wait_for_env_down(env, timeout_seconds=2, stop_action=None)

    assert idx["value"] >= 2
    fake_console.print.assert_called_once_with("table")


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
            {"svc": [["-", "cnt", "[white]running[/white]"]]},
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


def test_status_env_hides_gates_column(mocker: MockerFixture):
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
                        "[white]running[/white]",
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

    printed_table = cast(Table, fake_console.print.call_args.args[0])
    headers = [c.header for c in printed_table.columns]
    assert headers == ["Service", "Container", "State"]


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
    assert "[bold green]alpha[/bold green]" in details
    assert "[bold red]beta[/bold red]" in details
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


def test_build_env_status_table_includes_details_column_when_enabled(
    mocker: MockerFixture,
):
    mng = _new_environment_mng(mocker, cli_flags={"details": True})
    mng_any = cast(Any, mng)
    grouped = {
        "svc-1": [
            [
                "[dim]-[/dim]",
                "cnt-1",
                "[white]running[/white]",
                "[dim]a[/dim], [dim]b[/dim]",
            ]
        ]
    }
    table = mng_any._build_env_status_table("env-1", grouped)
    headers = [c.header for c in table.columns]
    assert headers == ["Gates", "Service", "Container", "State", "Probes"]


def test_build_env_status_table_with_command_log_panel(mocker: MockerFixture):
    mng = _new_environment_mng(mocker)
    mng_any = cast(Any, mng)
    grouped = {
        "svc-1": [
            [
                "[dim]-[/dim]",
                "cnt-1",
                "[white]running[/white]",
            ]
        ]
    }

    renderable = mng_any._build_env_status_table(
        "env-1",
        grouped,
        command_log=["[green]ok[/green]", "[red]fail[/red]"],
        command_log_limit=4,
    )
    assert isinstance(renderable, Group)
    assert isinstance(renderable.renderables[0], Table)
    assert isinstance(renderable.renderables[1], Panel)
    panel = renderable.renderables[1]
    assert panel.title == "Recent Commands"
    assert panel.border_style == "blue"
    assert panel.expand is True
    assert panel.box is not None
    assert len(str(panel.renderable).splitlines()) == 4


def test_build_env_status_table_with_error_panel(mocker: MockerFixture):
    mng = _new_environment_mng(mocker)
    mng_any = cast(Any, mng)
    grouped = {
        "svc-1": [
            [
                "[dim]-[/dim]",
                "cnt-1",
                "[white]running[/white]",
            ]
        ]
    }

    renderable = mng_any._build_env_status_table(
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
    assert len(renderable.renderables) == 3
    error_panel = renderable.renderables[2]
    assert isinstance(error_panel, Panel)
    assert error_panel.title == "Command start:db failed"
    assert error_panel.border_style == "red"
    assert len(str(error_panel.renderable).splitlines()) == 2


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
            {"svc": [["-", "cnt", "[white]running[/white]"]]},
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
    mocker.patch.object(mng, "_build_env_status_table", return_value="table")

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
            {"svc": [["-", "cnt", "[white]running[/white]"]]},
            True,
            True,
            True,
        )

    fake_console = mocker.Mock()
    fake_console.is_terminal = True
    mocker.patch.object(Util, "console", fake_console)
    mocker.patch.object(mng, "_collect_env_status", side_effect=collect_status)
    mocker.patch.object(mng, "_build_env_status_table", return_value="table")

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
                        "[white]running[/white]",
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

    build_table = mocker.Mock(return_value="table")
    hooks = WaitForEnvStateHooks(
        status_poll_seconds=0.001,
        is_quiet=lambda: False,
        get_required_gate_tags=lambda _env: set(),
        evaluate_gate_status=lambda _env, _tags: {},
        collect_env_status=collect_status,
        build_env_status_table=build_table,
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
        for call in build_table.call_args_list
        if "status_suffix" in call.kwargs
    ]
    assert "Checking" in suffixes
