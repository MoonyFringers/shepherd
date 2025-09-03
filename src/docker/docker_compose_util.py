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

import logging
import subprocess
import tempfile
from pathlib import Path


def run_compose(
    yaml: str, *args: str, capture: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run a docker compose command with the triggered_config YAML."""

    with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as tmp:
        tmp.write(yaml)
        tmp_path = Path(tmp.name)

    try:
        cmd = ["docker", "compose", "-f", str(tmp_path), *args]
        result = subprocess.run(
            cmd,
            check=False,
            text=True,
            capture_output=capture,
        )

        if result.returncode != 0:
            logging.warning(
                f"docker compose command failed "
                f"with exit code {result.returncode}\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

        return result
    finally:
        tmp_path.unlink(missing_ok=True)
