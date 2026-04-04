# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

import logging
import os
import sys


def setup_logging(
    log_file: str,
    format: str,
    log_level: str,
    to_stdout: bool,
):
    """
    Configure root logging handlers for file and optional stdout output.

    The function is intentionally idempotent-friendly: it ensures log file path
    existence before handing it to `FileHandler`, then delegates formatting and
    level setup to `logging.basicConfig`.
    """
    level = getattr(logging, log_level.upper(), logging.WARNING)
    handlers: list[logging.Handler] = []

    if log_file:
        log_path = os.path.expanduser(log_file)
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        if not os.path.exists(log_path):
            with open(log_path, "a"):
                pass
        file_handler = logging.FileHandler(log_path)
        handlers.append(file_handler)

    if to_stdout:
        stream_handler = logging.StreamHandler(sys.stdout)
        handlers.append(stream_handler)

    logging.basicConfig(level=level, format=format, handlers=handlers)
