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

from pytest_mock import MockerFixture

from environment.environment import EnvironmentMng
from util.util import Util


def _new_environment_mng(mocker: MockerFixture) -> EnvironmentMng:
    return EnvironmentMng(
        cli_flags={},
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
    mocker.patch.object(Util, "console", fake_console)
    mocker.patch.object(mng, "_collect_env_status", side_effect=collect_status)
    mocker.patch.object(mng, "_build_env_status_table", return_value="table")

    mng.wait_for_env_up(env, timeout_seconds=2, start_action=start_action)

    assert start_calls["count"] == 1
    assert status_idx["value"] == 1
    fake_console.print.assert_called_once_with(
        "[yellow]No services found for environment 'test-env'[/yellow]"
    )
