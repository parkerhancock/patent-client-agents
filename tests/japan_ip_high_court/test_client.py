"""Offline request-contract tests for the Japan IP High Court client."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from patent_client_agents.japan_ip_high_court import JapanIpHighCourtClient
from patent_client_agents.japan_ip_high_court.models import JapanIpHighCourtCaseList


@pytest.mark.asyncio
async def test_client_downloads_official_workbook_with_excel_accept_header() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=b"legacy xls")

    transport_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    expected = JapanIpHighCourtCaseList(pending_count=0, closed_count=0, cases=[])
    with patch(
        "patent_client_agents.japan_ip_high_court.client.parse_case_workbook",
        return_value=expected,
    ):
        async with JapanIpHighCourtClient(client=transport_client) as client:
            result = await client.list_cases()

    assert captured[0].url.path == "/ip/vc-files/ip/jikenitiran.xls"
    assert "application/vnd.ms-excel" in captured[0].headers["accept"]
    assert captured[0].headers["referer"] == "https://www.courts.go.jp/ip/"
    assert result == expected
