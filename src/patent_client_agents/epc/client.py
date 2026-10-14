"""Corpus-backed European Patent Convention (EPC) client.

Reads from a SQLite/FTS5 snapshot produced by
``patent-client-agents-build-epc-corpus`` and located via
``EPC_CORPUS_PATH`` or ``~/.cache/patent_client_agents/epc.db``.

The corpus covers both Articles of the Convention and Rules of the
Implementing Regulations. Slugs follow the EPO's URL convention:
``a1`` (Article 1), ``a10a`` (Article 10a), ``r1`` (Rule 1), etc.

Citation forms accepted by ``get_section``:

- ``Article 14``, ``Art. 14``, ``Art 14``, ``a14``
- ``Rule 71``, ``R. 71``, ``R 71``, ``r71``
- URL slug ``a14`` / ``r71`` / ``a14.html``
- Full URL ``https://www.epo.org/en/legal/epc/2020/a14.html``

Public surface mirrors :class:`patent_client_agents.mpep.MpepClient`:
``search``, ``get_section``, ``resolve_section_href``, ``list_versions``.
"""

from __future__ import annotations

import os
import re
from typing import Any

from patent_client_agents.fts_query import translate_fts_query

from .corpus.db import CorpusDB, CorpusUnavailable
from .models import EpcSearchHit, EpcSearchResponse, EpcSection, EpcVersion

# Citation forms to slug:
#   "Article 14" / "Art. 14" / "Art 14" → "a14"
#   "Rule 71" / "R. 71" / "R 71" → "r71"
_CITATION_PATTERN = re.compile(
    r"""
    ^\s*
    (?P<kind>article|art\.?|a|rule|r\.?)         # Article / Rule / abbreviation
    \s*
    (?P<num>\d+[a-z]?)                            # Number, optionally with suffix letter
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)
_SLUG_PATTERN = re.compile(r"^[ar]\d+[a-z]?$", re.IGNORECASE)


def _citation_to_slug(text: str) -> str | None:
    m = _CITATION_PATTERN.match(text)
    if not m:
        return None
    kind = m.group("kind").lower().rstrip(".")
    prefix = "a" if kind in {"article", "art", "a"} else "r"
    return f"{prefix}{m.group('num').lower()}"


def _normalize_href(value: str) -> str:
    """Normalize any of the input forms to a bare slug like ``a14`` / ``r71``."""
    h = value.strip()
    if h.startswith("http"):
        h = h.split("://", 1)[1].split("/", 1)[1]
    h = h.lstrip("/")
    h = re.sub(r"^(?:en/)?legal/epc/\d{4}/", "", h)
    h = h.removesuffix(".html")
    return h.lower()


def _build_result_url(base_url: str, version: str, href: str) -> str:
    return f"{base_url}/en/legal/epc/{version}/{href}.html"


def _hit_to_model(hit: Any, base_url: str, version: str) -> EpcSearchHit:
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
    return EpcSearchHit(
        title=title,
        href=hit.href,
        path=path,
        result_url=_build_result_url(base_url, version, hit.href),
    )


class EpcClient:
    """Corpus-backed EPC + Implementing Regulations client."""

    DEFAULT_BASE_URL: str = os.getenv("EPC_BASE_URL", "https://www.epo.org")
    CACHE_NAME: str = "epc"
    DEFAULT_VERSION: str = os.getenv("EPC_VERSION", "2020")

    def __init__(
        self,
        *,
        corpus_path: str | os.PathLike[str] | None = None,
        base_url: str | None = None,
    ) -> None:
        self._corpus_path = corpus_path
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._db: CorpusDB | None = None

    async def __aenter__(self) -> EpcClient:
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
    ) -> EpcSearchResponse:
        del version, include_content, include_index, include_notes
        del include_form_paragraphs, snippet
        db = self._open()
        fts_query = translate_fts_query(query, syntax)
        if not fts_query:
            return EpcSearchResponse(hits=[], page=page, per_page=per_page, has_more=False)
        offset = max(0, (page - 1) * per_page)
        rows = db.search(fts_query, limit=per_page + 1, offset=offset, sort=sort)
        has_more = len(rows) > per_page
        rows = rows[:per_page]
        meta = db.meta()
        epc_year = meta.get("epc_year", self.DEFAULT_VERSION)
        hits = [_hit_to_model(r, self._base_url, epc_year) for r in rows]
        return EpcSearchResponse(hits=hits, page=page, per_page=per_page, has_more=has_more)

    async def get_section(
        self,
        section: str,
        *,
        version: str = "current",
        highlight_query: str | None = None,  # noqa: ARG002
    ) -> EpcSection:
        del highlight_query
        db = self._open()
        # Citation form first ("Article 14" → "a14"), then bare-slug fallback.
        candidate = _citation_to_slug(section)
        if candidate:
            row = db.get_section(href=candidate)
            if row is not None:
                return EpcSection(
                    href=row.href,
                    html=row.html,
                    text=row.text,
                    version=version,
                    title=row.title,
                )
            # Sometimes callers pass "Article 14" as the section_number
            # (it's stored that way in the corpus).
            row = db.get_section(section_number=_section_number_from_slug(candidate))
            if row is not None:
                return EpcSection(
                    href=row.href,
                    html=row.html,
                    text=row.text,
                    version=version,
                    title=row.title,
                )
        href = _normalize_href(section)
        row = db.get_section(href=href)
        if row is None:
            raise ValueError(f"Could not find EPC section '{section}'")
        return EpcSection(
            href=row.href,
            html=row.html,
            text=row.text,
            version=version,
            title=row.title,
        )

    async def list_versions(self) -> list[EpcVersion]:
        db = self._open()
        meta = db.meta()
        snapshot = meta.get("snapshot_date", "unknown")
        epc_year = meta.get("epc_year", "unknown")
        return [
            EpcVersion(
                label=f"EPC {epc_year} edition (snapshot {snapshot})",
                value="current",
                current=True,
            )
        ]


def _section_number_from_slug(slug: str) -> str | None:
    m = re.match(r"^([ar])(\d+[a-z]?)$", slug, re.IGNORECASE)
    if not m:
        return None
    prefix, num = m.groups()
    label = "Article" if prefix.lower() == "a" else "Rule"
    return f"{label} {num}"


__all__ = [
    "EpcClient",
    "_CITATION_PATTERN",
    "_SLUG_PATTERN",
    "_citation_to_slug",
    "CorpusUnavailable",
]
