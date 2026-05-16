"""Corpus-backed client for the IPOS Singapore statutes."""

from __future__ import annotations

import os
import re

from .corpus.db import CorpusDB, CorpusUnavailable
from .models import (
    IposCorpusMeta,
    IposSection,
    IposStatute,
    IposStatuteSearchHit,
    IposStatuteSearchResponse,
)

# Map every reasonable spelling / abbreviation users will pass through MCP
# back to the canonical statute key written into the corpus. Lookups are
# case-insensitive — the resolver lowercases before keying.
STATUTE_ALIASES: dict[str, str] = {
    # Patents Act
    "patents": "patents",
    "patents act": "patents",
    "patents act 1994": "patents",
    "pa": "patents",
    "pa1994": "patents",
    # Trade Marks Act
    "tm": "tm",
    "trade marks": "tm",
    "trade marks act": "tm",
    "trade marks act 1998": "tm",
    "trademarks": "tm",
    "trademarks act": "tm",
    "tma": "tm",
    "tma1998": "tm",
    # Registered Designs Act
    "designs": "designs",
    "design": "designs",
    "registered designs": "designs",
    "registered designs act": "designs",
    "registered designs act 2000": "designs",
    "rda": "designs",
    "rda2000": "designs",
    # Copyright Act
    "copyright": "copyright",
    "copyright act": "copyright",
    "copyright act 2021": "copyright",
    "ca": "copyright",
    "ca2021": "copyright",
}


def _resolve_statute(name: str | None) -> str | None:
    """Return the canonical statute key or ``None``.

    Unknown keys are passed through lowercased so the DB query can fail
    cleanly downstream (consistent with UPC statutes).
    """
    if name is None:
        return None
    key = name.strip().lower()
    return STATUTE_ALIASES.get(key, key)


# Parses citations like:
#   "Section 13 Patents Act"
#   "Patents Act s. 13"
#   "s 27(1) Trade Marks Act"
#   "13 Patents Act"
#   "Patents Act 13"
_CITATION_FORMS = [
    # "Section <label> <statute>" / "s <label> <statute>" / "s. <label> <statute>"
    re.compile(
        r"^\s*(?:section|sec\.?|s\.?)\s+(?P<label>\d+[A-Z]?(?:\([0-9A-Za-z]+\))?)\s+"
        r"(?P<statute>.+?)\s*$",
        re.IGNORECASE,
    ),
    # "<statute> section <label>" / "<statute> s <label>"
    re.compile(
        r"^\s*(?P<statute>.+?)\s+(?:section|sec\.?|s\.?)\s+"
        r"(?P<label>\d+[A-Z]?(?:\([0-9A-Za-z]+\))?)\s*$",
        re.IGNORECASE,
    ),
    # "<label> <statute>" (bare-number prefix)
    re.compile(
        r"^\s*(?P<label>\d+[A-Z]?(?:\([0-9A-Za-z]+\))?)\s+(?P<statute>.+?)\s*$",
        re.IGNORECASE,
    ),
    # "<statute> <label>" (statute-prefix)
    re.compile(
        r"^\s*(?P<statute>.+?)\s+(?P<label>\d+[A-Z]?(?:\([0-9A-Za-z]+\))?)\s*$",
        re.IGNORECASE,
    ),
]


def parse_citation(citation: str) -> tuple[str, str] | None:
    """Parse a free-form citation into ``(statute_key, section_label)``.

    Returns ``None`` when the citation does not match any of the
    supported forms. The statute portion is resolved through
    :func:`_resolve_statute`; the section label is returned verbatim
    (the corpus stores labels in their upstream form, including
    sub-parts like ``13A`` or ``27(1)``).
    """
    for pattern in _CITATION_FORMS:
        match = pattern.match(citation)
        if not match:
            continue
        statute = _resolve_statute(match.group("statute"))
        label = match.group("label")
        if statute is None or label is None:
            continue
        return statute, label
    return None


_BARE_TOKEN_RE = re.compile(r"^\w+$", re.UNICODE)


def _quote_if_needed(token: str) -> str:
    if _BARE_TOKEN_RE.match(token):
        return token
    return '"' + token.replace('"', '""') + '"'


