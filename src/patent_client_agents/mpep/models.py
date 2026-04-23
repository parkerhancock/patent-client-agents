from __future__ import annotations

from pydantic import BaseModel, Field


class MpepSearchHit(BaseModel):
    title: str
    href: str
    path: list[str] = Field(default_factory=list)
    result_url: str


class MpepSearchResponse(BaseModel):
    hits: list[MpepSearchHit]
    page: int
    per_page: int
    has_more: bool


class MpepSection(BaseModel):
    href: str
    html: str
    text: str
    version: str
    title: str | None = None


class MpepVersion(BaseModel):
    label: str
    value: str
    current: bool = False
