"""Offline request-contract tests for the China SPC IP Court client."""

from __future__ import annotations

import httpx
import pytest

from patent_client_agents.china_spc_ip_court import ChinaSpcIpCourtClient

from .test_parsers import DETAIL_HTML, INDEX_HTML, SEARCH_HTML


def _mock_client(handler) -> ChinaSpcIpCourtClient:
    transport_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ChinaSpcIpCourtClient(client=transport_client)


@pytest.mark.asyncio
async def test_index_uses_public_hearing_path_and_browser_headers() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, text=INDEX_HTML)

    async with _mock_client(handler) as client:
        result = await client.list_hearing_index(page=2)

    assert captured[0].url.path.endswith("/news/more-4-15.html")
    assert captured[0].url.params["page"] == "2"
    assert "Mozilla" in captured[0].headers["user-agent"]
    assert result.notices[0].notice_id == "5999"


@pytest.mark.asyncio
async def test_exact_notice_fetch() -> None:
    async with _mock_client(lambda request: httpx.Response(200, text=DETAIL_HTML)) as client:
        result = await client.get_hearing_notice("5999")

    assert result.dispute_type == "发明专利权无效行政纠纷"


@pytest.mark.asyncio
async def test_exact_notice_rejects_official_looking_external_url() -> None:
    async with _mock_client(lambda request: httpx.Response(200, text=DETAIL_HTML)) as client:
        with pytest.raises(ValueError, match="official SPC IP Court host"):
            await client.get_hearing_notice("https://example.com/zh-cn/news/view-5999.html")


@pytest.mark.asyncio
async def test_site_search_passes_chinese_query() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, text=SEARCH_HTML)

    async with _mock_client(handler) as client:
        result = await client.search_site("芯片")

    assert captured[0].url.params["content"] == "芯片"
    assert result.total_count == 12
