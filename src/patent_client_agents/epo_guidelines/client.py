"""Corpus-backed EPO Guidelines for Examination client.

Reads from a SQLite/FTS5 snapshot produced by
``patent-client-agents-build-guidelines-corpus`` and located via
``GUIDELINES_CORPUS_PATH`` or ``~/.cache/patent_client_agents/guidelines.db``.

The corpus is scraped from ``www.epo.org/en/legal/guidelines-epc/<year>/...``.
EPO publishes the Guidelines section-by-section as HTML pages in an
8-part hierarchy (Part A through Part H, plus a "General Part"). Each
section has a stable slug like ``g_ii_3_1`` which encodes Part-Chapter-
Section-Subsection as ``<letter>_<roman>_<num>_<num>``.

Citation forms accepted by ``get_section``:

- URL slug — ``g_ii_3_1`` or ``g_ii_3_1.html``
- Canonical citation — ``G-II, 3.1`` or ``G-II 3.1`` or ``G.II.3.1``
- Path only — ``G-II`` (whole chapter) or ``A`` (whole part)

Public surface mirrors :class:`patent_client_agents.mpep.MpepClient`:
``search``, ``get_section``, ``resolve_section_href``, ``list_versions``.
"""

from __future__ import annotations

import os
import re
from typing import Any

from .corpus.db import CorpusDB, CorpusUnavailable
from .models import (
    GuidelinesSearchHit,
    GuidelinesSearchResponse,
    GuidelinesSection,
    GuidelinesVersion,
)

# Citation forms we recognize before falling back to "treat as slug":
#   G-II, 3.1
#   G-II 3.1
#   G.II.3.1
#   g_ii_3_1
#   G II 3.1
# All map to the URL slug ``g_ii_3_1``.
_CITATION_PATTERN = re.compile(
    r"""
    ^\s*
    (?P<part>[A-H])                          # Part letter
    (?:                                       # Optional chapter+section block
        [-_\s.,]+
        (?P<chapter>[IVX]+)                  # Chapter roman numeral
        (?:
            [-_\s.,]+
            (?P<section>\d+(?:[._-]\d+)*)    # Section numbers (any common separator)
        )?
    )?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)
# Bare slugs like ``g_ii_3_1`` or ``g_ii_3_1.html``:
_SLUG_PATTERN = re.compile(
    r"^([a-h](_[ivx]+(_\d+)*)?(\.html)?|index\.html|general_part\.html)$",
    re.IGNORECASE,
)


def _citation_to_slug(text: str) -> str | None:
    """Map a citation like 'G-II, 3.1' to slug 'g_ii_3_1'.

    Returns None when the input doesn't look like a citation we can
    decode. Bare slugs (``g_ii_3_1`` etc.) round-trip through this
    function unchanged via ``_normalize_href``.
    """
    m = _CITATION_PATTERN.match(text)
    if not m:
        return None
    part = m.group("part").lower()
    chapter = m.group("chapter")
    section = m.group("section")
    slug = part
    if chapter:
        slug += f"_{chapter.lower()}"
    if section:
        # Section numbers can be ``3``, ``3.1``, ``3-1``, ``3.1.4`` etc.
        normalized = re.sub(r"[.,\-]", "_", section)
        slug += "_" + normalized
    return slug


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
    """Normalize any of the input forms to a bare slug.

    Accepts:

    - bare slug ``g_ii_3_1`` (passthrough, just strips .html)
    - relative path ``/en/legal/guidelines-epc/2024/g_ii_3_1.html``
    - absolute URL ``https://www.epo.org/en/legal/guidelines-epc/2024/g_ii_3_1.html``
    """
    h = value.strip()
    if h.startswith("http"):
        h = h.split("://", 1)[1].split("/", 1)[1]
    h = h.lstrip("/")
    # Strip the date-versioned URL prefix in any of the common shapes.
    h = re.sub(r"^(?:en/)?legal/guidelines-epc/\d{4}/", "", h)
    h = h.removesuffix(".html")
    return h.lower()


def _build_result_url(base_url: str, version: str, href: str) -> str:
    return f"{base_url}/en/legal/guidelines-epc/{version}/{href}.html"


def _hit_to_model(hit: Any, base_url: str, version: str) -> GuidelinesSearchHit:
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
    return GuidelinesSearchHit(
        title=title,
        href=hit.href,
        path=path,
        result_url=_build_result_url(base_url, version, hit.href),
    )


class GuidelinesClient:
    """Corpus-backed EPO Guidelines for Examination client."""

    DEFAULT_BASE_URL: str = os.getenv("GUIDELINES_BASE_URL", "https://www.epo.org")
    CACHE_NAME: str = "guidelines"
    DEFAULT_VERSION: str = os.getenv("GUIDELINES_VERSION", "2024")

    def __init__(
        self,
        *,
        corpus_path: str | os.PathLike[str] | None = None,
        base_url: str | None = None,
    ) -> None:
        self._corpus_path = corpus_path
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._db: CorpusDB | None = None

    async def __aenter__(self) -> GuidelinesClient:
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
        version: str = "current",  # API parity; single-snapshot corpus
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
    ) -> GuidelinesSearchResponse:
        del version, include_content, include_index, include_notes
        del include_form_paragraphs, snippet
        db = self._open()
        fts_query = _translate_fts_query(query, syntax)
        if not fts_query:
            return GuidelinesSearchResponse(hits=[], page=page, per_page=per_page, has_more=False)
        offset = max(0, (page - 1) * per_page)
        rows = db.search(fts_query, limit=per_page + 1, offset=offset, sort=sort)
        has_more = len(rows) > per_page
        rows = rows[:per_page]
        meta = db.meta()
        guideline_year = meta.get("guidelines_year", self.DEFAULT_VERSION)
        hits = [_hit_to_model(r, self._base_url, guideline_year) for r in rows]
        return GuidelinesSearchResponse(hits=hits, page=page, per_page=per_page, has_more=has_more)

    async def get_section(
        self,
        section: str,
        *,
        version: str = "current",
        highlight_query: str | None = None,  # noqa: ARG002 — API parity
    ) -> GuidelinesSection:
        del highlight_query
        db = self._open()
        # Try citation-to-slug first (e.g. "G-II, 3.1" → "g_ii_3_1").
        candidate = _citation_to_slug(section)
        if candidate:
            row = db.get_section(href=candidate)
            if row is None:
                # Maybe the corpus indexed it as a section_number too.
                row = db.get_section(section_number=candidate)
            if row is not None:
                return GuidelinesSection(
                    href=row.href,
                    html=row.html,
                    text=row.text,
                    version=version,
                    title=row.title,
                )
        # Fall back to bare-slug / URL normalization.
        href = _normalize_href(section)
        row = db.get_section(href=href)
        if row is None:
            raise ValueError(f"Could not find EPO Guidelines section '{section}'")
        return GuidelinesSection(
            href=row.href,
            html=row.html,
            text=row.text,
            version=version,
            title=row.title,
        )

    async def list_versions(self) -> list[GuidelinesVersion]:
        db = self._open()
        meta = db.meta()
        snapshot = meta.get("snapshot_date", "unknown")
        gle_year = meta.get("guidelines_year", "unknown")
        return [
            GuidelinesVersion(
                label=f"{gle_year} edition (snapshot {snapshot})",
                value="current",
                current=True,
            )
        ]


__all__ = [
    "GuidelinesClient",
    "_CITATION_PATTERN",
    "_SLUG_PATTERN",
    "_citation_to_slug",
    "CorpusUnavailable",
]
