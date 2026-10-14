"""Normalized records returned by Spain's OEPM CEO web service."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


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


_OepmDate = Annotated[date | None, BeforeValidator(parse_oepm_date)]


class OepmProceedingAct(BaseModel):
    """One public processing act from an OEPM file."""

    act_date: _OepmDate = None
    description: str | None = None


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
    filing_date: _OepmDate = None
    priority_number: str | None = None
    priority_date: _OepmDate = None
    publication_date: _OepmDate = None
    grant_date: _OepmDate = None
    inventors: list[str] = Field(default_factory=list)


class OepmTrademarkRecord(_OepmRecord):
    """Spanish trademark or trade-name file."""

    application_number: str | None = None
    denomination: str | None = None
    mark_type: str | None = None
    image_url: str | None = None
    filing_date: _OepmDate = None
    publication_date: _OepmDate = None
    next_renewal_date: _OepmDate = None
    nice_classes: list[str] = Field(default_factory=list)
    vienna_classes: list[str] = Field(default_factory=list)


class OepmDesignRecord(_OepmRecord):
    """Spanish industrial-design file."""

    application_number: str | None = None
    filing_date: _OepmDate = None
    publication_date: _OepmDate = None
    resolution_date: _OepmDate = None
    filing_place: str | None = None
    creators: list[str] = Field(default_factory=list)
