"""DPMA Germany IP statutes connector (MCP-free public surface).

The six core German IP Acts — PatG, MarkenG, GebrMG, DesignG, UrhG,
GeschGehG — bundled into one SQLite/FTS5 corpus discriminated by
``statute``. Static corpus (``category=substantive_law``,
``transport=mcp_local``, ``update_strategy=scheduled_recrawl``,
cadence ``annual``).
"""

from __future__ import annotations

from patent_client_agents.shared.corpus import CorpusStatus, make_corpus_status

from .api import (
    USAGE_RESOURCE_URI,
    DpmaCorpusMeta,
    DpmaSearchHit,
    DpmaSearchResult,
    DpmaSection,
    DpmaStatutesClient,
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
    "DpmaStatutesClient",
    "CorpusUnavailable",
    "CorpusStatus",
    "DpmaSection",
    "DpmaSearchHit",
    "DpmaSearchResult",
    "DpmaCorpusMeta",
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
    CorpusDB, CorpusUnavailable, label="DPMA statutes", snapshot_label="snapshot-{}"
)
