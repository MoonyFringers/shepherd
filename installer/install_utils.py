#!/usr/bin/env python3

# Copyright (c) 2025 Lunatic Fringers
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


import os
import sys
import subprocess
import platform
import distro
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from constants import *

# Color constants (ANSI color codes)
RED = '\033[0;31m'
NC = '\033[0m'  # No Color
YELLOW = '\033[0;33m'
GREEN = '\033[0;32m'
BLUE = '\033[0;36m'


def print_color(message, color=NC):
    """Print a message with color."""
    print(f"{color}{message}{NC}")


def is_root():
    """Check if the script is running with root privileges."""
    return os.geteuid() == 0


def run_command(cmd, check=True, shell=False, capture_output=False):
    """Run a shell command and return the result.
    
    Args:
        cmd: Command to run (list or string)
        check: Whether to raise an exception on failure
        shell: Whether to run through shell
        capture_output: Whether to capture stdout/stderr
    
    Returns:
        CompletedProcess instance
    """
    if isinstance(cmd, str) and not shell:
        cmd = cmd.split()
    
    try:
        result = subprocess.run(
            cmd, 
            check=check, 
            shell=shell,
            text=True,
            capture_output=capture_output
        )
        return result
    except subprocess.CalledProcessError as e:
        print_color(f"Command failed: {e}", RED)
        if check:
            sys.exit(1)
        return e


def get_current_user():
    """Get the actual user, even when running with sudo."""
    return os.environ.get("SUDO_USER", os.getlogin())


def check_file_exists(path):
    """Check if a file exists and is accessible."""
    return os.path.isfile(path) and os.access(path, os.R_OK)


def check_package_installed(pkg_name):
    """Check if a Debian package is installed."""
    try:
        result = run_command(["dpkg", "-s", pkg_name], check=False, capture_output=True)
        return result.returncode == 0
    except Exception:
        return False

def install_missing_packages(distro, missing_packages, check = True):
    """Install missing packages using the appropriate package manager.
    
    Args:
        distro: The Linux distribution
        missing_packages: List of packages to install
    """
    if not missing_packages:  # Safeguard against empty lists
        print_color("No packages to install", YELLOW)
        return
        
    cmd_list = INSTALL_COMMANDS[distro].copy()  # Create a copy of the list
    cmd_list.extend(missing_packages)  # Modify the copy
    run_command(cmd_list, check=check)  # Pass the modified list

def add_docker_repository(distro, codename) -> None:
    """Add the proper repository for the detected distribution."""
    if distro not in REPO_STRINGS:
        raise RuntimeError(f"Unsupported distribution: {distro}")
    
    architecture = get_architecture()
    
    repo_string = REPO_STRINGS[distro].format(architecture=architecture, release=codename)
    repo_path = REPO_PATHS[distro]

    if os.path.exists(repo_path):
        return  # Exit early if the repository file already exists

    with open(repo_path, "w") as f:
        f.write(repo_string)

    update_command = UPDATE_COMMANDS[distro].split()
    run_command(update_command, check=True)  # Update the package list
    print_color("Repository added successfully.", GREEN)

    
