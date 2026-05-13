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
from typing import Any

from .corpus.db import CorpusDB, CorpusUnavailable
from .models import TmepSearchHit, TmepSearchResponse, TmepSection, TmepVersion

# Section number patterns: 1207, 1207.01, 1207.01(a), 710.01(c) etc.
SECTION_NUMBER_PATTERN = re.compile(r"^\d+(\.\d+)?(\([a-z]\))?(\(\d+\))?$", re.IGNORECASE)


def _translate_fts_query(query: str, syntax: str) -> str:
    cleaned = query.strip()
    if not cleaned:
        return ""
    if syntax in ("adj", "exact"):
        escaped = cleaned.replace('"', '""')
        return f'"{escaped}"'
    tokens = [t for t in re.split(r"\s+", cleaned) if t]
    if syntax == "or":
        return " OR ".join(tokens)
    return " ".join(tokens)


def _normalize_href(value: str) -> str:
    h = value.strip().lstrip("/")
    h = h.removeprefix("current/")
    if not h.endswith(".html"):
        h = f"{h}.html"
    return h


def _hit_to_model(hit: Any, base_url: str) -> TmepSearchHit:
    title = (
        f"{hit.section_number} - {hit.title}"
        if hit.section_number and hit.title
        else hit.title or hit.section_number or ""
    )
    path: list[str] = []
    if hit.chapter:
        path.append(f"Chapter {hit.chapter}")
    if hit.section_number:
        path.append(hit.section_number)
    return TmepSearchHit(
        title=title,
        href=hit.href,
        path=path,
        result_url=f"{base_url}/RDMS/TMEP/result?href={hit.href}",
    )


class TmepClient:
    """Corpus-backed eTMEP client.

    Opens the corpus lazily on first use. Construction in environments
    where the database hasn't been materialized doesn't raise — the
    error surfaces on the first actual query instead.
    """

    DEFAULT_BASE_URL: str = os.getenv("TMEP_BASE_URL", "https://tmep.uspto.gov")
    CACHE_NAME: str = "tmep"

    def __init__(
        self,
        *,
        corpus_path: str | os.PathLike[str] | None = None,
        base_url: str | None = None,
    ) -> None:
        self._corpus_path = corpus_path
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._db: CorpusDB | None = None

    async def __aenter__(self) -> TmepClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    @property
    def base_url(self) -> str:
        return self._base_url

    def _open(self) -> CorpusDB:
        if self._db is None:
            self._db = CorpusDB.open(self._corpus_path)
        return self._db

    async def resolve_section_href(
        self,
        section_number: str,
        *,
        version: str = "current",
    ) -> str | None:
        del version
        db = self._open()
        row = db.get_section(section_number=section_number)
        return row.href if row else None

    async def search(
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
    ) -> TmepSearchResponse:
        del version, include_content, include_index, include_notes, snippet
        db = self._open()
        fts_query = _translate_fts_query(query, syntax)
        if not fts_query:
            return TmepSearchResponse(hits=[], page=page, per_page=per_page, has_more=False)
        offset = max(0, (page - 1) * per_page)
        rows = db.search(fts_query, limit=per_page + 1, offset=offset, sort=sort)
        has_more = len(rows) > per_page
        rows = rows[:per_page]
        hits = [_hit_to_model(r, self._base_url) for r in rows]
        return TmepSearchResponse(hits=hits, page=page, per_page=per_page, has_more=has_more)

    async def get_section(
        self,
        section: str,
        *,
        version: str = "current",
        highlight_query: str | None = None,
    ) -> TmepSection:
        del highlight_query
        db = self._open()
        if SECTION_NUMBER_PATTERN.match(section):
            row = db.get_section(section_number=section)
            if row is None:
                raise ValueError(f"Could not find TMEP section '{section}'")
        else:
            href = _normalize_href(section)
            row = db.get_section(href=href)
            if row is None:
                raise ValueError(f"Could not find TMEP href '{section}'")
        return TmepSection(
            href=row.href,
            html=row.html,
            text=row.text,
            version=version,
            title=row.title,
        )

    async def list_versions(self) -> list[TmepVersion]:
        db = self._open()
        meta = db.meta()
        snapshot = meta.get("snapshot_date", "unknown")
        return [
            TmepVersion(
                label=f"current (snapshot {snapshot})",
                value="current",
                current=True,
            )
        ]


__all__ = ["TmepClient", "SECTION_NUMBER_PATTERN", "CorpusUnavailable"]
