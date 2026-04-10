#!/bin/bash

# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

cd "$(dirname "$0")/.."

PYTHON_BIN=".venv/bin/python3"
if [ -x "$PYTHON_BIN" ]; then
  PYTHON="$PYTHON_BIN"
else
  PYTHON="python3"
fi

OS_NAME="$(uname -s)"

# If no arguments or --help, run without sudo
if [ $# -eq 0 ] || [[ "$1" == "--help" ]]; then
  PYTHONPATH=src $PYTHON -m installer.install "$@"
elif [ "$OS_NAME" = "Darwin" ] && [ "$1" = "uninstall" ]; then
  sudo PYTHONPATH=src $PYTHON -m installer.install "$@"
elif [ "$OS_NAME" = "Darwin" ]; then
  PYTHONPATH=src $PYTHON -m installer.install "$@"
else
  sudo PYTHONPATH=src $PYTHON -m installer.install "$@"
fi
