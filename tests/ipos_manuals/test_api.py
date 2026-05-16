"""Tests for the module-level convenience functions in
``patent_client_agents.ipos_manuals.api``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from patent_client_agents.ipos_manuals import (
    ManualSearchInput,
    ManualSectionInput,
    get_by_citation,
    get_client,
    get_section,
    get_usage_resource,
    list_manuals,
    search,
)
from patent_client_agents.ipos_manuals.corpus.schema import DDL, SCHEMA_VERSION


def _seed_corpus(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(DDL)
        conn.execute(
            """
            INSERT INTO sections
                (manual, short_name, manual_title, section_label,
                 title, breadcrumb, source_url, source_version, text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "peg",
                "PEG",
                "IPOS Patent Examination Guidelines",
                "1.5.3",
                "Inventive Step",
                "PEG › 1.5.3",
                "https://example.com/peg.pdf#1.5.3",
                None,
                "1.5.3 Inventive Step. An invention shall be taken to involve an inventive step.",
            ),
        )
        for key, value in [
            ("schema_version", str(SCHEMA_VERSION)),
            ("snapshot_date", "2026-05-16"),
            ("section_count", "1"),
            ("manual_count", "1"),
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
    db = tmp_path / "ipos_manuals.db"
    _seed_corpus(db)
    monkeypatch.setenv("IPOS_MANUALS_CORPUS_PATH", str(db))
    return db


@pytest.mark.asyncio
async def test_get_client_returns_concrete_client():
    client = get_client()
    assert client.__class__.__name__ == "IposManualsClient"
    await client.close()


@pytest.mark.asyncio
async def test_search_convenience():
    response = await search(ManualSearchInput(query="inventive"))
    assert response.hits
    assert response.hits[0].manual == "peg"


@pytest.mark.asyncio
async def test_get_section_with_citation_string():
    section = await get_section("IPOS PEG 1.5.3")
    assert section is not None
    assert section.section_label == "1.5.3"


@pytest.mark.asyncio
async def test_get_section_with_input_discrete_fields():
    section = await get_section(ManualSectionInput(manual="peg", section_label="1.5.3"))
    assert section is not None


@pytest.mark.asyncio
async def test_get_section_returns_none_when_both_fields_omitted():
    section = await get_section(ManualSectionInput())
    assert section is None


@pytest.mark.asyncio
async def test_get_by_citation_convenience():
    section = await get_by_citation("IPOS PEG 1.5.3")
    assert section is not None
    assert section.manual == "peg"


@pytest.mark.asyncio
async def test_list_manuals_convenience():
    manuals = await list_manuals()
    assert len(manuals) == 1
    assert manuals[0].manual == "peg"


def test_get_usage_resource_returns_string():
    text = get_usage_resource()
    assert "IPOS" in text
    assert "search_ipos_manuals" in text
