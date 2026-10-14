"""Corpus-backed TMEP client.

Sister module to :mod:`patent_client_agents.mpep.client` — replaces the
old HTTP client against ``tmep.uspto.gov`` with reads from a frozen
SQLite/FTS5 corpus produced by
``patent-client-agents-build-tmep-corpus``. Corpus location is resolved
at runtime through ``TMEP_CORPUS_PATH`` → ``~/.cache/patent_client_agents/tmep.db``
→ :class:`CorpusUnavailable`.
"""

from __future__ import annotations

import os
import re

from patent_client_agents.shared.corpus.outline import OutlineCorpusClient

from .corpus.db import CorpusDB, CorpusUnavailable
from .models import TmepSearchHit, TmepSearchResponse, TmepSection, TmepVersion

# Section number patterns: 1207, 1207.01, 1207.01(a), 710.01(c) etc.
SECTION_NUMBER_PATTERN = re.compile(r"^\d+(\.\d+)?(\([a-z]\))?(\(\d+\))?$", re.IGNORECASE)


def _normalize_href(value: str) -> str:
    h = value.strip().lstrip("/")
    h = h.removeprefix("current/")
    if not h.endswith(".html"):
        h = f"{h}.html"
    return h


class TmepClient(OutlineCorpusClient[TmepSearchResponse, TmepSection, TmepVersion]):
    """Corpus-backed eTMEP client.

    Opens the corpus lazily on first use. Construction in environments
    where the database hasn't been materialized doesn't raise — the
    error surfaces on the first actual query instead.
    """

    DEFAULT_BASE_URL: str = os.getenv("TMEP_BASE_URL", "https://tmep.uspto.gov")
    CACHE_NAME: str = "tmep"

    CORPUS_DB = CorpusDB
    HIT_MODEL = TmepSearchHit
    RESPONSE_MODEL = TmepSearchResponse
    SECTION_MODEL = TmepSection
    VERSION_MODEL = TmepVersion
    NOT_FOUND_LABEL = "TMEP"
    SECTION_NUMBER_PATTERN = SECTION_NUMBER_PATTERN

    def _normalize_href(self, value: str) -> str:
        return _normalize_href(value)

    def _result_url(self, href: str, edition: str | None) -> str:
        return f"{self.base_url}/RDMS/TMEP/result?href={href}"

    # TMEP has no form paragraphs, so its ``search`` takes no
    # ``include_form_paragraphs`` flag.
    async def search(  # ty: ignore[invalid-method-override]
        self,
        query: str,
        *,
        version: str = "current",
        include_content: bool = True,
        include_index: bool = False,
        include_notes: bool = False,
        syntax: str = "adj",
        snippet: str = "compact",
        sort: str = "relevance",
        per_page: int = 10,
        page: int = 1,
        offset: int | None = None,
    ) -> TmepSearchResponse:
        return await super().search(
            query,
            version=version,
            include_content=include_content,
            include_index=include_index,
            include_notes=include_notes,
            syntax=syntax,
            snippet=snippet,
            sort=sort,
            per_page=per_page,
            page=page,
            offset=offset,
        )


__all__ = ["TmepClient", "SECTION_NUMBER_PATTERN", "CorpusUnavailable"]
