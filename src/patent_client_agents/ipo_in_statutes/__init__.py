"""IPO India statutes connector (MCP-free public surface).

The four core Indian IP Acts plus the Patent Rules — bundled into one
SQLite/FTS5 corpus discriminated by ``statute_name``. Static corpus
(``category=substantive_law``, ``transport=mcp_local``,
``update_strategy=scheduled_recrawl``, cadence ``annual``).
"""

from __future__ import annotations

from patent_client_agents.shared.corpus import CorpusStatus, make_corpus_status

from .api import (
    USAGE_RESOURCE_URI,
    IpoInCorpusMeta,
    IpoInSearchHit,
    IpoInSearchResponse,
    IpoInSection,
    IpoInStatutesClient,
    SectionInput,
    StatuteSearchInput,
    get_client,
    get_section,
    get_section_by_citation,
    get_usage_resource,
    list_statutes,
    parse_citation,
    search,
)
from .corpus import CorpusDB, CorpusUnavailable

__all__ = [
    "IpoInStatutesClient",
    "CorpusUnavailable",
    "CorpusStatus",
    "IpoInSection",
    "IpoInSearchHit",
    "IpoInSearchResponse",
    "IpoInCorpusMeta",
    "StatuteSearchInput",
    "SectionInput",
    "get_client",
    "search",
    "get_section",
    "get_section_by_citation",
    "list_statutes",
    "parse_citation",
    "get_corpus_status",
    "USAGE_RESOURCE_URI",
    "get_usage_resource",
]


get_corpus_status = make_corpus_status(
    CorpusDB, CorpusUnavailable, label="IPO India statutes", snapshot_label="snapshot-{}"
)
