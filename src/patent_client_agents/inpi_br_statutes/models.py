"""Pydantic models for the LPI (Lei 9.279/1996) statutes corpus."""

from __future__ import annotations

from pydantic import BaseModel, Field


class InpiBrSearchHit(BaseModel):
    """One ranked hit from a LPI corpus search."""

    title: str
    href: str
    article_number: str | None = None
    path: list[str] = Field(default_factory=list)
    result_url: str
    snippet: str | None = None


class InpiBrSearchResponse(BaseModel):
    """A page of LPI corpus search hits."""

    hits: list[InpiBrSearchHit]
    page: int
    per_page: int
    has_more: bool


class InpiBrSection(BaseModel):
    """One LPI Article record (PT authoritative, EN translation when available)."""

    href: str
    article_number: str | None = None
    title_pt: str | None = None
    title_en: str | None = None
    title_section: str | None = None
    text_pt: str
    text_en: str | None = None
    html_pt: str
    html_en: str | None = None
    version: str


class InpiBrVersion(BaseModel):
    """Corpus version label (lpi_year + snapshot_date)."""

    label: str
    value: str
    current: bool = False


__all__ = [
    "InpiBrSearchHit",
    "InpiBrSearchResponse",
    "InpiBrSection",
    "InpiBrVersion",
]
