"""Normalized records returned by Spain's OEPM CEO web service."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def parse_oepm_date(value: Any) -> date | None:
    """Parse date strings used by the public CEO WSDL contract."""
    if value is None or isinstance(value, date):
        return value.date() if isinstance(value, datetime) else value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    for pattern in ("%Y-%m-%d", "%Y%m%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], pattern).date()
        except ValueError:
            continue
    return None


class OepmProceedingAct(BaseModel):
    """One public processing act from an OEPM file."""

    act_date: date | None = None
    description: str | None = None

    @field_validator("act_date", mode="before")
    @classmethod
    def parse_date(cls, value: Any) -> date | None:
        return parse_oepm_date(value)


class _OepmRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    identifier: str
    modality: str
    status: str | None = None
    status_code: str | None = None
    owner: str | None = None
    applicant: str | None = None
    representative: str | None = None
    proceedings: list[OepmProceedingAct] = Field(default_factory=list)
    raw: dict[str, Any]


class OepmPatentRecord(_OepmRecord):
    """Spanish patent, utility-model, or related invention file."""

    application_number: str | None = None
    publication_number: str | None = None
    epo_publication_number: str | None = None
    pct_publication_number: str | None = None
    title: str | None = None
    filing_date: date | None = None
    priority_number: str | None = None
    priority_date: date | None = None
    publication_date: date | None = None
    grant_date: date | None = None
    inventors: list[str] = Field(default_factory=list)

    @field_validator(
        "filing_date", "priority_date", "publication_date", "grant_date", mode="before"
    )
    @classmethod
    def parse_dates(cls, value: Any) -> date | None:
        return parse_oepm_date(value)


class OepmTrademarkRecord(_OepmRecord):
    """Spanish trademark or trade-name file."""

    application_number: str | None = None
    denomination: str | None = None
    mark_type: str | None = None
    image_url: str | None = None
    filing_date: date | None = None
    publication_date: date | None = None
    next_renewal_date: date | None = None
    nice_classes: list[str] = Field(default_factory=list)
    vienna_classes: list[str] = Field(default_factory=list)

    @field_validator("filing_date", "publication_date", "next_renewal_date", mode="before")
    @classmethod
    def parse_dates(cls, value: Any) -> date | None:
        return parse_oepm_date(value)


class OepmDesignRecord(_OepmRecord):
    """Spanish industrial-design file."""

    application_number: str | None = None
    filing_date: date | None = None
    publication_date: date | None = None
    resolution_date: date | None = None
    filing_place: str | None = None
    creators: list[str] = Field(default_factory=list)

    @field_validator("filing_date", "publication_date", "resolution_date", mode="before")
    @classmethod
    def parse_dates(cls, value: Any) -> date | None:
        return parse_oepm_date(value)
