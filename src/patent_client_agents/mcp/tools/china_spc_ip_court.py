"""MCP tools for China's Supreme People's Court Intellectual Property Court."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from typing import Annotated, Any
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope, make_provenance
from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.china_spc_ip_court import ChinaSpcIpCourtClient

china_spc_ip_court_mcp = FastMCP("China SPC Intellectual Property Court")

_SOURCE_NAME = "Supreme People's Court Intellectual Property Court — Hearing Notices"
_BASE_URL = "https://ipc.court.gov.cn"
_INDEX_PATH = "/zh-cn/news/more-4-15.html"
_FANOUT_CONCURRENCY = 5
_CHINA_TIME = ZoneInfo("Asia/Shanghai")


def _provenance(path: str = _INDEX_PATH, *, status: str) -> Any:
    return make_provenance(
        source_url=f"{_BASE_URL}{path}",
        source_name=_SOURCE_NAME,
        as_of_status=status,
    )


def _lean_hearing(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "notice_id": record.get("notice_id"),
        "hearing_date": record.get("hearing_date"),
        "hearing_time_text": record.get("hearing_time_text"),
        "venue": record.get("venue"),
        "dispute_type": record.get("dispute_type"),
        "parties": record.get("parties") or [],
        "notice_url": record.get("notice_url"),
    }


def _terms(query: str | list[str] | None) -> list[str]:
    if query is None:
        return []
    values = [query] if isinstance(query, str) else query
    terms = [value.strip() for value in values if value.strip()]
    if not terms:
        raise ValidationError("query must contain at least one non-empty term")
    return terms


def _china_today(now: datetime | None = None) -> date:
    instant = now or datetime.now(UTC)
    if instant.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return instant.astimezone(_CHINA_TIME).date()


@china_spc_ip_court_mcp.tool(annotations=READ_ONLY)
async def search_china_spc_ip_hearing_notices(
    query: Annotated[
        str | list[str] | None,
        "Optional Chinese party/company or technology term, or OR-list such as ['芯片', '半导体', '集成电路'].",
    ] = None,
    pages: Annotated[
        int,
        "Recent hearing-index pages to inspect (1-50); each page currently contains five notices.",
    ] = 10,
    future_only: Annotated[
        bool,
        "Keep notices whose scheduled hearing date is today or later.",
    ] = True,
    limit: Annotated[int, "Maximum matching notices (1-100)."] = 25,
    full: Annotated[
        bool,
        "False returns lean hearing records; True also includes the Chinese notice body and raw party clause.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search recent scheduled hearings at China's national appellate IP court.

    The official feed covers public hearing notices from the Supreme People's
    Court Intellectual Property Court, including patent, integrated-circuit,
    trade-secret, software, plant-variety, and technology antitrust appeals.
    It is useful for pending-hearing monitoring but is not a complete case
    docket: notices may omit the case number, patent number, and subsequent
    disposition. Chinese party names or aliases produce the best matches.

    Related tools: get_china_spc_ip_hearing_notice,
    search_china_spc_ip_court_site.
    """
    if not 1 <= pages <= 50:
        raise ValidationError("pages must be between 1 and 50")
    if not 1 <= limit <= 100:
        raise ValidationError("limit must be between 1 and 100")
    search_terms = _terms(query)

    async with ChinaSpcIpCourtClient() as client:
        index_semaphore = asyncio.Semaphore(_FANOUT_CONCURRENCY)

        async def fetch_index(page: int):
            async with index_semaphore:
                return await client.list_hearing_index(page=page)

        indexes = await asyncio.gather(*(fetch_index(page) for page in range(1, pages + 1)))
        stubs = [stub for index in indexes for stub in index.notices]
        semaphore = asyncio.Semaphore(_FANOUT_CONCURRENCY)

        async def fetch(notice_id: str) -> dict[str, Any]:
            async with semaphore:
                notice = await client.get_hearing_notice(notice_id)
            return notice.model_dump(mode="json")

        records = list(await asyncio.gather(*(fetch(stub.notice_id) for stub in stubs)))

    today = _china_today().isoformat()
    if future_only:
        records = [record for record in records if (record.get("hearing_date") or "") >= today]
    if search_terms:
        folded_terms = [term.casefold() for term in search_terms]
        records = [
            record
            for record in records
            if any(
                term in " ".join(str(value) for value in record.values()).casefold()
                for term in folded_terms
            )
        ]
    records.sort(key=lambda record: record.get("hearing_date") or "", reverse=True)
    total_matches = len(records)
    records = records[:limit]
    items = records if full else [_lean_hearing(record) for record in records]
    total_index_pages = max((index.total_pages for index in indexes), default=pages)

    query_label = f" for {search_terms!r}" if search_terms else ""
    status = "scheduled hearings; not authoritative case status"
    return ListEnvelope[dict](
        summary=(
            f"China SPC IP Court hearing notices{query_label}: {len(items)} returned "
            f"from {total_matches} matches across {pages} recent index page(s). "
            "This is a hearing calendar, not a complete docket or party-side search."
        ),
        items=items,
        more_available=total_matches > len(items) or total_index_pages > pages,
        next_cursor=None,
        provenance=_provenance(status=status),
    )