def install_docker_packages(distro, codename):
    """Install Docker packages using the appropriate package manager.
    
    Args:
        distro: The Linux distribution
    """
    if check_package_installed("docker"):
        print_color("Docker is already installed.", GREEN)
        new_docker = False
    else:
        print_color("Docker is not installed. Installing...", YELLOW)
        new_docker = True
        # check keyring file existing
        if not check_file_exists(KEYRING_PATH):
            print_color("Docker keyring file is missing. Installing...", YELLOW)
            run_command(['curl', '-fsSL', GPG_KEYS[distro], '| gpg --dearmor -o ', KEYRING_PATH], check=True)
        else:
            print_color("Docker keyring file is already installed.", GREEN)
        
        # check if the repository is already added
        if not check_file_exists(REPO_PATHS[distro]):
            print_color("Docker repository is missing. Adding...", YELLOW)
            add_docker_repository(distro, codename)
        else:
            print_color("Docker repository already exist.", GREEN)
        
        missing_packages = []
        for pkg in REQUIRED_DOCKER_PKGS:
            print(f"Checking for package: {pkg}")  # Debug print
            if not check_package_installed(pkg):
                print_color(f"Package {pkg} is missing.", YELLOW)
                missing_packages.append(pkg)
            else:
                print_color(f"Package {pkg} is already installed.", GREEN)

        print(f"Missing packages: {missing_packages}")  # Debug print

        if missing_packages:
            print_color(f"Installing missing packages: {', '.join(missing_packages)}", BLUE)
            print("Calling install_missing_packages...")  # Debug print
            print(f"Detected missing packages: {missing_packages}")  # Debug statement
            print(f"Calling install_missing_packages with: {missing_packages}")  # Debug statement
            install_missing_packages(distro, missing_packages, check = False)
        else:
            print_color("All required packages are already installed.", GREEN)
        
        docker_version = run_command(["docker", "--version"], check=False, capture_output=True)
        print_color(f"Docker version: {docker_version.stdout}", GREEN)
        docker_compose_version = run_command(["docker-compose", "--version"], check=False, capture_output=True)
        print_color(f"Docker Compose version: {docker_compose_version.stdout}", GREEN)
        if new_docker:
            run_command(["systemctl", "enable", "docker"], check=True)
            run_command(["groupadd", "-f", "docker"], check=True)    
            running_user = os.environ.get("SUDO_USER", os.getlogin())
            run_command(["usermod", "-aG", "docker", running_user], check=True)
            print(f"Docker installed and user {running_user} added to docker group.")
            print("Please log out and back in for group membership to apply.")
        
        print_color("Docker installation complete!", GREEN)

def get_architecture() -> str:
    bits, linkage = platform.architecture()
    machine = platform.machine().lower()
    
    # First try the combination of bits and linkage
    if (bits, linkage) in ARCH_MAPPING:
        return ARCH_MAPPING[(bits, linkage)]
    
    # Fall back to machine type for ARM architectures
    if 'arm' in machine or 'aarch' in machine:
        return 'arm64'
    
    # Default to amd64 for 64-bit systems, i386 for others
    return 'amd64' if '64' in bits else 'i386'

def install_required_packages(distro):
    """Install required packages for the detected distribution.
    
    Args:
        distro: The Linux distribution
    """
    missing_packages = []
    for pkg in REQUIRED_PKGS:
        print(f"Checking for package: {pkg}")  # Debug print
        if not check_package_installed(pkg):
            print_color(f"Package {pkg} is missing.", YELLOW)
            missing_packages.append(pkg)
        else:
            print_color(f"Package {pkg} is already installed.", GREEN)

    print(f"Missing packages: {missing_packages}")  # Debug print

    if missing_packages:
        print_color(f"Installing missing packages: {', '.join(missing_packages)}", BLUE)
        print("Calling install_missing_packages...")  # Debug print
        print(f"Detected missing packages: {missing_packages}")  # Debug statement
        print(f"Calling install_missing_packages with: {missing_packages}")  # Debug statement
        install_missing_packages(distro, missing_packages)
    else:
        print_color("All required packages are already installed.", GREEN)

def install_python_packages(distro):
    """Install Python packages using the appropriate package manager.
    
    Args:
        distro: The Linux distribution
    """
    # Ensure Python >= 3.12 is installed
    executed_python_version = run_command(["python3", "--version"], check=False, capture_output=True)
    #parse result
    python_version = executed_python_version.stdout.split()[1]
    major, minor, _ = map(int, python_version.split('.'))
    if major < 3 or (major == 3 and minor < 12):
        print_color("Python version is less than 3.12. Going to update", YELLOW)
        install_missing_packages(distro, ["python3"])
    else:
        print_color("Python version is 3.12 or greater. No need to update", GREEN)
    
    missing_python_packages = []
    for pkg in REQUIRED_PYTHON_PKGS:
        print(f"Checking for Python package: {pkg}")  # Debug print
        if not check_package_installed(pkg):
            print_color(f"Python package {pkg} is missing.", YELLOW)
            missing_python_packages.append(pkg)
        else:
            print_color(f"Python package {pkg} is already installed.", GREEN)

    print(f"Missing Python packages: {missing_python_packages}")  # Debug print

    if missing_python_packages:
        print_color(f"Installing missing Python packages: {', '.join(missing_python_packages)}", BLUE)
        print("Calling install_missing_packages for Python packages...")  # Debug print
        install_missing_packages(distro, missing_python_packages)
    else:
        print_color("All required Python packages are already installed.", GREEN)
    
def install_packages(distro, codename, install_source):
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
