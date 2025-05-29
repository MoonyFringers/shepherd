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
from pathlib import Path
from typing import Any

import click

from installer import constants

# Import utility functions
from installer.install_utils import (
    BLUE,
    GREEN,
    RED,
    download_package,
    extract_package,
    get_os_info,
    install_packages,
    is_root,
    print_color,
    run_command,
)

# Global variables to store command line options
verbose = False
skip_ensure_deps = False
install_method = "binary"
force_source_download = False

# Configuration variables
script_dir = Path(__file__).parent.resolve()
py_src_dir = (script_dir.parent / "src").resolve()

# Get environment variables with defaults
install_shepctl_dir = os.environ.get("INSTALL_SHEPCTL_DIR", "/opt/shepctl")
install_shepctl_dir = Path(install_shepctl_dir).resolve()
symlink_dir = os.environ.get("SYMLINK_DIR", "/usr/local/bin")
symlink_dir = Path(symlink_dir)


@click.group()
@click.option(
    "-m",
    "--install-method",
    type=click.Choice(["binary", "source"]),
    default="binary",
    help="Specify the installation method (binary or source).",
)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose mode.")
@click.option(
    "-s",
    "--skip-deps",
    is_flag=True,
    help="Skip ensuring dependencies.",
)
@click.option(
    "-f",
    "--force-source-download",
    is_flag=True,
    help="Force source download during source installation.",
)
@click.pass_context
def cli(
    ctx: click.Context,
    install_method: str,
    verbose: bool,
    skip_deps: bool,
    force_source_download: bool,
) -> None:
    """Shepherd Control Tool Installer"""
    if ctx.obj is None:
        ctx.obj = {}

    # Store options in context for subcommands
    ctx.obj["install_method"] = install_method
    ctx.obj["verbose"] = verbose
    ctx.obj["skip_deps"] = skip_deps
    ctx.obj["force_source_download"] = force_source_download


@cli.command()
@click.pass_context
def install(ctx: click.Context) -> None:
    """Install shepctl."""
    # Check if running as root
    if not is_root():
        print_color("This script must be run as root.", RED)
        sys.exit(1)

    # Get options from context
    global verbose, skip_ensure_deps, install_method
    verbose = ctx.obj["verbose"]
    skip_ensure_deps = ctx.obj["skip_deps"]
    install_method = ctx.obj["install_method"]

    install_shepctl()


@cli.command()
@click.pass_context
def uninstall(ctx: click.Context) -> None:
    """Uninstall shepctl."""
    # Check if running as root
    if not is_root():
        print_color("This script must be run as root.", RED)
        sys.exit(1)

    # Get options from context
    global verbose, skip_ensure_deps, install_method
    verbose = ctx.obj["verbose"]
    skip_ensure_deps = ctx.obj["skip_deps"]
    install_method = ctx.obj["install_method"]

    uninstall_shepctl()


def install_binary() -> None:
    """Install shepctl from binary release."""
    install_shepctl_dir: str = os.environ.get(
        "INSTALL_SHEPCTL_DIR", "/opt/shepctl"
    )

    version = os.environ.get("VER", "latest")
    url = (
        f"https://github.com/LunaticFringers/shepherd/releases/download/"
        f"v{version}/shepctl-{version}.tar.gz"
    )

    # Download the binary
    print_color("Downloading shepctl binary...", BLUE)
    download_package(url, f"{install_shepctl_dir}/shepctl-{version}.tar.gz")

    # Extract the tar.gz file
    print_color("Extracting...", BLUE)
    extract_package(
        f"{install_shepctl_dir}/shepctl-{version}.tar.gz",
        str(install_shepctl_dir),
    )

    # Make the binary executable
    print_color("Setting permissions...", BLUE)
    os.chmod(f"{install_shepctl_dir}/shepctl", 0o755)

    # Create symlink if it doesn't exist
    symlink_dir = Path(
        os.environ.get("SYMLINK_DIR", "/usr/local/bin")
    ).resolve()
    symlink_path = symlink_dir / "shepctl"
    if not symlink_path.exists():
        print_color("Creating symlink...", BLUE)
        os.symlink(f"{install_shepctl_dir}/shepctl", symlink_path)


def manage_dependencies() -> None:
    print_color("Ensuring dependencies...", BLUE)

    os_info: Any = get_os_info()

    # Manage dependencies based on OS
    install_packages(
        os_info.distro,
        os_info.codename,
        install_method == "source",
    )