@china_spc_ip_court_mcp.tool(annotations=READ_ONLY)
async def get_china_spc_ip_hearing_notice(
    notice: Annotated[
        str | list[str],
        "Official numeric notice ID/URL or a list, e.g. '5999'.",
    ],
    full: Annotated[
        bool,
        "False returns lean normalized fields; True includes the complete Chinese notice text.",
    ] = True,
) -> ListEnvelope[dict]:
    """Get exact official Chinese SPC IP Court scheduled-hearing notices.

    Related tools: search_china_spc_ip_hearing_notices,
    search_china_spc_ip_court_site.
    """
    values = [notice] if isinstance(notice, str) else notice
    if not values:
        raise ValidationError("notice list must not be empty")
    if len(values) > 25:
        raise ValidationError("notice accepts at most 25 IDs/URLs per call")

    semaphore = asyncio.Semaphore(_FANOUT_CONCURRENCY)
    async with ChinaSpcIpCourtClient() as client:

        async def fetch(value: str) -> dict[str, Any]:
            async with semaphore:
                item = await client.get_hearing_notice(value)
            return item.model_dump(mode="json")

        records = list(await asyncio.gather(*(fetch(value) for value in values)))
    items = records if full else [_lean_hearing(record) for record in records]
    statuses = sorted({str(record.get("hearing_date") or "date unknown") for record in records})
    return ListEnvelope[dict](
        summary=f"Fetched {len(items)} official China SPC IP Court hearing notice(s).",
        items=items,
        more_available=False,
        next_cursor=None,
        provenance=_provenance(status=f"scheduled hearing date(s): {', '.join(statuses)}"),
    )


@china_spc_ip_court_mcp.tool(annotations=READ_ONLY)
async def search_china_spc_ip_court_site(
    query: Annotated[
        str,
        "Chinese party/company, case, or technology term; e.g. '华为', '芯片', or '集成电路'.",
    ],
    page: Annotated[int, "One-indexed upstream result page."] = 1,
    hearing_notices_only: Annotated[
        bool,
        "Keep results explicitly titled as hearing notices; false also returns judgments, case analyses, and court news.",
    ] = False,
    limit: Annotated[int, "Maximum results from this page (1-25)."] = 25,
) -> ListEnvelope[dict]:
    """Search the official China SPC IP Court website by party or technology term.

    This broader source can locate semiconductor-related judgments and court
    materials as well as hearing notices. It does not search the restricted
    national judicial-process system and should not be treated as exhaustive
    party litigation coverage.

    Related tools: search_china_spc_ip_hearing_notices,
    get_china_spc_ip_hearing_notice.
    """
    if page < 1:
        raise ValidationError("page must be at least 1")
    if not 1 <= limit <= 25:
        raise ValidationError("limit must be between 1 and 25")
    async with ChinaSpcIpCourtClient() as client:
        response = await client.search_site(query, page=page)
    hits = response.hits
    if hearing_notices_only:
        hits = [hit for hit in hits if hit.is_hearing_notice]
    records = [hit.model_dump(mode="json") for hit in hits[:limit]]
    encoded_query = quote_plus(query)
    return ListEnvelope[dict](
        summary=(
            f"China SPC IP Court site search for `{query}`: {len(records)} result(s) "
            f"returned from approximately {response.total_count} upstream matches."
        ),
        items=records,
        more_available=response.total_pages > page or len(hits) > len(records),
        next_cursor=str(page + 1) if response.total_pages > page else None,
        provenance=_provenance(
            f"/zh-cn/search.html?content={encoded_query}",
            status="site content; not authoritative case status",
        ),
    )


__all__ = ["china_spc_ip_court_mcp"]
