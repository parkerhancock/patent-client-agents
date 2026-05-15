"""UPC statutes corpus connector (MCP-free public surface)."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import TypedDict

from .api import (
    USAGE_RESOURCE_URI,
    InstrumentInput,
    StatuteSearchInput,
    UpcCorpusMeta,
    UpcInstrument,
    UpcInstrumentText,
    UpcStatutesClient,
    UpcStatuteSearchHit,
    UpcStatuteSearchResponse,
    get_client,
    get_instrument,
    get_usage_resource,
    list_instruments,
    search,
)
from .corpus import CorpusDB, CorpusUnavailable

__all__ = [
    "UpcStatutesClient",
    "CorpusUnavailable",
    "CorpusStatus",
    "UpcInstrument",
    "UpcInstrumentText",
    "UpcCorpusMeta",
    "UpcStatuteSearchHit",
    "UpcStatuteSearchResponse",
    "StatuteSearchInput",
    "InstrumentInput",
    "get_client",
    "search",
    "get_instrument",
    "list_instruments",
    "get_corpus_status",
    "USAGE_RESOURCE_URI",
    "get_usage_resource",
]


_logger = logging.getLogger(__name__)


class CorpusStatus(TypedDict):
    """Return shape for :func:`get_corpus_status`.

    ``corpus_synced_at`` is the UTC datetime the bundled corpus was last
    refreshed from upstream (parsed from the corpus ``meta.snapshot_date``).
    ``corpus_version`` is a free-text version label. The UPC statutes
    corpus is a snapshot of consolidated PDFs published by the Court at
    ``unifiedpatentcourt.org/en/court/legal-documents`` — those PDFs do
    not carry a discrete vendor version, so the version label is derived
    from ``meta.snapshot_date`` (e.g. ``"snapshot 2026-05-13"``). When
    the corpus is unbundled or unreadable both fields fall back to
    ``corpus_version="unknown"`` / ``corpus_synced_at=None`` — we never
    fabricate values.
    """

    corpus_synced_at: datetime | None
    corpus_version: str


def get_corpus_status() -> CorpusStatus:
    """Return UPC statutes corpus freshness metadata for the validator and Provenance helper.

    Reads ``meta.snapshot_date`` from the bundled SQLite corpus (see
    :mod:`patent_client_agents.upc_statutes.corpus.schema`). Does not
    require a live upstream call — this is the callable
    ``scripts/build_coverage.py`` uses to detect drift, and the UPC
    statutes MCP tools use to stamp ``Provenance.corpus_synced_at`` /
    ``Provenance.corpus_version`` on every response
    (CONNECTOR_STANDARDS.md §4, §5.9).

    The corpus is located via ``UPC_STATUTES_CORPUS_PATH`` or the
    local-dev default at
    ``~/.cache/patent_client_agents/upc_statutes.db``. If the file is
    missing, unreadable, or the schema is unexpected, returns
    ``corpus_version="unknown"`` and ``corpus_synced_at=None``.

    Returns:
        A :class:`CorpusStatus` mapping with keys ``corpus_synced_at``
        (UTC ``datetime`` or ``None``) and ``corpus_version`` (string).
    """
    try:
        with CorpusDB.open() as db:
            meta = db.meta()
    except CorpusUnavailable as exc:
        _logger.debug("UPC statutes corpus unavailable for get_corpus_status: %s", exc)
        return CorpusStatus(corpus_synced_at=None, corpus_version="unknown")
    except Exception as exc:  # pragma: no cover — defensive; never crash the caller
        _logger.warning(
            "UPC statutes get_corpus_status: unexpected error reading corpus meta: %r",
            exc,
        )
        return CorpusStatus(corpus_synced_at=None, corpus_version="unknown")

    snapshot_raw = meta.get("snapshot_date")
    synced_at = _parse_snapshot_date(snapshot_raw)
    # The consolidated UPC PDFs do not carry a discrete vendor version,
    # so use the snapshot date as the version label (the snapshot IS the
    # version for this corpus). Falls back to ``"unknown"`` only when no
    # snapshot_date is recorded.
    if snapshot_raw:
        version = f"snapshot {snapshot_raw}"
    else:
        version = "unknown"
    return CorpusStatus(corpus_synced_at=synced_at, corpus_version=version)


def _parse_snapshot_date(value: str | None) -> datetime | None:
    """Parse ``meta.snapshot_date`` (ISO YYYY-MM-DD) into a UTC datetime."""
    if not value:
        return None
    try:
        parsed_date = date.fromisoformat(value)
    except ValueError:
        _logger.debug(
            "UPC statutes get_corpus_status: snapshot_date %r is not ISO date",
            value,
        )
        return None
    return datetime(
        parsed_date.year,
        parsed_date.month,
        parsed_date.day,
        tzinfo=UTC,
    )
