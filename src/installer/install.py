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
import pwd
import shutil
import sys
from pathlib import Path
from typing import Any

import click

from installer.repository_manager import RepositoryManager
from util import Util, constants

# Command line options
verbose = False
skip_ensure_deps = False
install_method = "binary"
force_source_download = False

# Configuration
exec_dir = Path(__file__).parent.resolve()
py_src_dir = (exec_dir.parent).resolve()

# Environment variables with defaults
install_shepctl_dir = Path(
    os.environ.get("INSTALL_SHEPCTL_DIR", "/opt/shepctl")
).resolve()
symlink_dir = Path(os.environ.get("SYMLINK_DIR", "/usr/local/bin")).resolve()


####################################################
# Parse command line options and define the context
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
    # Installer needs to run as root
    # to install system-wide
    if not Util.is_root():
        Util.print_error_and_die("This script must be run as root")

    global verbose, skip_ensure_deps, install_method
    verbose = ctx.obj["verbose"]
    skip_ensure_deps = ctx.obj["skip_deps"]
    install_method = ctx.obj["install_method"]

    install_shepctl()  # Use the patchable alias


@cli.command()
@click.pass_context
def uninstall(ctx: click.Context) -> None:
    """Uninstall shepctl."""
    if not Util.is_root():
        Util.print_error_and_die("This script must be run as root")

    # Get options from context
    global verbose, skip_ensure_deps, install_method
    verbose = ctx.obj["verbose"]
    skip_ensure_deps = ctx.obj["skip_deps"]
    install_method = ctx.obj["install_method"]

    uninstall_shepctl()  # Use the patchable alias


def install_binary() -> None:
    """Install shepctl from binary release."""
    install_shepctl_dir: str = os.environ.get(
        "INSTALL_SHEPCTL_DIR", "/opt/shepctl"
    )

    version = os.environ.get("VER", "latest")
    url = constants.SHEPCTL_BINARY_URL.format(version=version)

    Util.console.print(
        f"[bold blue]Downloading shepctl binary from {url}...[/bold blue]"
    )
    Util.download_package(
        url,
        f"{install_shepctl_dir}/shepctl-{version}.tar.gz",
    )

    Util.console.print("[bold blue]Extracting...[/bold blue]")
    Util.extract_package(
        f"{install_shepctl_dir}/shepctl-{version}.tar.gz",
        str(install_shepctl_dir),
    )

    Util.console.print("[bold blue]Setting permissions...[/bold blue]")
    os.chmod(f"{install_shepctl_dir}/shepctl", 0o755)

    symlink_dir = Path(
        os.environ.get("SYMLINK_DIR", "/usr/local/bin")
    ).resolve()
    symlink_path = symlink_dir / "shepctl"
    if not symlink_path.exists():
        Util.console.print(
            f"[bold blue]Creating symlink in {symlink_dir}...[/bold blue]"
        )
        os.symlink(f"{install_shepctl_dir}/shepctl", symlink_path)


def manage_dependencies() -> None:
    Util.console.print("Ensuring dependencies...", style="blue")

    os_info: Any = Util.get_os_info()  # Use the patchable alias

    # Manage dependencies based on OS
    RepositoryManager.install_packages(
        os_info.distro,
        os_info.codename,
        install_method == "source",
    )


