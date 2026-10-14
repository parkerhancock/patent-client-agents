"""Légifrance IP statutes — CPI + Code de commerce L.151 trade secrets.

Static-law corpus served from a local SQLite/FTS5 snapshot built by
``patent-client-agents-build-legifrance-ip-corpus`` from the bundled
``data/seed.jsonl``. Runtime never calls Légifrance.

CONNECTOR_STANDARDS.md classification: ``category=substantive_law``,
``transport=mcp_local``, ``update_strategy=scheduled_recrawl``,
``update_cadence=annual``. See ``coverage/sources.yaml`` row
``FR/Legifrance/IP``.
"""

from __future__ import annotations

from patent_client_agents.shared.corpus import CorpusStatus, make_corpus_status

from .api import LegifranceIpClient, get_section, search
from .client import LegifranceIpClient as _LegifranceIpClient  # re-export alias
from .corpus import CorpusDB, CorpusUnavailable
from .models import LegifranceSearchHit, LegifranceSearchResult, LegifranceSection
from .resources import STATUTES, CitationParseError, parse_citation

__all__ = [
    "CitationParseError",
    "CorpusDB",
    "CorpusStatus",
    "CorpusUnavailable",
    "LegifranceIpClient",
    "LegifranceSearchHit",
    "LegifranceSearchResult",
    "LegifranceSection",
    "STATUTES",
    "get_corpus_status",
    "get_section",
    "parse_citation",
    "search",
]


_ = _LegifranceIpClient  # silence "unused import" — kept for symmetry with other connectors


get_corpus_status = make_corpus_status(CorpusDB, CorpusUnavailable, label="Légifrance IP")
