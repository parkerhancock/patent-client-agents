"""Normalized records returned by the New Zealand IPONZ API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from patent_client_agents.shared.models import IsoTimestampDate, parse_iso_timestamp_date

parse_iponz_date = parse_iso_timestamp_date


class _IponzRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    identifier: str
    status: str | None = None
    raw: dict[str, Any]


class IponzPatentRecord(_IponzRecord):
    """Public New Zealand patent register record."""

    patent_number: str
    international_application_number: str | None = None
    wipo_publication_number: str | None = None
    title: str | None = None
    abstract: str | None = None
    complete_filed_date: IsoTimestampDate = None
    national_phase_entry_date: IsoTimestampDate = None
    published_date: IsoTimestampDate = None
    grant_date: IsoTimestampDate = None
    expiry_date: IsoTimestampDate = None
    applicants: list[str] = Field(default_factory=list)
    inventors: list[str] = Field(default_factory=list)
    classifications: list[str] = Field(default_factory=list)


class IponzTrademarkRecord(_IponzRecord):
    """Public New Zealand trade mark register record."""

    application_number: str
    registration_number: str | None = None
    international_registration_number: str | None = None
    title: str | None = None
    application_date: IsoTimestampDate = None
    registration_date: IsoTimestampDate = None
    expiry_date: IsoTimestampDate = None
    applicants: list[str] = Field(default_factory=list)
    nice_classes: list[str] = Field(default_factory=list)
    word_marks: list[str] = Field(default_factory=list)


class IponzDesignRecord(_IponzRecord):
    """Public New Zealand design register record."""

    registration_number: str
    design_identifier: str | None = None
    title: str | None = None
    novelty_statement: str | None = None
    application_date: IsoTimestampDate = None
    registration_date: IsoTimestampDate = None
    expiry_date: IsoTimestampDate = None
    applicants: list[str] = Field(default_factory=list)
    articles: list[str] = Field(default_factory=list)


class IponzRegisterSummary(_IponzRecord):
    """One record from an IPONZ updated or registered date-range list."""

    right_type: Literal["patent", "trademark", "design"]
    event_date: IsoTimestampDate = None
