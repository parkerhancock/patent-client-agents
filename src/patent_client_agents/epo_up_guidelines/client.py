"""Corpus-backed EPO Unitary Patent (UP) Guidelines client.

Reads from a SQLite/FTS5 snapshot produced by
``patent-client-agents-build-up-guidelines-corpus`` and located via
``UP_GUIDELINES_CORPUS_PATH`` or ``~/.cache/patent_client_agents/up_guidelines.db``.

The corpus is scraped from ``www.epo.org/en/legal/guidelines-up/<year>/...``.
Unlike the EPC Guidelines (Parts A-H), UP Guidelines use a flat
``section_N_M_P`` slug matching the ``N.M.P`` numbering used in the
text. The 2026 edition has ~140 leaf sections.

Citation forms accepted by ``get_section``:

- Canonical citation — ``1.2.1`` / ``1-2-1`` / ``Section 1.2.1`` / ``§ 1.2.1``
- URL slug — ``section_1_2_1``
- Full URL — ``https://www.epo.org/en/legal/guidelines-up/2026/section_1_2_1``

Public surface mirrors :class:`patent_client_agents.mpep.MpepClient`:
``search``, ``get_section``, ``resolve_section_href``, ``list_versions``.
"""

from __future__ import annotations

import os
import re
from typing import Any

from patent_client_agents.fts_query import translate_fts_query
from patent_client_agents.shared.errors import SectionNotFoundError

from .corpus.db import CorpusDB, CorpusUnavailable
from .models import (
    UpGuidelinesSearchHit,
    UpGuidelinesSearchResponse,
    UpGuidelinesSection,
    UpGuidelinesVersion,
)

# UP Guidelines use a flat ``N.M.P`` numbering matching slug
# ``section_N_M_P``. Citation forms we recognize:
#   1.2.1
#   1-2-1
#   1 2 1
#   Section 1.2.1
#   § 1.2.1
_CITATION_PATTERN = re.compile(
    r"""
    ^\s*
    (?:section\s+|§\s*)?            # optional "Section " or "§" prefix
    (?P<chain>\d+(?:[._\s-]\d+)*)   # dotted/spaced/hyphenated number chain
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)
# Bare slugs like ``section_1_2_1``:
_SLUG_PATTERN = re.compile(r"^section(?:_\d+)+$", re.IGNORECASE)


def _citation_to_slug(text: str) -> str | None:
    """Map ``1.2.1`` (or variants) → ``section_1_2_1``."""
    m = _CITATION_PATTERN.match(text)
    if not m:
        return None
    chain = re.sub(r"[._\s-]+", "_", m.group("chain"))
    return f"section_{chain}"


def _normalize_href(value: str) -> str:
    """Normalize any of the input forms to a bare slug.

    Accepts:

    - bare slug ``section_1_2_1`` (passthrough)
    - relative path ``/en/legal/guidelines-up/2026/section_1_2_1``
    - absolute URL ``https://www.epo.org/en/legal/guidelines-up/2026/section_1_2_1``
    """
    h = value.strip()
    if h.startswith("http"):
        h = h.split("://", 1)[1].split("/", 1)[1]
    h = h.lstrip("/")
    # Strip the date-versioned URL prefix in any of the common shapes.
    h = re.sub(r"^(?:en/)?legal/guidelines-up/\d{4}/", "", h)
    h = h.removesuffix(".html")
    return h.lower()


def _build_result_url(base_url: str, version: str, href: str) -> str:
    return f"{base_url}/en/legal/guidelines-up/{version}/{href}"


def _hit_to_model(hit: Any, base_url: str, version: str) -> UpGuidelinesSearchHit:
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
    return UpGuidelinesSearchHit(
        title=title,
        href=hit.href,
        path=path,
        result_url=_build_result_url(base_url, version, hit.href),
    )


class UpGuidelinesClient:
    """Corpus-backed EPO Unitary Patent (UP) Guidelines client."""

    DEFAULT_BASE_URL: str = os.getenv("UP_GUIDELINES_BASE_URL", "https://www.epo.org")
    CACHE_NAME: str = "up_guidelines"
    DEFAULT_VERSION: str = os.getenv("UP_GUIDELINES_VERSION", "2026")

    def __init__(
        self,
        *,
        corpus_path: str | os.PathLike[str] | None = None,
        base_url: str | None = None,
    ) -> None:
        self._corpus_path = corpus_path
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._db: CorpusDB | None = None

    async def __aenter__(self) -> UpGuidelinesClient:
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
    ) -> UpGuidelinesSearchResponse:
        del version, include_content, include_index, include_notes
        del include_form_paragraphs, snippet
        db = self._open()
        fts_query = translate_fts_query(query, syntax)
        if not fts_query:
            return UpGuidelinesSearchResponse(hits=[], page=page, per_page=per_page, has_more=False)
        offset = max(0, (page - 1) * per_page)
        rows = db.search(fts_query, limit=per_page + 1, offset=offset, sort=sort)
        has_more = len(rows) > per_page
        rows = rows[:per_page]
        meta = db.meta()
        guideline_year = meta.get("up_guidelines_year", self.DEFAULT_VERSION)
        hits = [_hit_to_model(r, self._base_url, guideline_year) for r in rows]
        return UpGuidelinesSearchResponse(
            hits=hits, page=page, per_page=per_page, has_more=has_more
        )

    async def get_section(
        self,
        section: str,
        *,
        version: str = "current",
        highlight_query: str | None = None,  # noqa: ARG002 — API parity
    ) -> UpGuidelinesSection:
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
                return UpGuidelinesSection(
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
            raise SectionNotFoundError(f"Could not find UP Guidelines section '{section}'")
        return UpGuidelinesSection(
            href=row.href,
            html=row.html,
            text=row.text,
            version=version,
            title=row.title,
        )

    async def list_versions(self) -> list[UpGuidelinesVersion]:
        db = self._open()
        meta = db.meta()
        snapshot = meta.get("snapshot_date", "unknown")
        gle_year = meta.get("up_guidelines_year", "unknown")
        return [
            UpGuidelinesVersion(
                label=f"{gle_year} edition (snapshot {snapshot})",
                value="current",
                current=True,
            )
        ]


__all__ = [
    "UpGuidelinesClient",
    "_CITATION_PATTERN",
    "_SLUG_PATTERN",
    "_citation_to_slug",
    "CorpusUnavailable",
]
