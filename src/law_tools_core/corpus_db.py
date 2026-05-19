"""Shared read-only SQLite/FTS5 client for bundled law/IP corpora.

Connectors that ship a static corpus (MPEP, TMEP, EPC, EPO Guidelines,
DPMA, etc.) share the same lifecycle: locate the ``.db`` file, open it
read-only via SQLite URI mode, expose ``meta()``/``meta_get()`` from the
corpus's ``meta`` table, and serve FTS5 queries against the
``sections_fts`` virtual table. The per-corpus row shape varies — the
majority share an "outline" schema (href + section_number + breadcrumb
+ chapter + html + text), but a handful (statute-shaped corpora) carry
their own keys.

This module provides:

* :class:`CorpusUnavailable` — universal exception for missing/unopenable
  corpora. Subclassing ``RuntimeError`` preserves the pre-extraction
  catch hierarchy.
* :class:`CorpusDBBase` — lifecycle (open/close/context manager/path
  resolution/error formatting/``meta`` access). Subclasses declare the
  per-corpus class vars and implement their own ``get_section`` /
  ``search`` when the row schema diverges from the outline shape.
* :class:`OutlineCorpusSection` / :class:`OutlineCorpusHit` — frozen
  dataclasses for the eight outline-shaped corpora.
* :class:`OutlineCorpusDB` — drop-in base for the outline-shaped
  corpora; ships ``get_section``, ``search``, ``count_for``, and
  ``_row_to_section`` out of the box.

Subclassing example (outline shape — the common case)::

    from pathlib import Path
    from law_tools_core.corpus_db import OutlineCorpusDB, CorpusUnavailable

    class CorpusDB(OutlineCorpusDB):
        LABEL = "MPEP"
        ENV_VAR = "MPEP_CORPUS_PATH"
        DEFAULT_FILENAME = "mpep.db"
        BUILD_COMMAND = "patent-client-agents-build-mpep-corpus"

Statute-shaped subclassing (override ``get_section``/``search``)::

    class CorpusDB(CorpusDBBase):
        LABEL = "Taiwan Trade Secrets"
        ENV_VAR = "TW_TRADE_SECRETS_CORPUS_PATH"
        DEFAULT_FILENAME = "tw_trade_secrets.db"
        BUILD_COMMAND = "patent-client-agents-build-tw-trade-secrets-corpus"

        def get_section(self, section: str) -> CorpusSection | None: ...
        def search(self, query: str, *, limit: int = 10, ...): ...
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar


class CorpusUnavailable(RuntimeError):
    """Raised when a bundled corpus database cannot be located or opened."""


def _cache_root() -> Path:
    """The directory we recommend in install hints (and used as the default base)."""
    return Path.home() / ".cache" / "patent_client_agents"


class CorpusDBBase:
    """Read-only SQLite client for a bundled corpus.

    Subclasses must declare four class variables:

    * ``LABEL`` — human-readable corpus name used in error messages
      (e.g. ``"MPEP"``, ``"EPC"``, ``"DPMA statutes"``).
    * ``ENV_VAR`` — environment variable that overrides the default path
      (e.g. ``"MPEP_CORPUS_PATH"``).
    * ``DEFAULT_FILENAME`` — filename under ``~/.cache/patent_client_agents/``
      (e.g. ``"mpep.db"``).
    * ``BUILD_COMMAND`` — CLI command used to build the corpus, surfaced
      in error hints (e.g. ``"patent-client-agents-build-mpep-corpus"``).

    Subclasses MAY override :meth:`get_section`, :meth:`search`, and
    :meth:`_row_to_section` when the corpus row schema diverges from the
    outline shape. :class:`OutlineCorpusDB` provides defaults for the
    common case.
    """

    LABEL: ClassVar[str]
    ENV_VAR: ClassVar[str]
    DEFAULT_FILENAME: ClassVar[str]
    BUILD_COMMAND: ClassVar[str]

    def __init__(self, conn: sqlite3.Connection, path: Path) -> None:
        self._conn = conn
        self._path = path
        conn.row_factory = sqlite3.Row

    # ------------------------------------------------------------------
    # Path resolution + install hints
    # ------------------------------------------------------------------

    @classmethod
    def default_path(cls) -> Path:
        """Local-dev default location (``~/.cache/patent_client_agents/<file>``)."""
        return _cache_root() / cls.DEFAULT_FILENAME

    @classmethod
    def _resolve_path(cls, explicit: str | os.PathLike[str] | None) -> Path:
        if explicit is not None:
            return Path(explicit)
        env = os.environ.get(cls.ENV_VAR)
        if env:
            return Path(env)
        return cls.default_path()

    @classmethod
    def _install_hint(cls) -> str:
        return (
            f"Run `{cls.BUILD_COMMAND} --output "
            f"~/.cache/patent_client_agents/{cls.DEFAULT_FILENAME}` to build it, "
            f"or set {cls.ENV_VAR} to an existing corpus file."
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @classmethod
    def open(
        cls,
        path: str | os.PathLike[str] | None = None,
        *,
        must_exist: bool = True,
    ) -> CorpusDBBase:
        """Open the corpus read-only.

        Resolution order: explicit ``path`` → ``cls.ENV_VAR`` → default
        cache location. Raises :class:`CorpusUnavailable` with the
        connector's install hint if the file is missing (when
        ``must_exist=True``) or unopenable.
        """
        resolved = cls._resolve_path(path)
        if must_exist and not resolved.exists():
            raise CorpusUnavailable(
                f"{cls.LABEL} corpus not found at {resolved}. {cls._install_hint()}"
            )
        try:
            conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
        except sqlite3.OperationalError as exc:
            raise CorpusUnavailable(
                f"Could not open {cls.LABEL} corpus at {resolved}: {exc}. {cls._install_hint()}"
            ) from exc
        return cls(conn, resolved)

    @property
    def path(self) -> Path:
        return self._path

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> CorpusDBBase:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Meta — every corpus has a ``meta(key, value)`` table.
    # ------------------------------------------------------------------

    def meta(self) -> dict[str, str]:
        """Return every key/value row in the corpus's ``meta`` table."""
        rows = self._conn.execute("SELECT key, value FROM meta").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def meta_get(self, key: str, default: str | None = None) -> str | None:
        """Look up a single meta key, returning ``default`` when absent."""
        row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


