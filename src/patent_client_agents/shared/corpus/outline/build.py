"""Write-side helpers shared by the outline corpus builds."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from .schema import OUTLINE_DDL


def init_outline_corpus(conn: sqlite3.Connection, meta: Iterable[tuple[str, str]]) -> None:
    """Create the outline schema and record ``meta`` rows in the given order."""
    conn.executescript(OUTLINE_DDL)
    for key, value in meta:
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, value))


def insert_outline_section(
    conn: sqlite3.Connection,
    *,
    href: str,
    section_number: str | None,
    title: str | None,
    breadcrumb: str | None,
    chapter: str | None,
    html: str,
    text: str,
) -> None:
    """Insert (or replace, keyed on ``href``) one ``sections`` row."""
    conn.execute(
        "INSERT OR REPLACE INTO sections "
        "(href, section_number, title, breadcrumb, chapter, html, text) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (href, section_number, title, breadcrumb, chapter, html, text),
    )


__all__ = ["init_outline_corpus", "insert_outline_section"]
