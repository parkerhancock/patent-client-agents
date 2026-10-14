"""UPC statutes corpus connector (MCP-free public surface)."""

from __future__ import annotations

from patent_client_agents.shared.corpus import CorpusStatus, make_corpus_status

from .api import (
    USAGE_RESOURCE_URI,
    InstrumentInput,
    StatuteSearchInput,
    UpcCorpusMeta,
    UpcInstrument,
    UpcInstrumentText,
    UpcStatutesClient,
    UpcStatuteSearchHit,
    UpcStatuteSearchResponse,
    get_client,
    get_instrument,
    get_usage_resource,
    list_instruments,
    search,
)
from .corpus import CorpusDB, CorpusUnavailable

__all__ = [
    "UpcStatutesClient",
    "CorpusUnavailable",
    "CorpusStatus",
    "UpcInstrument",
    "UpcInstrumentText",
    "UpcCorpusMeta",
    "UpcStatuteSearchHit",
    "UpcStatuteSearchResponse",
    "StatuteSearchInput",
    "InstrumentInput",
    "get_client",
    "search",
    "get_instrument",
    "list_instruments",
    "get_corpus_status",
    "USAGE_RESOURCE_URI",
    "get_usage_resource",
]


# The consolidated UPC PDFs carry no vendor version, so the snapshot date is the version.
get_corpus_status = make_corpus_status(
    CorpusDB, CorpusUnavailable, label="UPC statutes", version_keys=(), snapshot_label="snapshot {}"
)
