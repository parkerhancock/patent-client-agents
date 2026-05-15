"""Envelope-shape tests for the migrated UPC decisions MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope shape + Provenance),
§5.4 (list-accepting fetches), §5.5 (lean default + ``full=True`` opt-in),
and §5.8 (vocab ``list_*`` enumerators returning ``ListEnvelope``).

Mocks the upstream UPC decisions client at the boundary so tests don't
hit the live unifiedpatentcourt.org listing.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from law_tools_core.envelope import ListEnvelope, Provenance
from law_tools_core.exceptions import ValidationError
from patent_client_agents.mcp.tools.upc import (
    get_upc_decision,
    list_upc_divisions,
    list_upc_languages,
    search_upc_decisions,
)
from patent_client_agents.upc_decisions.models import (
    UpcDecision,
    UpcDecisionSearchResponse,
    UpcDivision,
    UpcLanguage,
)


def _make_decision(
    case_id: str,
    *,
    court: str = "Düsseldorf (DE) Local Division",
    type_of_action: str = "Infringement Action",
    parties: tuple[str, ...] = ("Acme Co.", "Widget Corp."),
    pdf_urls: tuple[str, ...] = ("https://www.unifiedpatentcourt.org/sites/default/files/x.pdf",),
) -> UpcDecision:
    return UpcDecision(
        case_id=case_id,
        raw_references=[case_id],
        detail_url=f"https://www.unifiedpatentcourt.org/en/node/{abs(hash(case_id)) % 10000}",
        court=court,
        type_of_action=type_of_action,
        parties=list(parties),
        pdf_urls=list(pdf_urls),
    )


# ──────────────────────────────────────────────────────────────────────
# search_upc_decisions — §5.9, §5.5
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_upc_decisions_returns_lean_list_envelope_by_default():
    response = UpcDecisionSearchResponse(
        page=0,
        total_pages=5,
        hits=[
            _make_decision("UPC_CFI_1747/2025"),
            _make_decision("UPC_CoA_335/2023"),
        ],
    )
    with patch("patent_client_agents.mcp.tools.upc.search_decisions") as mock_search:
        mock_search.return_value = response

        result = await search_upc_decisions(page=0)

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "Unified Patent Court"
    assert "decisions-and-orders" in result.provenance.source_url
    assert result.provenance.corpus_version is None  # live proxy
    assert len(result.items) == 2
    # Lean projection (§5.5)
    assert set(result.items[0].keys()) == {
        "case_id",
        "court",
        "type_of_action",
        "parties",
        "detail_url",
        "primary_pdf_url",
    }
    assert result.items[0]["case_id"] == "UPC_CFI_1747/2025"
    assert result.more_available is True  # page 0 of 5
    assert "2 hits" in result.summary


@pytest.mark.asyncio
async def test_search_upc_decisions_full_true_returns_upstream_shape():
    response = UpcDecisionSearchResponse(
        page=4,
        total_pages=5,
        hits=[_make_decision("UPC_CFI_1747/2025")],
    )
    with patch("patent_client_agents.mcp.tools.upc.search_decisions") as mock_search:
        mock_search.return_value = response

        result = await search_upc_decisions(page=4, full=True)

    # Upstream-shaped row has pdf_urls (list) and raw_references
    assert "pdf_urls" in result.items[0]
    assert "raw_references" in result.items[0]
    # page 4 of 5 = 0-indexed last page → no more
    assert result.more_available is False


@pytest.mark.asyncio
async def test_search_upc_decisions_filter_label_in_summary():
    response = UpcDecisionSearchResponse(page=0, total_pages=1, hits=[])
    with patch("patent_client_agents.mcp.tools.upc.search_decisions") as mock_search:
        mock_search.return_value = response

        result = await search_upc_decisions(judgement_type="order", court_type="1")

    assert "type=order" in result.summary
    assert "court_type=1" in result.summary


# ──────────────────────────────────────────────────────────────────────
# get_upc_decision — §5.4 list-accepting
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_upc_decision_single_returns_list_envelope():
    record = _make_decision("UPC_CFI_1747/2025")
    with patch("patent_client_agents.mcp.tools.upc.UpcDecisionsClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_decision = AsyncMock(return_value=record)

        result = await get_upc_decision(case_id="UPC_CFI_1747/2025")

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 1
    assert "UPC_CFI_1747/2025" in result.summary
    assert "Düsseldorf" in result.summary
    assert "case_id=UPC_CFI_1747/2025" in result.provenance.source_url


@pytest.mark.asyncio
async def test_get_upc_decision_list_preserves_order():
    case_ids = ["UPC_CFI_1747/2025", "UPC_CoA_335/2023", "ACT_551054/2023"]
    records = [_make_decision(c) for c in case_ids]
    with patch("patent_client_agents.mcp.tools.upc.UpcDecisionsClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_decision = AsyncMock(side_effect=records)

        result = await get_upc_decision(case_id=case_ids)

    assert [r["case_id"] for r in result.items] == case_ids
    assert "3 of 3" in result.summary


@pytest.mark.asyncio
async def test_get_upc_decision_partial_not_found_lists_missing():
    case_ids = ["UPC_CFI_1747/2025", "UPC_CFI_9999/2099"]
    with patch("patent_client_agents.mcp.tools.upc.UpcDecisionsClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_decision = AsyncMock(
            side_effect=[_make_decision("UPC_CFI_1747/2025"), None]
        )

        result = await get_upc_decision(case_id=case_ids)

    assert len(result.items) == 1
    assert "UPC_CFI_9999/2099" in result.summary
    assert "Not found" in result.summary


@pytest.mark.asyncio
async def test_get_upc_decision_empty_list_raises():
    with pytest.raises(ValidationError, match="at least one"):
        await get_upc_decision(case_id=[])


# ──────────────────────────────────────────────────────────────────────
# list_upc_divisions / list_upc_languages — §5.8 vocab enumerators
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_upc_divisions_returns_list_envelope():
    divisions = [
        UpcDivision(id="35", name="Düsseldorf (DE) Local Division"),
        UpcDivision(id="36", name="Munich (DE) Local Division"),
    ]
    with patch("patent_client_agents.mcp.tools.upc.list_divisions") as mock_list:
        mock_list.return_value = divisions

        result = await list_upc_divisions()

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "Unified Patent Court"
    assert len(result.items) == 2
    assert result.items[0]["id"] == "35"
    assert "2 options" in result.summary


@pytest.mark.asyncio
async def test_list_upc_languages_returns_list_envelope():
    langs = [
        UpcLanguage(id="1", name="English"),
        UpcLanguage(id="2", name="French"),
        UpcLanguage(id="3", name="German"),
    ]
    with patch("patent_client_agents.mcp.tools.upc.list_languages") as mock_list:
        mock_list.return_value = langs

        result = await list_upc_languages()

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 3
    assert "3 options" in result.summary
