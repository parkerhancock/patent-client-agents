"""Read-side API for the LPI (Lei 9.279/1996) SQLite corpus.

The runtime never builds the corpus — it opens an already-built ``.db``
file produced by ``patent-client-agents-build-inpi-br-statutes-corpus``
and serves queries against it. Locator precedence:

1. ``INPI_BR_STATUTES_CORPUS_PATH`` env var (explicit, used in cloud
   deploys).
2. ``~/.cache/patent_client_agents/inpi_br_statutes.db`` (local-dev
   convenience).

Misses raise :class:`CorpusUnavailable` with a message that tells the
caller how to materialize the database — never a silent fallback.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path


class CorpusUnavailable(RuntimeError):
    """Raised when the LPI corpus database cannot be located or opened."""


@dataclass(frozen=True)
class CorpusSection:
    href: str
    article_number: str | None
    title_pt: str | None
    title_en: str | None
    title_section: str | None
    text_pt: str
    text_en: str | None
    html_pt: str
    html_en: str | None


@dataclass(frozen=True)
class CorpusHit:
    href: str
    article_number: str | None
    title_pt: str | None
    title_en: str | None
    title_section: str | None
    snippet: str


def default_corpus_path() -> Path:
    """Return the local-dev default location (~/.cache/...)."""
    return Path.home() / ".cache" / "patent_client_agents" / "inpi_br_statutes.db"


def _resolve_corpus_path(explicit: str | os.PathLike[str] | None) -> Path:
    if explicit is not None:
        return Path(explicit)
    env = os.environ.get("INPI_BR_STATUTES_CORPUS_PATH")
    if env:
        return Path(env)
    return default_corpus_path()


_INSTALL_HINT = (
    "Run `patent-client-agents-build-inpi-br-statutes-corpus --output "
    "~/.cache/patent_client_agents/inpi_br_statutes.db` to build it, or "
    "set INPI_BR_STATUTES_CORPUS_PATH to an existing corpus file."
)


class CorpusDB:
    """Thin wrapper around the corpus SQLite connection.

    Open via context manager so the underlying connection is closed
    deterministically::

        with CorpusDB.open() as corpus:
            section = corpus.get_section(article_number="Art. 6")
            hits = corpus.search("segredo industrial", limit=10)
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
            raise CorpusUnavailable(f"LPI corpus not found at {resolved}. {_INSTALL_HINT}")
        try:
            conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
        except sqlite3.OperationalError as exc:
            raise CorpusUnavailable(
                f"Could not open LPI corpus at {resolved}: {exc}. {_INSTALL_HINT}"
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
        article_number: str | None = None,
        href: str | None = None,
    ) -> CorpusSection | None:
        if article_number is None and href is None:
            raise ValueError("Provide either article_number or href")
        if href is not None:
            row = self._conn.execute("SELECT * FROM sections WHERE href = ?", (href,)).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM sections WHERE article_number = ?",
                (article_number,),
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
        """Run a FTS5 query against the corpus.

        Args:
            query: An FTS5 MATCH expression (callers translate from the
                public API's `syntax`/`sort` flags before calling).
            limit: Maximum hits to return.
            offset: Pagination offset.
            sort: ``relevance`` (default, BM25) or ``outline``
                (article_number ascending).
            snippet_chars: Approximate snippet width in characters.

        Returns:
            A list of :class:`CorpusHit` in the requested order.
        """
        order = "ORDER BY rank" if sort == "relevance" else "ORDER BY s.article_number"
        # Snippet from the PT text column (column index 3 in the FTS5
        # definition: article_number=0, title_pt=1, title_en=2, text_pt=3,
        # text_en=4). PT is the authoritative version, so it leads the
        # snippet.
        sql = f"""
            SELECT
                s.href,
                s.article_number,
                s.title_pt,
                s.title_en,
                s.title_section,
                snippet(sections_fts, 3, '<mark>', '</mark>', '…', ?) AS snippet
            FROM sections_fts
            JOIN sections s ON s.rowid = sections_fts.rowid
            WHERE sections_fts MATCH ?
            {order}
            LIMIT ? OFFSET ?
        """
        # FTS5 snippet() expects a token count, not chars — divide chars by ~5
        # (a rough average word length) to get a sensible window.
        token_count = max(8, min(snippet_chars // 5, 64))
        rows = self._conn.execute(sql, (token_count, query, limit, offset)).fetchall()
        return [
            CorpusHit(
                href=row["href"],
                article_number=row["article_number"],
                title_pt=row["title_pt"],
                title_en=row["title_en"],
                title_section=row["title_section"],
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
        article_number=row["article_number"],
        title_pt=row["title_pt"],
        title_en=row["title_en"],
        title_section=row["title_section"],
        text_pt=row["text_pt"],
        text_en=row["text_en"],
        html_pt=row["html_pt"],
        html_en=row["html_en"],
    )


__all__ = [
    "CorpusDB",
    "CorpusUnavailable",
    "CorpusSection",
    "CorpusHit",
    "default_corpus_path",
]
