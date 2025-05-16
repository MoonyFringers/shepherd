import getpass
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, List, Optional, Union

import distro

from installer.constants import (
    ARCH_MAPPING,
    GPG_KEYS,
    INSTALL_COMMANDS,
    KEYRING_PATH,
    REPO_PATHS,
    REPO_STRINGS,
    REQUIRED_DOCKER_PKGS,
    REQUIRED_PKGS,
    REQUIRED_PYTHON_PKGS,
    UPDATE_COMMANDS,
)

# Color constants (ANSI color codes)
RED = "\033[0;31m"
NC = "\033[0m"  # No Color
YELLOW = "\033[0;33m"
GREEN = "\033[0;32m"
BLUE = "\033[0;36m"


def print_color(message: str, color: str = NC) -> None:
    """Print a message with color."""
    print(f"{color}{message}{NC}")


def is_root() -> bool:
    """Check if the script is running with root privileges."""
    return os.geteuid() == 0


def run_command(
    cmd: Union[List[str], str],
    check: bool = True,
    shell: bool = False,
    capture_output: bool = False,
) -> Union[subprocess.CompletedProcess[Any], subprocess.CalledProcessError]:
    """Run a shell command and return the result.

    Args:
        cmd: Command to run (list or string)
        check: Whether to raise an exception on failure
        shell: Whether to run through shell
        capture_output: Whether to capture stdout/stderr

    Returns:
        CompletedProcess instance or CalledProcessError
    """
    if isinstance(cmd, str) and not shell:
        cmd = cmd.split()

    try:
        result = subprocess.run(
            cmd,
            check=check,
            shell=shell,
            text=True,
            capture_output=capture_output,
        )
        return result
    except subprocess.CalledProcessError as e:
        print_color(f"Command failed: {e}", RED)
        if check:
            sys.exit(1)
        return e


def get_current_user() -> str:
    """Get the actual user, even when running with sudo."""
    return os.environ.get("SUDO_USER") or _get_user_fallback()


def _get_user_fallback() -> str:
    try:
        return os.getlogin()
    except OSError:
        return getpass.getuser()


def check_file_exists(path: str) -> bool:
    """Check if a file exists and is readable at the given path."""
    return os.path.isfile(path) and os.access(path, os.R_OK)


def install_missing_packages(
    distro: str, missing_packages: List[str], check: bool = True
) -> None:
    """Install missing packages using the appropriate package manager.

    Args:
        distro: The Linux distribution
        missing_packages: List of packages to install
        check: Whether to raise an exception on failure
    """
    if not missing_packages:  # Safeguard against empty lists
        print_color("No packages to install", YELLOW)
        return

    cmd_list = INSTALL_COMMANDS[distro].copy()  # Create a copy of the list
    cmd_list.extend(missing_packages)  # Modify the copy
    run_command(cmd_list, check=check)  # Pass the modified list


def add_docker_repository(distro: str, codename: str) -> None:
    """Add the proper repository for the detected distribution."""
    if distro not in REPO_STRINGS:
        raise RuntimeError(f"Unsupported distribution: {distro}")

    architecture = get_architecture()

    repo_string = REPO_STRINGS[distro].format(
        architecture=architecture, release=codename
    )
    repo_path = REPO_PATHS[distro]

    if os.path.exists(repo_path):
        return  # Exit early if the repository file already exists

    with open(repo_path, "w") as f:
        f.write(repo_string)

    update_command = UPDATE_COMMANDS[distro].split()
    run_command(update_command, check=True)  # Update the package list
    print_color("Repository added successfully.", GREEN)


def install_docker_packages(distro: str, codename: str) -> None:
    """Install Docker packages using the appropriate package manager.

    Args:
        distro: The Linux distribution
        codename: The codename of the Linux distribution
    """
    if any(check_package_installed(pkg) for pkg in REQUIRED_DOCKER_PKGS):
        print_color("Docker is already installed.", GREEN)
        new_docker = False
    else:
        print_color("Docker is not installed. Installing...", YELLOW)
        new_docker = True
        # check keyring file existing
        if not check_file_exists(KEYRING_PATH):
            print_color("Docker keyring file is missing. Installing...", YELLOW)
            run_command(
                [
                    "curl",
                    "-fsSL",
                    GPG_KEYS[distro],
                    "| gpg --dearmor -o ",
                    KEYRING_PATH,
                ],
                check=True,
            )
        else:
            print_color("Docker keyring file is already installed.", GREEN)

        # check if the repository is already added
        if not check_file_exists(REPO_PATHS[distro]):
            print_color("Docker repository is missing. Adding...", YELLOW)
            add_docker_repository(distro, codename)
        else:
            print_color("Docker repository already exist.", GREEN)

        missing_packages: List[str] = []
        for pkg in REQUIRED_DOCKER_PKGS:
            print_color(f"Checking for package: {pkg}", BLUE)  # Debug print
            if not check_package_installed(pkg):
                print_color(f"Package {pkg} is missing.", YELLOW)
                missing_packages.append(pkg)
            else:
                print_color(f"Package {pkg} is already installed.", GREEN)

        print(f"Missing packages: {missing_packages}")  # Debug print

        if missing_packages:
            print_color(
                f"Installing missing packages: {', '.join(missing_packages)}",
                BLUE,
            )
            install_missing_packages(distro, missing_packages, check=False)
        else:
            print_color("All required packages are already installed.", GREEN)

        docker_version = run_command(
            ["docker", "--version"], check=False, capture_output=True
        )
        print_color(f"Docker version: {docker_version.stdout}", GREEN)
        docker_compose_version = run_command(
            ["docker-compose", "--version"], check=False, capture_output=True
        )
        print_color(
            f"Docker Compose version: {docker_compose_version.stdout}", GREEN
        )
        if new_docker:
            run_command(["sudo", "systemctl", "enable", "docker"], check=True)
            run_command(["sudo", "groupadd", "-f", "docker"], check=True)
            running_user = get_current_user()
            run_command(["usermod", "-aG", "docker", running_user], check=True)
            print(
                f"Docker installed and user {running_user} "
                "added to docker group."
            )
            print("Please log out and back in for group membership to apply.")

        print_color("Docker installation complete!", GREEN)


