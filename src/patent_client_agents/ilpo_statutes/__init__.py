"""ILPO Israel statutes corpus connector (MCP-free public surface).

Five Israeli IP statutes are indexed: Patents Law (5727-1967), Trade
Marks Ordinance (5732-1972), Designs Law (5777-2017), Copyright Act
(5768-2007), and **Commercial Torts Law (5759-1999)** — the
distinctive piece: Israel's standalone trade-secret regime with
statutory damages.
"""

from __future__ import annotations

from patent_client_agents.shared.corpus import CorpusStatus, make_corpus_status

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


get_corpus_status = make_corpus_status(CorpusDB, CorpusUnavailable, label="ILPO statutes")