def manage_python_dependencies() -> None:
    # Install Python dependencies
    print_color("Installing Python dependencies...", BLUE)

    # Save current directory
    original_dir = os.getcwd()
    os.chdir(install_shepctl_dir)

    try:
        # Use pip to install
        python_path = sys.executable
        run_command(
            [
                python_path,
                "-m",
                "pip",
                "install",
                "-e",
                f"{install_shepctl_dir}",
            ],
            check=True,
        )
    finally:
        # Restore original directory
        os.chdir(original_dir)


def should_download_sources(install_shepctl_dir: str) -> bool:
    """Check if sources should be downloaded."""
    if force_source_download:  # Source download is forced by user
        print_color(
            "Forcing source download as per user request.",
            BLUE,
        )
        return True
    elif (
        not Path(install_shepctl_dir).exists()
        or not any(Path(install_shepctl_dir).iterdir())
        # The directory does not exist or is empty
    ):
        print_color(
            f"Directory {install_shepctl_dir} does not exist or is empty. "
            "Downloading sources...",
            BLUE,
        )
        return True
    else:
        # The directory exists and is not empty, should not download again
        print_color(
            f"Directory {install_shepctl_dir} already exists and is not empty. "
            "Assuming existing installation.",
            RED,
        )
        return False


def download_sources(install_shepctl_dir: str, version: str) -> None:
    print_color("Downloading and extracting source package", BLUE)
    download_package(
        constants.SHEPCTL_SOURCE_URL.format(version=version),
        f"{install_shepctl_dir}/shepctl-{version}.tar.gz",
    )

    extract_package(
        f"{install_shepctl_dir}/shepctl-{version}.tar.gz",
        install_shepctl_dir,
    )


def manage_source_symlinks() -> None:
    bin_path: Path = Path(install_shepctl_dir) / "bin" / "shepctl"
    symlink_dir: Path = Path(
        os.environ.get("SYMLINK_DIR", "/usr/local/bin")
    ).resolve()
    symlink_path = symlink_dir / "shepctl"

    if symlink_path.exists():
        symlink_path.unlink()

    print_color(f"Creating symlink in {symlink_dir}...", BLUE)
    os.symlink(str(bin_path), symlink_path)


def install_source() -> None:
    """Install shepctl from source."""
    install_shepctl_dir: str = os.environ.get(
        "INSTALL_SHEPCTL_DIR", "/opt/shepctl"
    )

    version = os.environ.get("VER", "latest")

    # First of all..check if the directory already exists and it's not empty,
    # in this case we assume that the user wants to install the existing version
    # without downloading the sources again, so we will install shepctl
    if should_download_sources(install_shepctl_dir):
        download_sources(install_shepctl_dir, version)

    # Link do download the sources code package
    print_color("Installing shepctl from source...", BLUE)

    if not skip_ensure_deps:
        manage_python_dependencies()

    # Create symlink if it doesn't exist
    manage_source_symlinks()
    print_color("Source installation complete!", GREEN)


def install_shepctl() -> None:
    """Install shepctl."""
    print_color("Installing shepctl...", BLUE)

    if not skip_ensure_deps:
        manage_dependencies()

    # Clean existing installation if it exists
    if Path(install_shepctl_dir).exists():
        import shutil

        shutil.rmtree(Path(install_shepctl_dir))
    os.makedirs(Path(install_shepctl_dir), exist_ok=True)

    # Call appropriate installation function based on method
    if install_method == "binary":
        install_binary()
    elif install_method == "source":
        install_source()
    else:
        print_color(f"Error: Unknown install method '{install_method}'", RED)
        sys.exit(1)


def uninstall_shepctl() -> None:
    """Uninstall shepctl."""
    print_color("Uninstalling shepctl...", BLUE)

    # Remove installation directory
    if Path(install_shepctl_dir).exists():
        import shutil

        shutil.rmtree(install_shepctl_dir)
        print(f"Removed {install_shepctl_dir}")

    # Remove symlink
    symlink_path: Path = Path(symlink_dir) / "shepctl"
    if symlink_path.exists():
        symlink_path.unlink()
        print(f"Removed symlink {symlink_path}")

    print("shepctl uninstalled successfully")


execution_count = 0  # Global counter to track main function executions


if __name__ == "__main__":
    # Global variables to store command line options
    verbose = False
    skip_ensure_deps = False
    install_method = "binary"

    # Run the CLI
    cli()
