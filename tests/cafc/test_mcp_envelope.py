"""Envelope-shape tests for the migrated CAFC MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope), §5.5 (lean default +
``full=True`` opt-in), §5.6 (cross-references), and §5.4 (no batch
tools — CAFC is search-only on the envelope side; the existing
``download_cafc_pdf`` keeps its Shape E contract).

Mocks ``CAFCClient`` at the boundary — we're testing envelope shape,
not the upstream WordPress DataTables scraper.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from law_tools_core.envelope import ListEnvelope, Provenance
from patent_client_agents.cafc.models import CAFCOpinion
from patent_client_agents.mcp.tools.cafc import (
    search_cafc_opinions,
    search_cafc_patent_opinions,
)

# ──────────────────────────────────────────────────────────────────────
# Fakes — minimal CAFCOpinion instances
# ──────────────────────────────────────────────────────────────────────


def _make_opinion(
    appeal_number: str,
    *,
    case_name: str = "Acme v. Widget",
    origin: str = "PTO",
    document_type: str = "OPINION",
    precedential_status: str = "Precedential",
    is_patent_case: bool = True,
) -> CAFCOpinion:
    return CAFCOpinion(
        appeal_number=appeal_number,
        release_date=date(2025, 3, 14),
        origin=origin,
        document_type=document_type,
        case_name=case_name,
        case_name_short=case_name,
        precedential_status=precedential_status,
        file_path=f"opinions-orders/{appeal_number}.OPINION.pdf",
        pdf_url=f"https://www.cafc.uscourts.gov/opinions-orders/{appeal_number}.OPINION.pdf",
        is_patent_case=is_patent_case,
        patent_confidence=0.95 if is_patent_case else 0.0,
        patent_keywords=["patent"] if is_patent_case else [],
    )


# ──────────────────────────────────────────────────────────────────────
# search_cafc_opinions — §5.9, §5.5
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_cafc_opinions_returns_lean_list_envelope_by_default():
    opinions = [
        _make_opinion("2023-1234", case_name="Acme v. Widget"),
        _make_opinion("2024-5678", case_name="Foo v. Bar"),
    ]
    with patch("patent_client_agents.mcp.tools.cafc.CAFCClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=opinions)

        result = await search_cafc_opinions(query="patent eligibility")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    # Source name uses the official court name per the spec.
    assert result.provenance.source_name == "U.S. Court of Appeals for the Federal Circuit"
    assert result.provenance.source_url.startswith("https://www.cafc.uscourts.gov")
    assert "/home/case-information/opinions-orders/" in result.provenance.source_url
    # Substantive-law live-proxy → no corpus_synced_at / corpus_version.
    assert result.provenance.corpus_synced_at is None
    assert result.provenance.corpus_version is None
    assert len(result.items) == 2
    # Lean projection: exactly these keys.
    expected_keys = {
        "appeal_number",
        "case_name_short",
        "release_date",
        "origin",
        "document_type",
        "precedential_status",
        "is_patent_case",
        "pdf_url",
    }
    assert set(result.items[0].keys()) == expected_keys
    assert result.items[0]["appeal_number"] == "2023-1234"
    # Summary names the query and result count so an agent can quote it.
    assert "CAFC" in result.summary
    assert "`patent eligibility`" in result.summary
    assert "2 hits" in result.summary


@pytest.mark.asyncio
async def test_search_cafc_opinions_full_true_returns_upstream_shape():
    opinions = [_make_opinion("2023-1234")]
    with patch("patent_client_agents.mcp.tools.cafc.CAFCClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=opinions)

        result = await search_cafc_opinions(query="x", full=True)

    # Full mode returns the upstream-dumped record with all fields, not
    # the lean projection.
    item = result.items[0]
    assert "appeal_number" in item
    assert "file_path" in item
    assert "patent_confidence" in item
    assert "patent_keywords" in item


@pytest.mark.asyncio
async def test_search_cafc_opinions_summary_handles_no_query():
    with patch("patent_client_agents.mcp.tools.cafc.CAFCClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=[])

        result = await search_cafc_opinions()

    assert isinstance(result, ListEnvelope)
    assert "(recent opinions)" in result.summary
    assert "0 hits" in result.summary


@pytest.mark.asyncio
async def test_search_cafc_opinions_patent_only_annotates_summary():
    opinions = [
        _make_opinion("2023-1111", case_name="Patent Co v. Other", is_patent_case=True),
    ]
    with patch("patent_client_agents.mcp.tools.cafc.CAFCClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=opinions)

        result = await search_cafc_opinions(query="anything", patent_only=True)

    assert "patent only" in result.summary


# ──────────────────────────────────────────────────────────────────────
# search_cafc_patent_opinions — §5.9, §5.5
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_cafc_patent_opinions_returns_lean_list_envelope():
    opinions = [
        _make_opinion("2024-1000", origin="PTO"),
        _make_opinion("2024-2000", origin="DCT"),
    ]
    with patch("patent_client_agents.mcp.tools.cafc.CAFCClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search_patent_opinions = AsyncMock(return_value=opinions)

        result = await search_cafc_patent_opinions(
            date_from="2024-01-01",
            date_to="2024-12-31",
        )

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "U.S. Court of Appeals for the Federal Circuit"
    assert len(result.items) == 2
    # Lean by default — same projection as search_cafc_opinions.
    assert set(result.items[0].keys()) == {
        "appeal_number",
        "case_name_short",
        "release_date",
        "origin",
        "document_type",
        "precedential_status",
        "is_patent_case",
        "pdf_url",
    }
    # Summary names the date range so an agent can quote it.
    assert "from 2024-01-01" in result.summary
    assert "to 2024-12-31" in result.summary
    assert "2 hits" in result.summary


@pytest.mark.asyncio
async def test_search_cafc_patent_opinions_full_true_returns_upstream_shape():
    opinions = [_make_opinion("2024-1000")]
    with patch("patent_client_agents.mcp.tools.cafc.CAFCClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search_patent_opinions = AsyncMock(return_value=opinions)

        result = await search_cafc_patent_opinions(full=True)

    item = result.items[0]
    assert "file_path" in item
    assert "patent_confidence" in item


# ──────────────────────────────────────────────────────────────────────
# §5.4 invariant — no batch tools
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_batch_tool_present():
    """§5.4 forbids batch_* tools."""
    from patent_client_agents.mcp.tools import cafc as cafc_module

    assert not hasattr(cafc_module, "batch_cafc_opinions")
    assert not hasattr(cafc_module, "batch_search_cafc_opinions")
    assert not hasattr(cafc_module, "batch_download_cafc_pdf")
