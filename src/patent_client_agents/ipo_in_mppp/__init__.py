"""IPO India MPPP connector (MCP-free public surface).

The Manual of Patent Practice & Procedure published by the IPO India —
the office's internal examination manual, India's counterpart to the
USPTO MPEP / UKIPO MoPP / EPO Guidelines. Static corpus
(``category=substantive_law``, ``transport=mcp_local``,
``update_strategy=scheduled_recrawl``, cadence ``irregular`` — IPO
India ships major MPPP revisions roughly every 4-5 years).
"""

from __future__ import annotations

from patent_client_agents.shared.corpus import CorpusStatus, make_corpus_status

from .api import (
    USAGE_RESOURCE_URI,
    MpppClient,
    MpppCorpusMeta,
    MpppSearchHit,
    MpppSearchInput,
    MpppSearchResponse,
    MpppSection,
    MpppSectionInput,
    get_client,
    get_section,
    get_usage_resource,
    normalize_section_reference,
    search,
)
from .corpus import CorpusDB, CorpusUnavailable

__all__ = [
    "MpppClient",
    "CorpusUnavailable",
    "CorpusStatus",
    "MpppSection",
    "MpppSearchHit",
    "MpppSearchResponse",
    "MpppCorpusMeta",
    "MpppSearchInput",
    "MpppSectionInput",
    "get_client",
    "search",
    "get_section",
    "normalize_section_reference",
    "get_corpus_status",
    "USAGE_RESOURCE_URI",
    "get_usage_resource",
]


get_corpus_status = make_corpus_status(
    CorpusDB, CorpusUnavailable, label="IPO India MPPP", snapshot_label="snapshot-{}"
)
