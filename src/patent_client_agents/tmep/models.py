from __future__ import annotations

from pydantic import BaseModel, Field


class TmepSearchHit(BaseModel):
    """A single search result from the TMEP."""

    title: str
    href: str
    path: list[str] = Field(default_factory=list)
    result_url: str


class TmepSearchResponse(BaseModel):
    """Response from a TMEP search query."""

    hits: list[TmepSearchHit]
    page: int
    per_page: int
    has_more: bool


class TmepSection(BaseModel):
    """A section of the TMEP."""

    href: str
    html: str
    text: str
    version: str
    title: str | None = None


class TmepVersion(BaseModel):
    """An available TMEP version."""

    label: str
    value: str
    current: bool = False
