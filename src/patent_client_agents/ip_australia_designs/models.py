"""Pydantic models for the Australian Designs Search API.

Field shapes are inferred from the public description page at
``descriptions.api.gov.au/ipaustralia/design-search/``. The upstream
does not publish a Swagger spec; ``extra="allow"`` keeps parsing
forward-compatible.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from patent_client_agents.shared.models import ApiModel

_BASE_CONFIG: ConfigDict = ConfigDict(populate_by_name=True, extra="allow")


class DesignSearchHit(ApiModel):
    """Lean row from ``POST /search/quick`` on the designs API.

    Each hit carries the Australian design number plus the
    bibliographic fields IP Australia surfaces in its quick-search list
    view.
    """

    design_number: str | None = None
    application_number: str | None = None
    title: str | None = None
    status: str | None = None
    application_date: str | None = None
    registration_date: str | None = None
    locarno_classes: list[Any] = Field(default_factory=list)
    classifications: list[Any] = Field(default_factory=list)
    owners: list[Any] = Field(default_factory=list)

    model_config = _BASE_CONFIG


class DesignSearchResult(BaseModel):
    """Envelope returned by ``POST /search/quick`` on the designs API."""

    results: list[DesignSearchHit] = Field(default_factory=list)
    total: int | None = None

    model_config = _BASE_CONFIG


class Design(ApiModel):
    """Full Australian design record from ``GET /design/{ipRightIdentifier}``."""

    design_number: str | None = None
    application_number: str | None = None
    title: str | None = None
    status: str | None = None
    application_date: str | None = None
    registration_date: str | None = None
    examination_date: str | None = None
    expiry_date: str | None = None
    locarno_classes: list[Any] = Field(default_factory=list)
    classifications: list[Any] = Field(default_factory=list)
    owners: list[Any] = Field(default_factory=list)
    designers: list[Any] = Field(default_factory=list)
    representatives: list[Any] = Field(default_factory=list)
    priority_claims: list[Any] = Field(default_factory=list)

    model_config = _BASE_CONFIG


__all__ = [
    "Design",
    "DesignSearchHit",
    "DesignSearchResult",
]
