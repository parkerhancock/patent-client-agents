"""Read-side API for the UPC statutes SQLite corpus.

The runtime never builds the corpus — it opens an already-built ``.db``
file produced by ``patent-client-agents-build-upc-statutes-corpus`` and
serves queries against it. Locator precedence:

1. ``UPC_STATUTES_CORPUS_PATH`` env var (explicit, for cloud deploys).
2. ``~/.cache/patent_client_agents/upc_statutes.db`` (local-dev default).

Misses raise :class:`CorpusUnavailable` with a message that tells the
caller how to materialize the database.

Lifecycle inherits from :class:`law_tools_core.corpus_db.CorpusDBBase`;
this module declares the UPC ``instruments`` row schema and its FTS5
query path.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from law_tools_core.corpus_db import CorpusDBBase, CorpusUnavailable


@dataclass(frozen=True)
class CorpusInstrument:
    instrument: str
    language: str
    short_name: str
    title: str
    source_url: str
    source_version: str | None
    pdf_pages: int | None
    text: str


@dataclass(frozen=True)
class CorpusHit:
    instrument: str
    language: str
    short_name: str
    snippet: str
    rank: float | None


def default_corpus_path() -> Path:
    return Path.home() / ".cache" / "patent_client_agents" / "upc_statutes.db"


class CorpusDB(CorpusDBBase):
    """Thin wrapper around the UPC statutes corpus SQLite connection."""

    LABEL = "UPC statutes"
    ENV_VAR = "UPC_STATUTES_CORPUS_PATH"
    DEFAULT_FILENAME = "upc_statutes.db"
    BUILD_COMMAND = "patent-client-agents-build-upc-statutes-corpus"

    def list_instruments(self, *, language: str | None = None) -> list[CorpusInstrument]:
        if language is None:
            rows = self._conn.execute(
                "SELECT * FROM instruments ORDER BY instrument, language"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM instruments WHERE language = ? ORDER BY instrument",
                (language,),
            ).fetchall()
        return [_row_to_instrument(r) for r in rows]

    def get_instrument(self, *, instrument: str, language: str = "en") -> CorpusInstrument | None:
        row = self._conn.execute(
            "SELECT * FROM instruments WHERE instrument = ? AND language = ?",
            (instrument, language),
        ).fetchone()
        return _row_to_instrument(row) if row else None

    def search(
        self,
        query: str,
        *,
        instrument: str | None = None,
        language: str | None = None,
        limit: int = 10,
        offset: int = 0,
        sort: str = "relevance",
        snippet_chars: int = 200,
    ) -> list[CorpusHit]:
        """Run an FTS5 query against the corpus.

        Args:
            query: FTS5 MATCH expression.
            instrument: Optional filter by instrument key.
            language: Optional language filter.
            limit / offset: Pagination.
            sort: ``relevance`` (BM25, default) or ``instrument`` (alphabetical).
            snippet_chars: Approximate snippet width.
        """
        order = "ORDER BY rank" if sort == "relevance" else "ORDER BY i.instrument, i.language"
        filters: list[str] = []
        params: list[object] = []
        token_count = max(8, min(snippet_chars // 5, 64))
        # snippet() column index 2 = text
        sql_parts = [
            "SELECT i.instrument, i.language, i.short_name,",
            "       snippet(instruments_fts, 2, '<mark>', '</mark>', '…', ?) AS snippet,",
            "       rank",
            "FROM instruments_fts",
            "JOIN instruments i ON i.rowid = instruments_fts.rowid",
            "WHERE instruments_fts MATCH ?",
        ]
        params.extend([token_count, query])
        if instrument:
            filters.append("i.instrument = ?")
            params.append(instrument)
        if language:
            filters.append("i.language = ?")
            params.append(language)
        if filters:
            sql_parts.append("AND " + " AND ".join(filters))
        sql_parts.append(order)
        sql_parts.append("LIMIT ? OFFSET ?")
        params.extend([limit, offset])
        rows = self._conn.execute(" ".join(sql_parts), params).fetchall()
        return [
            CorpusHit(
                instrument=row["instrument"],
                language=row["language"],
                short_name=row["short_name"],
                snippet=row["snippet"] or "",
                rank=row["rank"],
            )
            for row in rows
        ]


def _row_to_instrument(row: sqlite3.Row) -> CorpusInstrument:
    return CorpusInstrument(
        instrument=row["instrument"],
        language=row["language"],
        short_name=row["short_name"],
        title=row["title"],
        source_url=row["source_url"],
        source_version=row["source_version"],
        pdf_pages=row["pdf_pages"],
        text=row["text"],
    )


__all__ = [
    "CorpusDB",
    "CorpusHit",
    "CorpusInstrument",
    "CorpusUnavailable",
    "default_corpus_path",
]
