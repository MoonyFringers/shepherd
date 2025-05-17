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
import shutil
import subprocess

APP_NAME = "shepctl"
ENTRY_FILE = "shepctl.py"
ICON_PATH = "resources/icon.ico"
EXCLUDE_LIBS: list[str] = []
EXTRA_FILES = ["resources/shpd.conf"]
VERSION_FILE = "version"

git_tagging = False  # Default Git tagging (disabled)


def read_version() -> str:
    """Read the version from the version file."""
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r") as f:
            version = f.read().strip()
            return version
    else:
        return "0.0.0"


def clean():
    """Remove previous build files."""
    folders = ["build", "dist", f"{APP_NAME}.spec"]
    for folder in folders:
        if os.path.exists(folder):
            if os.path.isdir(folder):
                shutil.rmtree(folder)
            else:
                os.remove(folder)


def git_tag(version: str):
    """Create and push Git tag."""
    tag = f"v{version}"
    subprocess.run(["git", "tag", tag], check=True)
    subprocess.run(["git", "push", "origin", "--tags"], check=True)


def copy_resources():
    """Copy resource files to dist directory."""
    dist_dir = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "..", "dist"
    )
    if not os.path.exists(dist_dir):
        os.makedirs(dist_dir)

    for file in EXTRA_FILES + [VERSION_FILE]:
        if os.path.exists(file):
            destination = os.path.join(dist_dir, os.path.basename(file))
            shutil.copy(file, destination)


def build(debug: bool = False):
    """Build the app."""
    version = read_version()

    cmd = [
        "pyinstaller",
        "--onefile",
        "--name",
        f"{APP_NAME}",
        "--clean",
        "--distpath",
        "../dist",
    ]

    if os.path.exists(ICON_PATH):
        cmd += ["--icon", ICON_PATH]

    for lib in EXCLUDE_LIBS:
        cmd += ["--exclude", lib]

    if debug:
        cmd += ["--log-level", "DEBUG"]

    cmd.append(ENTRY_FILE)
    subprocess.run(cmd, check=True)

    copy_resources()

    if git_tagging:
        git_tag(version)


def main():
    script_dir = os.path.dirname(os.path.realpath(__file__))
    os.chdir(script_dir)

    parser = argparse.ArgumentParser(
        description="Automate PyInstaller Build Process"
    )
    parser.add_argument(
        "--clean", action="store_true", help="Clean previous builds"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug logs"
    )
    parser.add_argument("--git", action="store_true", help="Enable Git tagging")
    parser.add_argument(
        "--version", action="store_true", help="Show app version"
    )

    args = parser.parse_args()

    if args.version:
        version = read_version()
        return

    if args.clean:
        clean()

    global git_tagging
    if args.git:
        git_tagging = True

    build(debug=args.debug)


if __name__ == "__main__":
    main()
