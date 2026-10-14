"""Provenance that reflects whether a tool call's data came from the HTTP cache.

CONNECTOR_STANDARDS §3: ``cache_hit`` is True only when no network round-trip
occurred, and ``retrieved_at`` is the original upstream fetch time, not the
cache-read time. A tool call can make several requests, so each response is
recorded during the call (``record_response``, installed on connector clients
by ``shared.client``) and ``provenance_for`` summarizes them: ``cache_hit`` if
every response came from cache, ``retrieved_at`` the oldest fetch among them.

Recording is scoped by ``track_fetches``; the MCP server's ``FetchTracking``
middleware (``patent_client_agents.mcp.middleware``) opens it for every tool
call. Outside that scope, or when a call made no HTTP requests,
``provenance_for`` behaves like ``make_provenance``.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

import httpx

from mcp_data_core.envelope import Provenance, make_provenance

# (served_from_cache, upstream fetch time as a Unix timestamp)
_fetches: ContextVar[list[tuple[bool, float]] | None] = ContextVar("pca_fetches", default=None)


@contextmanager
def track_fetches() -> Iterator[list[tuple[bool, float]]]:
    """Record every connector HTTP response made inside the block."""
    fetches: list[tuple[bool, float]] = []
    token = _fetches.set(fetches)
    try:
        yield fetches
    finally:
        _fetches.reset(token)


async def record_response(response: httpx.Response) -> None:
    """httpx response hook: note whether hishel served this from cache, and when it was fetched."""
    fetches = _fetches.get()
    if fetches is None:
        return
    extensions = response.extensions
    from_cache = bool(extensions.get("hishel_from_cache")) and not extensions.get(
        "hishel_revalidated"
    )
    created_at = extensions.get("hishel_created_at")
    # hishel stamps both fresh and cached responses with the original fetch time.
    fetched = float(created_at) if created_at else time.time()
    fetches.append((from_cache, fetched))


def provenance_for(source_url: str, source_name: str, **kwargs: Any) -> Provenance:
    """``make_provenance`` with ``cache_hit`` / ``retrieved_at`` from this call's responses.

    Explicit ``cache_hit`` or ``retrieved_at`` arguments win.
    """
    fetches = _fetches.get()
    if fetches and "cache_hit" not in kwargs and "retrieved_at" not in kwargs:
        kwargs["cache_hit"] = all(from_cache for from_cache, _ in fetches)
        kwargs["retrieved_at"] = datetime.fromtimestamp(min(t for _, t in fetches), UTC)
    return make_provenance(source_url, source_name, **kwargs)
