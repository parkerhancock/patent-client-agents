"""Pydantic models for the CanLII REST API.

Field names mirror the upstream JSON (camelCase). Optional fields are
``None`` where the API may omit them.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from patent_client_agents.shared.models import ApiModel

Language = Literal["en", "fr"]
"""Output language code accepted by CanLII."""


class LegislationType(StrEnum):
    STATUTE = "STATUTE"
    REGULATION = "REGULATION"
    ANNUAL_STATUTE = "ANNUAL_STATUTE"


class CaseDatabase(ApiModel):
    """A CanLII court / tribunal database (one per court)."""

    database_id: str
    jurisdiction: str
    name: str

    model_config = {"populate_by_name": True}


class CaseId(BaseModel):
    """CanLII case identifier, scoped by language."""

    en: str | None = None
    fr: str | None = None


class CaseRef(ApiModel):
    """Lightweight case reference returned by browse/citator endpoints."""

    database_id: str
    case_id: CaseId
    title: str
    citation: str

    model_config = {"populate_by_name": True}


class CaseMetadata(ApiModel):
    """Full metadata for a single case."""

    database_id: str
    case_id: str
    url: str
    title: str
    citation: str
    language: Language
    docket_number: str | None = None
    decision_date: date | None = None
    keywords: str | None = None
    concatenated_id: str | None = None

    model_config = {"populate_by_name": True}


class CaseList(BaseModel):
    """Paginated case list from caseBrowse."""

    cases: list[CaseRef]


class CitedCasesResponse(ApiModel):
    cited_cases: list[CaseRef]

    model_config = {"populate_by_name": True}


class CitingCasesResponse(ApiModel):
    citing_cases: list[CaseRef]

    model_config = {"populate_by_name": True}


class CitedLegislationRef(ApiModel):
    """A legislation reference returned by the citator."""

    database_id: str
    legislation_id: str
    title: str
    citation: str | None = None
    type: LegislationType | None = None

    model_config = {"populate_by_name": True}


class CitedLegislationsResponse(ApiModel):
    cited_legislations: list[CitedLegislationRef]

    model_config = {"populate_by_name": True}


class LegislationDatabase(ApiModel):
    """A CanLII legislation database (statutes or regulations, scoped by jurisdiction)."""

    database_id: str
    type: LegislationType
    jurisdiction: str
    name: str

    model_config = {"populate_by_name": True}


class LegislationRef(ApiModel):
    """A legislation reference returned by browse."""

    database_id: str
    legislation_id: str
    title: str
    citation: str
    type: LegislationType

    model_config = {"populate_by_name": True}


class LegislationList(BaseModel):
    legislations: list[LegislationRef]


class LegislationPart(ApiModel):
    """A part (chapter / division) of a statute or regulation."""

    part_id: str
    part_name: str

    model_config = {"populate_by_name": True}


class LegislationMetadata(ApiModel):
    """Full metadata for a single statute or regulation."""

    legislation_id: str
    url: str
    title: str
    citation: str
    type: LegislationType
    language: Language
    date_scheme: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    repealed: str | None = None
    content: list[LegislationPart] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class CaseDatabaseList(ApiModel):
    case_databases: list[CaseDatabase]

    model_config = {"populate_by_name": True}


class LegislationDatabaseList(ApiModel):
    legislation_databases: list[LegislationDatabase]

    model_config = {"populate_by_name": True}


__all__ = [
    "Language",
    "LegislationType",
    "CaseDatabase",
    "CaseDatabaseList",
    "CaseId",
    "CaseList",
    "CaseMetadata",
    "CaseRef",
    "CitedCasesResponse",
    "CitedLegislationRef",
    "CitedLegislationsResponse",
    "CitingCasesResponse",
    "LegislationDatabase",
    "LegislationDatabaseList",
    "LegislationList",
    "LegislationMetadata",
    "LegislationPart",
    "LegislationRef",
]
