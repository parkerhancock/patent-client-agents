"""Corpus-backed client for the DPMA Germany IP statutes corpus.

Reads from a SQLite/FTS5 snapshot produced by
``patent-client-agents-build-dpma-statutes-corpus`` and located via
``DPMA_STATUTES_CORPUS_PATH`` or
``~/.cache/patent_client_agents/dpma_statutes.db`` (see
:mod:`patent_client_agents.dpma_statutes.corpus.db`).

The corpus bundles the six core German IP Acts:

* PatG — Patentgesetz
* MarkenG — Markengesetz
* GebrMG — Gebrauchsmustergesetz
* DesignG — Designgesetz
* UrhG — Urheberrechtsgesetz
* GeschGehG — Geschäftsgeheimnisgesetz
"""

from __future__ import annotations

import os
import re

from patent_client_agents.shared.errors import SectionNotFoundError

from .corpus.db import CorpusDB, CorpusSection, CorpusUnavailable
from .corpus.schema import STATUTE_KEYS
from .models import DpmaCorpusMeta, DpmaSearchHit, DpmaSearchResult, DpmaSection


def _resolve_statute(name: str | None) -> str | None:
    """Map a user-facing statute label to its canonical short-name.

    Accepts case-insensitive synonyms — 'PatG', 'patentgesetz',
    'Patent Act'. Returns ``None`` when the input is ``None``
    (caller-driven "search all statutes"). Unknown labels are passed
    through untouched so the downstream filter cleanly returns no
    hits rather than silently matching everything.
    """
    if name is None:
        return None
    key = name.strip().lower()
    return STATUTE_KEYS.get(key, name.strip())


