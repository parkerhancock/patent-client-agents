"""Logging configuration for consumer libraries.

Configures file-based logging so that full tracebacks are written to a log file
rather than polluting the agent's context window. Error messages include the
log file path so agents can selectively inspect details when needed.

Each consumer library (consumer libraries) calls ``configure`` once at
import time with its own app name. Exception ``__str__`` methods consult
``log_file_hint`` to append the appropriate log path to error messages.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

_configured_log_files: dict[str, Path] = {}
_default_app: str | None = None


def configure(app_name: str, log_dir: Path | None = None) -> Path:
    """Configure file-based logging for a consumer app.

    Attaches a ``FileHandler`` to the ``app_name`` logger so all submodule
    loggers under that name write to ``{log_dir}/{app_name}.log``. Idempotent:
    calling twice with the same ``app_name`` returns the same path without
    adding duplicate handlers.

    Args:
        app_name: Root logger name for the app (e.g. ``"patent_client_agents"``). Used as
            both the logger name and the log filename stem.
        log_dir: Override the log directory. Defaults to
            ``$LAW_TOOLS_CORE_LOG_DIR`` when set, otherwise
            ``~/.cache/{app_name}``. If that path is not writable, falls
            back to ``{tempdir}/{app_name}``.

    Returns:
        Absolute path to the log file.
    """
    global _default_app  # noqa: PLW0603
    if _default_app is None:
        _default_app = app_name

    if app_name in _configured_log_files:
        return _configured_log_files[app_name]

    env_log_dir = os.environ.get("LAW_TOOLS_CORE_LOG_DIR")
    log_dir = log_dir or (Path(env_log_dir) if env_log_dir else Path.home() / ".cache" / app_name)
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        log_dir = Path(tempfile.gettempdir()) / app_name
        log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{app_name}.log"

    logger = logging.getLogger(app_name)
    logger.setLevel(logging.DEBUG)
    try:
        handler = logging.FileHandler(log_file)
    except OSError:
        log_dir = Path(tempfile.gettempdir()) / app_name
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{app_name}.log"
        handler = logging.FileHandler(log_file)
    handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    _configured_log_files[app_name] = log_file

    return log_file


def log_file_hint() -> str:
    """Return a ``"details: <path>"`` fragment for inclusion in error messages.

    If multiple apps have configured logging in the same process (e.g. both
    multiple consumers are loaded), all configured paths are listed. If
    nothing has been configured, returns an empty string.
    """
    if not _configured_log_files:
        return ""
    paths = list(_configured_log_files.values())
    if len(paths) == 1:
        return f"details: {paths[0]}"
    return "details: " + ", ".join(str(p) for p in paths)


def default_app_name() -> str:
    """Return the first-configured app name, or ``"app"`` if none."""
    return _default_app or "app"


__all__ = ["configure", "log_file_hint", "default_app_name"]
