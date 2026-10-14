"""Pydantic models for the EUIPO Design (RCD) Search API.

Field names mirror the upstream JSON (camelCase). Models use
``extra="allow"`` so EUIPO can add new optional fields without breaking
parsing. The list endpoint returns :class:`DesignSearchResultItem`; the
detail endpoint returns the richer :class:`Design`.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from patent_client_agents.shared.models import ApiModel

_BASE_CONFIG: ConfigDict = ConfigDict(populate_by_name=True, extra="allow")


class Status(StrEnum):
    """RCD lifecycle status."""

    RECEIVED = "RECEIVED"
    UNDER_EXAMINATION = "UNDER_EXAMINATION"
    REGISTRATION_PENDING = "REGISTRATION_PENDING"
    REGISTERED = "REGISTERED"
    REGISTERED_AND_FULLY_PUBLISHED = "REGISTERED_AND_FULLY_PUBLISHED"
    REGISTERED_AND_SUBJECT_TO_DEFERMENT = "REGISTERED_AND_SUBJECT_TO_DEFERMENT"
    LACK_OF_EFFECTS = "LACK_OF_EFFECTS"
    SURRENDERED = "SURRENDERED"
    INVALIDITY_PROCEDURE_PENDING = "INVALIDITY_PROCEDURE_PENDING"
    DESIGN_DECLARED_INVALID = "DESIGN_DECLARED_INVALID"
    EXPIRED = "EXPIRED"
    APPEALED = "APPEALED"
    APPEALABLE = "APPEALABLE"
    WITHDRAWN = "WITHDRAWN"
    REFUSED = "REFUSED"
    SPLIT = "SPLIT"


class Person(BaseModel):
    """Applicant or representative.

    ``name`` is documented as required but sandbox data sometimes
    returns Persons with only ``office`` + ``identifier``; we accept the
    looser shape to avoid bombing on real-world payloads.
    """

    office: str  # 'EM' or 'WO'
    name: str | None = None
    identifier: str | None = None

    model_config = _BASE_CONFIG


class Designer(BaseModel):
    identifier: str
    name: str | None = None

    model_config = _BASE_CONFIG


class ProductIndicationTerms(BaseModel):
    """Product description terms for one language."""

    language: str
    terms: list[str]

    model_config = _BASE_CONFIG


class View(ApiModel):
    """One angle of a design representation (e.g. front, side, top)."""

    order: int
    image_format: str

    model_config = _BASE_CONFIG


class Model3D(ApiModel):
    """3D model attached to a design."""

    model_format: str

    model_config = _BASE_CONFIG


class Publication(ApiModel):
    bulletin_number: str
    publication_section: str
    publication_date: date

    model_config = _BASE_CONFIG


class DesignSearchResultItem(ApiModel):
    """Lean row returned by ``GET /designs`` (search)."""

    design_number: str
    application_date: date
    status: Status
    applicants: list[Person]

    application_number: str | None = None
    applicant_reference: str | None = None
    registration_date: date | None = None
    expiry_date: date | None = None
    locarno_classes: list[str] = Field(default_factory=list)
    representatives: list[Person] = Field(default_factory=list)

    model_config = _BASE_CONFIG

    @property
    def is_live(self) -> bool:
        """True if the design is in any non-terminated state."""
        return self.status not in {
            Status.WITHDRAWN,
            Status.REFUSED,
            Status.LACK_OF_EFFECTS,
            Status.SURRENDERED,
            Status.DESIGN_DECLARED_INVALID,
            Status.EXPIRED,
        }

    @property
    def is_registered(self) -> bool:
        return self.status in {
            Status.REGISTERED,
            Status.REGISTERED_AND_FULLY_PUBLISHED,
            Status.REGISTERED_AND_SUBJECT_TO_DEFERMENT,
        }


class DesignSearchResult(ApiModel):
    """Envelope returned by ``GET /designs``."""

    designs: list[DesignSearchResultItem]
    total_elements: int
    total_pages: int
    size: int
    page: int

    model_config = _BASE_CONFIG


class Design(DesignSearchResultItem):
    """Full design record from ``GET /designs/{designNumber}``.

    Inherits the list-view fields and adds prosecution history + media
    metadata. Rare fields flow through via ``extra="allow"``.
    """

    application_language: str | None = None
    second_language: str | None = None
    status_date: date | None = None
    effective_date: date | None = None
    publication_deferment_indicator: bool | None = None
    deferment_expiration_date: date | None = None
    renewal_status: str | None = None

    verbal_element: str | None = None
    product_indications: list[ProductIndicationTerms] = Field(default_factory=list)

    views: list[View] = Field(default_factory=list)
    model: Model3D | None = None
    publications: list[Publication] = Field(default_factory=list)
    designers: list[Designer] = Field(default_factory=list)

    model_config = _BASE_CONFIG

    def product_terms_in(self, language: str) -> list[str]:
        """Return the product terms for ``language`` (e.g. ``'en'``), or ``[]``."""
        for entry in self.product_indications:
            if entry.language == language:
                return entry.terms
        return []


__all__ = [
    "Design",
    "DesignSearchResult",
    "DesignSearchResultItem",
    "Designer",
    "Model3D",
    "Person",
    "ProductIndicationTerms",
    "Publication",
    "Status",
    "View",
]
