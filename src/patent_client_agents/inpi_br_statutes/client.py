"""Corpus-backed LPI (Lei 9.279/1996) client.

Reads from a SQLite/FTS5 snapshot produced by
``patent-client-agents-build-inpi-br-statutes-corpus`` and located via
``INPI_BR_STATUTES_CORPUS_PATH`` or
``~/.cache/patent_client_agents/inpi_br_statutes.db``.

The corpus covers Articles of the *Lei da Propriedade Industrial*
(LPI), which is Brazil's unified IP statute — Title I (patents/utility
models, Arts. 6-93), Title II (designs, Arts. 94-121), Title III (trade
marks, Arts. 122-175), Title IV (geographical indications, Arts.
176-182), Title V (criminal offenses + unfair competition, Arts.
183-210, with the trade-secret rules in Art. 195), and the final
titles.

Slugs follow ``art{n}``: ``art6`` for Article 6, ``art195`` for Article
195 (trade-secret / unfair-competition), etc.

Citation forms accepted by ``get_section``:

- ``Art. 6``, ``Art 6``, ``Article 6``, ``Artigo 6``, ``Art 6 LPI``,
  ``Art. 195(XI) LPI``
- URL slug ``art6`` / ``art195``
- Full Planalto URL with anchor

Public surface mirrors :class:`patent_client_agents.epc.EpcClient`:
``search``, ``get_section``, ``resolve_section_href``,
``list_versions``.
"""

from __future__ import annotations

import os
import re
from typing import Any

from .corpus.db import CorpusDB, CorpusUnavailable
from .models import (
    InpiBrSearchHit,
    InpiBrSearchResponse,
    InpiBrSection,
    InpiBrVersion,
)

