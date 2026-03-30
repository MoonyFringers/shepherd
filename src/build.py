# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.io.

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
            print(f"[📄] Version read from file: {version}")
            return version
    else:
        print(f"[❗] Version file not found: {VERSION_FILE}")
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
            print(f"[✅] Removed: {folder}")


def git_tag(version: str):
    """Create and push Git tag."""
    tag = f"v{version}"
    print(f"[🔖] Creating Git tag: {tag}")

    subprocess.run(["git", "tag", tag], check=True)
    subprocess.run(["git", "push", "origin", "--tags"], check=True)
    print("[🚀] Git tag pushed")


def copy_resources():
    """
    Copy runtime support files next to the built binary in `../dist`.

    PyInstaller packages the executable; this step keeps external config/version
    artifacts available for runtime and release packaging.
    """
    dist_dir = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "..", "dist"
    )
    if not os.path.exists(dist_dir):
        os.makedirs(dist_dir)

    for file in EXTRA_FILES + [VERSION_FILE]:
        if os.path.exists(file):
            destination = os.path.join(dist_dir, os.path.basename(file))
            shutil.copy(file, destination)
            print(f"[📄] Copied: {file} -> {destination}")


def build(debug: bool = False):
    """
    Build the CLI as a single-file PyInstaller artifact.

    The command writes binaries to `../dist` (relative to `src/`) so release
    scripts can consume a stable output path.
    """
    version = read_version()
    print(f"\n[🚀] Building {APP_NAME} v{version}...")

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
        print(f"[🔑] Icon: {ICON_PATH}")

    for lib in EXCLUDE_LIBS:
        cmd += ["--exclude", lib]
        print(f"[🚫] Excluding: {lib}")

    if debug:
        cmd += ["--log-level", "DEBUG"]
        print("[🐞] Debug mode enabled")

    cmd.append(ENTRY_FILE)
    subprocess.run(cmd, check=True)
    print(f"[✅] Build completed: dist/{APP_NAME}")

    copy_resources()

    if git_tagging:
        git_tag(version)


def main():
    """
    CLI entrypoint for build automation.

    Option semantics:
    - `--clean` only removes previous artifacts before build.
    - `--git` enables post-build tag creation/push.
    - `--version` prints version and exits without building.
    """
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
        print(f"{APP_NAME} v{version}")
        return

    if args.clean:
        clean()

    global git_tagging
    if args.git:
        git_tagging = True
        print("[🔖] Git tagging enabled")

    build(debug=args.debug)


if __name__ == "__main__":
    main()
