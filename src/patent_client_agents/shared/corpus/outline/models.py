"""Result models shared by the outline corpus clients.

Each package subclasses these under its own names (``MpepSection``,
``EpcSearchHit``, ...) so the public classes and their JSON schemas stay
per-package. A package's search response redeclares ``hits`` with its own
hit class.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class OutlineSearchHit(BaseModel):
    title: str
    href: str
    path: list[str] = Field(default_factory=list)
    result_url: str


class OutlineSearchResponse(BaseModel):
    hits: list[OutlineSearchHit]
    page: int
    per_page: int
    has_more: bool


class OutlineSection(BaseModel):
    href: str
    html: str
    text: str
    version: str
    title: str | None = None


class OutlineVersion(BaseModel):
    label: str
    value: str
    current: bool = False


__all__ = ["OutlineSearchHit", "OutlineSearchResponse", "OutlineSection", "OutlineVersion"]
