"""Corpus-backed client for the ILPO Israel statutes."""

from __future__ import annotations

import os
import re

from .corpus.db import CorpusDB, CorpusUnavailable
from .models import (
    IlpoCorpusMeta,
    IlpoSearchHit,
    IlpoSearchResponse,
    IlpoSection,
    IlpoStatute,
)

# Friendly aliases → canonical statute key. The canonical keys are
# stable lowercase identifiers; the aliases cover the names lawyers and
# agents actually type. The trade-secret entries deliberately also map
# to ``commercial_torts`` so an agent searching "trade secrets" lands
# on the Israeli statute that governs them.
STATUTE_ALIASES: dict[str, str] = {
    "patents": "patents",
    "patents law": "patents",
    "patent": "patents",
    "trademarks": "trademarks",
    "trademark": "trademarks",
    "trade marks": "trademarks",
    "trade mark": "trademarks",
    "tm": "trademarks",
    "trade marks ordinance": "trademarks",
    "designs": "designs",
    "design": "designs",
    "designs law": "designs",
    "copyright": "copyright",
    "copyright act": "copyright",
    "commercial torts": "commercial_torts",
    "commercial_torts": "commercial_torts",
    "commercial torts law": "commercial_torts",
    "trade secret": "commercial_torts",
    "trade secrets": "commercial_torts",
}


def _resolve_statute(name: str | None) -> str | None:
    if name is None:
        return None
    key = name.strip().lower()
    return STATUTE_ALIASES.get(key, key)


def _translate_fts_query(query: str, syntax: str) -> str:
    """Translate a user-facing query into an FTS5 MATCH expression.

    FTS5 treats ``-``, ``:``, and other punctuation as syntactic
    operators. To keep the user-facing surface simple, every token that
    contains a non-word character is wrapped as a quoted phrase so it
    matches literally.
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


_BARE_TOKEN_RE = re.compile(r"^\w+$", re.UNICODE)


def _quote_if_needed(token: str) -> str:
    if _BARE_TOKEN_RE.match(token):
        return token
    return '"' + token.replace('"', '""') + '"'


# Citation parser: turns "Section 3 Patents Law", "Section 6 Commercial
# Torts Law", "Article 6 Commercial Torts", etc. into a ``(statute,
# section_number)`` pair. The unit prefix is optional; the statute name
# can be any STATUTE_ALIASES key (case-insensitive). Examples:
#   "Section 3 Patents Law" → ("patents", "3")
#   "section 6 commercial torts law" → ("commercial_torts", "6")
#   "Article 6 Commercial Torts" → ("commercial_torts", "6")
#   "patents §3" → ("patents", "3")
_CITATION_RE = re.compile(
    r"""
    ^\s*
    (?:section|sec\.?|article|art\.?|§)?   # optional unit prefix
    \s*
    (?P<num>\d{1,4}[A-Z]?)                # section number
    \s+
    (?P<statute>.+?)                       # statute name (rest of string)
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)


def parse_citation(citation: str) -> tuple[str, str] | None:
    """Parse a citation like ``"Section 3 Patents Law"`` into ``(statute, num)``.

    Returns ``None`` if the citation doesn't match the expected shape
    or the statute name doesn't resolve. The reverse form is also
    accepted — ``"Patents Law §3"`` parses identically.
    """
    cleaned = citation.strip()
    if not cleaned:
        return None
    # Try forward form: "Section 3 Patents Law"
    match = _CITATION_RE.match(cleaned)
    if match:
        statute = _resolve_statute(match.group("statute"))
        if statute is not None and statute in _CANONICAL_STATUTES:
            return statute, match.group("num")
    # Try reverse form: "Patents Law Section 3" / "Patents Law §3"
    reverse_match = re.match(
        r"^(?P<statute>.+?)\s+(?:section|sec\.?|article|art\.?|§)\s*"
        r"(?P<num>\d{1,4}[A-Z]?)\s*$",
        cleaned,
        re.IGNORECASE,
    )
    if reverse_match:
        statute = _resolve_statute(reverse_match.group("statute"))
        if statute is not None and statute in _CANONICAL_STATUTES:
            return statute, reverse_match.group("num")
    return None


_CANONICAL_STATUTES: set[str] = {
    "patents",
    "trademarks",
    "designs",
    "copyright",
    "commercial_torts",
}


class IlpoStatutesClient:
    """Read-only client over the ILPO Israel statutes SQLite corpus.

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

    async def __aenter__(self) -> IlpoStatutesClient:
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

    async def list_statutes(self) -> list[IlpoStatute]:
        db = self._open()
        rows = db.list_statutes()
        return [
            IlpoStatute(
                statute=str(row["statute"]),
                section_count=int(row["section_count"]),  # type: ignore[arg-type]
                source_url=(str(row["source_url"]) if row["source_url"] is not None else None),
            )
            for row in rows
        ]

    async def get_section(
        self,
        *,
        statute: str,
        section_number: str,
    ) -> IlpoSection | None:
        db = self._open()
        canonical = _resolve_statute(statute)
        if canonical is None:
            return None
        row = db.get_section(statute=canonical, section_number=section_number)
        if row is None:
            return None
        return IlpoSection(
            statute=row.statute,
            section_number=row.section_number,
            section_label=row.section_label,
            title=row.title,
            text=row.text,
            source_url=row.source_url,
        )

    async def get_section_by_citation(self, citation: str) -> IlpoSection | None:
        """Resolve a citation like ``"Section 3 Patents Law"`` to a section."""
        parsed = parse_citation(citation)
        if parsed is None:
            return None
        statute, section_number = parsed
        return await self.get_section(statute=statute, section_number=section_number)

    async def search(
        self,
        query: str,
        *,
        statute: str | None = None,
        syntax: str = "and",
        sort: str = "relevance",
        per_page: int = 10,
        page: int = 1,
    ) -> IlpoSearchResponse:
        db = self._open()
        fts_query = _translate_fts_query(query, syntax)
        if not fts_query:
            return IlpoSearchResponse(
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
            IlpoSearchHit(
                statute=r.statute,
                section_number=r.section_number,
                section_label=r.section_label,
                title=r.title,
                snippet=r.snippet,
                rank=r.rank,
            )
            for r in rows
        ]
        return IlpoSearchResponse(
            query=query, hits=hits, page=page, per_page=per_page, has_more=has_more
        )

    async def meta(self) -> IlpoCorpusMeta:
        db = self._open()
        meta = db.meta()
        return IlpoCorpusMeta(
            schema_version=int(meta.get("schema_version", 0)),
            snapshot_date=meta.get("snapshot_date"),
            source_version=meta.get("source_version"),
            section_count=int(meta.get("section_count", 0)),
        )


__all__ = [
    "IlpoStatutesClient",
    "CorpusUnavailable",
    "STATUTE_ALIASES",
    "parse_citation",
]
