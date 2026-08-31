"""MCP envelope tests for China SPC IP Court tools."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from mcp_data_core.envelope import ListEnvelope, Provenance
from patent_client_agents.china_spc_ip_court.models import (
    ChinaSpcIpHearingIndexItem,
    ChinaSpcIpHearingIndexResponse,
    ChinaSpcIpHearingNotice,
    ChinaSpcIpParty,
    ChinaSpcIpSiteSearchHit,
    ChinaSpcIpSiteSearchResponse,
)
from patent_client_agents.mcp.tools.china_spc_ip_court import (
    _china_today,
    get_china_spc_ip_hearing_notice,
    search_china_spc_ip_court_site,
    search_china_spc_ip_hearing_notices,
)


def test_future_filter_uses_china_calendar_date() -> None:
    late_utc = datetime(2026, 8, 20, 16, 30, tzinfo=UTC)
    assert _china_today(late_utc).isoformat() == "2026-08-21"


def _notice() -> ChinaSpcIpHearingNotice:
    return ChinaSpcIpHearingNotice(
        notice_id="9999",
        title="最高人民法院知识产权法庭2099年8月21日开庭公告",
        hearing_date="2099-08-21",
        hearing_time_text="上午九时",
        venue="第五法庭",
        dispute_type="侵害发明专利权纠纷",
        party_clause="上诉人某芯片公司与被上诉人某半导体公司",
        parties=[
            ChinaSpcIpParty(role_zh="上诉人", role_en="appellant", name="某芯片公司"),
            ChinaSpcIpParty(role_zh="被上诉人", role_en="appellee", name="某半导体公司"),
        ],
        body_text="公开开庭审理上诉人某芯片公司与被上诉人某半导体公司侵害发明专利权纠纷一案。",
        notice_url="https://ipc.court.gov.cn/zh-cn/news/view-9999.html",
    )


@pytest.mark.asyncio
async def test_recent_hearing_search_returns_scheduled_notice() -> None:
    index = ChinaSpcIpHearingIndexResponse(
        page=1,
        total_pages=1,
        notices=[
            ChinaSpcIpHearingIndexItem(
                notice_id="9999",
                title="开庭公告",
                notice_url="https://ipc.court.gov.cn/zh-cn/news/view-9999.html",
            )
        ],
    )
    with patch("patent_client_agents.mcp.tools.china_spc_ip_court.ChinaSpcIpCourtClient") as cls:
        client = cls.return_value.__aenter__.return_value
        client.list_hearing_index = AsyncMock(return_value=index)
        client.get_hearing_notice = AsyncMock(return_value=_notice())

        result = await search_china_spc_ip_hearing_notices(query=["芯片", "集成电路"], pages=1)

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.items[0]["dispute_type"] == "侵害发明专利权纠纷"
    assert result.items[0]["parties"][0]["role_en"] == "appellant"
    assert "not authoritative case status" in (result.provenance.as_of_status or "")


@pytest.mark.asyncio
async def test_get_exact_notice_can_return_full_text() -> None:
    with patch("patent_client_agents.mcp.tools.china_spc_ip_court.ChinaSpcIpCourtClient") as cls:
        client = cls.return_value.__aenter__.return_value
        client.get_hearing_notice = AsyncMock(return_value=_notice())

        result = await get_china_spc_ip_hearing_notice("9999")

    assert "body_text" in result.items[0]
    assert result.items[0]["notice_id"] == "9999"


@pytest.mark.asyncio
async def test_site_search_returns_semiconductor_material() -> None:
    response = ChinaSpcIpSiteSearchResponse(
        query="芯片",
        page=1,
        total_count=12,
        total_pages=2,
        hits=[
            ChinaSpcIpSiteSearchHit(
                title="锂电池保护芯片集成电路布图设计侵权案",
                url="https://ipc.court.gov.cn/zh-cn/news/view-5143.html",
            )
        ],
    )
    with patch("patent_client_agents.mcp.tools.china_spc_ip_court.ChinaSpcIpCourtClient") as cls:
        client = cls.return_value.__aenter__.return_value
        client.search_site = AsyncMock(return_value=response)

        result = await search_china_spc_ip_court_site("芯片")

    assert result.items[0]["title"].startswith("锂电池")
    assert result.more_available is True
    assert result.next_cursor == "2"
