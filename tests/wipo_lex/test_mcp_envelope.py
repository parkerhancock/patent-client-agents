"""Envelope-shape tests for the migrated WIPO Lex MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope), §5.4 (list-accepting
fetches; no batch tools), §5.5 (lean default + full opt-in), and §5.6
(cross-references).

Mocks ``WipoLexClient`` at the boundary — we're testing envelope shape,
not the upstream HTML parser.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from law_tools_core.envelope import ListEnvelope, Provenance
from patent_client_agents.mcp.tools.wipo_lex import (
    get_wipo_lex_legislation,
    search_wipo_lex_legislation,
)

# ──────────────────────────────────────────────────────────────────────
# Fakes — minimal Pydantic models that mimic WipoLexClient return types
# ──────────────────────────────────────────────────────────────────────


class _FakeHit(BaseModel):
    legislation_id: str
    title: str
    url: str


class _FakeSearchResponse(BaseModel):
    hits: list[_FakeHit] = []
    query_url: str = "https://www.wipo.int/wipolex/en/legislation/results?countryOrgs=CA"


class _FakeFileLink(BaseModel):
    label: str
    url: str
    mime_type: str | None = None


class _FakeDetail(BaseModel):
    legislation_id: str
    title: str
    jurisdiction: str | None = None
    summary: str | None = None
    url: str
    files: list[_FakeFileLink] = []


def _make_hit(lid: str, title: str = "Patent Act") -> _FakeHit:
    return _FakeHit(
        legislation_id=lid,
        title=title,
        url=f"https://www.wipo.int/wipolex/en/legislation/details/{lid}",
    )


def _make_detail(lid: str, title: str = "Patent Act", jurisdiction: str = "Canada") -> _FakeDetail:
    return _FakeDetail(
        legislation_id=lid,
        title=title,
        jurisdiction=jurisdiction,
        summary=f"{jurisdiction} - Year of Version: 2025 - Main IP Laws - Patents",
        url=f"https://www.wipo.int/wipolex/en/legislation/details/{lid}",
        files=[
            _FakeFileLink(label="English PDF", url="/edocs/x.pdf", mime_type="application/pdf"),
        ],
    )


# ──────────────────────────────────────────────────────────────────────
# search_wipo_lex_legislation — §5.9, §5.5
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_returns_lean_list_envelope_by_default():
    response = _FakeSearchResponse(
        hits=[_make_hit("23293", "Patent Act"), _make_hit("23437", "Patent Rules")]
    )
    with patch("patent_client_agents.mcp.tools.wipo_lex.WipoLexClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search_legislation = AsyncMock(return_value=response)

        result = await search_wipo_lex_legislation(country_codes=["CA"], subject_matter=[1])

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "WIPO Lex"
    assert "/wipolex/en/legislation/results" in result.provenance.source_url
    assert len(result.items) == 2
    # Lean projection: exactly these keys.
    assert set(result.items[0].keys()) == {"legislation_id", "title", "url"}
    assert result.items[0]["legislation_id"] == "23293"
    # Summary names the filter values so an agent can quote it.
    assert "WIPO Lex" in result.summary
    assert "countries=CA" in result.summary
    assert "2 hits" in result.summary


@pytest.mark.asyncio
async def test_search_full_true_returns_upstream_shape():
    response = _FakeSearchResponse(hits=[_make_hit("23293")])
    with patch("patent_client_agents.mcp.tools.wipo_lex.WipoLexClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search_legislation = AsyncMock(return_value=response)

        result = await search_wipo_lex_legislation(country_codes=["CA"], full=True)

    # Full mode returns the upstream-dumped dict; lean-only keys are still
    # present (they exist upstream too) plus whatever the model adds.
    assert "legislation_id" in result.items[0]
    assert result.items[0]["legislation_id"] == "23293"


@pytest.mark.asyncio
async def test_search_provenance_source_name_is_wipo_lex():
    response = _FakeSearchResponse(hits=[])
    with patch("patent_client_agents.mcp.tools.wipo_lex.WipoLexClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search_legislation = AsyncMock(return_value=response)

        result = await search_wipo_lex_legislation(keywords="trade secrets")

    assert result.provenance.source_name == "WIPO Lex"
    assert result.provenance.source_url.startswith("https://www.wipo.int")
    assert "`trade secrets`" in result.summary


# ──────────────────────────────────────────────────────────────────────
# get_wipo_lex_legislation — §5.4 list-accepting
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_single_string_returns_list_envelope():
    detail = _make_detail("23293", title="Patent Act", jurisdiction="Canada")
    with patch("patent_client_agents.mcp.tools.wipo_lex.WipoLexClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_legislation = AsyncMock(return_value=detail)

        result = await get_wipo_lex_legislation(legislation_id="23293")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "WIPO Lex"
    assert "/wipolex/en/legislation/details/23293" in result.provenance.source_url
    assert len(result.items) == 1
    assert result.items[0]["legislation_id"] == "23293"
    # Summary leads with the WIPO Lex identifier and includes the title.
    assert "23293" in result.summary
    assert "Patent Act" in result.summary


@pytest.mark.asyncio
async def test_get_list_preserves_order():
    ids = ["23293", "23437", "23298"]
    details = [_make_detail(lid, title=f"Law {lid}") for lid in ids]
    with patch("patent_client_agents.mcp.tools.wipo_lex.WipoLexClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_legislation = AsyncMock(side_effect=details)

        result = await get_wipo_lex_legislation(legislation_id=ids)

    assert isinstance(result, ListEnvelope)
    assert [r["legislation_id"] for r in result.items] == ids
    # Multi-record summary lists the IDs.
    assert "Fetched 3" in result.summary
    for lid in ids:
        assert lid in result.summary
    # Multi-record path is the collection root, not a specific record.
    assert result.provenance.source_url.endswith("/wipolex/en/legislation/details")


@pytest.mark.asyncio
async def test_get_summary_names_jurisdiction_and_attachments():
    detail = _make_detail("23293", title="Patent Act", jurisdiction="Canada")
    with patch("patent_client_agents.mcp.tools.wipo_lex.WipoLexClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_legislation = AsyncMock(return_value=detail)

        result = await get_wipo_lex_legislation(legislation_id="23293")

    assert "Canada" in result.summary
    assert "attachment" in result.summary


@pytest.mark.asyncio
async def test_no_batch_tool_present():
    """§5.4 forbids batch_* tools — list-accepting get_* replaces them."""
    from patent_client_agents.mcp.tools import wipo_lex as wl_module

    assert not hasattr(wl_module, "batch_wipo_lex_legislation")
    assert not hasattr(wl_module, "batch_get_wipo_lex_legislation")
