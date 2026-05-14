from __future__ import annotations

from pydantic import BaseModel, Field


class MoppSearchHit(BaseModel):
    title: str
    href: str
    path: list[str] = Field(default_factory=list)
    result_url: str


class MoppSearchResponse(BaseModel):
    hits: list[MoppSearchHit]
    page: int
    per_page: int
    has_more: bool


class MoppSection(BaseModel):
    href: str
    html: str
    text: str
    version: str
    title: str | None = None


class MoppVersion(BaseModel):
    label: str
    value: str
    current: bool = False
