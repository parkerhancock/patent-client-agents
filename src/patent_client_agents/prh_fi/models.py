"""Pydantic v2 row models for the PRH (Finland) JSON APIs.

Schemas reverse-engineered 2026-05-18 from the three PRH React
bundles plus end-to-end probes. Shapes are versionless; every model
uses ``extra="allow"`` so a new upstream field surfaces as a
passthrough dict entry rather than a validation failure.

Two row families:

* :class:`DossierSearchRow` — used by trademark, well-known TM (TMR),
  and design search responses (identical 21-field shape across all
  three rights).
* :class:`PatentSearchRow` — patent / UM / EP-FI / SPC corpus rows.

:class:`PatentGetRecord` is the full per-application register fetch
with prosecution events, trilingual titles + abstracts, payment
timeline, and document file-history pointers.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_BASE_CONFIG: ConfigDict = ConfigDict(populate_by_name=True, extra="allow")


def _parse_iso_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Shared sub-row pieces
# ---------------------------------------------------------------------------


class Party(BaseModel):
    """One party (applicant, representative, inventor, owner).

    Two shapes appear across the surface:
    * TM/TMR/Design rows: ``{name, ordinal}``
    * Patent rows + GET: ``{name, companyName, ordinal}`` (``name`` is
      the person name; ``companyName`` is the legal entity).
    """

    name: str | None = None
    company_name: str | None = Field(default=None, alias="companyName")
    ordinal: int | None = None

    model_config = _BASE_CONFIG


class GoodsAndServicesClass(BaseModel):
    """One Nice class entry on a trademark dossier."""

    class_number: int | None = Field(default=None, alias="classNumber")
    ordinal: int | None = None

    model_config = _BASE_CONFIG


class LocarnoClass(BaseModel):
    """One Locarno class entry on a design dossier."""

    class_number: str | None = Field(default=None, alias="classNumber")
    sub_class_number: str | None = Field(default=None, alias="subClassNumber")
    ordinal: int | None = None

    model_config = _BASE_CONFIG


class DesignEmbodiment(BaseModel):
    """One design embodiment within a design dossier's ``designs`` array."""

    title: str | None = None
    title_second_lng: str | None = Field(default=None, alias="titleSecondLng")
    number: int | None = None
    dominant_view_number: int | None = Field(default=None, alias="dominantViewNumber")
    dominant_view_image_url: str | None = Field(default=None, alias="dominantViewImageUrl")
    dominant_view_small_thumbnail_url: str | None = Field(
        default=None, alias="dominantViewSmallThumbnailUrl"
    )
    dominant_view_medium_thumbnail_url: str | None = Field(
        default=None, alias="dominantViewMediumThumbnailUrl"
    )
    ordinal: int | None = None

    model_config = _BASE_CONFIG


class TitleTranslation(BaseModel):
    """One trilingual title entry (FI / SV / EN).

    Search rows ship ``title`` as a scalar string; the GET ships it
    as a single-element list of strings. We accept both.
    """

    title: str | list[str] | None = None
    language: str | None = None
    ordinal: int | None = None

    model_config = _BASE_CONFIG


class AbstractTranslation(BaseModel):
    """One translated abstract."""

    content: str | None = None
    language: str | None = None
    ordinal: int | None = None

    model_config = _BASE_CONFIG


class Classification(BaseModel):
    """One IPC or CPC classification entry on a patent search row."""

    classification: str | None = None

    model_config = _BASE_CONFIG


class PatentPublication(BaseModel):
    """One publication entry on a patent search row."""

    publication_date: date | None = Field(default=None, alias="publicationDate")
    type: str | None = None
    publication_section: str | None = Field(default=None, alias="publicationSection")
    ordinal: int | None = None

    model_config = _BASE_CONFIG

    @field_validator("publication_date", mode="before")
    @classmethod
    def _coerce_date(cls, value: Any) -> Any:
        return _parse_iso_date(value)


class PriorityClaim(BaseModel):
    """One Paris priority claim on a patent GET record."""

    office_code: str | None = Field(default=None, alias="officeCode")
    filing_date: date | None = Field(default=None, alias="filingDate")
    application_number: str | None = Field(default=None, alias="applicationNumber")
    ordinal: int | None = None

    model_config = _BASE_CONFIG

    @field_validator("filing_date", mode="before")
    @classmethod
    def _coerce_date(cls, value: Any) -> Any:
        return _parse_iso_date(value)


