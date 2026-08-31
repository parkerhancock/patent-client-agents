"""Models for public hearing notices from China's SPC IP Court."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class ChinaSpcIpParty(BaseModel):
    """A party side parsed conservatively from the Chinese notice text."""

    role_zh: str
    role_en: str
    name: str


class ChinaSpcIpHearingIndexItem(BaseModel):
    """One row in the official hearing-notice index."""

    notice_id: str
    title: str
    published_date: date | None = None
    notice_url: str


class ChinaSpcIpHearingNotice(BaseModel):
    """A normalized scheduled-hearing notice."""

    notice_id: str
    title: str
    published_at: datetime | None = None
    hearing_date: date | None = None
    hearing_time_text: str | None = None
    venue: str | None = None
    dispute_type: str | None = None
    party_clause: str | None = None
    parties: list[ChinaSpcIpParty] = Field(default_factory=list)
    body_text: str
    notice_url: str


class ChinaSpcIpHearingIndexResponse(BaseModel):
    page: int
    total_pages: int
    notices: list[ChinaSpcIpHearingIndexItem]


class ChinaSpcIpSiteSearchHit(BaseModel):
    """One result from the Tribunal website's full-site search."""

    title: str
    snippet: str | None = None
    published_at: datetime | None = None
    url: str
    is_hearing_notice: bool = False


class ChinaSpcIpSiteSearchResponse(BaseModel):
    query: str
    page: int
    total_count: int
    total_pages: int
    hits: list[ChinaSpcIpSiteSearchHit]


__all__ = [
    "ChinaSpcIpHearingIndexItem",
    "ChinaSpcIpHearingIndexResponse",
    "ChinaSpcIpHearingNotice",
    "ChinaSpcIpParty",
    "ChinaSpcIpSiteSearchHit",
    "ChinaSpcIpSiteSearchResponse",
]
