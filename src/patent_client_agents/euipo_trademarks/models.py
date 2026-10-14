"""Pydantic models for the EUIPO Trademark Search API.

Field names mirror the upstream JSON (camelCase). Models use
``extra="allow"`` so the EUIPO can add new optional fields in a minor
version bump without breaking parsing — relevant because the sandbox
already runs v1.1.0 while production is on v1.0.0.

The list endpoint (``GET /trademarks``) returns
:class:`TrademarkSearchResultItem` rows — a lean projection. The detail
endpoint (``GET /trademarks/{applicationNumber}``) returns
:class:`Trademark` with ~40 fields including prosecution history.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

_BASE_CONFIG: ConfigDict = ConfigDict(populate_by_name=True, extra="allow")


class Status(StrEnum):
    """Trademark lifecycle status."""

    RECEIVED = "RECEIVED"
    UNDER_EXAMINATION = "UNDER_EXAMINATION"
    APPLICATION_PUBLISHED = "APPLICATION_PUBLISHED"
    REGISTRATION_PENDING = "REGISTRATION_PENDING"
    REGISTERED = "REGISTERED"
    WITHDRAWN = "WITHDRAWN"
    REFUSED = "REFUSED"
    OPPOSITION_PENDING = "OPPOSITION_PENDING"
    APPEALED = "APPEALED"
    CANCELLATION_PENDING = "CANCELLATION_PENDING"
    CANCELLED = "CANCELLED"
    SURRENDERED = "SURRENDERED"
    EXPIRED = "EXPIRED"
    APPEALABLE = "APPEALABLE"
    START_OF_OPPOSITION_PERIOD = "START_OF_OPPOSITION_PERIOD"
    ACCEPTANCE_PENDING = "ACCEPTANCE_PENDING"
    ACCEPTED = "ACCEPTED"
    REMOVED_FROM_REGISTER = "REMOVED_FROM_REGISTER"


class MarkFeature(StrEnum):
    WORD = "WORD"
    FIGURATIVE = "FIGURATIVE"
    SHAPE_3D = "SHAPE_3D"
    COLOUR = "COLOUR"
    SOUND = "SOUND"
    HOLOGRAM = "HOLOGRAM"
    OLFACTORY = "OLFACTORY"
    POSITION = "POSITION"
    PATTERN = "PATTERN"
    MOTION = "MOTION"
    MULTIMEDIA = "MULTIMEDIA"
    OTHER = "OTHER"


class MarkKind(StrEnum):
    INDIVIDUAL = "INDIVIDUAL"
    EU_COLLECTIVE = "EU_COLLECTIVE"
    EU_CERTIFICATION = "EU_CERTIFICATION"


class MarkBasis(StrEnum):
    EU_TRADEMARK = "EU_TRADEMARK"
    INTERNATIONAL_TRADEMARK = "INTERNATIONAL_TRADEMARK"


class Person(BaseModel):
    """Applicant or representative.

    ``name`` is documented as required but sandbox data sometimes
    returns Persons with only ``office`` + ``identifier``; we accept the
    looser shape to avoid bombing on real-world payloads.
    """

    office: str  # 'EM' (EUIPO) or 'WO' (WIPO)
    name: str | None = None
    identifier: str | None = None

    model_config = _BASE_CONFIG


class WordMarkSpecification(BaseModel):
    verbal_element: str = Field(alias="verbalElement")

    model_config = _BASE_CONFIG


class Publication(BaseModel):
    bulletin_number: str = Field(alias="bulletinNumber")
    publication_section: str = Field(alias="publicationSection")
    publication_date: date = Field(alias="publicationDate")

    model_config = _BASE_CONFIG


class GoodsAndServicesTerms(BaseModel):
    """One language's terms for a Nice class."""

    language: str
    terms: list[str]

    model_config = _BASE_CONFIG


class MultilingualText(BaseModel):
    """One language's text for a multilingual field (the spec's ``MultilingualElement``)."""

    language: str
    text: str

    model_config = _BASE_CONFIG


