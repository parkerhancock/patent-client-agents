"""Tests for the module-level ``search`` / ``get_section`` / ``list_statutes`` API.

These mirror the surface exposed at
``patent_client_agents.ilpo_statutes.api`` (and re-exported from the
package root). The MCP tool layer hits these convenience functions, so
we cover the module-level paths even though the underlying client
already has its own tests.
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from patent_client_agents.ilpo_statutes import (
    SectionInput,
    StatuteSearchInput,
    get_client,
    get_section,
    list_statutes,
    search,
)
from patent_client_agents.ilpo_statutes.corpus.schema import DDL, SCHEMA_VERSION


def _seed_corpus(path: Path) -> None:
    """Seed a minimal corpus with one section per statute (enough for API tests)."""
    rows = [
        (
            "patents",
            "3",
            "Section 3 Patents Law",
            "Patentable invention",
            "An invention is patentable.",
            "https://example/patents.pdf",
        ),
        (
            "commercial_torts",
            "6",
            "Article 6 Commercial Torts Law",
            "Trade secret",
            "A person shall not misappropriate.",
            "https://example/ct.pdf",
        ),
    ]
    conn = sqlite3.connect(path)
    try:
        conn.executescript(DDL)
        for row in rows:
            conn.execute(
                """
                INSERT INTO sections
                    (statute, section_number, section_label, title, text, source_url)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                row,
            )
        conn.executemany(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            [
                ("schema_version", str(SCHEMA_VERSION)),
                ("snapshot_date", "2026-05-16"),
                ("source_version", "WIPO Lex authoritative EN"),
                ("section_count", str(len(rows))),
            ],
        )
        conn.execute("INSERT INTO sections_fts(sections_fts) VALUES ('optimize')")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _ilpo_corpus_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    db = tmp_path / "ilpo_statutes.db"
    _seed_corpus(db)
    monkeypatch.setenv("ILPO_STATUTES_CORPUS_PATH", str(db))
    return db


def _run(coro):
    return asyncio.run(coro)


def test_get_client_returns_instance() -> None:
    client = get_client()
    assert client is not None


def test_search_via_api() -> None:
    response = _run(search(StatuteSearchInput(query="trade secret")))
    assert response.hits
    assert response.hits[0].statute == "commercial_torts"


def test_get_section_with_string_citation() -> None:
    section = _run(get_section("Article 6 Commercial Torts Law"))
    assert section is not None
    assert section.section_label == "Article 6 Commercial Torts Law"


def test_get_section_with_input_citation() -> None:
    section = _run(get_section(SectionInput(citation="Section 3 Patents Law")))
    assert section is not None
    assert section.statute == "patents"


def test_get_section_with_input_pair() -> None:
    section = _run(get_section(SectionInput(statute="patents", section_number="3")))
    assert section is not None
    assert section.section_number == "3"


def test_get_section_with_empty_input_returns_none() -> None:
    """An empty SectionInput (no citation, no pair) returns None."""
    section = _run(get_section(SectionInput()))
    assert section is None


def test_list_statutes_via_api() -> None:
    statutes = _run(list_statutes())
    keys = {s.statute for s in statutes}
    assert keys == {"patents", "commercial_torts"}
