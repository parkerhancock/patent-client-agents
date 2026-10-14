"""Helpers for the offline corpus-build smoke tests."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

_REAL_ASYNC_CLIENT = httpx.AsyncClient


def serve(
    monkeypatch: pytest.MonkeyPatch, pages: Callable[[httpx.Request], str | bytes | None]
) -> list[str]:
    """Route every ``httpx.AsyncClient`` the build creates to ``pages``.

    ``pages(request)`` returns the response body, or ``None`` for a 404.
    Returns the list of requested URLs, filled in as the build runs.
    """
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        body = pages(request)
        if body is None:
            return httpx.Response(404, text="not found")
        return httpx.Response(200, content=body.encode() if isinstance(body, str) else body)

    def client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(handler)
        return _REAL_ASYNC_CLIENT(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)
    return requested


def read_corpus(
    path: Path, *, table: str = "sections", columns: str = "*", order_by: str = "rowid"
) -> tuple[list[sqlite3.Row], dict[str, str]]:
    """Return ``(rows, meta)`` from a built corpus."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(f"SELECT {columns} FROM {table} ORDER BY {order_by}").fetchall()
        meta = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM meta")}
    finally:
        conn.close()
    return rows, meta


def today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")
