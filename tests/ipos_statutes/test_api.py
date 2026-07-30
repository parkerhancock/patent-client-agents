"""Tests for the module-level convenience functions in
``patent_client_agents.ipos_statutes.api``.

These wrap the client in a context manager so callers don't have to.
The corpus is seeded once (via the ``IPOS_STATUTES_CORPUS_PATH`` env
var the autouse fixture sets up) so the convenience helpers exercise
the full open → query → close path against a real SQLite/FTS5 corpus.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from patent_client_agents.ipos_statutes import (
    SectionInput,
    StatuteSearchInput,
    get_by_citation,
    get_client,
    get_section,
    get_usage_resource,
    list_statutes,
    search,
)
from patent_client_agents.ipos_statutes.corpus.schema import DDL, SCHEMA_VERSION


def _seed_corpus(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(DDL)
        conn.execute(
            """
            INSERT INTO sections
                (statute, short_name, statute_title, section_label,
                 title, breadcrumb, source_url, source_version, text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "patents",
                "Patents Act",
                "Patents Act 1994",
                "13",
                "Patentable inventions",
                "Patents Act › Section 13",
                "https://example.com/Act/PA1994#pr13",
                "2020 Revised Edition",
                "13. Patentable inventions. inventive step in Singapore.",
            ),
        )
        for key, value in [
            ("schema_version", str(SCHEMA_VERSION)),
            ("snapshot_date", "2026-05-16"),
            ("section_count", "1"),
            ("statute_count", "1"),
        ]:
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                (key, value),
            )
        conn.execute("INSERT INTO sections_fts(sections_fts) VALUES ('optimize')")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def seeded_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    db = tmp_path / "ipos_statutes.db"
    _seed_corpus(db)
    monkeypatch.setenv("IPOS_STATUTES_CORPUS_PATH", str(db))
    return db


@pytest.mark.asyncio
async def test_get_client_returns_concrete_client():
    client = get_client()
    assert client.__class__.__name__ == "IposStatutesClient"
    # Closing without ever opening shouldn't blow up.
    await client.close()


@pytest.mark.asyncio
async def test_search_convenience():
    response = await search(StatuteSearchInput(query="inventive"))
    assert response.hits
    assert response.hits[0].statute == "patents"


@pytest.mark.asyncio
async def test_get_section_with_citation_string():
    """SectionInput defaults the bare-string form to the ``citation`` field."""
    section = await get_section("Section 13 Patents Act")
    assert section is not None
    assert section.section_label == "13"


@pytest.mark.asyncio
async def test_get_section_with_section_input_discrete_fields():
    section = await get_section(SectionInput(statute="patents", section_label="13"))
    assert section is not None


@pytest.mark.asyncio
async def test_get_section_returns_none_when_both_fields_omitted():
    section = await get_section(SectionInput())
    assert section is None


@pytest.mark.asyncio
async def test_get_by_citation_convenience():
    section = await get_by_citation("Section 13 Patents Act")
    assert section is not None
    assert section.statute == "patents"


@pytest.mark.asyncio
async def test_list_statutes_convenience():
    statutes = await list_statutes()
    assert len(statutes) == 1
    assert statutes[0].statute == "patents"


def test_get_usage_resource_returns_string():
    text = get_usage_resource()
    assert "IPOS" in text
    assert "search_ipos_statutes" in text
