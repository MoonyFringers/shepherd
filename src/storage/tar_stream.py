# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

"""Produces an uncompressed tar byte stream from a Shepherd environment,
including host-mounted volumes (with sudo escalation when required)."""

from __future__ import annotations

from typing import IO


class TarStreamProducer:
    """Produces an uncompressed tar stream for a Shepherd environment.

    The stream covers:
    - The environment's data directory (``env.get_path()``).
    - All host-mounted volume paths declared in ``env_cfg.volumes``.

    When a volume path is not readable by the current process (e.g. DBMS data
    written under a non-root UID), the tar subprocess is spawned under ``sudo``,
    mirroring the existing ``_delete_dir_with_sudo`` pattern.
    """

    def stream(self) -> IO[bytes]:
        """Return a readable, uncompressed tar byte stream for the environment.

        The caller is responsible for closing the stream when done.
        """
        raise NotImplementedError  # TODO: Issue 4
