# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

import os
from typing import List

from util import Util, constants


class RepositoryManager:
    @staticmethod
    def install_missing_brew_packages(
        missing_packages: List[str], check: bool = True
    ) -> None:
        """Install missing Homebrew packages one by one."""
        if not missing_packages:
            Util.console.print("No packages to install", style="yellow")
            return

        for pkg in missing_packages:
            Util.run_command(["brew", "install", pkg], check=check)

    @staticmethod
    def add_docker_repository(distro: str, codename: str) -> None:
        """
        Add Docker apt repository metadata for the detected distro/codename.

        The operation is idempotent: existing repo file means no-op.
        """
        if distro not in constants.REPO_STRINGS:
            raise RuntimeError(f"Unsupported distribution: {distro}")

        architecture = Util.get_architecture()

        repo_string = constants.REPO_STRINGS[distro].format(
            architecture=architecture, release=codename
        )
        repo_path = constants.REPO_PATHS[distro]

        if os.path.exists(repo_path):
            return  # Exit early if the repository file already exists

        with open(repo_path, "w", encoding="utf-8") as f:
            f.write(repo_string)

        update_command = constants.UPDATE_COMMANDS[distro].split()
        Util.run_command(update_command, check=True)
        Util.console.print("Repository added successfully.", style="green")

    @staticmethod
    def install_missing_packages(
        distro: str, missing_packages: List[str], check: bool = True
    ) -> None:
        """Install missing Linux packages using the appropriate manager."""
        if not missing_packages:
            Util.console.print("No packages to install", style="yellow")
            return
        cmd_list = constants.INSTALL_COMMANDS[distro].copy()
        cmd_list.extend(missing_packages)
        Util.run_command(cmd_list, check=check)

    @staticmethod
    def check_package_installed(pkg: str) -> bool:
        """Check if a package is installed using dpkg."""
        try:
            result = Util.run_command(
                ["dpkg", "-s", pkg],
                check=False,
                capture_output=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def check_brew_package_installed(pkg: str) -> bool:
        """Check whether a Homebrew formula or cask is already installed."""
        for kind in ("formula", "cask"):
            try:
                result = Util.run_command(
                    ["brew", "list", f"--{kind}", pkg],
                    check=False,
                    capture_output=True,
                )
            except Exception:
                continue
            if result.returncode == 0:
                return True
        return False

    @staticmethod
    def install_required_packages(system: str, distro: str | None) -> None:
        """Install required non-Python system packages for the platform."""
        if system == "darwin":
            required_packages = ["bc", "jq", "curl", "rsync"]
            missing_packages: List[str] = []
            for pkg in required_packages:
                if not RepositoryManager.check_brew_package_installed(pkg):
                    Util.console.print(
                        f"Package {pkg} is missing.", style="yellow"
                    )
                    missing_packages.append(pkg)
                else:
                    Util.console.print(
                        f"Package {pkg} is already installed.",
                        style="green",
                    )
            if missing_packages:
                missing = ", ".join(missing_packages)
                Util.console.print(
                    f"Installing missing packages: {missing}",
                    style="blue",
                )
                RepositoryManager.install_missing_brew_packages(
                    missing_packages
                )
            else:
                Util.console.print(
                    "All required packages are already installed.",
                    style="green",
                )
            return

        if distro is None:
            raise RuntimeError("Linux distribution is required")

        missing_packages: List[str] = []
        for pkg in constants.REQUIRED_PKGS:
            if not RepositoryManager.check_package_installed(pkg):
                Util.console.print(
                    f"Package {pkg} is missing.",
                    style="yellow",
                )
                missing_packages.append(pkg)
            else:
                Util.console.print(
                    f"Package {pkg} is already installed.", style="green"
                )
        if missing_packages:
            Util.console.print(
                f"Installing missing packages: {', '.join(missing_packages)}",
                style="blue",
            )
            RepositoryManager.install_missing_packages(
                distro,
                missing_packages,
            )
        else:
            Util.console.print(
                "All required packages are already installed.",
                style="green",
            )

    @staticmethod
    def install_python_packages(system: str, distro: str | None) -> None:
        """Install Python prerequisites for source installs."""
        executed_python_version = Util.run_command(
            ["python3", "--version"], check=False, capture_output=True
        )
        python_version = executed_python_version.stdout.split()[1]
        major, minor, _ = map(int, python_version.split("."))
        if major < 3 or (major == 3 and minor < 12):
            Util.console.print(
                "Python version is less than 3.12. Going to update",
                style="yellow",
            )
            if system == "darwin":
                python_formula = "python@3.12"
                RepositoryManager.install_missing_brew_packages(
                    [python_formula]
                )
            else:
                if distro is None:
                    raise RuntimeError("Linux distribution is required")
                RepositoryManager.install_missing_packages(distro, ["python3"])
        else:
            Util.console.print(
                "Python version is 3.12 or greater. No need to update",
                style="green",
            )

        if system == "darwin":
            Util.console.print(
                "macOS source installs rely on Homebrew Python "
                "and bundled venv support.",
                style="green",
            )
            return

        if distro is None:
            raise RuntimeError("Linux distribution is required")

        missing_python_packages: List[str] = []
        for pkg in constants.REQUIRED_PYTHON_PKGS:
            if not RepositoryManager.check_package_installed(pkg):
                Util.console.print(
                    f"Python package {pkg} is missing.", style="yellow"
                )
                missing_python_packages.append(pkg)
            else:
                Util.console.print(
                    f"Python package {pkg} is already installed.",
                    style="green",
                )
        if missing_python_packages:
            Util.console.print(
                (
                    "Installing missing Python packages: "
                    f"{', '.join(missing_python_packages)}"
                ),
                style="blue",
            )
            RepositoryManager.install_missing_packages(
                distro, missing_python_packages
            )
        else:
            Util.console.print(
                "All required Python packages are already installed.",
                style="green",
            )

    @staticmethod
    def install_docker_packages(
        system: str, distro: str | None, codename: str | None
    ) -> None:
        """
        Ensure Docker engine/compose packages and runtime setup are present.
        """
        if system == "darwin":
            if RepositoryManager.check_brew_package_installed("docker"):
                Util.console.print(
                    "Docker is already installed.", style="green"
                )
            else:
                Util.console.print(
                    "Docker is not installed. Installing...", style="yellow"
                )
                RepositoryManager.install_missing_brew_packages(["docker"])

            docker_version = Util.run_command(
                ["docker", "--version"], check=False, capture_output=True
            )
            Util.console.print(
                f"Docker version: {docker_version.stdout}", style="green"
            )

            docker_compose_version = Util.run_command(
                ["docker", "compose", "version"],
                check=False,
                capture_output=True,
            )
            if docker_compose_version.returncode == 0:
                Util.console.print(
                    "Docker Compose is already installed.", style="green"
                )
            else:
                RepositoryManager.install_missing_brew_packages(
                    ["docker-compose"]
                )
                docker_compose_version = Util.run_command(
                    ["docker", "compose", "version"],
                    check=False,
                    capture_output=True,
                )
            Util.console.print(
                f"Docker Compose version: {docker_compose_version.stdout}",
                style="green",
            )

            docker_info = Util.run_command(
                ["docker", "info"], check=False, capture_output=True
            )
            if docker_info.returncode != 0:
                Util.console.print(
                    "Docker CLI installed, but no Docker daemon is reachable. "
                    "Install and start Docker Desktop before using shepctl.",
                    style="yellow",
                )
            else:
                Util.console.print(
                    "Docker daemon is reachable.",
                    style="green",
                )
            return

        if distro is None or codename is None:
            raise RuntimeError("Linux distro and codename are required")

        if any(
            RepositoryManager.check_package_installed(pkg)
            for pkg in constants.REQUIRED_DOCKER_PKGS
        ):
            Util.console.print("Docker is already installed.", style="green")
            new_docker = False
        else:
            Util.console.print(
                "Docker is not installed. Installing...", style="yellow"
            )
            new_docker = True
            if not Util.check_file_exists(constants.KEYRING_PATH):
                Util.console.print(
                    "Docker keyring file is missing. Installing...",
                    style="yellow",
                )
                Util.run_command(
                    [
                        "curl",
                        "-fsSL",
                        constants.GPG_KEYS[distro],
                        "-o",
                        "/tmp/docker.gpg",
                    ],
                    check=True,
                )
                Util.run_command(
                    [
                        "gpg",
                        "--dearmor",
                        "-o",
                        constants.KEYRING_PATH,
                        "/tmp/docker.gpg",
                    ],
                    check=True,
                )
            else:
                Util.console.print(
                    "Docker keyring file is already installed.",
                    style="green",
                )

            if not Util.check_file_exists(constants.REPO_PATHS[distro]):
                Util.console.print(
                    "Docker repository is missing. Adding...",
                    style="yellow",
                )
                RepositoryManager.add_docker_repository(distro, codename)
            else:
                Util.console.print(
                    "Docker repository already exists.", style="green"
                )

            missing_packages: List[str] = []
            for pkg in constants.REQUIRED_DOCKER_PKGS:
                Util.console.print(
                    f"Checking for package: {pkg}",
                    style="blue",
                )
                if not RepositoryManager.check_package_installed(pkg):
                    Util.console.print(
                        f"Package {pkg} is missing.", style="yellow"
                    )
                    missing_packages.append(pkg)
                else:
                    Util.console.print(
                        f"Package {pkg} is already installed.",
                        style="green",
                    )

            Util.console.print(f"Missing packages: {missing_packages}")

            if missing_packages:
                Util.console.print(
                    "Installing missing packages: "
                    f"{', '.join(missing_packages)}",
                    style="blue",
                )
                RepositoryManager.install_missing_packages(
                    distro, missing_packages
                )
            else:
                Util.console.print(
                    "All required packages are already installed.",
                    style="green",
                )

            docker_version = Util.run_command(
                ["docker", "--version"], check=False, capture_output=True
            )
            Util.console.print(
                f"Docker version: {docker_version.stdout}", style="green"
            )
            docker_compose_version = Util.run_command(
                ["docker", "compose", "version"],
                check=False,
                capture_output=True,
            )
            Util.console.print(
                f"Docker Compose version: {docker_compose_version.stdout}",
                style="green",
            )
            if new_docker:
                Util.run_command(
                    ["sudo", "systemctl", "enable", "docker"], check=True
                )
                Util.run_command(
                    ["sudo", "groupadd", "-f", "docker"], check=True
                )
                running_user = Util.get_current_user()
                Util.run_command(
                    ["usermod", "-aG", "docker", running_user], check=True
                )
                print(
                    f"Docker installed and user {running_user} "
                    "added to docker group."
                )
                Util.console.print(
                    "Please log out and back in for group membership to apply."
                )

            Util.console.print("Docker installation complete!", style="green")

    @staticmethod
    def install_packages(
        system: str,
        distro: str | None,
        codename: str | None,
        install_source: bool,
    ) -> None:
        """
        Install base dependencies and Docker stack.

        Python system packages are installed only for source-based installs.
        """
        RepositoryManager.install_required_packages(system, distro)
        if install_source:
            RepositoryManager.install_python_packages(system, distro)
        RepositoryManager.install_docker_packages(system, distro, codename)
