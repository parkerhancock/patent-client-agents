"""Normalized records returned by the Swiss IPI datadelivery API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def parse_ipi_date(value: Any) -> date | None:
    """Parse the ISO date forms used by the published IPI schemas."""
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


class IpiSearchMeta(BaseModel):
    """Pagination metadata from one IPI search result."""

    total_item_count: int | None = None
    item_count_offset: int | None = None
    item_count: int | None = None
    next_cursor: str | None = None


class _IpiRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    identifier: str
    status: str | None = None
    owner: str | None = None
    raw: dict[str, Any]


class IpiPatentRecord(_IpiRecord):
    """Swiss patent register record."""

    patent_number: str | None = None
    application_number: str | None = None
    publication_number: str | None = None
    title: str | None = None
    application_date: date | None = None
    publication_date: date | None = None
    grant_date: date | None = None
    ipc: list[str] = Field(default_factory=list)
    cpc: list[str] = Field(default_factory=list)
    inventors: list[str] = Field(default_factory=list)

    @field_validator("application_date", "publication_date", "grant_date", mode="before")
    @classmethod
    def parse_dates(cls, value: Any) -> date | None:
        return parse_ipi_date(value)


class IpiTrademarkRecord(_IpiRecord):
    """Swiss national trademark register record."""

    trademark_number: str | None = None
    application_number: str | None = None
    title: str | None = None
    word_element: str | None = None
    application_date: date | None = None
    registration_date: date | None = None
    expiry_date: date | None = None
    nice_classification: list[str] = Field(default_factory=list)

    @field_validator("application_date", "registration_date", "expiry_date", mode="before")
    @classmethod
    def parse_dates(cls, value: Any) -> date | None:
        return parse_ipi_date(value)


class IpiSpcRecord(_IpiRecord):
    """Swiss supplementary protection certificate record."""

    spc_number: str | None = None
    application_number: str | None = None
    product: str | None = None
    basic_patent_number: str | None = None
    authorisation_number: str | None = None
    application_date: date | None = None
    grant_date: date | None = None
    maximum_term_of_protection_date: date | None = None

    @field_validator(
        "application_date", "grant_date", "maximum_term_of_protection_date", mode="before"
    )
    @classmethod
    def parse_dates(cls, value: Any) -> date | None:
        return parse_ipi_date(value)


class IpiPublicationRecord(_IpiRecord):
    """Swiss patent or SPC publication notice."""

    right_type: Literal["patent", "spc"]
    publication_title: str | None = None
    publication_text: str | None = None
    published_remark: str | None = None
    reason_for_publication: str | None = None
    ip_right_number: str | None = None
    publication_date: date | None = None
    classification: list[str] = Field(default_factory=list)

    @field_validator("publication_date", mode="before")
    @classmethod
    def parse_publication_date(cls, value: Any) -> date | None:
        return parse_ipi_date(value)