# Citation forms to slug:
#   "Art. 6" / "Art 6" / "Article 6" / "Artigo 6" → "art6"
# Allow a trailing " LPI" or " da LPI" so attorney citations like
# "Art. 195(XI) LPI" round-trip. Sub-paragraphs in parentheses or roman
# numerals roll up to the parent Article for now (v1 stores Article-
# level rows; sub-section addressing is a v2 follow-up).
_CITATION_PATTERN = re.compile(
    r"""
    ^\s*
    (?:art\.?|article|artigo|a)        # Art / Article / Artigo / abbreviation
    \s*
    (?P<num>\d+[a-z]?)                  # Article number, optional letter suffix
    (?:\s*\([^)]*\))?                    # Optional "(XI)" sub-section roll-up
    (?:\s*(?:da\s+)?lpi)?                # Optional " LPI" / " da LPI" suffix
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)
_SLUG_PATTERN = re.compile(r"^art\d+[a-z]?$", re.IGNORECASE)


def _citation_to_slug(text: str) -> str | None:
    m = _CITATION_PATTERN.match(text)
    if not m:
        return None
    return f"art{m.group('num').lower()}"


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
    """Normalize any of the input forms to a bare slug like ``art6``."""
    h = value.strip()
    if h.startswith("http"):
        # Pull the fragment if present (#Art6); else strip the path entirely.
        if "#" in h:
            h = h.split("#", 1)[1]
        else:
            return h  # let the caller's lookup fail with a clear error
    h = h.lstrip("#/")
    return h.lower()


def _build_result_url(base_url: str, href: str) -> str:
    # Planalto's anchor convention uses ``#Art6`` (capitalized). We store
    # slug-cased hrefs ``art6`` and reconstruct the display anchor.
    if href.startswith("art"):
        num = href[3:]
        return f"{base_url}#Art{num}"
    return f"{base_url}#{href}"


def _hit_to_model(hit: Any, base_url: str) -> InpiBrSearchHit:
    title_pt = hit.title_pt or ""
    title_en = hit.title_en or ""
    label = hit.article_number or ""
    title = f"{label} — {title_pt}" if label and title_pt else (title_pt or label)
    path: list[str] = []
    if hit.title_section:
        path.append(hit.title_section)
    if hit.article_number:
        path.append(hit.article_number)
    return InpiBrSearchHit(
        title=title,
        href=hit.href,
        article_number=hit.article_number,
        path=path,
        result_url=_build_result_url(base_url, hit.href),
        snippet=hit.snippet,
    )
    # title_en is preserved on the underlying row; consumers needing
    # both languages call get_inpi_br_section.
    del title_en


class InpiBrStatutesClient:
    """Corpus-backed LPI client."""

    DEFAULT_BASE_URL: str = os.getenv(
        "INPI_BR_STATUTES_BASE_URL", "https://www.planalto.gov.br/ccivil_03/leis/l9279.htm"
    )
    CACHE_NAME: str = "inpi_br_statutes"
    DEFAULT_VERSION: str = "current"

    def __init__(
        self,
        *,
        corpus_path: str | os.PathLike[str] | None = None,
        base_url: str | None = None,
    ) -> None:
        self._corpus_path = corpus_path
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._db: CorpusDB | None = None

    async def __aenter__(self) -> InpiBrStatutesClient:
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
        self, article_number: str, *, version: str = "current"
    ) -> str | None:
        del version
        db = self._open()
        row = db.get_section(article_number=article_number)
        return row.href if row else None

    async def search(
        self,
        query: str,
        *,
        version: str = "current",
        syntax: str = "adj",
        sort: str = "relevance",
        per_page: int = 10,
        page: int = 1,
    ) -> InpiBrSearchResponse:
        del version
        db = self._open()
        fts_query = _translate_fts_query(query, syntax)
        if not fts_query:
            return InpiBrSearchResponse(hits=[], page=page, per_page=per_page, has_more=False)
        offset = max(0, (page - 1) * per_page)
        rows = db.search(fts_query, limit=per_page + 1, offset=offset, sort=sort)
        has_more = len(rows) > per_page
        rows = rows[:per_page]
        hits = [_hit_to_model(r, self._base_url) for r in rows]
        return InpiBrSearchResponse(hits=hits, page=page, per_page=per_page, has_more=has_more)

    async def get_section(
        self,
        section: str,
        *,
        version: str = "current",
    ) -> InpiBrSection:
        db = self._open()
        # Citation form first ("Art. 6" → "art6"), then bare-slug fallback.
        candidate = _citation_to_slug(section)
        if candidate:
            row = db.get_section(href=candidate)
            if row is not None:
                return _row_to_model(row, version)
            # Some corpora store the citation form on article_number.
            label = _article_label_from_slug(candidate)
            if label:
                row = db.get_section(article_number=label)
                if row is not None:
                    return _row_to_model(row, version)
        href = _normalize_href(section)
        row = db.get_section(href=href)
        if row is None:
            raise ValueError(f"Could not find LPI section '{section}'")
        return _row_to_model(row, version)

    async def list_versions(self) -> list[InpiBrVersion]:
        db = self._open()
        meta = db.meta()
        snapshot = meta.get("snapshot_date", "unknown")
        lpi_year = meta.get("lpi_year", "unknown")
        return [
            InpiBrVersion(
                label=f"LPI {lpi_year} consolidation (snapshot {snapshot})",
                value="current",
                current=True,
            )
        ]


def _row_to_model(row: Any, version: str) -> InpiBrSection:
    return InpiBrSection(
        href=row.href,
        article_number=row.article_number,
        title_pt=row.title_pt,
        title_en=row.title_en,
        title_section=row.title_section,
        text_pt=row.text_pt,
        text_en=row.text_en,
        html_pt=row.html_pt,
        html_en=row.html_en,
        version=version,
    )


def _article_label_from_slug(slug: str) -> str | None:
    m = re.match(r"^art(\d+[a-z]?)$", slug, re.IGNORECASE)
    if not m:
        return None
    return f"Art. {m.group(1)}"


__all__ = [
    "InpiBrStatutesClient",
    "_CITATION_PATTERN",
    "_SLUG_PATTERN",
    "_citation_to_slug",
    "CorpusUnavailable",
]
