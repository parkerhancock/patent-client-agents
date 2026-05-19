"""Read-side API for the Légifrance IP SQLite corpus.

The runtime never calls Légifrance — it opens an already-built ``.db``
file produced by ``patent-client-agents-build-legifrance-ip-corpus`` and
serves queries against it. Locator precedence:

1. ``LEGIFRANCE_IP_CORPUS_PATH`` env var (explicit, used in cloud deploys).
2. ``~/.cache/patent_client_agents/legifrance_ip.db`` (local-dev convenience).

Misses raise :class:`CorpusUnavailable` with a message telling the
caller how to materialize the database — never a silent fallback.

Lifecycle inherits from :class:`law_tools_core.corpus_db.CorpusDBBase`;
this module declares the Légifrance row schema (statute + section +
title + text) and its FTS5 query path.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from law_tools_core.corpus_db import CorpusDBBase, CorpusUnavailable


@dataclass(frozen=True)
class CorpusSection:
    statute: str
    section: str
    title: str | None
    text: str


@dataclass(frozen=True)
class CorpusHit:
    statute: str
    section: str
    title: str | None
    snippet: str


def default_corpus_path() -> Path:
    """Return the local-dev default location (~/.cache/...)."""
    return Path.home() / ".cache" / "patent_client_agents" / "legifrance_ip.db"


class CorpusDB(CorpusDBBase):
    """Légifrance IP corpus client.

    Open via context manager so the underlying connection is closed
    deterministically::

        with CorpusDB.open() as corpus:
            row = corpus.get_section("CPI", "L611-10")
            hits = corpus.search("brevetabilité")
    """

    LABEL = "Légifrance IP"
    ENV_VAR = "LEGIFRANCE_IP_CORPUS_PATH"
    DEFAULT_FILENAME = "legifrance_ip.db"
    BUILD_COMMAND = "patent-client-agents-build-legifrance-ip-corpus"

    def get_section(self, statute: str, section: str) -> CorpusSection | None:
        row = self._conn.execute(
            "SELECT statute, section, title, text FROM sections WHERE statute = ? AND section = ?",
            (statute, section),
        ).fetchone()
        return _row_to_section(row) if row else None

    def search(
        self,
        query: str,
        *,
        statute: str | None = None,
        limit: int = 10,
        offset: int = 0,
        snippet_chars: int = 200,
    ) -> list[CorpusHit]:
        """Run an FTS5 query against the corpus.

        Args:
            query: An FTS5 MATCH expression (callers translate from the
                public API before calling).
            statute: Optional filter — ``CPI`` or ``Code de commerce``.
            limit: Maximum hits to return.
            offset: Pagination offset.
            snippet_chars: Approximate snippet width in characters.

        Returns:
            A list of :class:`CorpusHit` ordered by BM25 relevance.
        """
        # FTS5 snippet() expects a token count, not chars — divide chars by ~5
        # (a rough average French token length) for a sensible window.
        token_count = max(8, min(snippet_chars // 5, 64))

        if statute is None:
            sql = """
                SELECT
                    s.statute,
                    s.section,
                    s.title,
                    snippet(sections_fts, 1, '<mark>', '</mark>', '…', ?) AS snippet
                FROM sections_fts
                JOIN sections s ON s.rowid = sections_fts.rowid
                WHERE sections_fts MATCH ?
                ORDER BY rank
                LIMIT ? OFFSET ?
            """
            params: tuple = (token_count, query, limit, offset)
        else:
            sql = """
                SELECT
                    s.statute,
                    s.section,
                    s.title,
                    snippet(sections_fts, 1, '<mark>', '</mark>', '…', ?) AS snippet
                FROM sections_fts
                JOIN sections s ON s.rowid = sections_fts.rowid
                WHERE sections_fts MATCH ? AND s.statute = ?
                ORDER BY rank
                LIMIT ? OFFSET ?
            """
            params = (token_count, query, statute, limit, offset)

        rows = self._conn.execute(sql, params).fetchall()
        return [
            CorpusHit(
                statute=row["statute"],
                section=row["section"],
                title=row["title"],
                snippet=row["snippet"] or "",
            )
            for row in rows
        ]

    def count_for(self, query: str, *, statute: str | None = None) -> int:
        if statute is None:
            row = self._conn.execute(
                "SELECT count(*) AS n FROM sections_fts WHERE sections_fts MATCH ?",
                (query,),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT count(*) AS n FROM sections_fts "
                "JOIN sections s ON s.rowid = sections_fts.rowid "
                "WHERE sections_fts MATCH ? AND s.statute = ?",
                (query, statute),
            ).fetchone()
        return int(row["n"])


def _row_to_section(row: sqlite3.Row) -> CorpusSection:
    return CorpusSection(
        statute=row["statute"],
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
