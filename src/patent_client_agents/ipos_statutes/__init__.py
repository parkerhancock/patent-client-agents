"""IPOS Singapore statutes corpus connector (MCP-free public surface)."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import TypedDict

from .api import (
    USAGE_RESOURCE_URI,
    IposCorpusMeta,
    IposSection,
    IposStatute,
    IposStatutesClient,
    IposStatuteSearchHit,
    IposStatuteSearchResponse,
    SectionInput,
    StatuteSearchInput,
    get_by_citation,
    get_client,
    get_section,
    get_usage_resource,
    list_statutes,
    search,
)
from .corpus import CorpusDB, CorpusUnavailable

__all__ = [
    "IposStatutesClient",
    "CorpusUnavailable",
    "CorpusStatus",
    "IposStatute",
    "IposSection",
    "IposCorpusMeta",
    "IposStatuteSearchHit",
    "IposStatuteSearchResponse",
    "StatuteSearchInput",
    "SectionInput",
    "get_client",
    "search",
    "get_section",
    "get_by_citation",
    "list_statutes",
    "get_corpus_status",
    "USAGE_RESOURCE_URI",
    "get_usage_resource",
]


_logger = logging.getLogger(__name__)


class CorpusStatus(TypedDict):
    """Return shape for :func:`get_corpus_status`.

    ``corpus_synced_at`` is the UTC datetime the bundled corpus was last
    refreshed from upstream (parsed from the corpus
    ``meta.snapshot_date``). ``corpus_version`` mirrors the vendor's
    version label as recorded in ``meta.source_version`` — for SSO this
    is typically ``"2020 Revised Edition"`` when stamped at build time;
    when no version is recorded we derive ``"snapshot YYYY-MM-DD"`` from
    the snapshot date so the field is still quotable. When the corpus is
    unbundled or unreadable both fields fall back to
    ``corpus_version="unknown"`` / ``corpus_synced_at=None`` — we never
    fabricate values.
    """

    corpus_synced_at: datetime | None
    corpus_version: str


def get_corpus_status() -> CorpusStatus:
    """Return IPOS statutes corpus freshness metadata.

    Reads ``meta.source_version`` and ``meta.snapshot_date`` from the
    bundled SQLite corpus (see
    :mod:`patent_client_agents.ipos_statutes.corpus.schema`). Does not
    require a live upstream call — this is the callable
    ``scripts/build_coverage.py`` uses to detect drift, and the IPOS
    statutes MCP tools use to stamp ``Provenance.corpus_synced_at`` /
    ``Provenance.corpus_version`` on every response
    (CONNECTOR_STANDARDS.md §4, §5.9).

    The corpus is located via ``IPOS_STATUTES_CORPUS_PATH`` or the
    local-dev default at
    ``~/.cache/patent_client_agents/ipos_statutes.db``. If the file is
    missing, unreadable, or the schema is unexpected, returns
    ``corpus_version="unknown"`` and ``corpus_synced_at=None``.
    """
    try:
        with CorpusDB.open() as db:
            meta = db.meta()
    except CorpusUnavailable as exc:
        _logger.debug("IPOS statutes corpus unavailable for get_corpus_status: %s", exc)
        return CorpusStatus(corpus_synced_at=None, corpus_version="unknown")
    except Exception as exc:  # pragma: no cover — defensive; never crash the caller
        _logger.warning(
            "IPOS statutes get_corpus_status: unexpected error reading corpus meta: %r",
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
            "IPOS statutes get_corpus_status: snapshot_date %r is not ISO date",
            value,
        )
        return None
    return datetime(
        parsed_date.year,
        parsed_date.month,
        parsed_date.day,
        tzinfo=UTC,
    )
