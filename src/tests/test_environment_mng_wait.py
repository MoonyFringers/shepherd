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

from environment.environment import EnvironmentMng, ProbeRunResult
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


def test_start_env_wraps_start_with_wait_loop(mocker: MockerFixture):
    mng = _new_environment_mng(mocker)

    env_cfg = cast(
        Any,
        SimpleNamespace(
            tag="test-env",
            status=SimpleNamespace(rendered_config=None),
        ),
    )
    env = mocker.Mock()
    env.envCfg = env_cfg
    env.render_target.return_value = {"ungated": "yaml"}

    mocker.patch.object(mng, "get_environment_from_cfg", return_value=env)
    wait_for_env_up = mocker.patch.object(mng, "wait_for_env_up")

    mng.start_env(env_cfg, timeout_seconds=15)

    assert env.start.call_count == 0
    wait_for_env_up.assert_called_once_with(
        env,
        timeout_seconds=15,
        start_action=env.start,
    )
    env.sync_config.assert_called_once()
    assert env.envCfg.status.rendered_config == {"ungated": "yaml"}


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
            {"svc": [["cnt", "[bold green]● running[/bold green]"]]},
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
    assert status_idx["value"] == 1
    fake_console.print.assert_called_once_with(
        "[yellow]No services found for environment 'test-env'[/yellow]"
    )


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
        == "[dim]○[/dim][dim]○[/dim]"
    )

    glyphs = mng_any._format_service_gate_glyphs(
        cast(Any, gated),
        gate_status={"p1": True, "p2": False},
    )
    assert "[bold red]●[/bold red]" in glyphs
    assert "[bold green]●[/bold green]" in glyphs


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
                "[bold green]● running[/bold green]",
                "[dim]a[/dim], [dim]b[/dim]",
            ]
        ]
    }
    table = mng_any._build_env_status_table("env-1", grouped)
    headers = [c.header for c in table.columns]
    assert headers == ["Gates", "Service", "Container", "State", "Probes"]


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
            {"svc": [["-", "cnt", "[bold green]● running[/bold green]"]]},
            False,
            True,
            True,
        ),
        (
            {"svc": [["-", "cnt", "[bold red]● stopped[/bold red]"]]},
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

    mocker.patch("environment.environment.Live", FakeLive)

    stop_calls = {"count": 0}

    def stop_action():
        stop_calls["count"] += 1

    mng.wait_for_env_down(env, timeout_seconds=2, stop_action=stop_action)

    assert stop_calls["count"] == 1
    assert idx["value"] >= 2
    assert live_updates
    assert live_stops["count"] == 0
