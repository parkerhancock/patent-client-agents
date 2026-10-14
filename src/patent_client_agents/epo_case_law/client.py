"""Corpus-backed EPO Case Law of the Boards of Appeal client.

Reads from a SQLite/FTS5 snapshot produced by
``patent-client-agents-build-caselaw-corpus`` and located via
``CASELAW_CORPUS_PATH`` or ``~/.cache/patent_client_agents/caselaw.db``.

The corpus is scraped from
``www.epo.org/en/legal/case-law/<year>/...``. EPO publishes the
canonical "white book" compilation of Boards of Appeal case law
every 2-3 years (2019, 2022, ...). Each section has a slug like
``clr_i_a_1`` encoding Part-Subpart-Subsubpart-Section.

Citation forms accepted by ``get_section``:

- Canonical citation: ``I.A.1`` / ``I-A-1`` / ``I A 1``
- URL slug: ``clr_i_a_1`` / ``clr_i_a_1.html``
- Full URL: ``https://www.epo.org/en/legal/case-law/2022/clr_i_a_1.html``
"""

from __future__ import annotations

import os
import re
from typing import Any

from patent_client_agents.fts_query import translate_fts_query

from .corpus.db import CorpusDB, CorpusUnavailable
from .models import CaseLawSearchHit, CaseLawSearchResponse, CaseLawSection, CaseLawVersion

_CITATION_PATTERN = re.compile(
    r"""
    ^\s*
    (?P<part>[IVX]+)                    # Roman-numeral Part
    (?:
        [-_\s.,]+
        (?P<subpart>[A-Z])              # Letter sub-part
        (?:
            [-_\s.,]+
            (?P<chain>[\dA-Z]+(?:[-_\s.,]+[\dA-Z]+)*)
        )?
    )?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)
_SLUG_PATTERN = re.compile(r"^clr_[a-z0-9_]+$", re.IGNORECASE)


def _citation_to_slug(text: str) -> str | None:
    m = _CITATION_PATTERN.match(text)
    if not m:
        return None
    part = m.group("part").lower()
    subpart = m.group("subpart")
    chain = m.group("chain")
    slug = f"clr_{part}"
    if subpart:
        slug += f"_{subpart.lower()}"
    if chain:
        normalized = re.sub(r"[-\s.,]+", "_", chain).lower()
        slug += f"_{normalized}"
    return slug


def _normalize_href(value: str) -> str:
    h = value.strip()
    if h.startswith("http"):
        h = h.split("://", 1)[1].split("/", 1)[1]
    h = h.lstrip("/")
    h = re.sub(r"^(?:en/)?legal/case-law/\d{4}/", "", h)
    h = h.removesuffix(".html")
    return h.lower()


def _build_result_url(base_url: str, version: str, href: str) -> str:
    return f"{base_url}/en/legal/case-law/{version}/{href}.html"


def _hit_to_model(hit: Any, base_url: str, version: str) -> CaseLawSearchHit:
    title = (
        f"{hit.section_number} - {hit.title}"
        if hit.section_number and hit.title
        else hit.title or hit.section_number or ""
    )
    path: list[str] = []
    if hit.chapter:
        path.append(hit.chapter)
    if hit.section_number:
        path.append(hit.section_number)
    return CaseLawSearchHit(
        title=title,
        href=hit.href,
        path=path,
        result_url=_build_result_url(base_url, version, hit.href),
    )


class CaseLawClient:
    """Corpus-backed EPO Case Law of the Boards of Appeal client."""

    DEFAULT_BASE_URL: str = os.getenv("CASELAW_BASE_URL", "https://www.epo.org")
    CACHE_NAME: str = "caselaw"
    DEFAULT_VERSION: str = os.getenv("CASELAW_VERSION", "2022")

    def __init__(
        self,
        *,
        corpus_path: str | os.PathLike[str] | None = None,
        base_url: str | None = None,
    ) -> None:
        self._corpus_path = corpus_path
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._db: CorpusDB | None = None

    async def __aenter__(self) -> CaseLawClient:
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
        self, section_number: str, *, version: str = "current"
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
        include_form_paragraphs: bool = False,
        syntax: str = "adj",
        snippet: str = "compact",
        sort: str = "relevance",
        per_page: int = 10,
        page: int = 1,
    ) -> CaseLawSearchResponse:
        del version, include_content, include_index, include_notes
        del include_form_paragraphs, snippet
        db = self._open()
        fts_query = translate_fts_query(query, syntax)
        if not fts_query:
            return CaseLawSearchResponse(hits=[], page=page, per_page=per_page, has_more=False)
        offset = max(0, (page - 1) * per_page)
        rows = db.search(fts_query, limit=per_page + 1, offset=offset, sort=sort)
        has_more = len(rows) > per_page
        rows = rows[:per_page]
        meta = db.meta()
        cl_year = meta.get("caselaw_year", self.DEFAULT_VERSION)
        hits = [_hit_to_model(r, self._base_url, cl_year) for r in rows]
        return CaseLawSearchResponse(hits=hits, page=page, per_page=per_page, has_more=has_more)

    async def get_section(
        self,
        section: str,
        *,
        version: str = "current",
        highlight_query: str | None = None,  # noqa: ARG002
    ) -> CaseLawSection:
        del highlight_query
        db = self._open()
        candidate = _citation_to_slug(section)
        if candidate:
            row = db.get_section(href=candidate)
            if row is not None:
                return CaseLawSection(
                    href=row.href,
                    html=row.html,
                    text=row.text,
                    version=version,
                    title=row.title,
                )
        href = _normalize_href(section)
        row = db.get_section(href=href)
        if row is None:
            raise ValueError(f"Could not find Case Law section '{section}'")
        return CaseLawSection(
            href=row.href,
            html=row.html,
            text=row.text,
            version=version,
            title=row.title,
        )

    async def list_versions(self) -> list[CaseLawVersion]:
        db = self._open()
        meta = db.meta()
        snapshot = meta.get("snapshot_date", "unknown")
        cl_year = meta.get("caselaw_year", "unknown")
        return [
            CaseLawVersion(
                label=f"Case Law {cl_year} edition (snapshot {snapshot})",
                value="current",
                current=True,
            )
        ]


__all__ = [
    "CaseLawClient",
    "_CITATION_PATTERN",
    "_SLUG_PATTERN",
    "_citation_to_slug",
    "CorpusUnavailable",
]
