"""Envelope-shape tests for the IPOS Singapore statutes MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope shape + Provenance with
``corpus_version`` set per §4 for the ``mcp_local`` substantive-law
corpus), §5.4 (list-accepting fetches), and §5.8 (vocab ``list_*``
enumerators returning ``ListEnvelope``).

Mocks the upstream search / client at the module boundary so tests
don't require the bulk corpus content to be materialized. A tiny
``meta``-only fixture corpus is seeded so ``get_corpus_status()``
returns deterministic values.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mcp_data_core.envelope import ListEnvelope, Provenance
from mcp_data_core.exceptions import ValidationError
from patent_client_agents.ipos_statutes.corpus.schema import DDL, SCHEMA_VERSION
from patent_client_agents.ipos_statutes.models import (
    IposSection,
    IposStatute,
    IposStatuteSearchHit,
    IposStatuteSearchResponse,
)
from patent_client_agents.mcp.tools.ipos import (
    get_ipos_section,
    list_ipos_statutes,
    search_ipos_statutes,
)

_FIXTURE_SNAPSHOT_DATE = "2026-05-16"
_FIXTURE_SOURCE_VERSION = "2020 Revised Edition"


@pytest.fixture(autouse=True)
def _ipos_statutes_corpus_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Seed a meta-only corpus and point ``IPOS_STATUTES_CORPUS_PATH`` at it."""
    db = tmp_path / "ipos_statutes_meta_only.db"
    conn = sqlite3.connect(db)
    try:
        conn.executescript(DDL)
        conn.executemany(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            [
                ("schema_version", str(SCHEMA_VERSION)),
                ("snapshot_date", _FIXTURE_SNAPSHOT_DATE),
                ("source_version", _FIXTURE_SOURCE_VERSION),
                ("section_count", "0"),
                ("statute_count", "0"),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setenv("IPOS_STATUTES_CORPUS_PATH", str(db))
    return db


def _make_hit(
    statute: str = "patents",
    *,
    section_label: str = "13",
    snippet: str = "<mark>inventive step</mark> in Singapore...",
) -> IposStatuteSearchHit:
    return IposStatuteSearchHit(
        statute=statute,
        short_name="Patents Act" if statute == "patents" else "Trade Marks Act",
        section_label=section_label,
        title="Patentable inventions",
        breadcrumb=f"{statute} › Section {section_label}",
        snippet=snippet,
        rank=-1.5,
    )


def _make_statute(statute: str = "patents", *, short_name: str = "Patents Act") -> IposStatute:
    return IposStatute(
        statute=statute,
        short_name=short_name,
        title=f"{short_name} 1994 (2020 Revised Edition)",
        source_url=f"https://example.com/Act/{statute.upper()}",
        source_version=_FIXTURE_SOURCE_VERSION,
    )


def _make_section(
    statute: str = "patents",
    *,
    section_label: str = "13",
    title: str = "Patentable inventions",
) -> IposSection:
    return IposSection(
        statute=statute,
        short_name="Patents Act" if statute == "patents" else "Trade Marks Act",
        statute_title=f"{statute.title()} Act",
        section_label=section_label,
        title=title,
        breadcrumb=f"{statute} › Section {section_label}",
        source_url=f"https://example.com/Act/{statute.upper()}#pr{section_label}",
        source_version=_FIXTURE_SOURCE_VERSION,
        text=f"{section_label}. {title}. Body text...",
    )


# ──────────────────────────────────────────────────────────────────────
# search_ipos_statutes — §5.9 envelope + corpus_version provenance
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_ipos_statutes_returns_list_envelope_with_corpus_version():
    response = IposStatuteSearchResponse(
        query="inventive step",
        hits=[_make_hit("patents"), _make_hit("patents", section_label="14")],
        page=1,
        per_page=10,
        has_more=False,
    )
    with patch("patent_client_agents.mcp.tools.ipos._search_statutes") as mock_search:
        mock_search.return_value = response
        result = await search_ipos_statutes(query="inventive step")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "IPOS Singapore"
    assert result.provenance.corpus_version == _FIXTURE_SOURCE_VERSION
    assert isinstance(result.provenance.corpus_synced_at, datetime)
    assert len(result.items) == 2
    assert "inventive step" in result.summary
    assert result.more_available is False


@pytest.mark.asyncio
async def test_search_ipos_statutes_more_available_when_has_more():
    response = IposStatuteSearchResponse(
        query="trade mark",
        hits=[_make_hit("tm", section_label="27")],
        page=1,
        per_page=10,
        has_more=True,
    )
    with patch("patent_client_agents.mcp.tools.ipos._search_statutes") as mock_search:
        mock_search.return_value = response
        result = await search_ipos_statutes(query="trade mark", statute="tm")

    assert result.more_available is True
    assert "statute=tm" in result.summary


# ──────────────────────────────────────────────────────────────────────
# get_ipos_section — §5.4 list-accepting, ListEnvelope shape
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_ipos_section_single_returns_list_envelope():
    section = _make_section("patents", section_label="13")
    with patch("patent_client_agents.mcp.tools.ipos.IposStatutesClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_by_citation = AsyncMock(return_value=section)

        result = await get_ipos_section(citation="Section 13 Patents Act")

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 1
    assert result.items[0]["section_label"] == "13"
    assert "Patents Act" in result.summary
    assert "Patentable inventions" in result.summary
    assert result.provenance.corpus_version == _FIXTURE_SOURCE_VERSION
    assert isinstance(result.provenance.corpus_synced_at, datetime)


@pytest.mark.asyncio
async def test_get_ipos_section_list_preserves_order():
    citations = [
        "Section 13 Patents Act",
        "Section 14 Patents Act",
        "Section 27 Trade Marks Act",
    ]
    sections = [
        _make_section("patents", section_label="13"),
        _make_section("patents", section_label="14"),
        _make_section("tm", section_label="27"),
    ]
    with patch("patent_client_agents.mcp.tools.ipos.IposStatutesClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_by_citation = AsyncMock(side_effect=sections)

        result = await get_ipos_section(citation=citations)

    assert [r["section_label"] for r in result.items] == ["13", "14", "27"]
    assert "3 of 3" in result.summary


@pytest.mark.asyncio
async def test_get_ipos_section_not_found_appears_in_summary():
    with patch("patent_client_agents.mcp.tools.ipos.IposStatutesClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_by_citation = AsyncMock(return_value=None)

        result = await get_ipos_section(citation="Section 999 Patents Act")

    assert result.items == []
    assert "not found" in result.summary


@pytest.mark.asyncio
async def test_get_ipos_section_empty_list_raises():
    with pytest.raises(ValidationError, match="at least one"):
        await get_ipos_section(citation=[])


@pytest.mark.asyncio
async def test_get_ipos_section_partial_not_found_in_summary():
    citations = ["Section 13 Patents Act", "Section 999 Patents Act"]
    sections: list[IposSection | None] = [
        _make_section("patents", section_label="13"),
        None,
    ]
    with patch("patent_client_agents.mcp.tools.ipos.IposStatutesClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_by_citation = AsyncMock(side_effect=sections)

        result = await get_ipos_section(citation=citations)

    assert len(result.items) == 1
    assert "Not found" in result.summary


# ──────────────────────────────────────────────────────────────────────
# list_ipos_statutes — §5.8 vocab enumerator
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_ipos_statutes_returns_list_envelope():
    statutes = [
        _make_statute("patents", short_name="Patents Act"),
        _make_statute("tm", short_name="Trade Marks Act"),
    ]
    with patch("patent_client_agents.mcp.tools.ipos._list_statutes") as mock_list:
        mock_list.return_value = statutes

        result = await list_ipos_statutes()

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "IPOS Singapore"
    assert result.provenance.corpus_version == _FIXTURE_SOURCE_VERSION
    assert isinstance(result.provenance.corpus_synced_at, datetime)
    assert len(result.items) == 2
    assert "2 Acts" in result.summary
