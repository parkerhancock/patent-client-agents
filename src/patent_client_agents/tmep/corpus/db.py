"""Read-side API for the TMEP SQLite corpus.

Parallel to :mod:`patent_client_agents.mpep.corpus.db`. Locator
precedence:

1. ``TMEP_CORPUS_PATH`` env var (explicit, used in cloud deploys).
2. ``~/.cache/patent_client_agents/tmep.db`` (local-dev convenience).
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path


class CorpusUnavailable(RuntimeError):
    """Raised when the TMEP corpus database cannot be located or opened."""


@dataclass(frozen=True)
class CorpusSection:
    href: str
    section_number: str | None
    title: str | None
    breadcrumb: str | None
    chapter: str | None
    html: str
    text: str


@dataclass(frozen=True)
class CorpusHit:
    href: str
    section_number: str | None
    title: str | None
    breadcrumb: str | None
    chapter: str | None
    snippet: str


def default_corpus_path() -> Path:
    return Path.home() / ".cache" / "patent_client_agents" / "tmep.db"


def _resolve_corpus_path(explicit: str | os.PathLike[str] | None) -> Path:
    if explicit is not None:
        return Path(explicit)
    env = os.environ.get("TMEP_CORPUS_PATH")
    if env:
        return Path(env)
    return default_corpus_path()


_INSTALL_HINT = (
    "Run `patent-client-agents-build-tmep-corpus --output "
    "~/.cache/patent_client_agents/tmep.db` to build it, or set "
    "TMEP_CORPUS_PATH to an existing corpus file."
)


class CorpusDB:
    """Thin wrapper around the corpus SQLite connection.

    Open via context manager so the underlying connection is closed
    deterministically::

        with CorpusDB.open() as corpus:
            section = corpus.get_section(section_number="1209.03")
            hits = corpus.search("likelihood of confusion", limit=10)
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
            raise CorpusUnavailable(f"TMEP corpus not found at {resolved}. {_INSTALL_HINT}")
        try:
            conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
        except sqlite3.OperationalError as exc:
            raise CorpusUnavailable(
                f"Could not open TMEP corpus at {resolved}: {exc}. {_INSTALL_HINT}"
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

    def get_section(
        self,
        *,
        section_number: str | None = None,
        href: str | None = None,
    ) -> CorpusSection | None:
        if section_number is None and href is None:
            raise ValueError("Provide either section_number or href")
        if href is not None:
            row = self._conn.execute("SELECT * FROM sections WHERE href = ?", (href,)).fetchone()
        else:
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
        order = "ORDER BY rank" if sort == "relevance" else "ORDER BY s.section_number"
        sql = f"""
            SELECT
                s.href,
                s.section_number,
                s.title,
                s.breadcrumb,
                s.chapter,
                snippet(sections_fts, 2, '<mark>', '</mark>', '…', ?) AS snippet
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
                href=row["href"],
                section_number=row["section_number"],
                title=row["title"],
                breadcrumb=row["breadcrumb"],
                chapter=row["chapter"],
                snippet=row["snippet"] or "",
            )
            for row in rows
        ]

    def count_for(self, query: str) -> int:
        row = self._conn.execute(
            "SELECT count(*) AS n FROM sections_fts WHERE sections_fts MATCH ?",
            (query,),
        ).fetchone()
        return int(row["n"])


def _row_to_section(row: sqlite3.Row) -> CorpusSection:
    return CorpusSection(
        href=row["href"],
        section_number=row["section_number"],
        title=row["title"],
        breadcrumb=row["breadcrumb"],
        chapter=row["chapter"],
        html=row["html"],
        text=row["text"],
    )


__all__ = [
    "CorpusDB",
    "CorpusUnavailable",
    "CorpusSection",
    "CorpusHit",
    "default_corpus_path",
]
