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

from util import Util


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


def build_docker_image(
    dockerfile_path: Path, context_path: Path, tag: str
) -> subprocess.CompletedProcess[str]:
    """
    Build a Docker image using the specified Dockerfile and context
    directory.

    Args:
        dockerfile_path (Path): Path to the Dockerfile.
        context_path (Path): Path to the Docker build context (directory).
        tag (str): The resulting image tag, e.g. "myapp:latest".

    Returns:
        subprocess.CompletedProcess[str]: The result of the docker build
        command.
    """

    if not dockerfile_path.exists():
        Util.print_error_and_die(f"Dockerfile not found: {dockerfile_path}")

    if not context_path.exists() or not context_path.is_dir():
        Util.print_error_and_die(
            f"Invalid Docker build context: {context_path}"
        )

    cmd = [
        "docker",
        "build",
        "-t",
        tag,
        "-f",
        str(dockerfile_path),
        "--progress=auto",
        str(context_path),
    ]

    logging.info(f"Building Docker image '{tag}'")
    logging.debug(f"Docker build command: {' '.join(cmd)}")

    process = subprocess.run(
        cmd,
        check=False,
        text=True,
        stdout=None,
        stderr=None,
    )

    if process.returncode != 0:
        logging.warning(
            f"Docker build failed with exit code {process.returncode}"
        )
        Util.print_error_and_die(f"Docker build failed for image '{tag}'")

    logging.info(f"Docker image '{tag}' built successfully.")
    return process
