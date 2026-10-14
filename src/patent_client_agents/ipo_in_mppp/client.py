"""Corpus-backed client for the IPO India MPPP corpus.

Reads from a SQLite/FTS5 snapshot produced by
``patent-client-agents-build-ipo-in-mppp-corpus`` and located via
``IPO_IN_MPPP_CORPUS_PATH`` or
``~/.cache/patent_client_agents/ipo_in_mppp.db`` (see
:mod:`patent_client_agents.ipo_in_mppp.corpus.db`).

The MPPP (Manual of Patent Practice & Procedure) is the IPO India's
internal examination manual — the US MPEP / UK MoPP / EPO Guidelines
equivalent. Citation form: ``MPPP Chapter 04.05.01``.
"""

from __future__ import annotations

import os
import re

from patent_client_agents.shared.errors import SectionNotFoundError

from .corpus.db import CorpusDB, CorpusSection, CorpusUnavailable
from .models import MpppCorpusMeta, MpppSearchHit, MpppSearchResponse, MpppSection

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


_CITATION_RE = re.compile(
    r"^\s*(?:MPPP\s+)?(?:Chapter\s+|Ch\.?\s+)?(?P<num>\d+(?:\.\d+)*)\s*$",
    re.IGNORECASE,
)


def normalize_section_reference(value: str) -> str:
    """Normalize a user-supplied MPPP section reference to the bare number.

    Accepts:

    * ``"04.05.01"``                     → ``"04.05.01"``
    * ``"Chapter 04.05.01"``             → ``"04.05.01"``
    * ``"MPPP Chapter 04.05.01"``        → ``"04.05.01"``

    Raises ``ValueError`` on unparseable input.
    """
    m = _CITATION_RE.match(value)
    if not m:
        raise ValueError(
            f"Could not parse MPPP reference {value!r}; expected e.g. '04.05.01' or 'MPPP Chapter 04.05.01'."
        )
    return m.group("num")


def _section_to_model(row: CorpusSection) -> MpppSection:
    return MpppSection(
        section_number=row.section_number,
        chapter=row.chapter,
        title=row.title,
        text=row.text,
        source_url=row.source_url,
    )


class MpppClient:
    """Read-only client over the IPO India MPPP SQLite corpus.

    The corpus is opened lazily on first use so callers can construct a
    client in environments where the database hasn't been materialized
    yet (it'll raise :class:`CorpusUnavailable` on the first actual
    call instead).
    """

    def __init__(
        self,
        *,
        corpus_path: str | os.PathLike[str] | None = None,
    ) -> None:
        self._corpus_path = corpus_path
        self._db: CorpusDB | None = None

    async def __aenter__(self) -> MpppClient:
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

    async def meta(self) -> MpppCorpusMeta:
        db = self._open()
        meta = db.meta()
        return MpppCorpusMeta(
            schema_version=int(meta.get("schema_version", 0)),
            snapshot_date=meta.get("snapshot_date"),
            source_version=meta.get("source_version"),
            section_count=int(meta.get("section_count", 0)),
        )

    async def get_section(self, section_reference: str) -> MpppSection:
        """Fetch one MPPP section by reference (e.g. ``'04.05.01'``).

        Accepts the bare dotted number or the citation forms
        ``'Chapter 04.05.01'`` / ``'MPPP Chapter 04.05.01'``.
        """
        db = self._open()
        section_number = normalize_section_reference(section_reference)
        row = db.get_section(section_number=section_number)
        if row is None:
            raise SectionNotFoundError(f"MPPP section {section_reference!r} not found.")
        return _section_to_model(row)

    async def search(
        self,
        query: str,
        *,
        syntax: str = "and",
        sort: str = "relevance",
        per_page: int = 10,
        page: int = 1,
    ) -> MpppSearchResponse:
        db = self._open()
        fts_query = _translate_fts_query(query, syntax)
        if not fts_query:
            return MpppSearchResponse(
                query=query, hits=[], page=page, per_page=per_page, has_more=False
            )
        offset = max(0, (page - 1) * per_page)
        rows = db.search(
            fts_query,
            limit=per_page + 1,
            offset=offset,
            sort=sort,
        )
        has_more = len(rows) > per_page
        rows = rows[:per_page]
        hits = [
            MpppSearchHit(
                section_number=r.section_number,
                chapter=r.chapter,
                title=r.title,
                snippet=r.snippet,
                rank=r.rank,
            )
            for r in rows
        ]
        return MpppSearchResponse(
            query=query,
            hits=hits,
            page=page,
            per_page=per_page,
            has_more=has_more,
        )


__all__ = ["MpppClient", "CorpusUnavailable", "normalize_section_reference"]
