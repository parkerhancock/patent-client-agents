"""Tests for shared logging configuration."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from law_tools_core import logging as core_logging


def test_configure_uses_env_log_dir(monkeypatch, tmp_path: Path) -> None:
    app_name = "test_logging_env"
    monkeypatch.setenv("LAW_TOOLS_CORE_LOG_DIR", str(tmp_path))

    log_file = core_logging.configure(app_name)

    assert log_file == tmp_path / f"{app_name}.log"
    logging.getLogger(app_name).error("test message")
    assert log_file.exists()


def test_configure_falls_back_to_tempdir_when_file_handler_fails(monkeypatch) -> None:
    app_name = "test_logging_fallback"
    original_file_handler = core_logging.logging.FileHandler
    calls: list[Path] = []

    def flaky_file_handler(path: Path, *args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        calls.append(Path(path))
        if len(calls) == 1:
            raise OSError("not writable")
        return original_file_handler(path, *args, **kwargs)

    monkeypatch.setattr(core_logging.logging, "FileHandler", flaky_file_handler)

    log_file = core_logging.configure(app_name)

    assert calls[0].name == f"{app_name}.log"
    assert log_file == Path(tempfile.gettempdir()) / app_name / f"{app_name}.log"
