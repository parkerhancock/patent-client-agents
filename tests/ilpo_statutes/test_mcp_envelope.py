"""Envelope-shape tests for the ILPO Israel statutes MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope shape + Provenance with
``corpus_version`` set for the ``mcp_local`` substantive-law corpus per
§4), §5.4 (list-accepting fetches), and the standard test pattern from
``tests/upc_statutes/test_mcp_envelope.py``.

Mocks the upstream statute client / API at the boundary so tests don't
require the bulk corpus content to be materialized. A tiny ``meta``-only
fixture corpus is seeded so ``get_corpus_status()`` returns deterministic
values.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from law_tools_core.envelope import ListEnvelope, Provenance
from law_tools_core.exceptions import ValidationError
from patent_client_agents.ilpo_statutes.corpus.schema import DDL, SCHEMA_VERSION
from patent_client_agents.ilpo_statutes.models import (
    IlpoSearchHit,
    IlpoSearchResponse,
    IlpoSection,
)
from patent_client_agents.mcp.tools.ilpo import (
    get_ilpo_section,
    search_ilpo_statutes,
)

_FIXTURE_SNAPSHOT_DATE = "2026-05-16"
_FIXTURE_CORPUS_VERSION = "WIPO Lex authoritative EN"


@pytest.fixture(autouse=True)
def _ilpo_statutes_corpus_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Seed a meta-only corpus and point ``ILPO_STATUTES_CORPUS_PATH`` at it."""
    db = tmp_path / "ilpo_statutes_meta_only.db"
    conn = sqlite3.connect(db)
    try:
        conn.executescript(DDL)
        conn.executemany(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            [
                ("schema_version", str(SCHEMA_VERSION)),
                ("snapshot_date", _FIXTURE_SNAPSHOT_DATE),
                ("source_version", _FIXTURE_CORPUS_VERSION),
                ("section_count", "0"),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setenv("ILPO_STATUTES_CORPUS_PATH", str(db))
    return db


def _make_hit(
    statute: str = "commercial_torts",
    *,
    section_number: str = "6",
    snippet: str = "<mark>trade secret</mark> ...",
) -> IlpoSearchHit:
    return IlpoSearchHit(
        statute=statute,
        section_number=section_number,
        section_label=f"Article {section_number} Commercial Torts Law",
        title="Trade secret",
        snippet=snippet,
        rank=-1.5,
    )


def _make_section(
    statute: str = "commercial_torts",
    *,
    section_number: str = "6",
) -> IlpoSection:
    label_unit = "Article" if statute == "commercial_torts" else "Section"
    short = {
        "patents": "Patents Law",
        "trademarks": "Trade Marks Ordinance",
        "designs": "Designs Law",
        "copyright": "Copyright Act",
        "commercial_torts": "Commercial Torts Law",
    }[statute]
    return IlpoSection(
        statute=statute,
        section_number=section_number,
        section_label=f"{label_unit} {section_number} {short}",
        title="Trade secret" if statute == "commercial_torts" else "Patentable invention",
        text=f"Body of {statute} §{section_number}.",
        source_url=f"https://example/{statute}.pdf",
    )


# ──────────────────────────────────────────────────────────────────────
# search_ilpo_statutes — §5.9 envelope + corpus_version provenance
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_ilpo_statutes_returns_list_envelope_with_corpus_version():
    response = IlpoSearchResponse(
        query="trade secret",
        hits=[_make_hit(), _make_hit(section_number="13")],
        page=1,
        per_page=10,
        has_more=False,
    )
    with patch("patent_client_agents.mcp.tools.ilpo.search") as mock_search:
        mock_search.return_value = response

        result = await search_ilpo_statutes(query="trade secret")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "ILPO Israel — Statutes (WIPO Lex)"
    assert result.provenance.corpus_version == _FIXTURE_CORPUS_VERSION
    assert isinstance(result.provenance.corpus_synced_at, datetime)
    assert len(result.items) == 2
    assert "trade secret" in result.summary
    assert result.more_available is False


@pytest.mark.asyncio
async def test_search_ilpo_statutes_more_available_when_has_more():
    response = IlpoSearchResponse(
        query="Definitions",
        hits=[_make_hit("patents", section_number="1")],
        page=1,
        per_page=10,
        has_more=True,
    )
    with patch("patent_client_agents.mcp.tools.ilpo.search") as mock_search:
        mock_search.return_value = response

        result = await search_ilpo_statutes(query="Definitions")

    assert result.more_available is True


@pytest.mark.asyncio
async def test_search_ilpo_statutes_statute_label_in_summary():
    response = IlpoSearchResponse(
        query="trade secret",
        hits=[],
        page=1,
        per_page=10,
        has_more=False,
    )
    with patch("patent_client_agents.mcp.tools.ilpo.search") as mock_search:
        mock_search.return_value = response

        result = await search_ilpo_statutes(query="trade secret", statute="commercial_torts")

    assert "commercial_torts" in result.summary


# ──────────────────────────────────────────────────────────────────────
# get_ilpo_section — §5.4 list-accepting, ListEnvelope shape
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_ilpo_section_single_returns_list_envelope():
    section = _make_section()
    with patch("patent_client_agents.mcp.tools.ilpo.IlpoStatutesClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_section_by_citation = AsyncMock(return_value=section)

        result = await get_ilpo_section(citation="Article 6 Commercial Torts Law")

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 1
    assert result.items[0]["statute"] == "commercial_torts"
    # Summary includes the section label
    assert "Article 6 Commercial Torts Law" in result.summary
    # corpus_* provenance flows from get_corpus_status()
    assert result.provenance.corpus_version == _FIXTURE_CORPUS_VERSION
    assert isinstance(result.provenance.corpus_synced_at, datetime)


@pytest.mark.asyncio
async def test_get_ilpo_section_list_preserves_order():
    cites = [
        "Article 6 Commercial Torts Law",
        "Section 3 Patents Law",
        "Section 1 Trade Marks Ordinance",
    ]
    sections = [
        _make_section("commercial_torts", section_number="6"),
        _make_section("patents", section_number="3"),
        _make_section("trademarks", section_number="1"),
    ]
    with patch("patent_client_agents.mcp.tools.ilpo.IlpoStatutesClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_section_by_citation = AsyncMock(side_effect=sections)

        result = await get_ilpo_section(citation=cites)

    assert [r["statute"] for r in result.items] == [
        "commercial_torts",
        "patents",
        "trademarks",
    ]
    assert "3 of 3" in result.summary


@pytest.mark.asyncio
async def test_get_ilpo_section_not_found_path():
    with patch("patent_client_agents.mcp.tools.ilpo.IlpoStatutesClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_section_by_citation = AsyncMock(return_value=None)

        result = await get_ilpo_section(citation="Section 9999 Patents Law")

    assert len(result.items) == 0
    assert "not found" in result.summary


@pytest.mark.asyncio
async def test_get_ilpo_section_partial_not_found_path():
    sections = [
        _make_section("commercial_torts", section_number="6"),
        None,
    ]
    with patch("patent_client_agents.mcp.tools.ilpo.IlpoStatutesClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_section_by_citation = AsyncMock(side_effect=sections)

        result = await get_ilpo_section(
            citation=["Article 6 Commercial Torts Law", "Section 9999 Patents Law"]
        )

    assert len(result.items) == 1
    assert "1 of 2" in result.summary
    assert "Not found" in result.summary


@pytest.mark.asyncio
async def test_get_ilpo_section_empty_list_raises():
    with pytest.raises(ValidationError, match="at least one"):
        await get_ilpo_section(citation=[])
