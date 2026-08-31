"""Models for the Canadian Federal Court public Court Files service."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

CourtDivision = Literal["t", "a", "b"]
StatusAssessment = Literal["likely_pending", "likely_closed", "unknown"]

_MICROSOFT_DATE_RE = re.compile(r"^/Date\((?P<millis>-?\d+)(?:[+-]\d{4})?\)/$")


def parse_court_date(value: object) -> date | None:
    """Parse the Court's Microsoft-JSON or ISO date representation."""
    if value in {None, ""}:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        match = _MICROSOFT_DATE_RE.match(value)
        if match:
            millis = int(match.group("millis"))
            return datetime.fromtimestamp(millis / 1000, tz=UTC).date()
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    raise ValueError(f"Unsupported court date value: {value!r}")


class FederalCourtCase(BaseModel):
    """One Federal Court or Federal Court of Appeal case-file search hit."""

    court_number: str = Field(alias="COURT_NO")
    court_sequence: str | None = Field(default=None, alias="COURT_SEQ")
    style_of_cause: str = Field(alias="STYLE_OF_CAUSE")
    nature_code: str | None = Field(default=None, alias="NATURE_CD")
    nature_en: str | None = Field(default=None, alias="ENGLISH_NATURE_DESC")
    nature_fr: str | None = Field(default=None, alias="FRENCH_NATURE_DESC")
    division: str = Field(alias="DIVISION")
    filed_date: date | None = Field(default=None, alias="FILE_DT")
    office_code: str | None = Field(default=None, alias="OFF_CD")
    city_en: str | None = Field(default=None, alias="ENGLISH_CITY_NAME")
    city_fr: str | None = Field(default=None, alias="FRENCH_CITY_NAME")
    proceeding_type_en: str | None = Field(default=None, alias="ENGLISH_PROCEEDING_TYPE")
    proceeding_type_fr: str | None = Field(default=None, alias="FRENCH_PROCEEDING_TYPE")
    proceeding_class_en: str | None = Field(default=None, alias="ENGLISH_PROCEEDING_CLASS")
    proceeding_class_fr: str | None = Field(default=None, alias="FRENCH_PROCEEDING_CLASS")
    language_code: str | None = Field(default=None, alias="LANG_CD")
    language_en: str | None = Field(default=None, alias="ENGLISH_LANGUAGE_NAME")
    language_fr: str | None = Field(default=None, alias="FRENCH_LANGUAGE_NAME")
    parties: list[str] = Field(default_factory=list, alias="Party")

    model_config = {"populate_by_name": True}

    @field_validator("filed_date", mode="before")
    @classmethod
    def _parse_filed_date(cls, value: object) -> date | None:
        return parse_court_date(value)

    @property
    def is_patent_case(self) -> bool:
        description = f"{self.nature_en or ''} {self.nature_fr or ''}".lower()
        return "patent" in description or "brevet" in description


class FederalCourtParty(BaseModel):
    """Party and public counsel information for a court file."""

    name: str = Field(alias="PARTY_NAME")
    solicitor_firm: str | None = Field(default=None, alias="SOLCTR_FIRM")
    solicitor_contact: str | None = Field(default=None, alias="SOLCTR_CONTACT")

    model_config = {"populate_by_name": True}


class FederalCourtIntellectualProperty(BaseModel):
    """IP name or registration/application number associated with a court file."""

    title: str | None = Field(default=None, alias="INT_PROPERTY_TITLE")
    number: str | None = Field(default=None, alias="INT_PROPERTY_NUMBER")

    model_config = {"populate_by_name": True}

    @field_validator("number", mode="before")
    @classmethod
    def _normalize_number(cls, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)


class FederalCourtRelatedCase(BaseModel):
    """Related Federal Court file returned by the Registry."""

    court_number: str = Field(alias="RELATED_COURT_NO")
    style_of_cause: str | None = Field(default=None, alias="STYLE_OF_CAUSE")
    nature_en: str | None = Field(default=None, alias="ENGLISH_NATURE_DESC")
    nature_fr: str | None = Field(default=None, alias="FRENCH_NATURE_DESC")

    model_config = {"populate_by_name": True}


class FederalCourtDocketEntry(BaseModel):
    """One recorded entry from a Federal Court case history."""

    court_number: str = Field(alias="COURT_NO")
    style_of_cause: str | None = Field(default=None, alias="STYLE_OF_CAUSE")
    filing_date: date | None = Field(default=None, alias="FILING_DATE")
    nature_code: str | None = Field(default=None, alias="NATURE_CD")
    nature_en: str | None = Field(default=None, alias="ENGLISH_NATURE_DESC")
    track_en: str | None = Field(default=None, alias="ENGLISH_TRACK_NAME")
    office_en: str | None = Field(default=None, alias="ENGLISH_OFFICE_NAME")
    document_number: int | None = Field(default=None, alias="DOCNO")
    entry_number: int = Field(alias="RE_NO")
    document_id: str | None = Field(default=None, alias="FOREMOST_NUMBER")
    summary: str = Field(alias="RECORDED_ENTRY")
    document_date: date | None = Field(default=None, alias="DOC_DT")
    registry_notes: str | None = Field(default=None, alias="REGISTRY_NOTES_EXTERNAL")
    command_phrase_en: str | None = Field(default=None, alias="COMMAND_PHRASE_EN")
    command_phrase_fr: str | None = Field(default=None, alias="COMMAND_PHRASE_FR")
    can_download: bool = Field(default=False, alias="CAN_PUBLISH_DOCUMENT")
    is_confidential: bool = Field(default=False, alias="IS_CONFIDENTIAL")
    download_url: str | None = None

    model_config = {"populate_by_name": True}

    @field_validator("filing_date", "document_date", mode="before")
    @classmethod
    def _parse_dates(cls, value: object) -> date | None:
        return parse_court_date(value)

    @field_validator("can_download", mode="before")
    @classmethod
    def _parse_download_flag(cls, value: object) -> bool:
        return value == "Y" or value is True

    @field_validator("is_confidential", mode="before")
    @classmethod
    def _parse_confidential_flag(cls, value: object) -> bool:
        return value == "Y" or value is True


class DocketStatus(BaseModel):
    """A deliberately conservative, non-authoritative docket-status assessment."""

    assessment: StatusAssessment
    basis: str
    inferred: bool = True


class FederalCourtCaseSearchResponse(BaseModel):
    query: str
    upstream_count: int
    filtered_count: int
    cases: list[FederalCourtCase]


class FederalCourtCaseRecord(BaseModel):
    case: FederalCourtCase
    parties: list[FederalCourtParty] = Field(default_factory=list)
    intellectual_property: list[FederalCourtIntellectualProperty] = Field(default_factory=list)
    related_cases: list[FederalCourtRelatedCase] = Field(default_factory=list)


class FederalCourtDocketResponse(BaseModel):
    court_number: str
    total_count: int
    status: DocketStatus
    entries: list[FederalCourtDocketEntry]


__all__ = [
    "CourtDivision",
    "DocketStatus",
    "FederalCourtCase",
    "FederalCourtCaseRecord",
    "FederalCourtCaseSearchResponse",
    "FederalCourtDocketEntry",
    "FederalCourtDocketResponse",
    "FederalCourtIntellectualProperty",
    "FederalCourtParty",
    "FederalCourtRelatedCase",
    "StatusAssessment",
    "parse_court_date",
]
