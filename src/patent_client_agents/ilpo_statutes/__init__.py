"""ILPO Israel statutes corpus connector (MCP-free public surface).

Five Israeli IP statutes are indexed: Patents Law (5727-1967), Trade
Marks Ordinance (5732-1972), Designs Law (5777-2017), Copyright Act
(5768-2007), and **Commercial Torts Law (5759-1999)** — the
distinctive piece: Israel's standalone trade-secret regime with
statutory damages.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import TypedDict

from .api import (
    USAGE_RESOURCE_URI,
    IlpoCorpusMeta,
    IlpoSearchHit,
    IlpoSearchResponse,
    IlpoSection,
    IlpoStatute,
    IlpoStatutesClient,
    SectionInput,
    StatuteSearchInput,
    get_client,
    get_section,
    get_usage_resource,
    list_statutes,
    search,
)
from .corpus import CorpusDB, CorpusUnavailable

__all__ = [
    "IlpoStatutesClient",
    "CorpusUnavailable",
    "CorpusStatus",
    "IlpoStatute",
    "IlpoSection",
    "IlpoCorpusMeta",
    "IlpoSearchHit",
    "IlpoSearchResponse",
    "StatuteSearchInput",
    "SectionInput",
    "get_client",
    "search",
    "get_section",
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
    ``meta.snapshot_date``). ``corpus_version`` mirrors the vendor /
    source version label recorded in ``meta.source_version`` — for the
    ILPO statutes corpus this is the WIPO Lex revision label (typically
    ``"WIPO Lex authoritative EN"``). When the corpus is unbundled or
    unreadable the version falls back to ``"unknown"`` and the sync
    timestamp to ``None`` — we never fabricate values.
    """

    corpus_synced_at: datetime | None
    corpus_version: str


def get_corpus_status() -> CorpusStatus:
    """Return ILPO statutes corpus freshness metadata for the validator and Provenance helper.

    Reads ``meta.source_version`` and ``meta.snapshot_date`` from the
    bundled SQLite corpus (see
    :mod:`patent_client_agents.ilpo_statutes.corpus.schema`). Does not
    require a live upstream call — this is the callable
    ``scripts/build_coverage.py`` uses to detect drift, and the ILPO
    MCP tools use to stamp ``Provenance.corpus_synced_at`` /
    ``Provenance.corpus_version`` on every response
    (CONNECTOR_STANDARDS.md §4, §5.9).

    The corpus is located via ``ILPO_STATUTES_CORPUS_PATH`` or the
    local-dev default at
    ``~/.cache/patent_client_agents/ilpo_statutes.db``. If the file is
    missing, unreadable, or the schema is unexpected, returns
    ``corpus_version="unknown"`` and ``corpus_synced_at=None``.
    """
    try:
        with CorpusDB.open() as db:
            meta = db.meta()
    except CorpusUnavailable as exc:
        _logger.debug("ILPO statutes corpus unavailable for get_corpus_status: %s", exc)
        return CorpusStatus(corpus_synced_at=None, corpus_version="unknown")
    except Exception as exc:  # pragma: no cover — defensive; never crash the caller
        _logger.warning(
            "ILPO statutes get_corpus_status: unexpected error reading corpus meta: %r",
            exc,
        )
        return CorpusStatus(corpus_synced_at=None, corpus_version="unknown")

    version = meta.get("source_version") or "unknown"
    snapshot_raw = meta.get("snapshot_date")
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
            "ILPO statutes get_corpus_status: snapshot_date %r is not ISO date",
            value,
        )
        return None
    return datetime(
        parsed_date.year,
        parsed_date.month,
        parsed_date.day,
        tzinfo=UTC,
    )
