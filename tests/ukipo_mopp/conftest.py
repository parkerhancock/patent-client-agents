"""Shared fixtures for UKIPO MoPP tests.

Builds a tiny on-disk corpus from hand-authored rows so the read path
is exercised end-to-end without a 192-page gov.uk scrape.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from patent_client_agents.ukipo_mopp.corpus.schema import DDL, SCHEMA_VERSION


def _row(slug: str, section_number: str | None, title: str, text: str) -> tuple:
    return (
        slug,
        section_number,
        title,
        None,  # breadcrumb
        None,  # chapter
        f"<div><h2>{title}</h2><p>{text}</p></div>",
        f"{title} {text}",
    )


@pytest.fixture(scope="session")
def mopp_corpus_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("mopp-corpus") / "mopp.db"
    rows = [
        _row(
            "section-1-patentability",
            "1",
            "Section 1: Patentability",
            "Section 1(1) sets out the basic requirements for a patentable "
            "invention: novelty, inventive step, industrial applicability, "
            "and not a section 1(2) exclusion.",
        ),
        _row(
            "-section-4a-methods-of-treatment-or-diagnosis",
            "4A",
            "Section 4A: methods of treatment or diagnosis",
            "Section 4A excludes methods of treatment by surgery or therapy "
            "and methods of diagnosis practised on the human or animal body.",
        ),
        _row(
            "section-14-the-application",
            "14",
            "Section 14: The application",
            "Section 14 governs the form and content of a UK patent application.",
        ),
        _row(
            "glossary-of-terms-and-abbreviations-used-in-this-manual",
            None,
            "Glossary",
            "Definitions used throughout the Manual of Patent Practice.",
        ),
    ]
    conn = sqlite3.connect(out)
    try:
        conn.executescript(DDL)
        for key, val in (
            ("schema_version", str(SCHEMA_VERSION)),
            ("source", "fixture"),
            ("snapshot_date", datetime.now(UTC).strftime("%Y-%m-%d")),
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
