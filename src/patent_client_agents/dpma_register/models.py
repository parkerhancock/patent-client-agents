"""Normalized DPMAconnectPlus register records.

The public DPMA documentation does not include authenticated response samples.
These permissive models therefore keep the normalized XML in ``raw`` while
exposing a small stable field set.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def parse_dpma_date(value: Any) -> date | None:
    if value is None or isinstance(value, date):
        return value.date() if isinstance(value, datetime) else value
    if not isinstance(value, str):
        return None
    value = value.strip()
    for pattern in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue
    return None


class _Record(BaseModel):
    model_config = ConfigDict(extra="allow")

    identifier: str
    application_number: str | None = None
    registration_number: str | None = None
    status: str | None = None
    application_date: date | None = None
    registration_date: date | None = None
    owner: str | None = None
    raw: dict[str, Any]

    @field_validator("application_date", "registration_date", mode="before")
    @classmethod
    def parse_dates(cls, value: Any) -> date | None:
        return parse_dpma_date(value)


class PatentUtilityRecord(_Record):
    """German patent or utility-model register record."""

    publication_number: str | None = None
    publication_date: date | None = None
    title: str | None = None
    classification: str | None = None
    right_type: str | None = None
    inventors: list[str] = Field(default_factory=list)

    @field_validator("publication_date", mode="before")
    @classmethod
    def parse_publication_date(cls, value: Any) -> date | None:
        return parse_dpma_date(value)


class TrademarkRecord(_Record):
    """German national trademark register record."""

    mark_text: str | None = None
    nice_classification: str | None = None
    vienna_classification: str | None = None


class DesignRecord(_Record):
    """German national design register record."""

    design_number: str | None = None
    product_indication: str | None = None
    locarno_classification: str | None = None
