"""IPOS Singapore manuals corpus connector (MCP-free public surface)."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import TypedDict

from .api import (
    USAGE_RESOURCE_URI,
    IposManual,
    IposManualsClient,
    IposManualsCorpusMeta,
    IposManualSearchHit,
    IposManualSearchResponse,
    IposManualSection,
    ManualSearchInput,
    ManualSectionInput,
    get_by_citation,
    get_client,
    get_section,
    get_usage_resource,
    list_manuals,
    search,
)
from .corpus import CorpusDB, CorpusUnavailable

__all__ = [
    "IposManualsClient",
    "CorpusUnavailable",
    "CorpusStatus",
    "IposManual",
    "IposManualSection",
    "IposManualsCorpusMeta",
    "IposManualSearchHit",
    "IposManualSearchResponse",
    "ManualSearchInput",
    "ManualSectionInput",
    "get_client",
    "search",
    "get_section",
    "get_by_citation",
    "list_manuals",
    "get_corpus_status",
    "USAGE_RESOURCE_URI",
    "get_usage_resource",
]


_logger = logging.getLogger(__name__)


class CorpusStatus(TypedDict):
    """Return shape for :func:`get_corpus_status`.

    Mirrors :class:`patent_client_agents.ipos_statutes.CorpusStatus`.
    When no ``meta.source_version`` is stamped the version falls back
    to ``"snapshot YYYY-MM-DD"`` so agents always have a quotable label.
    """

    corpus_synced_at: datetime | None
    corpus_version: str


def get_corpus_status() -> CorpusStatus:
    """Return IPOS manuals corpus freshness metadata.

    Reads ``meta.source_version`` and ``meta.snapshot_date`` from the
    bundled SQLite corpus. Does not require a live upstream call.
    Locator precedence: ``IPOS_MANUALS_CORPUS_PATH`` env var, then
    ``~/.cache/patent_client_agents/ipos_manuals.db``.
    """
    try:
        with CorpusDB.open() as db:
            meta = db.meta()
    except CorpusUnavailable as exc:
        _logger.debug("IPOS manuals corpus unavailable for get_corpus_status: %s", exc)
        return CorpusStatus(corpus_synced_at=None, corpus_version="unknown")
    except Exception as exc:  # pragma: no cover — defensive; never crash the caller
        _logger.warning(
            "IPOS manuals get_corpus_status: unexpected error reading corpus meta: %r",
            exc,
        )
        return CorpusStatus(corpus_synced_at=None, corpus_version="unknown")

    snapshot_raw = meta.get("snapshot_date")
    explicit_version = meta.get("source_version")
    if explicit_version:
        version = explicit_version
    elif snapshot_raw:
        version = f"snapshot {snapshot_raw}"
    else:
        version = "unknown"
    return CorpusStatus(
        corpus_synced_at=_parse_snapshot_date(snapshot_raw),
        corpus_version=version,
    )


def _parse_snapshot_date(value: str | None) -> datetime | None:
    """Parse ``meta.snapshot_date`` (ISO YYYY-MM-DD) into a UTC datetime."""
    if not value:
        return None
    try:
        parsed_date = date.fromisoformat(value)
    except ValueError:
        _logger.debug(
            "IPOS manuals get_corpus_status: snapshot_date %r is not ISO date",
            value,
        )
        return None
    return datetime(
        parsed_date.year,
        parsed_date.month,
        parsed_date.day,
        tzinfo=UTC,
    )
