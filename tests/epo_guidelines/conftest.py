"""Shared fixtures for EPO Guidelines tests.

Builds a tiny on-disk corpus from hand-authored rows so the read path
is exercised end-to-end without a 500+-page EPO scrape.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from patent_client_agents.epo_guidelines.corpus.schema import DDL, SCHEMA_VERSION


def _row(
    slug: str, section_number: str | None, title: str, chapter: str | None, text: str
) -> tuple:
    return (
        slug,
        section_number,
        title,
        None,  # breadcrumb
        chapter,
        f"<div><h1>{title}</h1><p>{text}</p></div>",
        f"{title} {text}",
    )


@pytest.fixture(scope="session")
def guidelines_corpus_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("guidelines-corpus") / "guidelines.db"
    rows = [
        _row(
            "a_i",
            "A-I",
            "Chapter I – Introduction",
            "A",
            "This Part deals with the formalities of European patent applications.",
        ),
        _row(
            "g_ii_3_1",
            "G-II, 3.1",
            "3.1 Discoveries",
            "G",
            "Discoveries as such are not regarded as inventions under Article 52(2)(a) EPC.",
        ),
        _row(
            "g_ii_3",
            "G-II, 3",
            "3. Exclusions under Article 52(2) and (3)",
            "G",
            "The European Patent Convention excludes from patentability "
            "discoveries, scientific theories, and mathematical methods.",
        ),
        _row(
            "h",
            "H",
            "Part H – Amendments and corrections",
            "H",
            "Part H deals with permissible amendments under Article 123 EPC.",
        ),
    ]
    conn = sqlite3.connect(out)
    try:
        conn.executescript(DDL)
        for key, val in (
            ("schema_version", str(SCHEMA_VERSION)),
            ("source", "fixture"),
            ("snapshot_date", datetime.now(UTC).strftime("%Y-%m-%d")),
            ("guidelines_year", "2024"),
        ):
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, val))
        conn.executemany(
            "INSERT INTO sections (href, section_number, title, breadcrumb, chapter, html, text) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
    return out