def manage_python_dependencies() -> None:
    Util.console.print("Installing Python dependencies...", style="blue")

    # Save current directory
    original_dir = os.getcwd()
    os.chdir(install_shepctl_dir)

    try:
        python_path = sys.executable
        Util.run_command(
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


# Symbolic links management for source files
# (set to /usr/local/bin by default)
def manage_source_symlinks() -> None:
    bin_path: Path = Path(install_shepctl_dir) / "bin" / "shepctl"
    symlink_dir: Path = Path(
        os.environ.get("SYMLINK_DIR", "/usr/local/bin")
    ).resolve()
    symlink_path = symlink_dir / "shepctl"

    if symlink_path.exists():
        symlink_path.unlink()

    Util.console.print(f"Creating symlink in {symlink_dir}...", style="blue")
    os.symlink(str(bin_path), symlink_path)


def copy_python_sources(src_dir: Path, dest_dir: Path) -> None:
    """Recursively copy all .py files from src_dir to dest_dir, preserving
    directory structure."""
    Util.console.print(
        f"Copying Python source files from {src_dir} to {dest_dir}...",
        style="blue",
    )
    for py_file in src_dir.rglob("*.py"):
        relative_path = py_file.relative_to(src_dir)
        target_path = dest_dir / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(py_file, target_path)


def install_requirements_in_venv(py_src_dir: Path, venv_path: Path) -> None:
    """
    Install dependencies from requirements.txt into the given virtualenv.
    - Upgrades pip in the virtual environment.
    - Installs all dependencies listed in requirements.txt.
    - Exits with error if requirements.txt is missing or installation fails.
    """
    pip_path = venv_path / "bin" / "pip"
    req_file = py_src_dir / "requirements.txt"
    Util.console.print(
        "Installing dependencies into virtual environment...", style="blue"
    )
    if req_file.exists():
        try:
            Util.run_command(
                [str(pip_path), "install", "--upgrade", "pip"], check=True
            )
            Util.run_command(
                [str(pip_path), "install", "-r", str(req_file)], check=True
            )
        except Exception as e:
            Util.console.print(
                f"Failed to install dependencies: {e}[", style="red"
            )
            sys.exit(1)
    else:
        Util.console.print(
            f"requirements.txt not found in {py_src_dir}", style="red"
        )
        sys.exit(1)


# Shepherd source files installer (for development purposes)
def install_source() -> None:
    """Install shepctl from source."""
    install_shepctl_dir: Path = Path(
        os.environ.get("INSTALL_SHEPCTL_DIR", "/opt/shepctl")
    ).resolve()

    # Ensure the installation directory exists
    if not install_shepctl_dir.exists():
        Util.console.print(
            f"Creating installation directory: {install_shepctl_dir}",
            style="blue",
        )
        os.makedirs(install_shepctl_dir, exist_ok=True)

    copy_python_sources(py_src_dir, install_shepctl_dir)
    set_py_permissions(install_shepctl_dir)
    venv_path = create_virtualenv(install_shepctl_dir)
    install_requirements_in_venv(py_src_dir, venv_path)
    create_wrapper_script(install_shepctl_dir, symlink_dir)

    Util.console.print(
        "shepctl installed from source with isolated dependencies.",
        style="green",
    )
    Util.console.print("You can now run it with: shepctl", style="green")


def set_py_permissions(dest_dir: Path) -> None:
    """Set permissions 664 for all .py files in dest_dir recursively."""
    for py_file in dest_dir.rglob("*.py"):
        py_file.chmod(0o664)


def install_shepctl() -> None:
    Util.console.print("Installing shepctl...", style="blue")

    if not skip_ensure_deps:
        manage_dependencies()

    # Clean existing installation if it exists
    if Path(install_shepctl_dir).exists():
        shutil.rmtree(Path(install_shepctl_dir))
    os.makedirs(Path(install_shepctl_dir), exist_ok=True)

    if install_method == "binary":
        install_binary()
    elif install_method == "source":
        install_source()
    else:
        Util.console.print(
            f"Error: Unknown install method '{install_method}'", style="red"
        )
        sys.exit(1)
    install_completion()


def get_script_completion_src() -> tuple[Path, str]:
    """
    Get the path to the shell completion script for shepctl.
    This is used to install the script in /etc/bash_completion.d.
    """
    scripts_dir = py_src_dir.parent.resolve() / "scripts"
    script_completion_name = "shepctl_completion.sh"
    return scripts_dir / script_completion_name, script_completion_name


def install_completion() -> None:
    """
    Install the shell completion script for shepctl if /etc/bash_completion.d
    exists.
    """
    completion_dir = Path("/etc/bash_completion.d")

    src, script_completion_filename = get_script_completion_src()
    dest = completion_dir / script_completion_filename

    if completion_dir.is_dir():
        Util.console.print(
            "Installing shell completion script...", style="blue"
        )
        try:
            shutil.copy2(src, dest)
            os.chmod(dest, 0o755)
            Util.console.print(
                "Shell completion script installed.", style="green"
            )
        except Exception as e:
            Util.console.print(
                f"Failed to install completion script: {e}", style="red"
            )
    else:
        Util.console.print(
            "Bash completion directory not found. Please install manually.",
            style="yellow",
        )


def uninstall_shepctl() -> None:
    """Uninstall shepctl."""
    Util.console.print("Uninstalling shepctl...", style="blue")

    # Remove installation directory
    if Path(install_shepctl_dir).exists():
        shutil.rmtree(install_shepctl_dir)
        Util.print(f"Removed {install_shepctl_dir}")

    # Remove symlink
    symlink_path: Path = Path(symlink_dir) / "shepctl"
    if symlink_path.exists():
        symlink_path.unlink()
        Util.print(f"Removed symlink {symlink_path}")

    # Remove autocompletion script
    completion_dir = Path("/etc/bash_completion.d")
    completion_script = completion_dir / "shepctl_completion.sh"
    if completion_script.exists():
        completion_script.unlink()
        Util.print(f"Removed completion script {completion_script}")

    Util.print("shepctl uninstalled successfully")


def create_wrapper_script(
    install_dir: Path, symlink_dir: Path, script_name: str = "shepctl"
) -> None:
    """
    Create a wrapper script in the symlink directory that runs shepctl.py
    using the Python interpreter from the virtual environment.
    """
    # Ensure the symlink directory exists
    symlink_dir.mkdir(parents=True, exist_ok=True)
    wrapper_path = symlink_dir / script_name
    venv_python = install_dir / ".venv" / "bin" / "python"
    shepctl_py = install_dir / "shepctl.py"
    # Write the wrapper script
    wrapper_content = (
        "#!/bin/bash\n" f'exec "{venv_python}" "{shepctl_py}" "$@"\n'
    )
    with open(wrapper_path, "w") as f:
        f.write(wrapper_content)
    # Make the script executable
    wrapper_path.chmod(0o755)


def create_virtualenv(install_dir: Path) -> Path:
    """
    Create a Python virtual environment in install_dir/.venv and set ownership
    of the entire .venv directory to the current user.
    Returns the Path to the created virtualenv.
    """
    Util.console.print("Creating Python virtual environment...", style="blue")
    python_path = sys.executable
    venv_path = install_dir / ".venv"
    if not venv_path.exists():
        Util.run_command(
            [python_path, "-m", "venv", str(venv_path)],
            check=True,
        )
    # Change ownership of the .venv directory to the current user
    user = Util.get_current_user()
    uid = pwd.getpwnam(user).pw_uid
    gid = pwd.getpwnam(user).pw_gid
    for root, dirs, files in os.walk(venv_path):
        os.chown(root, uid, gid)
        for d in dirs:
            os.chown(os.path.join(root, d), uid, gid)
        for f in files:
            os.chown(os.path.join(root, f), uid, gid)
    return venv_path


if __name__ == "__main__":
    cli()
