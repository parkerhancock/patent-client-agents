"""Async API for the USPTO eMPEP without MCP wiring."""

from __future__ import annotations

from patent_client_agents.shared.corpus import CorpusStatus, make_corpus_status

from .api import (  # noqa: F401
    USAGE_RESOURCE_URI,
    MpepClient,
    MpepSearchResponse,
    MpepSection,
    MpepVersion,
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
    "MpepClient",
    "MpepSearchResponse",
    "MpepSection",
    "MpepVersion",
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


# ``synced_at`` is the precise build timestamp; older corpora only have ``snapshot_date``.
get_corpus_status = make_corpus_status(
    CorpusDB, CorpusUnavailable, label="MPEP", synced_at_keys=("synced_at", "snapshot_date")
)
