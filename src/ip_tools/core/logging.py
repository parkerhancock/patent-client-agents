"""Logging configuration for ip_tools.

Configures file-based logging so that full tracebacks are written to a log file
rather than polluting the agent's context window. Error messages include the
log file path so agents can selectively inspect details when needed.
"""

from __future__ import annotations

import logging
from pathlib import Path

LOG_DIR = Path.home() / ".cache" / "ip_tools"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "ip_tools.log"

_configured = False


def configure_logging() -> None:
    """Configure file-based logging for ip_tools.

    Sets up a FileHandler on the root ``ip_tools`` logger so all submodule
    loggers (``ip_tools.google_patents``, ``ip_tools.epo_ops``, etc.) write
    to the shared log file. Called once at import time.
    """
    global _configured  # noqa: PLW0603
    if _configured:
        return
    _configured = True

    root_logger = logging.getLogger("ip_tools")
    root_logger.setLevel(logging.DEBUG)

    handler = logging.FileHandler(LOG_FILE)
    handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    root_logger.addHandler(handler)


# Configure on import so all ip_tools loggers get the file handler
configure_logging()

__all__ = ["LOG_DIR", "LOG_FILE", "configure_logging"]