def _translate_fts_query(query: str, syntax: str) -> str:
    """Translate a user-facing query into an FTS5 MATCH expression.

    FTS5 treats ``-``, ``:``, and other punctuation as operators
    (``-token`` is "exclude", ``col:term`` is column-filter). To keep
    the public surface simple we quote any token containing
    non-word characters so it matches literally.
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


class IposStatutesClient:
    """Read-only client over the IPOS statutes SQLite corpus.

    The corpus is opened lazily so callers can construct a client in
    environments where the database hasn't been materialized yet — the
    first method call raises :class:`CorpusUnavailable` with a hint at
    how to build it.
    """

    def __init__(
        self,
        *,
        corpus_path: str | os.PathLike[str] | None = None,
    ) -> None:
        self._corpus_path = corpus_path
        self._db: CorpusDB | None = None

    async def __aenter__(self) -> IposStatutesClient:
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

    async def list_statutes(self) -> list[IposStatute]:
        db = self._open()
        rows = db.list_statutes()
        return [
            IposStatute(
                statute=row.statute,
                short_name=row.short_name,
                title=row.statute_title,
                source_url=row.source_url,
                source_version=row.source_version,
            )
            for row in rows
        ]

    async def get_section(
        self,
        *,
        statute: str,
        section_label: str,
    ) -> IposSection | None:
        """Fetch one section by ``(statute, section_label)``.

        ``statute`` may be a canonical key or any alias accepted by
        :func:`_resolve_statute` (e.g. ``"Patents Act"``).
        """
        canonical = _resolve_statute(statute)
        if canonical is None:
            return None
        db = self._open()
        row = db.get_section(statute=canonical, section_label=section_label)
        if row is None:
            return None
        return IposSection(
            statute=row.statute,
            short_name=row.short_name,
            statute_title=row.statute_title,
            section_label=row.section_label,
            title=row.title,
            breadcrumb=row.breadcrumb,
            source_url=row.source_url,
            source_version=row.source_version,
            text=row.text,
        )

    async def get_by_citation(self, citation: str) -> IposSection | None:
        """Convenience wrapper that parses a free-form citation string.

        See :func:`parse_citation` for the accepted forms. Returns
        ``None`` when the citation can't be parsed or no matching
        section exists.
        """
        parsed = parse_citation(citation)
        if parsed is None:
            return None
        statute, label = parsed
        return await self.get_section(statute=statute, section_label=label)

    async def search(
        self,
        query: str,
        *,
        statute: str | None = None,
        syntax: str = "and",
        sort: str = "relevance",
        per_page: int = 10,
        page: int = 1,
    ) -> IposStatuteSearchResponse:
        db = self._open()
        fts_query = _translate_fts_query(query, syntax)
        if not fts_query:
            return IposStatuteSearchResponse(
                query=query, hits=[], page=page, per_page=per_page, has_more=False
            )
        offset = max(0, (page - 1) * per_page)
        rows = db.search(
            fts_query,
            statute=_resolve_statute(statute),
            limit=per_page + 1,
            offset=offset,
            sort=sort,
        )
        has_more = len(rows) > per_page
        rows = rows[:per_page]
        hits = [
            IposStatuteSearchHit(
                statute=r.statute,
                short_name=r.short_name,
                section_label=r.section_label,
                title=r.title,
                breadcrumb=r.breadcrumb,
                snippet=r.snippet,
                rank=r.rank,
            )
            for r in rows
        ]
        return IposStatuteSearchResponse(
            query=query, hits=hits, page=page, per_page=per_page, has_more=has_more
        )

    async def meta(self) -> IposCorpusMeta:
        db = self._open()
        meta = db.meta()
        return IposCorpusMeta(
            schema_version=int(meta.get("schema_version", 0)),
            snapshot_date=meta.get("snapshot_date"),
            section_count=int(meta.get("section_count", 0)),
            statute_count=int(meta.get("statute_count", 0)),
            source_version=meta.get("source_version"),
        )


__all__ = [
    "IposStatutesClient",
    "CorpusUnavailable",
    "parse_citation",
    "STATUTE_ALIASES",
]
