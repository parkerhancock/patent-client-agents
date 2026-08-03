"""Normalized records returned by the New Zealand IPONZ API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def parse_iponz_date(value: Any) -> date | None:
    """Parse dates from the published IPONZ XML schemas."""
    if value is None or isinstance(value, date):
        return value.date() if isinstance(value, datetime) else value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(text, "%Y%m%d").date()
        except ValueError:
            return None


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
    complete_filed_date: date | None = None
    national_phase_entry_date: date | None = None
    published_date: date | None = None
    grant_date: date | None = None
    expiry_date: date | None = None
    applicants: list[str] = Field(default_factory=list)
    inventors: list[str] = Field(default_factory=list)
    classifications: list[str] = Field(default_factory=list)

    @field_validator(
        "complete_filed_date",
        "national_phase_entry_date",
        "published_date",
        "grant_date",
        "expiry_date",
        mode="before",
    )
    @classmethod
    def parse_dates(cls, value: Any) -> date | None:
        return parse_iponz_date(value)


class IponzTrademarkRecord(_IponzRecord):
    """Public New Zealand trade mark register record."""

    application_number: str
    registration_number: str | None = None
    international_registration_number: str | None = None
    title: str | None = None
    application_date: date | None = None
    registration_date: date | None = None
    expiry_date: date | None = None
    applicants: list[str] = Field(default_factory=list)
    nice_classes: list[str] = Field(default_factory=list)
    word_marks: list[str] = Field(default_factory=list)

    @field_validator("application_date", "registration_date", "expiry_date", mode="before")
    @classmethod
    def parse_dates(cls, value: Any) -> date | None:
        return parse_iponz_date(value)


class IponzDesignRecord(_IponzRecord):
    """Public New Zealand design register record."""

    registration_number: str
    design_identifier: str | None = None
    title: str | None = None
    novelty_statement: str | None = None
    application_date: date | None = None
    registration_date: date | None = None
    expiry_date: date | None = None
    applicants: list[str] = Field(default_factory=list)
    articles: list[str] = Field(default_factory=list)

    @field_validator("application_date", "registration_date", "expiry_date", mode="before")
    @classmethod
    def parse_dates(cls, value: Any) -> date | None:
        return parse_iponz_date(value)


class IponzRegisterSummary(_IponzRecord):
    """One record from an IPONZ updated or registered date-range list."""

    right_type: Literal["patent", "trademark", "design"]
    event_date: date | None = None

    @field_validator("event_date", mode="before")
    @classmethod
    def parse_event_date(cls, value: Any) -> date | None:
        return parse_iponz_date(value)
