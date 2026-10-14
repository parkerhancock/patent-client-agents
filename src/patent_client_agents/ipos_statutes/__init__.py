"""IPOS Singapore statutes corpus connector (MCP-free public surface)."""

from __future__ import annotations

from patent_client_agents.shared.corpus import CorpusStatus, make_corpus_status

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


get_corpus_status = make_corpus_status(
    CorpusDB, CorpusUnavailable, label="IPOS statutes", snapshot_label="snapshot {}"
)