class GoodsAndServicesClass(BaseModel):
    """A Nice class with its multilingual goods-and-services terms."""

    class_number: int = Field(alias="classNumber")
    description: list[GoodsAndServicesTerms] = Field(default_factory=list)

    model_config = _BASE_CONFIG

    def terms_in(self, language: str) -> list[str]:
        """Return the terms for ``language`` (e.g. ``'en'``), or ``[]`` if absent."""
        for entry in self.description:
            if entry.language == language:
                return entry.terms
        return []


class TrademarkSearchResultItem(BaseModel):
    """Lean row returned by ``GET /trademarks`` (search)."""

    application_number: str = Field(alias="applicationNumber")
    status: Status
    mark_feature: MarkFeature = Field(alias="markFeature")
    nice_classes: list[int] = Field(alias="niceClasses", default_factory=list)

    applicant_reference: str | None = Field(default=None, alias="applicantReference")
    mark_kind: MarkKind | None = Field(default=None, alias="markKind")
    mark_basis: MarkBasis | None = Field(default=None, alias="markBasis")
    word_mark_specification: WordMarkSpecification | None = Field(
        default=None, alias="wordMarkSpecification"
    )
    applicants: list[Person] = Field(default_factory=list)
    representatives: list[Person] = Field(default_factory=list)
    application_date: date | None = Field(default=None, alias="applicationDate")
    registration_date: date | None = Field(default=None, alias="registrationDate")
    designation_date: date | None = Field(default=None, alias="designationDate")
    expiry_date: date | None = Field(default=None, alias="expiryDate")
    publications: list[Publication] = Field(default_factory=list)

    model_config = _BASE_CONFIG

    @property
    def is_live(self) -> bool:
        """True if the mark is in any non-terminated state."""
        return self.status not in {
            Status.WITHDRAWN,
            Status.REFUSED,
            Status.CANCELLED,
            Status.SURRENDERED,
            Status.EXPIRED,
            Status.REMOVED_FROM_REGISTER,
        }

    @property
    def is_registered(self) -> bool:
        return self.status == Status.REGISTERED


class TrademarkSearchResult(BaseModel):
    """Envelope returned by ``GET /trademarks``."""

    trademarks: list[TrademarkSearchResultItem]
    total_elements: int = Field(alias="totalElements")
    total_pages: int = Field(alias="totalPages")
    size: int
    page: int

    model_config = _BASE_CONFIG


class Trademark(TrademarkSearchResultItem):
    """Full trademark record from ``GET /trademarks/{applicationNumber}``.

    Inherits the list-view fields and adds prosecution history. We only
    type the fields callers commonly use; the spec ships ~40 fields and
    rare ones flow through via ``extra="allow"``.
    """

    application_language: str | None = Field(default=None, alias="applicationLanguage")
    second_language: str | None = Field(default=None, alias="secondLanguage")
    receipt_date: date | None = Field(default=None, alias="receiptDate")
    publication_date: date | None = Field(default=None, alias="publicationDate")
    status_date: date | None = Field(default=None, alias="statusDate")

    description: list[MultilingualText] = Field(default_factory=list)
    disclaimer: list[MultilingualText] = Field(default_factory=list)
    goods_and_services: list[GoodsAndServicesClass] = Field(
        alias="goodsAndServices", default_factory=list
    )

    opposition_period_start_date: date | None = Field(
        default=None, alias="oppositionPeriodStartDate"
    )
    opposition_period_end_date: date | None = Field(default=None, alias="oppositionPeriodEndDate")
    renewal_status: str | None = Field(default=None, alias="renewalStatus")
    fast_track_indicator: bool | None = Field(default=None, alias="fastTrackIndicator")
    trade_distinctiveness_indicator: bool | None = Field(
        default=None, alias="tradeDistinctivenessIndicator"
    )

    model_config = _BASE_CONFIG


__all__ = [
    "GoodsAndServicesClass",
    "GoodsAndServicesTerms",
    "MarkBasis",
    "MarkFeature",
    "MarkKind",
    "Person",
    "Publication",
    "Status",
    "Trademark",
    "TrademarkSearchResult",
    "TrademarkSearchResultItem",
    "WordMarkSpecification",
]