# ----------------------------------------------------------------------
# Outline-shaped corpora (mpep / tmep / epc / ukipo_mopp / epo_guidelines /
# epo_pct_guidelines / epo_up_guidelines / epo_case_law)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class OutlineCorpusSection:
    """Row shape used by the outline-style corpora.

    These corpora model an outlined document (an examination manual, a
    treaty, a guidelines book): every section has a stable href, a
    section number, a breadcrumb showing where it sits in the outline,
    a chapter label, and both an HTML and a plaintext rendering of the
    body.
    """

    href: str
    section_number: str | None
    title: str | None
    breadcrumb: str | None
    chapter: str | None
    html: str
    text: str


@dataclass(frozen=True)
class OutlineCorpusHit:
    """Search-hit shape for the outline-style corpora."""

    href: str
    section_number: str | None
    title: str | None
    breadcrumb: str | None
    chapter: str | None
    snippet: str


class OutlineCorpusDB(CorpusDBBase):
    """Concrete base for outline-shaped corpora.

    Ships ``get_section``, ``search``, ``count_for``, and
    ``_row_to_section`` matching the outline row schema. Subclasses only
    need to set the four class vars from :class:`CorpusDBBase`.
    """

    def get_section(
        self,
        *,
        section_number: str | None = None,
        href: str | None = None,
    ) -> OutlineCorpusSection | None:
        if section_number is None and href is None:
            raise ValueError("Provide either section_number or href")
        if href is not None:
            row = self._conn.execute("SELECT * FROM sections WHERE href = ?", (href,)).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM sections WHERE section_number = ?",
                (section_number,),
            ).fetchone()
        return self._row_to_section(row) if row else None

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        sort: str = "relevance",
        snippet_chars: int = 200,
    ) -> list[OutlineCorpusHit]:
        """Run a FTS5 query against the corpus.

        Args:
            query: An FTS5 MATCH expression (callers translate from the
                public API's ``syntax``/``sort`` flags before calling).
            limit: Maximum hits to return.
            offset: Pagination offset.
            sort: ``relevance`` (default, BM25) or ``outline``
                (section_number ascending).
            snippet_chars: Approximate snippet width in characters.

        Returns:
            A list of :class:`OutlineCorpusHit` in the requested order.
        """
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
        # FTS5 snippet() expects a token count, not chars — divide chars by ~5
        # (a rough average English token length) to get a sensible window.
        token_count = max(8, min(snippet_chars // 5, 64))
        rows = self._conn.execute(sql, (token_count, query, limit, offset)).fetchall()
        return [
            OutlineCorpusHit(
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

    @staticmethod
    def _row_to_section(row: sqlite3.Row) -> OutlineCorpusSection:
        return OutlineCorpusSection(
            href=row["href"],
            section_number=row["section_number"],
            title=row["title"],
            breadcrumb=row["breadcrumb"],
            chapter=row["chapter"],
            html=row["html"],
            text=row["text"],
        )


__all__ = [
    "CorpusDBBase",
    "CorpusUnavailable",
    "OutlineCorpusDB",
    "OutlineCorpusHit",
    "OutlineCorpusSection",
]
