"""MCP envelope tests for the Canadian Federal Court docket tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from mcp_data_core.envelope import ListEnvelope, Provenance
from patent_client_agents.canada_federal_court.models import (
    DocketStatus,
    FederalCourtCase,
    FederalCourtCaseRecord,
    FederalCourtCaseSearchResponse,
    FederalCourtDocketEntry,
    FederalCourtDocketResponse,
    FederalCourtIntellectualProperty,
    FederalCourtParty,
)
from patent_client_agents.mcp.tools.canada_federal_court import (
    get_canada_federal_court_case,
    list_canada_federal_court_docket_entries,
    search_canada_federal_court_patent_cases,
)


def _case() -> FederalCourtCase:
    return FederalCourtCase(
        court_number="T-2962-24",
        style_of_cause="PFIZER CANADA ULC v. TARO PHARMACEUTICALS INC.",
        nature_en="Patent Infringement",
        division="T",
        filed_date="2024-10-31",
        parties=["PFIZER CANADA ULC", "TARO PHARMACEUTICALS INC"],
    )


def _docket() -> FederalCourtDocketResponse:
    return FederalCourtDocketResponse(
        court_number="T-2962-24",
        total_count=1,
        status=DocketStatus(
            assessment="likely_pending",
            basis="Latest entry schedules a case management conference.",
        ),
        entries=[
            FederalCourtDocketEntry(
                court_number="T-2962-24",
                entry_number=10,
                summary="Case management conference scheduled",
                document_date="2024-11-21",
            )
        ],
    )


@pytest.mark.asyncio
async def test_search_returns_lean_cases_with_inferred_status() -> None:
    response = FederalCourtCaseSearchResponse(
        query="Pfizer",
        upstream_count=5,
        filtered_count=1,
        cases=[_case()],
    )
    with patch(
        "patent_client_agents.mcp.tools.canada_federal_court.CanadaFederalCourtClient"
    ) as cls:
        client = cls.return_value.__aenter__.return_value
        client.search_party_cases = AsyncMock(return_value=response)
        client.list_docket_entries = AsyncMock(return_value=_docket())

        result = await search_canada_federal_court_patent_cases("Pfizer")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.as_of_status == "inferred per item"
    assert result.items[0]["court_number"] == "T-2962-24"
    assert result.items[0]["status_assessment"]["assessment"] == "likely_pending"
    assert "intellectual_property" not in result.items[0]


@pytest.mark.asyncio
async def test_get_case_includes_parties_patents_and_status() -> None:
    record = FederalCourtCaseRecord(
        case=_case(),
        parties=[FederalCourtParty(name="PFIZER CANADA ULC")],
        intellectual_property=[FederalCourtIntellectualProperty(number="2688467")],
    )
    with patch(
        "patent_client_agents.mcp.tools.canada_federal_court.CanadaFederalCourtClient"
    ) as cls:
        client = cls.return_value.__aenter__.return_value
        client.get_case = AsyncMock(return_value=record)
        client.list_docket_entries = AsyncMock(return_value=_docket())

        result = await get_canada_federal_court_case("T-2962-24")

    assert len(result.items) == 1
    assert result.items[0]["intellectual_property"][0]["number"] == "2688467"
    assert result.provenance.as_of_status == "likely_pending"


@pytest.mark.asyncio
async def test_docket_returns_lean_entries_and_status_provenance() -> None:
    with patch(
        "patent_client_agents.mcp.tools.canada_federal_court.CanadaFederalCourtClient"
    ) as cls:
        client = cls.return_value.__aenter__.return_value
        client.list_docket_entries = AsyncMock(return_value=_docket())

        result = await list_canada_federal_court_docket_entries("T-2962-24")

    assert result.provenance.as_of_status == "likely_pending"
    assert result.items[0]["summary"] == "Case management conference scheduled"
    assert set(result.items[0]) == {
        "entry_number",
        "document_date",
        "office_en",
        "summary",
        "document_number",
        "download_url",
    }


@pytest.mark.asyncio
async def test_search_without_status_check_says_status_unknown() -> None:
    response = FederalCourtCaseSearchResponse(
        query="Pfizer",
        upstream_count=1,
        filtered_count=1,
        cases=[_case()],
    )
    with patch(
        "patent_client_agents.mcp.tools.canada_federal_court.CanadaFederalCourtClient"
    ) as cls:
        client = cls.return_value.__aenter__.return_value
        client.search_party_cases = AsyncMock(return_value=response)

        result = await search_canada_federal_court_patent_cases("Pfizer", assess_status=False)

    assert result.items[0]["status_assessment"]["assessment"] == "unknown"
    assert result.provenance.as_of_status == "not reported by upstream"


@pytest.mark.asyncio
async def test_search_preserves_case_when_status_lookup_fails() -> None:
    response = FederalCourtCaseSearchResponse(
        query="Pfizer",
        upstream_count=1,
        filtered_count=1,
        cases=[_case()],
    )
    with patch(
        "patent_client_agents.mcp.tools.canada_federal_court.CanadaFederalCourtClient"
    ) as cls:
        client = cls.return_value.__aenter__.return_value
        client.search_party_cases = AsyncMock(return_value=response)
        client.list_docket_entries = AsyncMock(side_effect=ValueError("bad payload"))

        result = await search_canada_federal_court_patent_cases("Pfizer")

    assert result.items[0]["court_number"] == "T-2962-24"
    assert result.items[0]["status_assessment"]["assessment"] == "unknown"
