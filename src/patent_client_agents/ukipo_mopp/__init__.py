"""Async API for the UKIPO Manual of Patent Practice (MoPP) without MCP wiring."""

from __future__ import annotations

from patent_client_agents.shared.corpus import CorpusStatus, make_corpus_status

from .api import (  # noqa: F401
    USAGE_RESOURCE_URI,
    MoppClient,
    MoppSearchResponse,
    MoppSection,
    MoppVersion,
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
    "MoppClient",
    "MoppSearchResponse",
    "MoppSection",
    "MoppVersion",
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


# gov.uk publishes no stable MoPP revision tag; fall back to a ``snapshot-<date>`` label.
get_corpus_status = make_corpus_status(
    CorpusDB, CorpusUnavailable, label="MoPP", snapshot_label="snapshot-{}"
)
