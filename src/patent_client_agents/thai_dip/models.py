"""Normalized records from Thailand's DIP Data Exchange catalogue."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


def parse_dip_date(value: Any) -> date | None:
    """Parse the date formats documented in the DIP field catalogue."""
    if value is None or isinstance(value, date):
        return value.date() if isinstance(value, datetime) else value
    if not isinstance(value, str):
        return None
    text = value.strip().split("T", 1)[0].split(" ", 1)[0]
    for pattern in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


class _ThaiDipRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    identifier: str
    raw: dict[str, Any]


class ThaiDipPatentRecord(_ThaiDipRecord):
    """Thai invention patent, design patent, or petty-patent record."""

    right_type: str
    application_number: str | None = None
    publication_number: str | None = None
    patent_number: str | None = None
    title: str | None = None
    status: str | None = None
    filing_date: date | None = None
    publication_date: date | None = None
    grant_date: date | None = None
    expiry_date: date | None = None
    applicant: str | None = None
    inventor: str | None = None
    agent: str | None = None
    ipc: str | None = None
    abstract: str | None = None

    @field_validator("filing_date", "publication_date", "grant_date", "expiry_date", mode="before")
    @classmethod
    def parse_dates(cls, value: Any) -> date | None:
        return parse_dip_date(value)


class ThaiDipTrademarkRecord(_ThaiDipRecord):
    """Thai national trademark record."""

    application_number: str | None = None
    registration_number: str | None = None
    mark_name: str | None = None
    status: str | None = None
    application_date: date | None = None
    registration_date: date | None = None
    publication_date: date | None = None
    expiry_date: date | None = None
    owner: str | None = None
    nice_class: str | None = None
    goods: str | None = None

    @field_validator(
        "application_date", "registration_date", "publication_date", "expiry_date", mode="before"
    )
    @classmethod
    def parse_dates(cls, value: Any) -> date | None:
        return parse_dip_date(value)


class ThaiDipCopyrightRecord(_ThaiDipRecord):
    """Thai voluntary copyright notification record."""

    request_number: str | None = None
    registration_number: str | None = None
    work_name: str | None = None
    category: str | None = None
    work_type: str | None = None
    submit_date: date | None = None
    owner: str | None = None
    creator: str | None = None
    description: str | None = None

    @field_validator("submit_date", mode="before")
    @classmethod
    def parse_submit_date(cls, value: Any) -> date | None:
        return parse_dip_date(value)


class ThaiDipSongRecord(_ThaiDipRecord):
    """Thai music-copyright service record."""

    song_name: str | None = None
    album_name: str | None = None
    lyric_author: str | None = None
    composer: str | None = None
    song_type: str | None = None
    license_owner: str | None = None
    license_end_date: date | None = None

    @field_validator("license_end_date", mode="before")
    @classmethod
    def parse_license_end_date(cls, value: Any) -> date | None:
        return parse_dip_date(value)


class ThaiDipGiRecord(_ThaiDipRecord):
    """Thai geographical-indication record."""

    request_number: str | None = None
    application_number: str | None = None
    name: str | None = None
    product: str | None = None
    category: str | None = None
    product_type: str | None = None
    province: str | None = None
    region: str | None = None
    application_date: date | None = None
    publication_date: date | None = None

    @field_validator("application_date", "publication_date", mode="before")
    @classmethod
    def parse_dates(cls, value: Any) -> date | None:
        return parse_dip_date(value)
