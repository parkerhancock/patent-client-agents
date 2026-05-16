"""Envelope-shape tests for the IPOS Singapore manuals MCP tools."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from law_tools_core.envelope import ListEnvelope, Provenance
from law_tools_core.exceptions import ValidationError
from patent_client_agents.ipos_manuals.corpus.schema import DDL, SCHEMA_VERSION
from patent_client_agents.ipos_manuals.models import (
    IposManual,
    IposManualSearchHit,
    IposManualSearchResponse,
    IposManualSection,
)
from patent_client_agents.mcp.tools.ipos import (
    get_ipos_manual_section,
    list_ipos_manuals,
    search_ipos_manuals,
)

_FIXTURE_SNAPSHOT_DATE = "2026-05-16"
_FIXTURE_CORPUS_VERSION = f"snapshot {_FIXTURE_SNAPSHOT_DATE}"


@pytest.fixture(autouse=True)
def _ipos_manuals_corpus_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    db = tmp_path / "ipos_manuals_meta_only.db"
    conn = sqlite3.connect(db)
    try:
        conn.executescript(DDL)
        conn.executemany(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            [
                ("schema_version", str(SCHEMA_VERSION)),
                ("snapshot_date", _FIXTURE_SNAPSHOT_DATE),
                ("section_count", "0"),
                ("manual_count", "0"),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setenv("IPOS_MANUALS_CORPUS_PATH", str(db))
    return db


def _make_hit(
    manual: str = "peg",
    *,
    section_label: str = "1.5.3",
    snippet: str = "<mark>inventive step</mark>...",
) -> IposManualSearchHit:
    short_name = {
        "peg": "PEG",
        "tm": "TM Work Manual",
        "designs": "Designs Work Manual",
    }[manual]
    return IposManualSearchHit(
        manual=manual,
        short_name=short_name,
        section_label=section_label,
        title="Inventive Step",
        breadcrumb=f"{short_name} › {section_label}",
        snippet=snippet,
        rank=-1.5,
    )


def _make_manual(manual: str = "peg") -> IposManual:
    short_name = {
        "peg": "PEG",
        "tm": "TM Work Manual",
        "designs": "Designs Work Manual",
    }[manual]
    return IposManual(
        manual=manual,
        short_name=short_name,
        title=f"IPOS {short_name}",
        source_url=f"https://example.com/{manual}.pdf",
        source_version=None,
    )


def _make_section(
    manual: str = "peg",
    *,
    section_label: str = "1.5.3",
    title: str = "Inventive Step",
) -> IposManualSection:
    short_name = {
        "peg": "PEG",
        "tm": "TM Work Manual",
        "designs": "Designs Work Manual",
    }[manual]
    return IposManualSection(
        manual=manual,
        short_name=short_name,
        manual_title=f"IPOS {short_name}",
        section_label=section_label,
        title=title,
        breadcrumb=f"{short_name} › {section_label}",
        source_url=f"https://example.com/{manual}.pdf#{section_label}",
        source_version=None,
        text=f"{section_label} {title}. Body text...",
    )


# ──────────────────────────────────────────────────────────────────────
# search_ipos_manuals — §5.9 envelope + corpus_version provenance
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_ipos_manuals_returns_list_envelope_with_corpus_version():
    response = IposManualSearchResponse(
        query="inventive step",
        hits=[_make_hit("peg"), _make_hit("peg", section_label="1.6")],
        page=1,
        per_page=10,
        has_more=False,
    )
    with patch("patent_client_agents.mcp.tools.ipos._search_manuals") as mock_search:
        mock_search.return_value = response
        result = await search_ipos_manuals(query="inventive step")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "IPOS Singapore"
    assert result.provenance.corpus_version == _FIXTURE_CORPUS_VERSION
    assert isinstance(result.provenance.corpus_synced_at, datetime)
    assert len(result.items) == 2
    assert "inventive step" in result.summary


@pytest.mark.asyncio
async def test_search_ipos_manuals_more_available_when_has_more():
    response = IposManualSearchResponse(
        query="distinctiveness",
        hits=[_make_hit("tm", section_label="3.4")],
        page=1,
        per_page=10,
        has_more=True,
    )
    with patch("patent_client_agents.mcp.tools.ipos._search_manuals") as mock_search:
        mock_search.return_value = response
        result = await search_ipos_manuals(query="distinctiveness", manual="tm")

    assert result.more_available is True
    assert "manual=tm" in result.summary


# ──────────────────────────────────────────────────────────────────────
# get_ipos_manual_section — §5.4 list-accepting, ListEnvelope shape
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_ipos_manual_section_single_returns_list_envelope():
    section = _make_section("peg", section_label="1.5.3")
    with patch("patent_client_agents.mcp.tools.ipos.IposManualsClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_by_citation = AsyncMock(return_value=section)

        result = await get_ipos_manual_section(citation="IPOS PEG 1.5.3")

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 1
    assert result.items[0]["section_label"] == "1.5.3"
    assert "PEG" in result.summary
    assert "Inventive Step" in result.summary
    assert result.provenance.corpus_version == _FIXTURE_CORPUS_VERSION


@pytest.mark.asyncio
async def test_get_ipos_manual_section_list_preserves_order():
    citations = [
        "IPOS PEG 1.5.3",
        "IPOS TM Work Manual 3.4",
        "IPOS Designs Work Manual 2.1",
    ]
    sections = [
        _make_section("peg", section_label="1.5.3"),
        _make_section("tm", section_label="3.4"),
        _make_section("designs", section_label="2.1"),
    ]
    with patch("patent_client_agents.mcp.tools.ipos.IposManualsClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_by_citation = AsyncMock(side_effect=sections)

        result = await get_ipos_manual_section(citation=citations)

    assert [r["section_label"] for r in result.items] == ["1.5.3", "3.4", "2.1"]
    assert "3 of 3" in result.summary


@pytest.mark.asyncio
async def test_get_ipos_manual_section_not_found_in_summary():
    with patch("patent_client_agents.mcp.tools.ipos.IposManualsClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_by_citation = AsyncMock(return_value=None)

        result = await get_ipos_manual_section(citation="IPOS PEG 9.9.9")

    assert result.items == []
    assert "not found" in result.summary


@pytest.mark.asyncio
async def test_get_ipos_manual_section_partial_not_found_in_summary():
    citations = ["IPOS PEG 1.5.3", "IPOS PEG 9.9.9"]
    sections: list[IposManualSection | None] = [
        _make_section("peg", section_label="1.5.3"),
        None,
    ]
    with patch("patent_client_agents.mcp.tools.ipos.IposManualsClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_by_citation = AsyncMock(side_effect=sections)

        result = await get_ipos_manual_section(citation=citations)

    assert len(result.items) == 1
    assert "Not found" in result.summary


@pytest.mark.asyncio
async def test_get_ipos_manual_section_empty_list_raises():
    with pytest.raises(ValidationError, match="at least one"):
        await get_ipos_manual_section(citation=[])


# ──────────────────────────────────────────────────────────────────────
# list_ipos_manuals — §5.8 vocab enumerator
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_ipos_manuals_returns_list_envelope():
    manuals = [_make_manual("peg"), _make_manual("tm"), _make_manual("designs")]
    with patch("patent_client_agents.mcp.tools.ipos._list_manuals") as mock_list:
        mock_list.return_value = manuals

        result = await list_ipos_manuals()

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "IPOS Singapore"
    assert result.provenance.corpus_version == _FIXTURE_CORPUS_VERSION
    assert len(result.items) == 3
    assert "3 manuals" in result.summary