class Examiner(BaseModel):
    """Named examiner on a patent GET record."""

    full_name: str | None = Field(default=None, alias="fullName")

    model_config = _BASE_CONFIG


class DossierPriority(BaseModel):
    """One priority claim on a TM/design dossier row."""

    office_code: str | None = Field(default=None, alias="officeCode")
    application_date: date | None = Field(default=None, alias="applicationDate")
    application_number: str | None = Field(default=None, alias="applicationNumber")
    ordinal: int | None = None

    model_config = _BASE_CONFIG

    @field_validator("application_date", mode="before")
    @classmethod
    def _coerce_date(cls, value: Any) -> Any:
        return _parse_iso_date(value)


# ---------------------------------------------------------------------------
# Unified dossier row — TM, TMR (well-known), design (same 21-field shape)
# ---------------------------------------------------------------------------


class DossierSearchRow(BaseModel):
    """One row in the trademark, well-known-trademark, or design search.

    PRH ships an identical row shape across the three rights — what
    discriminates them is the endpoint (``/trademark``, ``/tmr``,
    ``/design``) and which optional slots populate (``locarnos`` +
    ``designs`` for designs; ``goodsAndServices`` + ``trademarkWord``
    + ``imageUrl`` for trademarks).
    """

    dossier_id: int | None = Field(default=None, alias="dossierId")
    application_number: str | None = Field(default=None, alias="applicationNumber")
    registration_number: str | None = Field(default=None, alias="registrationNumber")
    dossier_status: str | None = Field(default=None, alias="dossierStatus")
    dossier_sub_type: str | None = Field(default=None, alias="dossierSubType")
    application_date: date | None = Field(default=None, alias="applicationDate")
    registration_date: date | None = Field(default=None, alias="registrationDate")
    expiration_date: date | None = Field(default=None, alias="expirationDate")
    applicants: list[Party] = Field(default_factory=list)
    representatives: list[Party] = Field(default_factory=list)
    priorities: list[DossierPriority] = Field(default_factory=list)
    trademark_word: str | None = Field(default=None, alias="trademarkWord")
    trademark_has_image: bool | None = Field(default=None, alias="trademarkHasImage")
    goods_and_services: list[GoodsAndServicesClass] = Field(
        default_factory=list, alias="goodsAndServices"
    )
    target_group: str | None = Field(default=None, alias="targetGroup")
    locarnos: list[LocarnoClass] = Field(default_factory=list)
    designs: list[DesignEmbodiment] = Field(default_factory=list)
    image_url: str | None = Field(default=None, alias="imageUrl")
    thumbnail_url: str | None = Field(default=None, alias="thumbnailUrl")
    large_thumbnail_url: str | None = Field(default=None, alias="largeThumbnailUrl")
    ordinal: int | None = None

    model_config = _BASE_CONFIG

    @field_validator("application_date", "registration_date", "expiration_date", mode="before")
    @classmethod
    def _coerce_dates(cls, value: Any) -> Any:
        return _parse_iso_date(value)


class DossierSearchResponse(BaseModel):
    """Top-level envelope for TM, TMR, and design search responses."""

    total_results: int = Field(default=0, alias="totalResults")
    results: list[DossierSearchRow] = Field(default_factory=list)

    model_config = _BASE_CONFIG


# ---------------------------------------------------------------------------
# Patent search row + envelope
# ---------------------------------------------------------------------------


class PatentSearchRow(BaseModel):
    """One row in the PRH patent corpus search.

    Covers FI-national patents (``dossierType=PatentDossier``), utility
    models (``PatentDossierUtilityModel``), EP-FI validations
    (``PatentEurope``), and supplementary protection certificates
    (``Spc``).
    """

    application_number: str | None = Field(default=None, alias="applicationNumber")
    registration_number: str | None = Field(default=None, alias="registrationNumber")
    dossier_status: str | None = Field(default=None, alias="dossierStatus")
    dossier_type: str | None = Field(default=None, alias="dossierType")
    application_date: date | None = Field(default=None, alias="applicationDate")
    status_date: date | None = Field(default=None, alias="statusDate")
    applicants: list[Party] = Field(default_factory=list)
    owners: list[Party] = Field(default_factory=list)
    classifications: list[Classification] = Field(default_factory=list)
    titles: list[TitleTranslation] = Field(default_factory=list)
    appms: list[Any] = Field(default_factory=list)
    publications: list[PatentPublication] = Field(default_factory=list)
    ordinal: int | None = None

    model_config = _BASE_CONFIG

    @field_validator("application_date", "status_date", mode="before")
    @classmethod
    def _coerce_dates(cls, value: Any) -> Any:
        return _parse_iso_date(value)


