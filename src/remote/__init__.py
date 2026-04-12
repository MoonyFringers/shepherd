# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Remote storage backends and orchestration manager."""

from .backend import RemoteBackend
from .ftp_backend import FTPBackend
from .remote_mng import RemoteMng
from .sftp_backend import SFTPBackend

__all__ = [
    "FTPBackend",
    "RemoteBackend",
    "RemoteMng",
    "SFTPBackend",
]
