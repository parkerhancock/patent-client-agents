"""Client for public hearing notices from China's SPC IP Court."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any
from urllib.parse import urljoin

import httpx
from lxml import html

from mcp_data_core import BaseAsyncClient
from mcp_data_core.exceptions import NotFoundError, ParseError

from .models import (
    ChinaSpcIpHearingIndexItem,
    ChinaSpcIpHearingIndexResponse,
    ChinaSpcIpHearingNotice,
    ChinaSpcIpParty,
    ChinaSpcIpSiteSearchHit,
    ChinaSpcIpSiteSearchResponse,
)

DEFAULT_BASE_URL = "https://ipc.court.gov.cn"
HEARING_INDEX_PATH = "/zh-cn/news/more-4-15.html"
HEARING_INDEX_URL = f"{DEFAULT_BASE_URL}{HEARING_INDEX_PATH}"

_BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": f"{DEFAULT_BASE_URL}/zh-cn/index",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0 Safari/537.36"
    ),
}

_NOTICE_ID_RE = re.compile(r"view-(\d+)\.html")
_ARABIC_DATE_RE = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")
_PUBLISHED_RE = re.compile(r"发布时间[：:]\s*(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}:\d{2})?)")
_TIME_RE = re.compile(
    r"(?:上午|下午|晚间|中午)?[〇零一二三四五六七八九十百两0-9]+时"
    r"(?:[〇零一二三四五六七八九十百两0-9]+分)?"
)
_ROLE_RE = re.compile(
    r"(上诉人|被上诉人|一审原告|一审被告|原审原告|原审被告|再审申请人|"
    r"申请再审人|被申请人|原告|被告|第三人)(.+?)(?=(?:与|及)?(?:上诉人|被上诉人|"
    r"一审原告|一审被告|原审原告|原审被告|再审申请人|申请再审人|被申请人|"
    r"原告|被告|第三人)|$)"
)
_ROLE_EN = {
    "上诉人": "appellant",
    "被上诉人": "appellee",
    "一审原告": "first_instance_plaintiff",
    "一审被告": "first_instance_defendant",
    "原审原告": "original_plaintiff",
    "原审被告": "original_defendant",
    "再审申请人": "retrial_applicant",
    "申请再审人": "retrial_applicant",
    "被申请人": "respondent",
    "原告": "plaintiff",
    "被告": "defendant",
    "第三人": "third_party",
}
_DISPUTE_STARTERS = (
    "确认不侵害",
    "侵害",
    "发明专利",
    "实用新型",
    "外观设计",
    "专利权",
    "集成电路",
    "计算机软件",
    "技术合同",
    "技术秘密",
    "商业秘密",
    "标准必要专利",
    "垄断",
    "植物新品种",
)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value.replace("\u3000", " ")).strip()


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        return None


def _notice_id(url: str) -> str:
    match = _NOTICE_ID_RE.search(url)
    if not match:
        raise ParseError(f"Could not parse hearing-notice ID from {url}")
    return match.group(1)


def parse_hearing_index(
    html_text: str,
    *,
    page: int = 1,
    base_url: str = DEFAULT_BASE_URL,
) -> ChinaSpcIpHearingIndexResponse:
    """Parse one page of the official hearing-notice index."""
    tree = html.fromstring(html_text)
    notices: list[ChinaSpcIpHearingIndexItem] = []
    for row in tree.xpath("//div[contains(@class, 'listing')]//li"):
        anchors = row.xpath(".//a[contains(@href, '/news/view-')]")
        if not anchors:
            continue
        anchor = anchors[0]
        href = anchor.get("href") or ""
        title = " ".join(anchor.text_content().split())
        date_text = "".join(row.xpath(".//span[contains(@class, 'right')]/text()"))
        try:
            published_date = date.fromisoformat(date_text.strip())
        except ValueError:
            published_date = None
        url = urljoin(base_url, href)
        notices.append(
            ChinaSpcIpHearingIndexItem(
                notice_id=_notice_id(url),
                title=title,
                published_date=published_date,
                notice_url=url,
            )
        )

    total_pages = page
    for href in tree.xpath("//div[contains(@class, 'pagination')]//a/@href"):
        match = re.search(r"[?&]page=(\d+)", href)
        if match:
            total_pages = max(total_pages, int(match.group(1)))
    return ChinaSpcIpHearingIndexResponse(
        page=page,
        total_pages=total_pages,
        notices=notices,
    )


def _split_case_clause(case_clause: str) -> tuple[str | None, str | None]:
    for starter in _DISPUTE_STARTERS:
        index = case_clause.rfind(starter)
        if index >= 0 and case_clause.endswith("纠纷"):
            return case_clause[:index].rstrip("，,"), case_clause[index:]
    return case_clause or None, None


def _parse_parties(party_clause: str | None) -> list[ChinaSpcIpParty]:
    if not party_clause:
        return []
    parties: list[ChinaSpcIpParty] = []
    for match in _ROLE_RE.finditer(party_clause):
        role = match.group(1)
        name = match.group(2).strip("与及、，, ")
        if name:
            parties.append(ChinaSpcIpParty(role_zh=role, role_en=_ROLE_EN[role], name=name))
    return parties


def parse_hearing_notice(
    html_text: str,
    *,
    notice_url: str,
) -> ChinaSpcIpHearingNotice:
    """Parse one official scheduled-hearing notice."""
    tree = html.fromstring(html_text)
    title_nodes = tree.xpath("//div[contains(@class, 'detail')]/h2")
    body_nodes = tree.xpath("//div[contains(@class, 'detail')]//div[contains(@class, 'txt')]")
    if not title_nodes or not body_nodes:
        raise ParseError(f"Unexpected SPC IP Court hearing-notice shape: {notice_url}")

    title = " ".join(title_nodes[0].text_content().split())
    body_text = _normalize_text(body_nodes[0].text_content())
    message = " ".join(
        tree.xpath("//div[contains(@class, 'detail')]//div[contains(@class, 'message')]//text()")
    )
    published_match = _PUBLISHED_RE.search(message)
    published_at = _parse_iso_datetime(published_match.group(1)) if published_match else None

    hearing_date = None
    date_match = _ARABIC_DATE_RE.search(title)
    if date_match:
        hearing_date = date(*(int(value) for value in date_match.groups()))

    hearing_time_text = None
    time_match = _TIME_RE.search(body_text)
    if time_match:
        hearing_time_text = time_match.group(0)

    venue = None
    venue_match = re.search(r"(?:时|分)在(.+?)公开开庭审理", body_text)
    if venue_match:
        venue = venue_match.group(1)

    party_clause = None
    dispute_type = None
    case_match = re.search(r"公开开庭审理(.+?)一案", body_text)
    if case_match:
        party_clause, dispute_type = _split_case_clause(case_match.group(1))

    return ChinaSpcIpHearingNotice(
        notice_id=_notice_id(notice_url),
        title=title,
        published_at=published_at,
        hearing_date=hearing_date,
        hearing_time_text=hearing_time_text,
        venue=venue,
        dispute_type=dispute_type,
        party_clause=party_clause,
        parties=_parse_parties(party_clause),
        body_text=body_text,
        notice_url=notice_url,
    )


def parse_site_search(
    html_text: str,
    *,
    query: str,
    page: int = 1,
    base_url: str = DEFAULT_BASE_URL,
) -> ChinaSpcIpSiteSearchResponse:
    """Parse one page of the Tribunal website's full-site search."""
    tree = html.fromstring(html_text)
    hits: list[ChinaSpcIpSiteSearchHit] = []
    for row in tree.xpath(
        "//div[contains(@class, 'search_list')]//ul[contains(@class, 'list')]/li"
    ):
        anchors = row.xpath("./a[@href]")
        if not anchors:
            continue
        anchor = anchors[0]
        title = " ".join(anchor.text_content().split())
        href = anchor.get("href") or ""
        snippets = row.xpath("./span")
        snippet = " ".join(snippets[0].text_content().split()) if snippets else None
        date_nodes = row.xpath("./i[contains(@class, 'date')]/text()")
        published_at = _parse_iso_datetime(date_nodes[0]) if date_nodes else None
        hits.append(
            ChinaSpcIpSiteSearchHit(
                title=title,
                snippet=snippet,
                published_at=published_at,
                url=urljoin(base_url, href),
                is_hearing_notice="开庭公告" in title,
            )
        )

    count_nodes = tree.xpath(
        "//div[contains(@class, 'count')]//span[contains(@class, 'num')]/text()"
    )
    total_count = int(count_nodes[0]) if count_nodes and count_nodes[0].isdigit() else len(hits)
    total_pages = page
    for href in tree.xpath("//div[contains(@class, 'pagination')]//a/@href"):
        match = re.search(r"[?&]page=(\d+)", href)
        if match:
            total_pages = max(total_pages, int(match.group(1)))
    return ChinaSpcIpSiteSearchResponse(
        query=query,
        page=page,
        total_count=total_count,
        total_pages=total_pages,
        hits=hits,
    )


