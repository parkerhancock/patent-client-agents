"""Corpus-backed client for the Taiwan Trade Secrets Act.

Reads from a SQLite/FTS5 snapshot produced by
``patent-client-agents-build-tw-trade-secrets-corpus`` and located via
``TW_TRADE_SECRETS_CORPUS_PATH`` or
``~/.cache/patent_client_agents/tw_trade_secrets.db`` (see
:mod:`patent_client_agents.tw_trade_secrets.corpus.db`).

The corpus bundles the seven core Articles of the Taiwan Trade Secrets
Act (營業秘密法) in the official English translation:

* Art. 1 — Legislative Purpose
* Art. 2 — Definition of Trade Secret
* Art. 3 — Ownership of Trade Secret Derived from Employment
* Art. 10 — Acts Constituting Misappropriation
* Art. 11 — Right to Injunction and Damages
* Art. 13 — Calculation of Damages (incl. treble damages for intent)
* Art. 13-1 — Criminal Liability (inserted by 2013 amendment)
"""

from __future__ import annotations

import os
import re

from patent_client_agents.shared.errors import SectionNotFoundError

from .corpus.db import CorpusDB, CorpusSection, CorpusUnavailable
from .models import (
    TwTradeSecretsCorpusMeta,
    TwTradeSecretsSearchHit,
    TwTradeSecretsSearchResult,
    TwTradeSecretsSection,
)

# Citation forms accepted (case-insensitive):
#   'Art. 2 Trade Secrets Act'
#   'Article 13'
#   'Section 13 Trade Secrets Act'
#   'Sec. 13-1'
#   'S. 13'
#   bare '13' or '13-1'
_CITATION_RE = re.compile(
    r"""
    ^\s*
    (?:art(?:icle|\.)?|sec(?:tion|\.)?|s\.?)\s+   # Art./Article/Sec./Section/S.
    (?P<num>[0-9]+(?:-[0-9]+)?)                    # article number, optional -N suffix
    (?:\s+                                         # optional trailing statute name
        (?:of\s+the\s+)?
        (?:trade\s+secrets?\s+act|act)
    )?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

_BARE_NUM_RE = re.compile(r"^[0-9]+(-[0-9]+)?$")


def parse_citation(citation: str) -> str:
    """Parse a free-text citation into a section number.

    Examples accepted:

    * ``"Art. 2 Trade Secrets Act"`` → ``"2"``
    * ``"Section 13 Trade Secrets Act"`` → ``"13"``
    * ``"Art. 13-1"`` → ``"13-1"``
    * ``"13"`` → ``"13"`` (bare)

    Raises ``ValueError`` on unparseable input.
    """
    text = citation.strip()
    m = _CITATION_RE.match(text)
    if m:
        return m.group("num")
    if _BARE_NUM_RE.match(text):
        return text
    raise ValueError(
        f"Could not parse citation {citation!r}; expected e.g. 'Art. 2 Trade Secrets Act'."
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


def _section_to_model(row: CorpusSection) -> TwTradeSecretsSection:
    return TwTradeSecretsSection(
        section=row.section,
        title=row.title,
        text=row.text,
    )


class TwTradeSecretsClient:
    """Read-only client over the Taiwan Trade Secrets Act SQLite corpus.

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

    async def __aenter__(self) -> TwTradeSecretsClient:
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

    async def meta(self) -> TwTradeSecretsCorpusMeta:
        db = self._open()
        meta = db.meta()
        return TwTradeSecretsCorpusMeta(
            schema_version=int(meta.get("schema_version", 0)),
            snapshot_date=meta.get("snapshot_date"),
            source_version=meta.get("source_version"),
            section_count=int(meta.get("section_count", 0)),
        )

    async def get_section(self, section: str) -> TwTradeSecretsSection:
        """Fetch one Article by section number.

        Accepts either a bare number (``"13"``, ``"13-1"``) or any of
        the citation forms recognised by :func:`parse_citation`.
        """
        db = self._open()
        normalized = (
            parse_citation(section) if not _BARE_NUM_RE.match(section.strip()) else section.strip()
        )
        row = db.get_section(normalized)
        if row is None:
            raise SectionNotFoundError(
                f"Article {normalized!r} not found in the Taiwan Trade Secrets Act corpus."
            )
        return _section_to_model(row)

    async def get_section_by_citation(self, citation: str) -> TwTradeSecretsSection:
        """Fetch one Article by free-text citation.

        Delegates to :func:`parse_citation` then :meth:`get_section`.
        """
        section_number = parse_citation(citation)
        return await self.get_section(section_number)

    async def search(
        self,
        query: str,
        *,
        syntax: str = "and",
        sort: str = "relevance",
        per_page: int = 10,
        page: int = 1,
    ) -> TwTradeSecretsSearchResult:
        db = self._open()
        fts_query = _translate_fts_query(query, syntax)
        if not fts_query:
            return TwTradeSecretsSearchResult(
                query=query,
                hits=[],
                page=page,
                per_page=per_page,
                has_more=False,
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
            TwTradeSecretsSearchHit(
                section=r.section,
                title=r.title,
                snippet=r.snippet,
                rank=r.rank,
            )
            for r in rows
        ]
        return TwTradeSecretsSearchResult(
            query=query,
            hits=hits,
            page=page,
            per_page=per_page,
            has_more=has_more,
        )


__all__ = [
    "TwTradeSecretsClient",
    "CorpusUnavailable",
    "parse_citation",
]
