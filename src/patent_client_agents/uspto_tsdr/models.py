"""Pydantic models for USPTO TSDR API responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Owner(BaseModel):
    """Trademark owner information."""

    name: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postcode: str | None = None
    entity_type: str | None = Field(default=None, alias="entityType")


class GoodsServices(BaseModel):
    """Goods and services classification."""

    class_number: int | None = Field(default=None, alias="classNumber")
    class_description: str | None = Field(default=None, alias="classDescription")
    first_use_date: str | None = Field(default=None, alias="firstUseDate")
    first_use_commerce_date: str | None = Field(default=None, alias="firstUseDateInCommerce")


class ProsecutionEvent(BaseModel):
    """A prosecution history event."""

    event_date: str | None = Field(default=None, alias="eventDate")
    event_description: str | None = Field(default=None, alias="eventDescription")
    event_code: str | None = Field(default=None, alias="eventCode")


class TrademarkStatus(BaseModel):
    """Trademark status information from TSDR."""

    serial_number: str = Field(alias="serialNumber")
    registration_number: str | None = Field(default=None, alias="registrationNumber")
    mark_text: str | None = Field(default=None, alias="markText")
    mark_type: str | None = Field(default=None, alias="markType")
    status_code: str | None = Field(default=None, alias="statusCode")
    status_description: str | None = Field(default=None, alias="statusDescription")
    status_date: str | None = Field(default=None, alias="statusDate")
    filing_date: str | None = Field(default=None, alias="filingDate")
    registration_date: str | None = Field(default=None, alias="registrationDate")
    abandonment_date: str | None = Field(default=None, alias="abandonmentDate")
    cancellation_date: str | None = Field(default=None, alias="cancellationDate")
    expiration_date: str | None = Field(default=None, alias="expirationDate")
    renewal_date: str | None = Field(default=None, alias="renewalDate")
    owner: Owner | None = None
    owners: list[Owner] = Field(default_factory=list)
    goods_services: list[GoodsServices] = Field(default_factory=list, alias="goodsServices")
    prosecution_history: list[ProsecutionEvent] = Field(
        default_factory=list, alias="prosecutionHistory"
    )
    international_registration_number: str | None = Field(
        default=None, alias="internationalRegistrationNumber"
    )

    @property
    def is_registered(self) -> bool:
        """Check if the trademark is currently registered."""
        return self.registration_number is not None and self.cancellation_date is None

    @property
    def is_live(self) -> bool:
        """Check if the trademark is live (not abandoned or cancelled)."""
        return self.abandonment_date is None and self.cancellation_date is None


class TsdrDocument(BaseModel):
    """A document in the trademark prosecution file."""

    doc_id: str = Field(alias="docId")
    doc_type: str | None = Field(default=None, alias="docType")
    doc_category: str | None = Field(default=None, alias="docCategory")
    doc_date: str | None = Field(default=None, alias="docDate")
    description: str | None = None
    page_count: int | None = Field(default=None, alias="pageCount")
    mail_date: str | None = Field(default=None, alias="mailDate")


class LastUpdateInfo(BaseModel):
    """Last update information for a trademark case."""

    serial_number: str = Field(alias="serialNumber")
    last_update_date: str | None = Field(default=None, alias="lastUpdateDate")
    last_update_time: str | None = Field(default=None, alias="lastUpdateTime")


class MultiCaseStatus(BaseModel):
    """Status information for multiple cases."""

    cases: list[TrademarkStatus] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)


__all__ = [
    "Owner",
    "GoodsServices",
    "ProsecutionEvent",
    "TrademarkStatus",
    "TsdrDocument",
    "LastUpdateInfo",
    "MultiCaseStatus",
]
