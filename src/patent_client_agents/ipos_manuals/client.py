"""Corpus-backed client for the IPOS Singapore work manuals."""

from __future__ import annotations

import os
import re

from .corpus.db import CorpusDB, CorpusUnavailable
from .models import (
    IposManual,
    IposManualsCorpusMeta,
    IposManualSearchHit,
    IposManualSearchResponse,
    IposManualSection,
)

# Map every reasonable spelling / abbreviation onto the canonical manual
# key written into the corpus. Lookups are case-insensitive.
MANUAL_ALIASES: dict[str, str] = {
    # Patent Examination Guidelines
    "peg": "peg",
    "patent examination guidelines": "peg",
    "patent guidelines": "peg",
    "patents examination guidelines": "peg",
    "examination guidelines": "peg",
    # Trade Marks Work Manual
    "tm": "tm",
    "tm work manual": "tm",
    "trade marks work manual": "tm",
    "trademarks work manual": "tm",
    "tmwm": "tm",
    # Industrial Designs Work Manual
    "designs": "designs",
    "designs work manual": "designs",
    "industrial designs work manual": "designs",
    "dwm": "designs",
}


def _resolve_manual(name: str | None) -> str | None:
    if name is None:
        return None
    key = name.strip().lower()
    return MANUAL_ALIASES.get(key, key)


# Citation forms accepted by parse_citation:
#   "IPOS PEG 1.5.3"
#   "PEG 1.5.3"
#   "IPOS TM Work Manual 3.4"
#   "TM Work Manual 3.4"
#   "Designs Work Manual 2.1"
_CITATION_FORMS = [
    # "[IPOS ]<manual> <label>"
    re.compile(
        r"^\s*(?:ipos\s+)?(?P<manual>peg|tm(?:\s+work\s+manual)?|designs(?:\s+work\s+manual)?|"
        r"patent\s+examination\s+guidelines|trade\s+marks\s+work\s+manual|"
        r"trademarks\s+work\s+manual|industrial\s+designs\s+work\s+manual)"
        r"\s+(?P<label>\d+(?:\.\d+){0,3}|\d+\.[A-Z](?:\.\d+)?)\s*$",
        re.IGNORECASE,
    ),
    # "<label> <manual>"
    re.compile(
        r"^\s*(?P<label>\d+(?:\.\d+){0,3}|\d+\.[A-Z](?:\.\d+)?)"
        r"\s+(?:ipos\s+)?(?P<manual>peg|tm(?:\s+work\s+manual)?|designs(?:\s+work\s+manual)?|"
        r"patent\s+examination\s+guidelines|trade\s+marks\s+work\s+manual|"
        r"trademarks\s+work\s+manual|industrial\s+designs\s+work\s+manual)\s*$",
        re.IGNORECASE,
    ),
]


def parse_citation(citation: str) -> tuple[str, str] | None:
    """Parse a free-form citation into ``(manual_key, section_label)``."""
    for pattern in _CITATION_FORMS:
        match = pattern.match(citation)
        if not match:
            continue
        manual = _resolve_manual(match.group("manual"))
        label = match.group("label")
        if manual is None or label is None:
            continue
        return manual, label
    return None


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


class IposManualsClient:
    """Read-only client over the IPOS manuals SQLite corpus."""

    def __init__(
        self,
        *,
        corpus_path: str | os.PathLike[str] | None = None,
    ) -> None:
        self._corpus_path = corpus_path
        self._db: CorpusDB | None = None

    async def __aenter__(self) -> IposManualsClient:
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

    async def list_manuals(self) -> list[IposManual]:
        db = self._open()
        rows = db.list_manuals()
        return [
            IposManual(
                manual=row.manual,
                short_name=row.short_name,
                title=row.manual_title,
                source_url=row.source_url,
                source_version=row.source_version,
            )
            for row in rows
        ]

    async def get_section(
        self,
        *,
        manual: str,
        section_label: str,
    ) -> IposManualSection | None:
        canonical = _resolve_manual(manual)
        if canonical is None:
            return None
        db = self._open()
        row = db.get_section(manual=canonical, section_label=section_label)
        if row is None:
            return None
        return IposManualSection(
            manual=row.manual,
            short_name=row.short_name,
            manual_title=row.manual_title,
            section_label=row.section_label,
            title=row.title,
            breadcrumb=row.breadcrumb,
            source_url=row.source_url,
            source_version=row.source_version,
            text=row.text,
        )

    async def get_by_citation(self, citation: str) -> IposManualSection | None:
        parsed = parse_citation(citation)
        if parsed is None:
            return None
        manual, label = parsed
        return await self.get_section(manual=manual, section_label=label)

    async def search(
        self,
        query: str,
        *,
        manual: str | None = None,
        syntax: str = "and",
        sort: str = "relevance",
        per_page: int = 10,
        page: int = 1,
    ) -> IposManualSearchResponse:
        db = self._open()
        fts_query = _translate_fts_query(query, syntax)
        if not fts_query:
            return IposManualSearchResponse(
                query=query, hits=[], page=page, per_page=per_page, has_more=False
            )
        offset = max(0, (page - 1) * per_page)
        rows = db.search(
            fts_query,
            manual=_resolve_manual(manual),
            limit=per_page + 1,
            offset=offset,
            sort=sort,
        )
        has_more = len(rows) > per_page
        rows = rows[:per_page]
        hits = [
            IposManualSearchHit(
                manual=r.manual,
                short_name=r.short_name,
                section_label=r.section_label,
                title=r.title,
                breadcrumb=r.breadcrumb,
                snippet=r.snippet,
                rank=r.rank,
            )
            for r in rows
        ]
        return IposManualSearchResponse(
            query=query, hits=hits, page=page, per_page=per_page, has_more=has_more
        )

    async def meta(self) -> IposManualsCorpusMeta:
        db = self._open()
        meta = db.meta()
        return IposManualsCorpusMeta(
            schema_version=int(meta.get("schema_version", 0)),
            snapshot_date=meta.get("snapshot_date"),
            section_count=int(meta.get("section_count", 0)),
            manual_count=int(meta.get("manual_count", 0)),
            source_version=meta.get("source_version"),
        )


__all__ = [
    "IposManualsClient",
    "CorpusUnavailable",
    "parse_citation",
    "MANUAL_ALIASES",
]
