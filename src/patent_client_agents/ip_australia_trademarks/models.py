"""Pydantic models for the Australian Trade Mark Search API.

Field shapes are inferred from the public description page at
``descriptions.api.gov.au/ipaustralia/trademark-search/`` and from the
ATMOSS UI; the upstream does not publish a Swagger spec. ``extra="allow"``
keeps parsing forward-compatible with fields the upstream may add.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from patent_client_agents.shared.models import ApiModel

_BASE_CONFIG: ConfigDict = ConfigDict(populate_by_name=True, extra="allow")


class TrademarkSearchHit(ApiModel):
    """Lean row from ``POST /search/quick`` on the trade marks API.

    Each hit carries the Australian trade mark number (``serial_number``)
    plus the bibliographic fields IP Australia surfaces in its
    quick-search list view.
    """

    serial_number: str | None = None
    word_mark: str | None = None
    status: str | None = None
    mark_type: str | None = None
    application_date: str | None = None
    registration_date: str | None = None
    nice_classes: list[Any] = Field(default_factory=list)
    owners: list[Any] = Field(default_factory=list)

    model_config = _BASE_CONFIG


class TrademarkSearchResult(BaseModel):
    """Envelope returned by ``POST /search/quick`` on the trade marks API."""

    results: list[TrademarkSearchHit] = Field(default_factory=list)
    total: int | None = None

    model_config = _BASE_CONFIG


class Trademark(ApiModel):
    """Full Australian trade mark record from ``GET /trade-mark/{id}``."""

    serial_number: str | None = None
    word_mark: str | None = None
    status: str | None = None
    mark_type: str | None = None
    application_date: str | None = None
    registration_date: str | None = None
    renewal_date: str | None = None
    expiry_date: str | None = None
    nice_classes: list[Any] = Field(default_factory=list)
    owners: list[Any] = Field(default_factory=list)
    goods_and_services: list[Any] = Field(default_factory=list)
    representatives: list[Any] = Field(default_factory=list)

    model_config = _BASE_CONFIG


__all__ = [
    "Trademark",
    "TrademarkSearchHit",
    "TrademarkSearchResult",
]
