"""Taiwan Trade Secrets Act connector (MCP-free public surface).

The Taiwan Trade Secrets Act (營業秘密法) in its official English
translation, bundled into one SQLite/FTS5 corpus. Static corpus
(``category=substantive_law``, ``transport=mcp_local``,
``update_strategy=scheduled_recrawl``, cadence ``irregular``). The TIPO
live REST API and bulk-data tracks are out of scope for this connector
— see the follow-up PR plan in CHANGELOG.md.
"""

from __future__ import annotations

from patent_client_agents.shared.corpus import CorpusStatus, make_corpus_status

from .api import (
    USAGE_RESOURCE_URI,
    SearchInput,
    SectionInput,
    TwTradeSecretsClient,
    TwTradeSecretsCorpusMeta,
    TwTradeSecretsSearchHit,
    TwTradeSecretsSearchResult,
    TwTradeSecretsSection,
    get_client,
    get_section,
    get_section_by_citation,
    get_usage_resource,
    parse_citation,
    search,
)
from .corpus import CorpusDB, CorpusUnavailable

__all__ = [
    "TwTradeSecretsClient",
    "CorpusUnavailable",
    "CorpusStatus",
    "TwTradeSecretsSection",
    "TwTradeSecretsSearchHit",
    "TwTradeSecretsSearchResult",
    "TwTradeSecretsCorpusMeta",
    "SearchInput",
    "SectionInput",
    "get_client",
    "search",
    "get_section",
    "get_section_by_citation",
    "parse_citation",
    "get_corpus_status",
    "USAGE_RESOURCE_URI",
    "get_usage_resource",
]


get_corpus_status = make_corpus_status(
    CorpusDB, CorpusUnavailable, label="TW Trade Secrets", snapshot_label="snapshot-{}"
)