# Citation parser — accepts:
#   "§ 1 PatG", "§ 139 PatG"
#   "Section 14 MarkenG", "Sec. 14 MarkenG", "S. 14 MarkenG", "s. 14 MarkenG"
#   "§ 5 GeschGehG" (with or without trailing statute)
#   bare numbers like "139" (statute optional)
_CITATION_RE = re.compile(
    r"""
    ^\s*
    (?:§|section|sec\.?|s\.?)\s*       # leading kind: § / Section / Sec. / s.
    (?P<num>[0-9]+[A-Za-z]?             # section number, optional letter suffix
        (?:\([0-9a-zA-Z]+\))*           # optional sub-paragraph(s)
        (?:\.[0-9]+)*                   # optional dotted subsection
    )
    (?:\s+                              # optional statute name
        (?:of\s+the\s+)?
        (?P<statute>.+?)
    )?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def parse_citation(citation: str) -> tuple[str, str | None]:
    """Parse a free-text DPMA citation into (section, statute | None).

    Examples accepted:

    * ``"§ 1 PatG"``          → (``"1"``,    ``"PatG"``)
    * ``"§ 139 PatG"``        → (``"139"``,  ``"PatG"``)
    * ``"§ 14 MarkenG"``      → (``"14"``,   ``"MarkenG"``)
    * ``"§ 1 GebrMG"``        → (``"1"``,    ``"GebrMG"``)
    * ``"§ 5 GeschGehG"``     → (``"5"``,    ``"GeschGehG"``)
    * ``"Section 14 MarkenG"``→ (``"14"``,   ``"MarkenG"``)
    * ``"S. 139 PatG"``       → (``"139"``,  ``"PatG"``)
    * ``"139"``               → (``"139"``,  ``None``)

    Raises ``ValueError`` on unparseable input.
    """
    m = _CITATION_RE.match(citation)
    if m:
        num = m.group("num")
        statute = m.group("statute")
        return num, _resolve_statute(statute) if statute else None
    # Bare section number?
    bare = citation.strip()
    if re.match(r"^[0-9]+[A-Za-z]?(\([0-9a-zA-Z]+\))*(\.[0-9]+)*$", bare):
        return bare, None
    raise ValueError(
        f"Could not parse citation {citation!r}; expected e.g. '§ 1 PatG' or 'Section 14 MarkenG'."
    )


_BARE_TOKEN_RE = re.compile(r"^\w+$", re.UNICODE)


def _quote_if_needed(token: str) -> str:
    if _BARE_TOKEN_RE.match(token):
        return token
    return '"' + token.replace('"', '""') + '"'


def _translate_fts_query(query: str, syntax: str) -> str:
    """Translate a user-facing query into an FTS5 MATCH expression."""
    cleaned = query.strip()
    if not cleaned:
        return ""
    if syntax in ("adj", "exact"):
        escaped = cleaned.replace('"', '""')
        return f'"{escaped}"'
    tokens = [t for t in re.split(r"\s+", cleaned) if t]
    quoted = [_quote_if_needed(t) for t in tokens]
    if syntax == "or":
        return " OR ".join(quoted)
    return " ".join(quoted)


def _section_to_model(row: CorpusSection) -> DpmaSection:
    return DpmaSection(
        statute=row.statute,
        section=row.section,
        title=row.title,
        text=row.text,
    )


class DpmaStatutesClient:
    """Read-only client over the DPMA Germany IP statutes SQLite corpus.

    The corpus is opened lazily on first use so consumers can construct
    a client in environments where the database hasn't been
    materialized yet (it'll raise :class:`CorpusUnavailable` on the
    first actual call instead).
    """

    def __init__(
        self,
        *,
        corpus_path: str | os.PathLike[str] | None = None,
    ) -> None:
        self._corpus_path = corpus_path
        self._db: CorpusDB | None = None

    async def __aenter__(self) -> DpmaStatutesClient:
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

    async def list_statutes(self) -> list[str]:
        db = self._open()
        return db.list_statutes()

    async def meta(self) -> DpmaCorpusMeta:
        db = self._open()
        meta = db.meta()
        return DpmaCorpusMeta(
            schema_version=int(meta.get("schema_version", 0)),
            snapshot_date=meta.get("snapshot_date"),
            source_version=meta.get("source_version"),
            section_count=int(meta.get("section_count", 0)),
        )

    async def get_section(
        self,
        section: str,
        *,
        statute: str | None = None,
    ) -> DpmaSection:
        """Fetch one section by ``(statute, section)``.

        If ``statute`` is omitted, searches all statutes — when the
        section number exists in exactly one, returns it; when it
        exists in multiple, raises ``ValueError`` listing the
        ambiguities; when it doesn't exist at all, raises
        ``ValueError``.
        """
        db = self._open()
        canon = _resolve_statute(statute)
        if canon is not None:
            row = db.get_section(statute=canon, section=section)
            if row is None:
                raise SectionNotFoundError(f"Section {section!r} not found in {canon!r}.")
            return _section_to_model(row)
        rows = db.find_section_by_number(section)
        if not rows:
            raise SectionNotFoundError(f"Section {section!r} not found in any bundled statute.")
        if len(rows) > 1:
            names = ", ".join(r.statute for r in rows)
            raise ValueError(
                f"Section {section!r} is ambiguous — exists in: {names}. "
                "Pass statute= to disambiguate."
            )
        return _section_to_model(rows[0])

    async def get_section_by_citation(self, citation: str) -> DpmaSection:
        """Fetch one section by free-text citation (e.g. ``'§ 139 PatG'``)."""
        section, statute = parse_citation(citation)
        return await self.get_section(section, statute=statute)

    async def search(
        self,
        query: str,
        *,
        statute: str | None = None,
        syntax: str = "and",
        sort: str = "relevance",
        per_page: int = 10,
        page: int = 1,
        offset: int | None = None,
    ) -> DpmaSearchResult:
        db = self._open()
        canon = _resolve_statute(statute)
        fts_query = _translate_fts_query(query, syntax)
        if not fts_query:
            return DpmaSearchResult(
                query=query,
                statute=canon,
                hits=[],
                page=page,
                per_page=per_page,
                has_more=False,
            )
        # A row ``offset`` takes precedence over ``page`` when given.
        if offset is None:
            offset = max(0, (page - 1) * per_page)
        rows = db.search(
            fts_query,
            statute=canon,
            limit=per_page + 1,
            offset=offset,
            sort=sort,
        )
        has_more = len(rows) > per_page
        rows = rows[:per_page]
        hits = [
            DpmaSearchHit(
                statute=r.statute,
                section=r.section,
                title=r.title,
                snippet=r.snippet,
                rank=r.rank,
            )
            for r in rows
        ]
        return DpmaSearchResult(
            query=query,
            statute=canon,
            hits=hits,
            page=page,
            per_page=per_page,
            has_more=has_more,
        )


__all__ = [
    "DpmaStatutesClient",
    "CorpusUnavailable",
    "parse_citation",
]
