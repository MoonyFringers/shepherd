# Copyright (c) 2025 Moony Fringers
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
