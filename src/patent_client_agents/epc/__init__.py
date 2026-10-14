"""Async API for the European Patent Convention (EPC) corpus without MCP wiring."""

from __future__ import annotations

from patent_client_agents.shared.corpus import CorpusStatus, make_corpus_status

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


get_corpus_status = make_corpus_status(
    CorpusDB, CorpusUnavailable, label="EPC", version_keys=("epc_year",)
)
