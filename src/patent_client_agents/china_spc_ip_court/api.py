"""MCP-free convenience API for China's SPC IP Court connector."""

from __future__ import annotations

from .client import ChinaSpcIpCourtClient
from .models import (
    ChinaSpcIpHearingIndexResponse,
    ChinaSpcIpHearingNotice,
    ChinaSpcIpSiteSearchResponse,
)


async def list_hearing_index(page: int = 1) -> ChinaSpcIpHearingIndexResponse:
    async with ChinaSpcIpCourtClient() as client:
        return await client.list_hearing_index(page=page)


async def get_hearing_notice(notice: str) -> ChinaSpcIpHearingNotice:
    async with ChinaSpcIpCourtClient() as client:
        return await client.get_hearing_notice(notice)


async def search_site(query: str, page: int = 1) -> ChinaSpcIpSiteSearchResponse:
    async with ChinaSpcIpCourtClient() as client:
        return await client.search_site(query, page=page)


__all__ = ["get_hearing_notice", "list_hearing_index", "search_site"]
