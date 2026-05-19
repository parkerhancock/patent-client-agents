"""Read-side API for the IPO India MPPP SQLite corpus.

The runtime never builds the corpus — it opens an already-built ``.db``
file produced by ``patent-client-agents-build-ipo-in-mppp-corpus``
and serves queries against it. Locator precedence:

1. ``IPO_IN_MPPP_CORPUS_PATH`` env var (explicit, for cloud deploys).
2. ``~/.cache/patent_client_agents/ipo_in_mppp.db`` (local-dev default).

Misses raise :class:`CorpusUnavailable` with a hint at how to build it.

Lifecycle inherits from :class:`law_tools_core.corpus_db.CorpusDBBase`;
this module declares the MPPP row schema (section_number + chapter +
title + text + source_url) and its FTS5 query path.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from law_tools_core.corpus_db import CorpusDBBase, CorpusUnavailable


@dataclass(frozen=True)
class CorpusSection:
    section_number: str
    chapter: str | None
    title: str | None
    text: str
    source_url: str | None


@dataclass(frozen=True)
class CorpusHit:
    section_number: str
    chapter: str | None
    title: str | None
    snippet: str
    rank: float | None


def default_corpus_path() -> Path:
    """Return the local-dev default location (~/.cache/...)."""
    return Path.home() / ".cache" / "patent_client_agents" / "ipo_in_mppp.db"


class CorpusDB(CorpusDBBase):
    """Thin wrapper around the IPO India MPPP corpus SQLite connection."""

    LABEL = "IPO India MPPP"
    ENV_VAR = "IPO_IN_MPPP_CORPUS_PATH"
    DEFAULT_FILENAME = "ipo_in_mppp.db"
    BUILD_COMMAND = "patent-client-agents-build-ipo-in-mppp-corpus"

    def get_section(self, *, section_number: str) -> CorpusSection | None:
        row = self._conn.execute(
            "SELECT * FROM sections WHERE section_number = ?",
            (section_number,),
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
            query: FTS5 MATCH expression.
            limit / offset: Pagination.
            sort: ``relevance`` (BM25, default) or ``outline``
                (section_number ascending).
            snippet_chars: Approximate snippet width in characters.
        """
        order = "ORDER BY rank" if sort == "relevance" else "ORDER BY s.section_number"
        # snippet() column index 2 = text (section_number, title, text)
        sql = f"""
            SELECT
                s.section_number,
                s.chapter,
                s.title,
                snippet(sections_fts, 2, '<mark>', '</mark>', '…', ?) AS snippet,
                rank
            FROM sections_fts
            JOIN sections s ON s.rowid = sections_fts.rowid
            WHERE sections_fts MATCH ?
            {order}
            LIMIT ? OFFSET ?
        """
        token_count = max(8, min(snippet_chars // 5, 64))
        rows = self._conn.execute(sql, (token_count, query, limit, offset)).fetchall()
        return [
            CorpusHit(
                section_number=row["section_number"],
                chapter=row["chapter"],
                title=row["title"],
                snippet=row["snippet"] or "",
                rank=row["rank"],
            )
            for row in rows
        ]


def _row_to_section(row: sqlite3.Row) -> CorpusSection:
    return CorpusSection(
        section_number=row["section_number"],
        chapter=row["chapter"],
        title=row["title"],
        text=row["text"],
        source_url=row["source_url"],
    )


__all__ = [
    "CorpusDB",
    "CorpusHit",
    "CorpusSection",
    "CorpusUnavailable",
    "default_corpus_path",
]
