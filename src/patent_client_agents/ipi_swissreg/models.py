"""Normalized records returned by the Swiss IPI datadelivery API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from patent_client_agents.shared.models import IsoTimestampDate, parse_iso_timestamp_date

parse_ipi_date = parse_iso_timestamp_date


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
    application_date: IsoTimestampDate = None
    publication_date: IsoTimestampDate = None
    grant_date: IsoTimestampDate = None
    ipc: list[str] = Field(default_factory=list)
    cpc: list[str] = Field(default_factory=list)
    inventors: list[str] = Field(default_factory=list)


class IpiTrademarkRecord(_IpiRecord):
    """Swiss national trademark register record."""

    trademark_number: str | None = None
    application_number: str | None = None
    title: str | None = None
    word_element: str | None = None
    application_date: IsoTimestampDate = None
    registration_date: IsoTimestampDate = None
    expiry_date: IsoTimestampDate = None
    nice_classification: list[str] = Field(default_factory=list)


class IpiSpcRecord(_IpiRecord):
    """Swiss supplementary protection certificate record."""

    spc_number: str | None = None
    application_number: str | None = None
    product: str | None = None
    basic_patent_number: str | None = None
    authorisation_number: str | None = None
    application_date: IsoTimestampDate = None
    grant_date: IsoTimestampDate = None
    maximum_term_of_protection_date: IsoTimestampDate = None


class IpiPublicationRecord(_IpiRecord):
    """Swiss patent or SPC publication notice."""

    right_type: Literal["patent", "spc"]
    publication_title: str | None = None
    publication_text: str | None = None
    published_remark: str | None = None
    reason_for_publication: str | None = None
    ip_right_number: str | None = None
    publication_date: IsoTimestampDate = None
    classification: list[str] = Field(default_factory=list)
