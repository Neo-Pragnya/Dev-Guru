"""``--logs FILE``: a record of what a command did, for when something goes wrong on someone else's machine.

It holds what helps to find a fault, and nothing that's a secret: the versions, the operating system, the folder and
the command line, then each step with how long it took, what it found, any warning and the full trace of any error.
It never holds environment variables, tokens or file contents.
"""

from __future__ import annotations

import logging
import os
import platform
import sys
from pathlib import Path

LOGGER = logging.getLogger("dev_guru")


def start(path: Path, command: str) -> Path:
    """Starts writing to ``path``, replacing what was there, and records where this is running."""
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.DEBUG)
    from dev_guru.version import __version__

    try:
        from ananke.plexus.version import __version__ as ananke
    except ImportError:
        ananke = "not installed"
    LOGGER.info("dev %s", command)
    LOGGER.info("Dev Guru %s, Ananke %s", __version__, ananke)
    LOGGER.info(
        "Python %s on %s (%s)", platform.python_version(), platform.platform(), platform.machine()
    )
    LOGGER.info("path separator %r, file system encoding %s", os.sep, sys.getfilesystemencoding())
    LOGGER.info("working folder %s", Path.cwd())
    LOGGER.info("arguments %s", " ".join(sys.argv[1:]))
    return path


def stop() -> None:
    for handler in list(LOGGER.handlers):
        handler.close()
        LOGGER.removeHandler(handler)


__all__ = ["LOGGER", "start", "stop"]
