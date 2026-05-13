"""Corpus-backed MPEP client.

Replaces the previous HTTP client against ``mpep.uspto.gov`` — USPTO's
``/RDMS/MPEP/search`` endpoint has been intermittently broken since
2026-05-13, and even when healthy, search round-trips are slow. The
runtime now reads exclusively from a SQLite/FTS5 snapshot produced by
``patent-client-agents-build-mpep-corpus`` and located via
``MPEP_CORPUS_PATH`` or ``~/.cache/patent_client_agents/mpep.db`` (see
:mod:`patent_client_agents.mpep.corpus.db`).

The public surface here is preserved exactly so callers don't change:
``search``, ``get_section``, ``resolve_section_href``, ``list_versions``.
"""

from __future__ import annotations

import os
import re
from typing import Any

from .corpus.db import CorpusDB, CorpusUnavailable
from .models import MpepSearchHit, MpepSearchResponse, MpepSection, MpepVersion

# Pattern to detect if input looks like a section number vs an href.
# Section numbers: 2106, 2106.04, 2106.04(a), 706.03(a)(1)
# Hrefs: d0e197244.html, ch2100_d29a1b_13a9e_2dc.html
SECTION_NUMBER_PATTERN = re.compile(r"^\d+(\.\d+)?(\([a-z]\))?(\(\d+\))?$", re.IGNORECASE)


def _translate_fts_query(query: str, syntax: str) -> str:
    """Convert eMPEP-API search params to an FTS5 MATCH expression.

    - ``adj`` / ``exact`` → quoted phrase (multi-word terms stay
      adjacent, which matches eMPEP's ``adj`` semantics).
    - ``or`` → ``term1 OR term2`` between whitespace-separated terms.
    - ``and`` / anything else → space-separated terms (FTS5's default).
    """
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
    """Accept hrefs in any of the forms callers commonly produce."""
    h = value.strip().lstrip("/")
    h = h.removeprefix("current/")
    if not h.endswith(".html"):
        h = f"{h}.html"
    return h


def _hit_to_model(hit: Any, base_url: str) -> MpepSearchHit:
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
    return MpepSearchHit(
        title=title,
        href=hit.href,
        path=path,
        result_url=f"{base_url}/RDMS/MPEP/result?href={hit.href}",
    )


class MpepClient:
    """Corpus-backed eMPEP client.

    The corpus is opened lazily on first use so consumers can still
    construct clients in environments where the database hasn't been
    materialized yet (it'll raise ``CorpusUnavailable`` on the first
    actual call instead).
    """

    DEFAULT_BASE_URL: str = os.getenv("MPEP_BASE_URL", "https://mpep.uspto.gov")
    CACHE_NAME: str = "mpep"

    def __init__(
        self,
        *,
        corpus_path: str | os.PathLike[str] | None = None,
        base_url: str | None = None,
    ) -> None:
        self._corpus_path = corpus_path
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._db: CorpusDB | None = None

    async def __aenter__(self) -> MpepClient:
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
        version: str = "current",  # accepted for API parity; corpus is single-snapshot
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
        snippet: str = "compact",  # FTS5 snippet is always compact-ish
        sort: str = "relevance",
        per_page: int = 10,
        page: int = 1,
    ) -> MpepSearchResponse:
        # Corpus snapshot doesn't distinguish content / index / notes / form
        # paragraphs — all body text is indexed together. We accept the
        # flags for API parity but have no separate corpus to filter on.
        del version, include_content, include_index, include_notes
        del include_form_paragraphs, snippet
        db = self._open()
        fts_query = _translate_fts_query(query, syntax)
        if not fts_query:
            return MpepSearchResponse(hits=[], page=page, per_page=per_page, has_more=False)
        offset = max(0, (page - 1) * per_page)
        # Fetch one extra row to detect whether more pages exist.
        rows = db.search(fts_query, limit=per_page + 1, offset=offset, sort=sort)
        has_more = len(rows) > per_page
        rows = rows[:per_page]
        hits = [_hit_to_model(r, self._base_url) for r in rows]
        return MpepSearchResponse(hits=hits, page=page, per_page=per_page, has_more=has_more)

    async def get_section(
        self,
        section: str,
        *,
        version: str = "current",
        highlight_query: str | None = None,  # noqa: ARG002 — API parity
    ) -> MpepSection:
        del (
            highlight_query
        )  # the corpus stores the canonical HTML; no need to re-fetch a highlighted view
        db = self._open()
        if SECTION_NUMBER_PATTERN.match(section):
            row = db.get_section(section_number=section)
            if row is None:
                raise ValueError(f"Could not find MPEP section '{section}'")
        else:
            href = _normalize_href(section)
            row = db.get_section(href=href)
            if row is None:
                raise ValueError(f"Could not find MPEP href '{section}'")
        return MpepSection(
            href=row.href,
            html=row.html,
            text=row.text,
            version=version,
            title=row.title,
        )

    async def list_versions(self) -> list[MpepVersion]:
        """Single-entry list reflecting the loaded corpus snapshot.

        The corpus only ships one MPEP version (the snapshot recorded
        when ``patent-client-agents-build-mpep-corpus`` last ran);
        return a value field of ``"current"`` so callers passing it to
        :meth:`search` continue to work.
        """
        db = self._open()
        meta = db.meta()
        snapshot = meta.get("snapshot_date", "unknown")
        return [
            MpepVersion(
                label=f"current (snapshot {snapshot})",
                value="current",
                current=True,
            )
        ]


__all__ = ["MpepClient", "SECTION_NUMBER_PATTERN", "CorpusUnavailable"]
