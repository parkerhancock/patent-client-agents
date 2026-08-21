"""MCP envelope tests for Japan IP High Court tools."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from mcp_data_core.envelope import ListEnvelope, Provenance
from mcp_data_core.exceptions import ValidationError
from patent_client_agents.japan_ip_high_court.models import (
    JapanIpHighCourtCase,
    JapanIpHighCourtCaseList,
)
from patent_client_agents.mcp.tools.japan_ip_high_court import (
    get_japan_ip_high_court_case,
    search_japan_ip_high_court_cases,
)


def _case_list() -> JapanIpHighCourtCaseList:
    pending = JapanIpHighCourtCase(
        case_status="pending",
        case_number="令和7年（行ケ）第10011号",
        filing_year=2025,
        era_name="令和",
        era_year=7,
        case_type="行ケ",
        serial_number=10011,
        proceeding_type="審決取消（特許）",
        subject_identifier="特願2022-700422",
        subject_identifier_type="patent_application",
        division="知財高裁第２部",
        scheduled_judgment_date=date(2026, 10, 14),
    )
    closed = JapanIpHighCourtCase(
        case_status="closed",
        case_number="令和4年（行ケ）第10108号",
        filing_year=2022,
        era_name="令和",
        era_year=4,
        case_type="行ケ",
        serial_number=10108,
        proceeding_type="審決取消（特許）",
        subject_identifier="特許6806401",
        subject_identifier_type="patent",
        division="知財高裁第２部",
        termination_date=date(2023, 8, 10),
        disposition="判決（請求棄却）",
        appeal_filed=False,
    )
    return JapanIpHighCourtCaseList(
        as_of_date=date(2026, 8, 14),
        pending_count=1,
        closed_count=1,
        cases=[pending, closed],
    )


@pytest.mark.asyncio
async def test_search_defaults_to_pending_and_matches_application_number() -> None:
    with patch("patent_client_agents.mcp.tools.japan_ip_high_court.JapanIpHighCourtClient") as cls:
        client = cls.return_value.__aenter__.return_value
        client.list_cases = AsyncMock(return_value=_case_list())

        result = await search_japan_ip_high_court_cases(query="2022-700422")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert len(result.items) == 1
    assert result.items[0]["case_status"] == "pending"
    assert result.items[0]["subject_identifier"] == "特願2022-700422"
    assert "party names are not published" in (result.provenance.as_of_status or "")
    assert "not a general infringement docket" in result.summary


@pytest.mark.asyncio
async def test_search_normalizes_case_number_width_and_spacing() -> None:
    with patch("patent_client_agents.mcp.tools.japan_ip_high_court.JapanIpHighCourtClient") as cls:
        client = cls.return_value.__aenter__.return_value
        client.list_cases = AsyncMock(return_value=_case_list())

        result = await search_japan_ip_high_court_cases(query="令和7年 (行ケ) 第10011号")

    assert [item["case_number"] for item in result.items] == ["令和7年（行ケ）第10011号"]


@pytest.mark.asyncio
async def test_closed_search_filters_termination_date() -> None:
    with patch("patent_client_agents.mcp.tools.japan_ip_high_court.JapanIpHighCourtClient") as cls:
        client = cls.return_value.__aenter__.return_value
        client.list_cases = AsyncMock(return_value=_case_list())

        result = await search_japan_ip_high_court_cases(
            case_status="closed",
            date_from="2023-08-01",
            date_to="2023-08-31",
        )

    assert [item["case_number"] for item in result.items] == ["令和4年（行ケ）第10108号"]


@pytest.mark.asyncio
async def test_exact_lookup_normalizes_parentheses() -> None:
    with patch("patent_client_agents.mcp.tools.japan_ip_high_court.JapanIpHighCourtClient") as cls:
        client = cls.return_value.__aenter__.return_value
        client.list_cases = AsyncMock(return_value=_case_list())

        result = await get_japan_ip_high_court_case("令和7年 (行ケ) 第10011号")

    assert result.items[0]["case_number"] == "令和7年（行ケ）第10011号"
    assert result.more_available is False


@pytest.mark.asyncio
async def test_search_rejects_reversed_dates() -> None:
    with pytest.raises(ValidationError, match="date_from"):
        await search_japan_ip_high_court_cases(
            date_from="2026-10-15",
            date_to="2026-10-14",
        )
