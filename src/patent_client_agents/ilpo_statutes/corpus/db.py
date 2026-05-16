"""Read-side API for the ILPO Israel statutes SQLite corpus.

The runtime never builds the corpus — it opens an already-built ``.db``
file produced by ``patent-client-agents-build-ilpo-statutes-corpus`` and
serves queries against it. Locator precedence:

1. ``ILPO_STATUTES_CORPUS_PATH`` env var (explicit, for cloud deploys).
2. ``~/.cache/patent_client_agents/ilpo_statutes.db`` (local-dev default).

Misses raise :class:`CorpusUnavailable` with a message that tells the
caller how to materialize the database.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path


class CorpusUnavailable(RuntimeError):
    """Raised when the ILPO statutes corpus cannot be located or opened."""


@dataclass(frozen=True)
class CorpusSection:
    statute: str
    section_number: str
    section_label: str
    title: str | None
    text: str
    source_url: str | None


@dataclass(frozen=True)
class CorpusHit:
    statute: str
    section_number: str
    section_label: str
    title: str | None
    snippet: str
    rank: float | None


def default_corpus_path() -> Path:
    """Return the local-dev default location (~/.cache/...)."""
    return Path.home() / ".cache" / "patent_client_agents" / "ilpo_statutes.db"


def _resolve_corpus_path(explicit: str | os.PathLike[str] | None) -> Path:
    if explicit is not None:
        return Path(explicit)
    env = os.environ.get("ILPO_STATUTES_CORPUS_PATH")
    if env:
        return Path(env)
    return default_corpus_path()


_INSTALL_HINT = (
    "Run `patent-client-agents-build-ilpo-statutes-corpus --output "
    "~/.cache/patent_client_agents/ilpo_statutes.db` to build it, or set "
    "ILPO_STATUTES_CORPUS_PATH to an existing corpus file."
)


class CorpusDB:
    """Thin wrapper around the corpus SQLite connection.

    Open via context manager so the underlying connection is closed
    deterministically::

        with CorpusDB.open() as corpus:
            section = corpus.get_section(statute="patents", section_number="3")
            hits = corpus.search("trade secret", statute="commercial_torts")
    """

    def __init__(self, conn: sqlite3.Connection, path: Path) -> None:
        self._conn = conn
        self._path = path
        conn.row_factory = sqlite3.Row

    @classmethod
    def open(
        cls, path: str | os.PathLike[str] | None = None, *, must_exist: bool = True
    ) -> CorpusDB:
        resolved = _resolve_corpus_path(path)
        if must_exist and not resolved.exists():
            raise CorpusUnavailable(
                f"ILPO statutes corpus not found at {resolved}. {_INSTALL_HINT}"
            )
        try:
            conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
        except sqlite3.OperationalError as exc:
            raise CorpusUnavailable(
                f"Could not open ILPO statutes corpus at {resolved}: {exc}. {_INSTALL_HINT}"
            ) from exc
        return cls(conn, resolved)

    @property
    def path(self) -> Path:
        return self._path

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> CorpusDB:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def meta(self) -> dict[str, str]:
        rows = self._conn.execute("SELECT key, value FROM meta").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def list_statutes(self) -> list[dict[str, object]]:
        """Return one row per statute with its section count and source URL."""
        rows = self._conn.execute(
            """
            SELECT statute,
                   COUNT(*) AS section_count,
                   MIN(source_url) AS source_url
            FROM sections
            GROUP BY statute
            ORDER BY statute
            """
        ).fetchall()
        return [
            {
                "statute": row["statute"],
                "section_count": int(row["section_count"]),
                "source_url": row["source_url"],
            }
            for row in rows
        ]

    def get_section(
        self,
        *,
        statute: str,
        section_number: str,
    ) -> CorpusSection | None:
        row = self._conn.execute(
            "SELECT * FROM sections WHERE statute = ? AND section_number = ?",
            (statute, section_number),
        ).fetchone()
        return _row_to_section(row) if row else None

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
            statute: Optional statute key filter (e.g. ``"patents"``).
            limit / offset: Pagination.
            sort: ``relevance`` (BM25, default) or ``outline``
                (statute then section_number).
            snippet_chars: Approximate snippet width in characters.

        Returns:
            A list of :class:`CorpusHit` in the requested order.
        """
        order = "ORDER BY rank" if sort == "relevance" else "ORDER BY s.statute, s.section_number"
        filters: list[str] = []
        params: list[object] = []
        token_count = max(8, min(snippet_chars // 5, 64))
        sql_parts = [
            "SELECT s.statute, s.section_number, s.section_label, s.title,",
            "       snippet(sections_fts, 3, '<mark>', '</mark>', '…', ?) AS snippet,",
            "       rank",
            "FROM sections_fts",
            "JOIN sections s ON s.rowid = sections_fts.rowid",
            "WHERE sections_fts MATCH ?",
        ]
        params.extend([token_count, query])
        if statute:
            filters.append("s.statute = ?")
            params.append(statute)
        if filters:
            sql_parts.append("AND " + " AND ".join(filters))
        sql_parts.append(order)
        sql_parts.append("LIMIT ? OFFSET ?")
        params.extend([limit, offset])
        rows = self._conn.execute(" ".join(sql_parts), params).fetchall()
        return [
            CorpusHit(
                statute=row["statute"],
                section_number=row["section_number"],
                section_label=row["section_label"],
                title=row["title"],
                snippet=row["snippet"] or "",
                rank=row["rank"],
            )
            for row in rows
        ]


def _row_to_section(row: sqlite3.Row) -> CorpusSection:
    return CorpusSection(
        statute=row["statute"],
        section_number=row["section_number"],
        section_label=row["section_label"],
        title=row["title"],
        text=row["text"],
        source_url=row["source_url"],
    )


__all__ = [
    "CorpusDB",
    "CorpusUnavailable",
    "CorpusSection",
    "CorpusHit",
    "default_corpus_path",
]
