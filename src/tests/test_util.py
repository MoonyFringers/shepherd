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

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from util.util import Util


def read_fixture(*parts: str) -> str:
    """
    Read a test fixture file under tests/fixtures.
    Usage: read_fixture("cfg", "base.yaml")
    """
    here = Path(__file__).resolve().parent
    fixtures_dir = here / "fixtures"
    return (fixtures_dir.joinpath(*parts)).read_text(encoding="utf-8")


def test_print_error_and_die_uses_minimal_error_prefix(
    mocker: MockerFixture,
):
    console = mocker.Mock()
    mocker.patch.object(Util, "console", console)

    with pytest.raises(SystemExit) as excinfo:
        Util.print_error_and_die("test failure")

    assert excinfo.value.code == 1
    console.print.assert_called_once_with(
        "[red]Error:[/red] test failure",
        highlight=False,
    )
