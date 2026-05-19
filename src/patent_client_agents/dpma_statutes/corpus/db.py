"""Read-side API for the DPMA Germany IP statutes SQLite corpus.

The runtime never builds the corpus — it opens an already-built ``.db``
file produced by ``patent-client-agents-build-dpma-statutes-corpus``
and serves queries against it. Locator precedence:

1. ``DPMA_STATUTES_CORPUS_PATH`` env var (explicit, used in cloud deploys).
2. ``~/.cache/patent_client_agents/dpma_statutes.db`` (local-dev default).

Misses raise :class:`CorpusUnavailable` with a hint at how to build it.

Lifecycle inherits from :class:`law_tools_core.corpus_db.CorpusDBBase`;
this module declares the DPMA row schema (statute + section + title +
text) and its FTS5 query path.
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
    rank: float | None


def default_corpus_path() -> Path:
    """Return the local-dev default location (~/.cache/...)."""
    return Path.home() / ".cache" / "patent_client_agents" / "dpma_statutes.db"


class CorpusDB(CorpusDBBase):
    """DPMA Germany IP statutes corpus client.

    Open via context manager so the underlying connection is closed
    deterministically::

        with CorpusDB.open() as corpus:
            section = corpus.get_section(statute="PatG", section="139")
            hits = corpus.search("Patent", limit=10)
    """

    LABEL = "DPMA statutes"
    ENV_VAR = "DPMA_STATUTES_CORPUS_PATH"
    DEFAULT_FILENAME = "dpma_statutes.db"
    BUILD_COMMAND = "patent-client-agents-build-dpma-statutes-corpus"

    def list_statutes(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT statute FROM sections ORDER BY statute"
        ).fetchall()
        return [row["statute"] for row in rows]

    def get_section(self, *, statute: str, section: str) -> CorpusSection | None:
        row = self._conn.execute(
            "SELECT * FROM sections WHERE statute = ? AND section = ?",
            (statute, section),
        ).fetchone()
        return _row_to_section(row) if row else None

    def find_section_by_number(self, section: str) -> list[CorpusSection]:
        """Return every section matching ``section`` across statutes."""
        rows = self._conn.execute(
            "SELECT * FROM sections WHERE section = ? ORDER BY statute",
            (section,),
        ).fetchall()
        return [_row_to_section(r) for r in rows]

    def search(
        self,
        query: str,
        *,
        statute: str | None = None,
        limit: int = 10,
        offset: int = 0,
        sort: str = "relevance",
        snippet_chars: int = 200,
    ) -> list[CorpusHit]:
        """Run an FTS5 query against the corpus.

        Args:
            query: An FTS5 MATCH expression (callers translate from the
                public API's ``syntax`` flag before calling).
            statute: Optional filter to a single Act
                (canonical short-name from :data:`STATUTE_KEYS`).
            limit / offset: Pagination.
            sort: ``relevance`` (BM25, default) or ``outline``
                (statute + section ascending).
            snippet_chars: Approximate snippet width in characters.

        Returns:
            A list of :class:`CorpusHit` in the requested order.
        """
        order = "ORDER BY rank" if sort == "relevance" else "ORDER BY s.statute, s.section"
        # snippet() column index 3 = text (statute, section, title, text)
        token_count = max(8, min(snippet_chars // 5, 64))
        sql_parts = [
            "SELECT s.statute, s.section, s.title,",
            "       snippet(sections_fts, 3, '<mark>', '</mark>', '…', ?) AS snippet,",
            "       rank",
            "FROM sections_fts",
            "JOIN sections s ON s.rowid = sections_fts.rowid",
            "WHERE sections_fts MATCH ?",
        ]
        params: list[object] = [token_count, query]
        if statute:
            sql_parts.append("AND s.statute = ?")
            params.append(statute)
        sql_parts.append(order)
        sql_parts.append("LIMIT ? OFFSET ?")
        params.extend([limit, offset])
        rows = self._conn.execute(" ".join(sql_parts), params).fetchall()
        return [
            CorpusHit(
                statute=row["statute"],
                section=row["section"],
                title=row["title"],
                snippet=row["snippet"] or "",
                rank=row["rank"],
            )
            for row in rows
        ]


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