def get_architecture() -> str:
    bits, linkage = platform.architecture()
    machine = platform.machine().lower()

    # First try the combination of bits and linkage
    if (bits, linkage) in ARCH_MAPPING:
        return ARCH_MAPPING[(bits, linkage)]

    # Fall back to machine type for ARM architectures
    if "arm" in machine or "aarch" in machine:
        return "arm64"

    # Default to amd64 for 64-bit systems, i386 for others
    return "amd64" if "64" in bits else "i386"


def install_required_packages(distro: str) -> None:
    """Install required packages for the detected distribution.

    Args:
        distro: The Linux distribution
    """
    missing_packages: List[str] = []
    for pkg in REQUIRED_PKGS:
        print(f"Checking for package: {pkg}")  # Debug print
        if not check_package_installed(pkg):
            print_color(f"Package {pkg} is missing.", YELLOW)
            missing_packages.append(pkg)
        else:
            print_color(f"Package {pkg} is already installed.", GREEN)

    print(f"Missing packages: {missing_packages}")  # Debug print

    if missing_packages:
        print_color(
            f"Installing missing packages: {', '.join(missing_packages)}", BLUE
        )
        install_missing_packages(distro, missing_packages)
    else:
        print_color("All required packages are already installed.", GREEN)


def install_python_packages(distro: str) -> None:
    """Install Python packages using the appropriate package manager.

    Args:
        distro: The Linux distribution
    """
    # Ensure Python >= 3.12 is installed
    executed_python_version = run_command(
        ["python3", "--version"], check=False, capture_output=True
    )
    # parse result
    python_version = executed_python_version.stdout.split()[1]
    major, minor, _ = map(int, python_version.split("."))
    if major < 3 or (major == 3 and minor < 12):
        print_color("Python version is less than 3.12. Going to update", YELLOW)
        install_missing_packages(distro, ["python3"])
    else:
        print_color(
            "Python version is 3.12 or greater. No need to update", GREEN
        )

    missing_python_packages: List[str] = []
    for pkg in REQUIRED_PYTHON_PKGS:
        print(f"Checking for Python package: {pkg}")  # Debug print
        if not check_package_installed(pkg):
            print_color(f"Python package {pkg} is missing.", YELLOW)
            missing_python_packages.append(pkg)
        else:
            print_color(f"Python package {pkg} is already installed.", GREEN)

    print(f"Missing Python packages: {missing_python_packages}")  # Debug print

    if missing_python_packages:
        print_color(
            (
                "Installing missing Python packages: "
                f"{', '.join(missing_python_packages)}"
            ),
            BLUE,
        )
        install_missing_packages(distro, missing_python_packages)
    else:
        print_color(
            "All required Python packages are already installed.", GREEN
        )


def install_packages(distro: str, codename: str, install_source: bool) -> None:
    install_required_packages(distro)
    if install_source:
        install_python_packages(distro)
    install_docker_packages(distro, codename)


@dataclass
class OsInfo:
    """Structured information about the operating system."""

    system: str
    distro: Optional[str] = None
    codename: Optional[str] = None


def get_os_info() -> OsInfo:
    """
    Identifies the operating system type, distribution, and codename.

    Returns:
        OsInfo: A dataclass containing system type, distribution, and codename

    Raises:
        ValueError: If the operating system is not supported
    """
    system = platform.system().lower()

    if system in ("windows", "win32", "darwin"):
        raise ValueError(f"Unsupported operating system: {system}")

    elif system == "linux":
        dist_id = distro.id().lower()
        code_name = distro.codename().lower()
        return OsInfo(system=system, distro=dist_id, codename=code_name)

    # Fallback for other systems
    return OsInfo(system=system)


def check_package_installed(pkg: str) -> bool:
    """Check if a package is installed using dpkg."""
    try:
        result = run_command(
            ["dpkg", "-s", pkg],
            check=False,
            capture_output=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def download_package(url: str, dest: str) -> None:
    """Download a package from a URL to a destination path."""
    run_command(["curl", "-fsSL", url, "-o", dest], check=True)
    print_color(f"Package downloaded to {dest}", GREEN)


def extract_package(package_path: str, extract_to: str) -> None:
    """Extract a tar.gz package to a specified directory."""
    run_command(["tar", "-xzf", package_path, "-C", extract_to], check=True)
    print_color(f"Package extracted to {extract_to}", GREEN)
