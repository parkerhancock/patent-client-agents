"""IPOS Singapore manuals corpus connector (MCP-free public surface)."""

from __future__ import annotations

from patent_client_agents.shared.corpus import CorpusStatus, make_corpus_status

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


get_corpus_status = make_corpus_status(
    CorpusDB, CorpusUnavailable, label="IPOS manuals", snapshot_label="snapshot {}"
)
