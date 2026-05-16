"""Read-side API for the IPOS Singapore manuals SQLite corpus.

The runtime never builds the corpus — it opens an already-built ``.db``
file produced by ``patent-client-agents-build-ipos-manuals-corpus`` and
serves queries against it. Locator precedence:

1. ``IPOS_MANUALS_CORPUS_PATH`` env var (explicit, used in cloud deploys).
2. ``~/.cache/patent_client_agents/ipos_manuals.db`` (local-dev convenience).

Misses raise :class:`CorpusUnavailable` with a message that tells the
caller how to materialize the database — never a silent fallback.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path


class CorpusUnavailable(RuntimeError):
    """Raised when the IPOS manuals corpus database cannot be located or opened."""


@dataclass(frozen=True)
class CorpusSection:
    manual: str
    short_name: str
    manual_title: str
    section_label: str
    title: str | None
    breadcrumb: str | None
    source_url: str
    source_version: str | None
    text: str


@dataclass(frozen=True)
class CorpusHit:
    manual: str
    short_name: str
    section_label: str
    title: str | None
    breadcrumb: str | None
    snippet: str
    rank: float | None


def default_corpus_path() -> Path:
    """Return the local-dev default location (~/.cache/...)."""
    return Path.home() / ".cache" / "patent_client_agents" / "ipos_manuals.db"


def _resolve_corpus_path(explicit: str | os.PathLike[str] | None) -> Path:
    if explicit is not None:
        return Path(explicit)
    env = os.environ.get("IPOS_MANUALS_CORPUS_PATH")
    if env:
        return Path(env)
    return default_corpus_path()


_INSTALL_HINT = (
    "Run `patent-client-agents-build-ipos-manuals-corpus --output "
    "~/.cache/patent_client_agents/ipos_manuals.db` to build it, or set "
    "IPOS_MANUALS_CORPUS_PATH to an existing corpus file."
)


class CorpusDB:
    """Thin wrapper around the IPOS manuals corpus SQLite connection."""

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
            raise CorpusUnavailable(f"IPOS manuals corpus not found at {resolved}. {_INSTALL_HINT}")
        try:
            conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
        except sqlite3.OperationalError as exc:
            raise CorpusUnavailable(
                f"Could not open IPOS manuals corpus at {resolved}: {exc}. {_INSTALL_HINT}"
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

    def list_manuals(self) -> list[CorpusSection]:
        """Return one representative row per manual (lowest rowid)."""
        rows = self._conn.execute(
            """
            SELECT s.*
            FROM sections s
            INNER JOIN (
                SELECT manual, MIN(rowid) AS min_rowid
                FROM sections
                GROUP BY manual
            ) g ON s.rowid = g.min_rowid
            ORDER BY s.manual
            """
        ).fetchall()
        return [_row_to_section(r) for r in rows]

    def get_section(
        self,
        *,
        manual: str,
        section_label: str,
    ) -> CorpusSection | None:
        row = self._conn.execute(
            "SELECT * FROM sections WHERE manual = ? AND section_label = ?",
            (manual, section_label),
        ).fetchone()
        return _row_to_section(row) if row else None

    def search(
        self,
        query: str,
        *,
        manual: str | None = None,
        limit: int = 10,
        offset: int = 0,
        sort: str = "relevance",
        snippet_chars: int = 200,
    ) -> list[CorpusHit]:
        order = "ORDER BY rank" if sort == "relevance" else "ORDER BY s.manual, s.section_label"
        token_count = max(8, min(snippet_chars // 5, 64))
        filters: list[str] = []
        params: list[object] = [token_count, query]
        sql_parts = [
            "SELECT s.manual, s.short_name, s.section_label, s.title,",
            "       s.breadcrumb,",
            "       snippet(sections_fts, 2, '<mark>', '</mark>', '…', ?) AS snippet,",
            "       rank",
            "FROM sections_fts",
            "JOIN sections s ON s.rowid = sections_fts.rowid",
            "WHERE sections_fts MATCH ?",
        ]
        if manual:
            filters.append("s.manual = ?")
            params.append(manual)
        if filters:
            sql_parts.append("AND " + " AND ".join(filters))
        sql_parts.append(order)
        sql_parts.append("LIMIT ? OFFSET ?")
        params.extend([limit, offset])
        rows = self._conn.execute(" ".join(sql_parts), params).fetchall()
        return [
            CorpusHit(
                manual=row["manual"],
                short_name=row["short_name"],
                section_label=row["section_label"],
                title=row["title"],
                breadcrumb=row["breadcrumb"],
                snippet=row["snippet"] or "",
                rank=row["rank"],
            )
            for row in rows
        ]


def _row_to_section(row: sqlite3.Row) -> CorpusSection:
    return CorpusSection(
        manual=row["manual"],
        short_name=row["short_name"],
        manual_title=row["manual_title"],
        section_label=row["section_label"],
        title=row["title"],
        breadcrumb=row["breadcrumb"],
        source_url=row["source_url"],
        source_version=row["source_version"],
        text=row["text"],
    )


__all__ = [
    "CorpusDB",
    "CorpusUnavailable",
    "CorpusSection",
    "CorpusHit",
    "default_corpus_path",
]
