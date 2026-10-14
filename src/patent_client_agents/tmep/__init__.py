"""USPTO Trademark Manual of Examining Procedure (TMEP) client."""

from __future__ import annotations

from patent_client_agents.shared.corpus import CorpusStatus, make_corpus_status

from .api import (
    USAGE_RESOURCE_URI,
    SearchInput,
    SectionInput,
    TmepClient,
    TmepSearchResponse,
    TmepSection,
    TmepVersion,
    get_section,
    get_usage_resource,
    list_versions,
    search,
)
from .corpus import CorpusDB, CorpusUnavailable

__all__ = [
    "TmepClient",
    "TmepSearchResponse",
    "TmepSection",
    "TmepVersion",
    "SearchInput",
    "SectionInput",
    "CorpusUnavailable",
    "CorpusStatus",
    "search",
    "get_section",
    "list_versions",
    "get_corpus_status",
    "USAGE_RESOURCE_URI",
    "get_usage_resource",
]


get_corpus_status = make_corpus_status(CorpusDB, CorpusUnavailable, label="TMEP")
