"""Read-side API for the Taiwan Trade Secrets Act SQLite corpus.

The runtime never builds the corpus — it opens an already-built ``.db``
file produced by ``patent-client-agents-build-tw-trade-secrets-corpus``
and serves queries against it. Locator precedence:

1. ``TW_TRADE_SECRETS_CORPUS_PATH`` env var (explicit, used in cloud deploys).
2. ``~/.cache/patent_client_agents/tw_trade_secrets.db`` (local-dev default).

Misses raise :class:`CorpusUnavailable` with a hint at how to build it.

Lifecycle (open/close/meta/path resolution) inherits from
:class:`law_tools_core.corpus_db.CorpusDBBase`; this module declares the
TW Trade Secrets row schema (section + title + text) and its FTS5
query path.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from law_tools_core.corpus_db import CorpusDBBase, CorpusUnavailable


@dataclass(frozen=True)
class CorpusSection:
    section: str
    title: str | None
    text: str


@dataclass(frozen=True)
class CorpusHit:
    section: str
    title: str | None
    snippet: str
    rank: float | None


def default_corpus_path() -> Path:
    """Return the local-dev default location (~/.cache/...)."""
    return Path.home() / ".cache" / "patent_client_agents" / "tw_trade_secrets.db"


class CorpusDB(CorpusDBBase):
    """Taiwan Trade Secrets Act corpus client.

    Open via context manager so the underlying connection is closed
    deterministically::

        with CorpusDB.open() as corpus:
            section = corpus.get_section("13-1")
            hits = corpus.search("damages", limit=10)
    """

    LABEL = "TW Trade Secrets"
    ENV_VAR = "TW_TRADE_SECRETS_CORPUS_PATH"
    DEFAULT_FILENAME = "tw_trade_secrets.db"
    BUILD_COMMAND = "patent-client-agents-build-tw-trade-secrets-corpus"

    def get_section(self, section: str) -> CorpusSection | None:
        row = self._conn.execute(
            "SELECT section, title, text FROM sections WHERE section = ?",
            (section,),
        ).fetchone()
        return _row_to_section(row) if row else None

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        sort: str = "relevance",
        snippet_chars: int = 200,
    ) -> list[CorpusHit]:
        """Run an FTS5 query against the corpus.

        Args:
            query: An FTS5 MATCH expression (callers translate from the
                public API's ``syntax`` flag before calling).
            limit / offset: Pagination.
            sort: ``relevance`` (BM25, default) or ``outline`` (section
                ascending — note this is a string sort over numeric-ish
                values, so ``"13-1"`` sorts after ``"13"`` and before
                ``"2"`` lexicographically; callers can re-sort if a
                strict numeric outline is needed).
            snippet_chars: Approximate snippet width in characters.

        Returns:
            A list of :class:`CorpusHit` in the requested order.
        """
        order = "ORDER BY rank" if sort == "relevance" else "ORDER BY s.section"
        # snippet() column index 2 = text (section, title, text)
        token_count = max(8, min(snippet_chars // 5, 64))
        sql = f"""
            SELECT
                s.section,
                s.title,
                snippet(sections_fts, 2, '<mark>', '</mark>', '…', ?) AS snippet,
                rank
            FROM sections_fts
            JOIN sections s ON s.rowid = sections_fts.rowid
            WHERE sections_fts MATCH ?
            {order}
            LIMIT ? OFFSET ?
        """
        rows = self._conn.execute(sql, (token_count, query, limit, offset)).fetchall()
        return [
            CorpusHit(
                section=row["section"],
                title=row["title"],
                snippet=row["snippet"] or "",
                rank=row["rank"],
            )
            for row in rows
        ]


def _row_to_section(row: sqlite3.Row) -> CorpusSection:
    return CorpusSection(
        section=row["section"],
        title=row["title"],
        text=row["text"],
    )


__all__ = [
    "CorpusDB",
    "CorpusHit",
    "CorpusSection",
    "CorpusUnavailable",
    "default_corpus_path",
]
