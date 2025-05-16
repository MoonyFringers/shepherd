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

import argparse
import os
import sys
from pathlib import Path
from typing import Any

# Import utility functions
from installer.install_utils import (
    BLUE,
    GREEN,
    RED,
    get_os_info,
    install_packages,
    is_root,
    print_color,
    run_command,
)

# Configuration variables
script_dir = Path(__file__).parent.resolve()
py_src_dir = (script_dir.parent / "src").resolve()

# Get environment variables with defaults
install_shepctl_dir = os.environ.get("INSTALL_SHEPCTL_DIR", "/opt/shepctl")
install_shepctl_dir = Path(install_shepctl_dir).resolve()
symlink_dir = os.environ.get("SYMLINK_DIR", "/usr/local/bin")
symlink_dir = Path(symlink_dir)

version = os.environ.get("VER", "latest")
url = (
    f"https://github.com/LunaticFringers/shepherd/releases/download/"
    f"v{version}/shepctl-{version}.tar.gz"
)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Shepherd Control Tool Installer",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "-m",
        "--install-method",
        choices=["binary", "source"],
        default="binary",
        help=(
            "Specify the installation method (binary or source). "
            "Default is binary."
        ),
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose mode."
    )

    parser.add_argument(
        "-s",
        "--skip-deps",
        action="store_true",
        help="Skip ensuring dependencies.",
    )

    parser.add_argument(
        "command", choices=["install", "uninstall"], help="Command to execute."
    )

    return parser.parse_args()


def install_binary() -> None:
    """Install shepctl from binary release."""
    install_shepctl_dir: Path = Path(
        os.environ.get("INSTALL_SHEPCTL_DIR", "/opt/shepctl")
    ).resolve()
    version: str = os.environ.get("VER", "latest")
    url: str = (
        f"https://github.com/LunaticFringers/shepherd/releases/download/"
        f"v{version}/shepctl-{version}.tar.gz"
    )

    # Download the binary
    print_color("Downloading shepctl binary...", BLUE)
    run_command(
        [
            "curl",
            "-fsSL",
            url,
            "-o",
            f"{install_shepctl_dir}/shepctl-{version}.tar.gz",
        ],
        check=True,
    )

    # Extract the tar.gz file
    print_color("Extracting...", BLUE)
    run_command(
        [
            "tar",
            "-xzf",
            f"{install_shepctl_dir}/shepctl-{version}.tar.gz",
            "-C",
            str(install_shepctl_dir),
        ],
        check=True,
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


def install_source() -> None:
    """Install shepctl from source."""
    install_shepctl_dir: Path = Path(
        os.environ.get("INSTALL_SHEPCTL_DIR", "/opt/shepctl")
    ).resolve()
    symlink_dir: Path = Path(
        os.environ.get("SYMLINK_DIR", "/usr/local/bin")
    ).resolve()

    print_color("Installing shepctl from source...", BLUE)

    # Clone the repo
    print_color("Cloning repository...", BLUE)
    run_command(
        [
            "git",
            "clone",
            "https://github.com/LunaticFringers/shepherd.git",
            str(install_shepctl_dir),
        ],
        check=True,
    )

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

    # Create symlink if it doesn't exist
    bin_path = install_shepctl_dir / "bin" / "shepctl"
    symlink_path = symlink_dir / "shepctl"

    if symlink_path.exists():
        symlink_path.unlink()

    print_color(f"Creating symlink in {symlink_dir}...", BLUE)
    os.symlink(str(bin_path), symlink_path)

    print_color("Source installation complete!", GREEN)


def install() -> None:
    """Install shepctl."""
    print_color("Installing shepctl...", BLUE)

    if not skip_ensure_deps:
        print_color("Ensuring dependencies...", BLUE)

        os_info: Any = get_os_info()

        # Manage dependencies based on OS
        install_packages(
            os_info.distro,
            os_info.codename,
            install_method == "source",
        )

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


def uninstall() -> None:
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


def main() -> None:
    # Check if running as root
    if not is_root():
        print_color("This script must be run as root.", RED)
        sys.exit(1)

    args: argparse.Namespace = parse_arguments()

    # Store arguments for use in other functions
    global verbose, skip_ensure_deps, install_method
    verbose = args.verbose
    skip_ensure_deps = args.skip_deps
    install_method = args.install_method

    # Execute the requested command
    if args.command == "install":
        install()
    elif args.command == "uninstall":
        uninstall()
    else:
        sys.exit(1)


if __name__ == "__main__":
    # Global variables to store command line options
    verbose = False
    skip_ensure_deps = False
    install_method = "binary"

    # Run the main function
    main()