class PatentSearchResponse(BaseModel):
    """Top-level envelope for patent search responses."""

    total_results: int = Field(default=0, alias="totalResults")
    results: list[PatentSearchRow] = Field(default_factory=list)

    model_config = _BASE_CONFIG


# ---------------------------------------------------------------------------
# Patent per-record GET
# ---------------------------------------------------------------------------


class PatentGetRecord(BaseModel):
    """Full patent register record from ``GET /patent/{appno}``.

    Carries the trilingual title + abstracts (FI/SV/EN), prosecution
    events, full file-history pointer list (``documents.document``),
    named examiner, payment timeline, and SPC authorizations. The
    ``relatedDossierType`` discriminates Paris-route national filings
    from PCT national-phase entries and EP-FI validations.
    """

    application_number: str | None = Field(default=None, alias="applicationNumber")
    application_type: str | None = Field(default=None, alias="applicationType")
    registration_number: str | None = Field(default=None, alias="registrationNumber")
    related_dossier_type: str | None = Field(default=None, alias="relatedDossierType")
    base_patent_number: str | None = Field(default=None, alias="basePatentNumber")
    t3_publication_date: date | None = Field(default=None, alias="t3PublicationDate")
    application_date: date | None = Field(default=None, alias="applicationDate")
    filing_date: date | None = Field(default=None, alias="filingDate")
    grant_date: date | None = Field(default=None, alias="grantDate")
    publication_date: date | None = Field(default=None, alias="publicationDate")
    dossier_status: str | None = Field(default=None, alias="dossierStatus")
    dossier_status_date: date | None = Field(default=None, alias="dossierStatusDate")
    filing_language: str | None = Field(default=None, alias="filingLanguage")
    patent_title: list[TitleTranslation] = Field(default_factory=list, alias="patentTitle")
    abstracts: list[AbstractTranslation] = Field(default_factory=list)
    events: list[Any] = Field(default_factory=list)
    documents: Any | None = None
    examiner: Examiner | None = None
    inventors: list[Party] = Field(default_factory=list)
    applicants: list[Party] = Field(default_factory=list)
    owners: list[Party] = Field(default_factory=list)
    representatives: list[Party] = Field(default_factory=list)
    ipc_classifications: list[str] = Field(default_factory=list, alias="ipcClassifications")
    cpc_classifications: list[str] = Field(default_factory=list, alias="cpcClassifications")
    payment_details: Any | None = Field(default=None, alias="paymentDetails")
    priority_claims: list[PriorityClaim] = Field(default_factory=list, alias="priorityClaims")
    related_dossiers: list[Any] = Field(default_factory=list, alias="relatedDossiers")
    spc_authorizations: list[Any] = Field(default_factory=list, alias="spcAuthorizations")
    image_url: str | None = Field(default=None, alias="imageUrl")

    model_config = _BASE_CONFIG

    @field_validator(
        "application_date",
        "filing_date",
        "grant_date",
        "publication_date",
        "dossier_status_date",
        "t3_publication_date",
        mode="before",
    )
    @classmethod
    def _coerce_dates(cls, value: Any) -> Any:
        return _parse_iso_date(value)


__all__ = [
    "Party",
    "GoodsAndServicesClass",
    "LocarnoClass",
    "DesignEmbodiment",
    "TitleTranslation",
    "AbstractTranslation",
    "Classification",
    "PatentPublication",
    "PriorityClaim",
    "Examiner",
    "DossierPriority",
    "DossierSearchRow",
    "DossierSearchResponse",
    "PatentSearchRow",
    "PatentSearchResponse",
    "PatentGetRecord",
]
