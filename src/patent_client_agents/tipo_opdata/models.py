"""Pydantic models for the Australian Patent Search API.

The public description page at ``descriptions.api.gov.au`` documents the
endpoint paths but not the response schema; field shapes here are
inferred from the symmetric trade-marks / designs surface and from the
AusPat UI at ``pericles.ipaustralia.gov.au/ols/auspat/quickSearch.do``.

``extra="allow"`` keeps parsing forward-compatible with fields the
upstream may add — important because IP Australia ships incremental
schema changes without bumping the API version.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_BASE_CONFIG: ConfigDict = ConfigDict(populate_by_name=True, extra="allow")


class PatentSearchHit(BaseModel):
    """Lean row from the Australian Patent Search quick-search response.

    Each hit carries the Australian patent / application number plus the
    bibliographic fields IP Australia surfaces in its quick-search list
    view. Additional fields flow through via ``extra="allow"``.
    """

    application_number: str | None = Field(default=None, alias="applicationNumber")
    patent_number: str | None = Field(default=None, alias="patentNumber")
    title: str | None = None
    status: str | None = None
    application_date: str | None = Field(default=None, alias="applicationDate")
    grant_date: str | None = Field(default=None, alias="grantDate")
    applicants: list[Any] = Field(default_factory=list)
    inventors: list[Any] = Field(default_factory=list)
    ipc_classifications: list[Any] = Field(default_factory=list, alias="ipcClassifications")

    model_config = _BASE_CONFIG


class PatentSearchResult(BaseModel):
    """Envelope returned by ``POST /search/quick`` on the patents API."""

    results: list[PatentSearchHit] = Field(default_factory=list)
    total: int | None = None

    model_config = _BASE_CONFIG


class Patent(BaseModel):
    """Full Australian patent record from ``GET /patent/{ipRightIdentifier}``.

    The Australian Patent Search API publishes "all publicly available
    information" for the patent; we surface the bibliographic + status
    fields and let everything else flow through ``extra="allow"``.
    """

    application_number: str | None = Field(default=None, alias="applicationNumber")
    patent_number: str | None = Field(default=None, alias="patentNumber")
    title: str | None = None
    abstract: str | None = None
    status: str | None = None
    application_date: str | None = Field(default=None, alias="applicationDate")
    grant_date: str | None = Field(default=None, alias="grantDate")
    publication_date: str | None = Field(default=None, alias="publicationDate")
    applicants: list[Any] = Field(default_factory=list)
    inventors: list[Any] = Field(default_factory=list)
    ipc_classifications: list[Any] = Field(default_factory=list, alias="ipcClassifications")
    priority_claims: list[Any] = Field(default_factory=list, alias="priorityClaims")

    model_config = _BASE_CONFIG


__all__ = [
    "Patent",
    "PatentSearchHit",
    "PatentSearchResult",
]
