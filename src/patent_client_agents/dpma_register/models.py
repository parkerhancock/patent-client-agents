"""Normalized DPMAconnectPlus register records.

The public DPMA documentation does not include authenticated response samples.
These permissive models therefore keep the normalized XML in ``raw`` while
exposing a small stable field set.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from patent_client_agents.shared.models import lenient_date

parse_dpma_date = lenient_date("%Y-%m-%d", "%Y%m%d")
_DpmaDate = Annotated[date | None, BeforeValidator(parse_dpma_date)]


class _Record(BaseModel):
    model_config = ConfigDict(extra="allow")

    identifier: str
    application_number: str | None = None
    registration_number: str | None = None
    status: str | None = None
    application_date: _DpmaDate = None
    registration_date: _DpmaDate = None
    owner: str | None = None
    raw: dict[str, Any]


class PatentUtilityRecord(_Record):
    """German patent or utility-model register record."""

    publication_number: str | None = None
    publication_date: _DpmaDate = None
    title: str | None = None
    classification: str | None = None
    right_type: str | None = None
    inventors: list[str] = Field(default_factory=list)


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
