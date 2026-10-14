"""Corpus-backed Légifrance IP client.

Reads exclusively from a SQLite/FTS5 snapshot of the CPI + Code de
commerce L.151 trade-secret regime. The corpus is built by
``patent-client-agents-build-legifrance-ip-corpus`` from the bundled
``data/seed.jsonl`` and located via ``LEGIFRANCE_IP_CORPUS_PATH`` or
``~/.cache/patent_client_agents/legifrance_ip.db`` (see
:mod:`patent_client_agents.legifrance_ip.corpus.db`).
"""

from __future__ import annotations

import os
import re

from patent_client_agents.fts_query import translate_fts_query

from .corpus.db import CorpusDB
from .models import LegifranceSearchHit, LegifranceSearchResult, LegifranceSection
from .resources import parse_citation


def _normalize_section(value: str) -> str:
    """Canonicalize a section identifier to the seed schema form ``L611-10``.

    Accepts ``L. 611-10``, ``L611-10``, ``L 611.10`` and returns
    ``L611-10`` (capital ``L``, no spaces, dot replaced by hyphen). The
    corpus stores the canonical form; this function exists so direct
    ``get_section`` callers can pass either shape.
    """
    cleaned = re.sub(r"\s+", "", value).upper()
    # Drop a single leading "L." or "L " variants down to bare "L".
    cleaned = cleaned.replace(".", "-")
    if cleaned.startswith("L-"):
        cleaned = "L" + cleaned[2:]
    return cleaned


class LegifranceIpClient:
    """Async-shaped client over the local corpus.

    Mirrors the shape of the other ``mcp_local`` substantive-law
    clients in this codebase (MPEP, EPC, UPC statutes) so MCP tool
    files can copy-paste the surrounding scaffolding.
    """

    def __init__(self, *, corpus_path: str | os.PathLike[str] | None = None) -> None:
        self._corpus_path = corpus_path
        self._db: CorpusDB | None = None

    async def __aenter__(self) -> LegifranceIpClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    def _open(self) -> CorpusDB:
        if self._db is None:
            self._db = CorpusDB.open(self._corpus_path)
        return self._db

    async def search(
        self,
        query: str,
        *,
        statute: str | None = None,
        per_page: int = 10,
        page: int = 1,
    ) -> LegifranceSearchResult:
        """Full-text search across the corpus.

        Args:
            query: Free-text query in French (or English fallback).
            statute: Optional filter — ``'CPI'`` or ``'Code de commerce'``.
            per_page: Maximum hits to return (1-100).
            page: 1-indexed page number.
        """
        db = self._open()
        fts_query = translate_fts_query(query)
        if not fts_query:
            return LegifranceSearchResult(hits=[], page=page, per_page=per_page, has_more=False)
        offset = max(0, (page - 1) * per_page)
        rows = db.search(
            fts_query,
            statute=statute,
            limit=per_page + 1,
            offset=offset,
        )
        has_more = len(rows) > per_page
        rows = rows[:per_page]
        hits = [
            LegifranceSearchHit(
                statute=row.statute,
                section=row.section,
                title=row.title,
                snippet=row.snippet,
            )
            for row in rows
        ]
        return LegifranceSearchResult(hits=hits, page=page, per_page=per_page, has_more=has_more)

    async def get_section(self, citation: str) -> LegifranceSection:
        """Resolve a citation (or raw section number) to a corpus row.

        Accepts:
            * Full citations (``"L. 611-10 CPI"``, ``"Art. L. 151-1 Code
              de commerce"``) — routed through :func:`parse_citation`.
            * Bare canonical section numbers (``"L611-10"``) when the
              caller already knows the statute and passes it via
              ``statute=`` (not supported here — the citation form is the
              canonical entry point for the MCP tool, and most callers
              should use it).

        Raises:
            ValueError: when the citation cannot be parsed or the
                article is not present in the corpus.
        """
        statute, section = parse_citation(citation)
        db = self._open()
        row = db.get_section(statute, section)
        if row is None:
            raise ValueError(
                f"could not find Légifrance article {section} in {statute!r}; "
                "is the corpus built and does the seed cover this article?"
            )
        return LegifranceSection(
            statute=row.statute,
            section=row.section,
            title=row.title,
            text=row.text,
        )

    async def get_by_section_number(
        self,
        statute: str,
        section: str,
    ) -> LegifranceSection:
        """Get a section by ``(statute, section)`` directly.

        Useful for tests and internal callers that already know the
        normalized identifiers; the public MCP surface goes through
        :meth:`get_section` (citation form).
        """
        canonical_section = _normalize_section(section)
        db = self._open()
        row = db.get_section(statute, canonical_section)
        if row is None:
            raise ValueError(
                f"could not find Légifrance article {canonical_section} in {statute!r}"
            )
        return LegifranceSection(
            statute=row.statute,
            section=row.section,
            title=row.title,
            text=row.text,
        )


__all__ = ["LegifranceIpClient"]
