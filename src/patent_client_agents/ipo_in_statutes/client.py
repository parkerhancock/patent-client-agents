"""Corpus-backed client for the IPO India statutes corpus.

Reads from a SQLite/FTS5 snapshot produced by
``patent-client-agents-build-ipo-in-statutes-corpus`` and located via
``IPO_IN_STATUTES_CORPUS_PATH`` or
``~/.cache/patent_client_agents/ipo_in_statutes.db`` (see
:mod:`patent_client_agents.ipo_in_statutes.corpus.db`).

The corpus bundles four Indian IP Acts plus the Patent Rules:

* Patents Act, 1970 (incorporating amendments through 2024)
* Patent Rules, 2003 (with 2024 amendments)
* Designs Act, 2000
* Trade Marks Act, 1999
* Copyright Act, 1957 (last amended 2012)

The four Acts cross-reference each other (e.g. §107A Patents Act
references the Copyright Act parallel-imports rule), so bundling them
in one corpus with a ``statute_name`` discriminator avoids a multi-DB
join.
"""

from __future__ import annotations

import os
import re

from patent_client_agents.shared.errors import SectionNotFoundError

from .corpus.db import CorpusDB, CorpusSection, CorpusUnavailable
from .corpus.schema import STATUTE_KEYS
from .models import IpoInCorpusMeta, IpoInSearchHit, IpoInSearchResponse, IpoInSection


def _resolve_statute(name: str | None) -> str | None:
    """Map a user-facing statute label to its canonical ``statute_name``.

    Accepts case-insensitive synonyms — 'patents act', 'PATENTS ACT 1970',
    'trademarks', 'trade marks act 1999', etc. Returns ``None`` when the
    input is ``None`` (caller-driven "search all statutes").
    """
    if name is None:
        return None
    key = name.strip().lower()
    return STATUTE_KEYS.get(key, name.strip())


_CITATION_RE = re.compile(
    r"""
    ^\s*
    (?:section|sec\.?|s\.?|rule|r\.?)\s+      # leading kind
    (?P<num>[0-9]+[A-Za-z]?                    # section number, optional letter suffix
        (?:\([0-9a-zA-Z]+\))*                  # optional sub-paragraph(s)
        (?:\.[0-9]+)*                          # optional dotted subsection
    )
    (?:\s+                                     # optional statute name
        (?:of\s+the\s+)?
        (?P<statute>.+?)
    )?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def parse_citation(citation: str) -> tuple[str, str | None]:
    """Parse a free-text citation into (section_number, statute_name | None).

    Examples accepted:

    * ``"Section 3(d) Patents Act"`` → (``"3(d)"``, ``"Patents Act"``)
    * ``"Section 25(2)"``           → (``"25(2)"``, ``None``)
    * ``"Rule 71 Patent Rules"``    → (``"71"``,    ``"Patent Rules"``)
    * ``"S. 84"``                   → (``"84"``,    ``None``)

    Raises ``ValueError`` on unparseable input. The bare-number form
    (``"3(d)"``) is accepted by :meth:`IpoInStatutesClient.get_section`;
    this parser is the more permissive surface for the MCP layer.
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
        f"Could not parse citation {citation!r}; expected e.g. 'Section 3(d) Patents Act'."
    )


_BARE_TOKEN_RE = re.compile(r"^\w+$", re.UNICODE)


def _quote_if_needed(token: str) -> str:
    if _BARE_TOKEN_RE.match(token):
        return token
    return '"' + token.replace('"', '""') + '"'


def _translate_fts_query(query: str, syntax: str) -> str:
    """Translate a user-facing query into an FTS5 MATCH expression.

    FTS5 treats ``-``, ``:``, and other punctuation as syntactic
    operators; every token containing a non-word character is wrapped
    as a quoted phrase so it matches literally.
    """
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


def _section_to_model(row: CorpusSection) -> IpoInSection:
    return IpoInSection(
        statute_name=row.statute_name,
        section_number=row.section_number,
        title=row.title,
        text=row.text,
        source_url=row.source_url,
    )


class IpoInStatutesClient:
    """Read-only client over the IPO India statutes SQLite corpus.

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

    async def __aenter__(self) -> IpoInStatutesClient:
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

    async def meta(self) -> IpoInCorpusMeta:
        db = self._open()
        meta = db.meta()
        return IpoInCorpusMeta(
            schema_version=int(meta.get("schema_version", 0)),
            snapshot_date=meta.get("snapshot_date"),
            source_version=meta.get("source_version"),
            section_count=int(meta.get("section_count", 0)),
        )

    async def get_section(
        self,
        section_number: str,
        *,
        statute_name: str | None = None,
    ) -> IpoInSection:
        """Fetch one section by ``(statute_name, section_number)``.

        If ``statute_name`` is omitted, searches all statutes — when
        the section number exists in exactly one, returns it; when it
        exists in multiple, raises ``ValueError`` listing the
        ambiguities; when it doesn't exist at all, raises
        ``ValueError``.
        """
        db = self._open()
        statute = _resolve_statute(statute_name)
        if statute is not None:
            row = db.get_section(statute_name=statute, section_number=section_number)
            if row is None:
                raise SectionNotFoundError(f"Section {section_number!r} not found in {statute!r}.")
            return _section_to_model(row)
        # Statute not specified — disambiguate via cross-statute lookup.
        rows = db.find_section_by_number(section_number)
        if not rows:
            raise SectionNotFoundError(
                f"Section {section_number!r} not found in any bundled statute."
            )
        if len(rows) > 1:
            names = ", ".join(r.statute_name for r in rows)
            raise ValueError(
                f"Section {section_number!r} is ambiguous — exists in: {names}. "
                "Pass statute_name= to disambiguate."
            )
        return _section_to_model(rows[0])

    async def get_section_by_citation(self, citation: str) -> IpoInSection:
        """Fetch one section by free-text citation (e.g. ``'Section 3(d) Patents Act'``).

        Delegates to :func:`parse_citation` then :meth:`get_section`.
        """
        section_number, statute_name = parse_citation(citation)
        return await self.get_section(section_number, statute_name=statute_name)

    async def search(
        self,
        query: str,
        *,
        statute_name: str | None = None,
        syntax: str = "and",
        sort: str = "relevance",
        per_page: int = 10,
        page: int = 1,
        offset: int | None = None,
    ) -> IpoInSearchResponse:
        db = self._open()
        statute = _resolve_statute(statute_name)
        fts_query = _translate_fts_query(query, syntax)
        if not fts_query:
            return IpoInSearchResponse(
                query=query,
                statute_name=statute,
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
            statute_name=statute,
            limit=per_page + 1,
            offset=offset,
            sort=sort,
        )
        has_more = len(rows) > per_page
        rows = rows[:per_page]
        hits = [
            IpoInSearchHit(
                statute_name=r.statute_name,
                section_number=r.section_number,
                title=r.title,
                snippet=r.snippet,
                rank=r.rank,
            )
            for r in rows
        ]
        return IpoInSearchResponse(
            query=query,
            statute_name=statute,
            hits=hits,
            page=page,
            per_page=per_page,
            has_more=has_more,
        )


__all__ = [
    "IpoInStatutesClient",
    "CorpusUnavailable",
    "parse_citation",
]