class ChinaSpcIpCourtClient(BaseAsyncClient):
    """Read-only client for the SPC IP Court's public website."""

    DEFAULT_BASE_URL = DEFAULT_BASE_URL
    CACHE_NAME = "china_spc_ip_court"
    DEFAULT_TIMEOUT = 60.0

    def __init__(self, *, client: httpx.AsyncClient | None = None, **kwargs: Any) -> None:
        kwargs.setdefault("ttl_seconds", 600)
        super().__init__(client=client, headers=_BROWSER_HEADERS, **kwargs)
        if client is not None:
            client.headers.update(_BROWSER_HEADERS)

    async def list_hearing_index(self, *, page: int = 1) -> ChinaSpcIpHearingIndexResponse:
        if page < 1:
            raise ValueError("page must be at least 1")
        response = await self._request(
            "GET",
            HEARING_INDEX_PATH,
            params={"page": page} if page > 1 else None,
            context="SPC IP Court hearing index",
        )
        return parse_hearing_index(response.text, page=page, base_url=self.base_url)

    async def get_hearing_notice(self, notice: str) -> ChinaSpcIpHearingNotice:
        value = notice.strip()
        if value.isdigit():
            path = f"/zh-cn/news/view-{value}.html"
            url = urljoin(self.base_url, path)
        elif value.startswith("http"):
            if not value.startswith(f"{self.base_url}/zh-cn/news/view-"):
                raise ValueError("notice URL must use the official SPC IP Court host")
            url = value
            path = url.removeprefix(self.base_url)
        else:
            match = _NOTICE_ID_RE.search(value)
            if not match:
                raise ValueError("notice must be a numeric notice ID or official notice URL")
            path = f"/zh-cn/news/view-{match.group(1)}.html"
            url = urljoin(self.base_url, path)
        response = await self._request("GET", path, context=f"SPC IP Court notice {value}")
        if "开庭公告" not in response.text:
            raise NotFoundError(f"SPC IP Court hearing notice not found: {value}")
        return parse_hearing_notice(response.text, notice_url=url)

    async def search_site(self, query: str, *, page: int = 1) -> ChinaSpcIpSiteSearchResponse:
        term = query.strip()
        if len(term) < 2:
            raise ValueError("query must contain at least 2 characters")
        if page < 1:
            raise ValueError("page must be at least 1")
        params: dict[str, Any] = {"content": term}
        if page > 1:
            params["page"] = page
        response = await self._request(
            "GET",
            "/zh-cn/search.html",
            params=params,
            context="SPC IP Court site search",
        )
        return parse_site_search(response.text, query=term, page=page, base_url=self.base_url)


__all__ = [
    "DEFAULT_BASE_URL",
    "HEARING_INDEX_URL",
    "ChinaSpcIpCourtClient",
    "parse_hearing_index",
    "parse_hearing_notice",
    "parse_site_search",
]
