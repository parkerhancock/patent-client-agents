"""Async API for the European Patent Convention (EPC) corpus without MCP wiring."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import TypedDict

from .api import (  # noqa: F401
    USAGE_RESOURCE_URI,
    EpcClient,
    EpcSearchResponse,
    EpcSection,
    EpcVersion,
    SearchInput,
    SectionInput,
    get_client,
    get_section,
    get_usage_resource,
    list_versions,
    search,
)
from .corpus import CorpusDB, CorpusUnavailable

__all__ = [
    "EpcClient",
    "EpcSearchResponse",
    "EpcSection",
    "EpcVersion",
    "SearchInput",
    "SectionInput",
    "CorpusUnavailable",
    "CorpusStatus",
    "search",
    "get_section",
    "list_versions",
    "get_client",
    "get_corpus_status",
    "USAGE_RESOURCE_URI",
    "get_usage_resource",
]


_logger = logging.getLogger(__name__)


class CorpusStatus(TypedDict):
    """Return shape for :func:`get_corpus_status`.

    ``corpus_synced_at`` is the UTC datetime the bundled corpus was last
    refreshed from upstream (parsed from the corpus ``meta.snapshot_date``).
    ``corpus_version`` mirrors the EPC edition year as recorded in
    ``meta.epc_year`` — for the current corpus this is the EPO's published
    EPC edition (e.g. ``"2020"`` for the EPC 2020 edition). When the corpus
    is unbundled or unreadable the version falls back to ``"unknown"`` and
    the sync timestamp to ``None`` — we never fabricate values.
    """

    corpus_synced_at: datetime | None
    corpus_version: str


def get_corpus_status() -> CorpusStatus:
    """Return EPC corpus freshness metadata for the validator and Provenance helper.

    Reads ``meta.epc_year`` and ``meta.snapshot_date`` from the bundled
    SQLite corpus (see
    :mod:`patent_client_agents.epc.corpus.schema`). Does not require a
    live upstream call — this is the callable
    ``scripts/build_coverage.py`` uses to detect drift, and the EPC MCP
    tools use to stamp ``Provenance.corpus_synced_at`` /
    ``Provenance.corpus_version`` on every response (CONNECTOR_STANDARDS.md
    §4, §5.9).

    The corpus is located via ``EPC_CORPUS_PATH`` or the local-dev
    default at ``~/.cache/patent_client_agents/epc.db``. If the file is
    missing, unreadable, or the schema is unexpected, returns
    ``corpus_version="unknown"`` and ``corpus_synced_at=None`` — callers
    can still surface a Provenance object, just without freshness info.

    Returns:
        A :class:`CorpusStatus` mapping with keys ``corpus_synced_at``
        (UTC ``datetime`` or ``None``) and ``corpus_version`` (string).
    """
    try:
        with CorpusDB.open() as db:
            meta = db.meta()
    except CorpusUnavailable as exc:
        _logger.debug("EPC corpus unavailable for get_corpus_status: %s", exc)
        return CorpusStatus(corpus_synced_at=None, corpus_version="unknown")
    except Exception as exc:  # pragma: no cover — defensive; never crash the caller
        _logger.warning("EPC get_corpus_status: unexpected error reading corpus meta: %r", exc)
        return CorpusStatus(corpus_synced_at=None, corpus_version="unknown")

    version = meta.get("epc_year") or "unknown"
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
        _logger.debug("EPC get_corpus_status: snapshot_date %r is not ISO date", value)
        return None
    return datetime(
        parsed_date.year,
        parsed_date.month,
        parsed_date.day,
        tzinfo=UTC,
    )
