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
from typing import Any, Iterable, Optional

from config.config import ContainerCfg
from util import Util


def run_compose(
    yamls: str | Iterable[str],
    *args: str,
    capture: bool = False,
    project_name: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
) -> subprocess.CompletedProcess[str]:
    """
    Run a docker compose command with one or more YAML definitions.

    For multi-file Compose usage, order matters:
      - base files first
      - overlay files later (they override/extend earlier ones)

    Example:
      run_compose([base_yaml, overlay_yaml], "up", "-d", "new-service")
    """

    if isinstance(yamls, str):
        yaml_list = [yamls]
    else:
        yaml_list = list(yamls)

    if not yaml_list:
        raise ValueError("run_compose: at least one YAML must be provided")

    tmp_paths: list[Path] = []

    try:
        for yml in yaml_list:
            with tempfile.NamedTemporaryFile(
                "w", suffix=".yml", delete=False
            ) as tmp:
                tmp.write(yml)
                tmp_paths.append(Path(tmp.name))

        cmd: list[str] = ["docker", "compose"]
        if project_name:
            cmd += ["-p", project_name]
        for p in tmp_paths:
            cmd += ["-f", str(p)]
        cmd += list(args)

        try:
            result = subprocess.run(
                cmd,
                check=False,
                text=True,
                capture_output=capture,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as e:
            # Normalize the timeout into a CompletedProcess-like result
            stdout = (
                e.stdout
                if isinstance(e.stdout, str)
                else (e.stdout.decode() if e.stdout else "")
            )
            stderr = (
                e.stderr
                if isinstance(e.stderr, str)
                else (e.stderr.decode() if e.stderr else "")
            )
            return subprocess.CompletedProcess(
                cmd, returncode=124, stdout=stdout, stderr=stderr
            )

        logging.debug(
            f"docker compose command run:\n"
            f"CMD: {' '.join(cmd)}\n"
            f"with exit code {result.returncode}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

        if result.returncode != 0:
            logging.warning(
                "docker compose command failed "
                f"with exit code {result.returncode}\n"
                f"CMD: {' '.join(cmd)}\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            )

        return result

    finally:
        for p in tmp_paths:
            try:
                p.unlink(missing_ok=True)
            except Exception as e:
                logging.debug(f"Failed to remove temp compose file {p}: {e}")


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


def render_container(
    cnt: ContainerCfg, labels: Optional[list[str]]
) -> dict[str, Any]:
    """
    Render the container configuration in the target system.
    """
    container_def: dict[str, Any] = {}
    if cnt.image:
        container_def["image"] = cnt.image
    if cnt.run_hostname:
        container_def["hostname"] = cnt.run_hostname
    if cnt.run_container_name:
        container_def["container_name"] = cnt.run_container_name
    if cnt.workdir:
        container_def["working_dir"] = cnt.workdir
    if cnt.volumes:
        container_def["volumes"] = cnt.volumes
    if cnt.environment:
        container_def["environment"] = cnt.environment
    if cnt.ports:
        container_def["ports"] = cnt.ports
    if cnt.networks:
        container_def["networks"] = cnt.networks
    if cnt.extra_hosts:
        container_def["extra_hosts"] = cnt.extra_hosts
    if labels:
        container_def["labels"] = labels
    return container_def


def build_container(container: ContainerCfg) -> None:
    """Build a container."""
    if not container.build:
        Util.print_error_and_die(
            f"Container '{container.tag}' "
            f"does not have a build configuration."
        )

    if build := container.build:
        if not build.dockerfile_path:
            Util.print_error_and_die(
                f"Container '{container.tag}' "
                f"build configuration is missing "
                f"a Dockerfile path."
            )
        if not build.context_path:
            Util.print_error_and_die(
                f"Container '{container.tag}' "
                f"build configuration is missing "
                f"a build context path."
            )

        if build.dockerfile_path and build.context_path:
            build_docker_image(
                Path(build.dockerfile_path),
                Path(build.context_path),
                container.image or "",
            )
