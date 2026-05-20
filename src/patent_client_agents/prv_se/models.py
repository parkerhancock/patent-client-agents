"""Pydantic v2 row models for the PRV (Sweden) JSON APIs.

Schemas are reverse-engineered from the ``search.prv.se`` React bundle
plus end-to-end probes of the three host APIs (2026-05-18). The shapes
are versionless — every model uses ``extra="allow"`` so a new
upstream field surfaces as an unmodeled dict entry rather than a
validation failure.

Dates arrive as ISO ``YYYY-MM-DD`` strings; empty strings and other
non-parseable inputs deserialize to ``None`` so partial records still
validate.
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
    """One party (applicant, inventor, representative).

    Shape differs slightly between hosts: patents return
    ``{"name", "address"}`` dicts; designs use the same shape; the
    patent-get response squashes representatives to plain strings — we
    accept both via :class:`PartyOrString`.
    """

    name: str | None = None
    address: str | None = None

    model_config = _BASE_CONFIG


class PublicationStatus(BaseModel):
    """Status block on patent-search rows.

    Carries the numeric ``status`` code plus multilingual display-text
    slots. The slots are often ``null`` on freshly-filed applications;
    the patent-get response populates them.
    """

    status: str | None = None
    status_text: str | None = Field(default=None, alias="statusText")
    status_display_text_en: str | None = Field(default=None, alias="statusDisplayTextEn")
    status_display_text_sv: str | None = Field(default=None, alias="statusDisplayTextSv")
    status_sub_text: str | None = Field(default=None, alias="statusSubText")
    status_display_sub_text_en: str | None = Field(default=None, alias="statusDisplaySubTextEn")
    status_display_sub_text_sv: str | None = Field(default=None, alias="statusDisplaySubTextSv")

    model_config = _BASE_CONFIG


class Publication(BaseModel):
    """One publication on a patent-get record."""

    title: str | None = None
    url: str | None = None

    model_config = _BASE_CONFIG


class RegistryEntry(BaseModel):
    """One register timeline entry on a patent-get record."""

    entry_date: date | None = Field(default=None, alias="date")
    event: str | None = None

    model_config = _BASE_CONFIG

    @field_validator("entry_date", mode="before")
    @classmethod
    def _coerce_date(cls, value: Any) -> Any:
        return _parse_iso_date(value)


class GazetteAnnouncement(BaseModel):
    """One gazette announcement on a patent-get record."""

    issue: str | None = None
    type: str | None = None
    text: str | None = None
    announcement_date: date | None = Field(default=None, alias="announcementDate")

    model_config = _BASE_CONFIG

    @field_validator("announcement_date", mode="before")
    @classmethod
    def _coerce_date(cls, value: Any) -> Any:
        return _parse_iso_date(value)


class Drawing(BaseModel):
    """First-drawing block on a patent-get record.

    Carries the base64-encoded image bytes in ``data``. MCP lean
    projection drops ``data`` to keep the response under context
    budget; the metadata (application number, page number) is kept.
    """

    application_number: str | None = Field(default=None, alias="applicationNumber")
    page_number: int | None = Field(default=None, alias="pageNumber")
    data: str | None = None

    model_config = _BASE_CONFIG


# ---------------------------------------------------------------------------
# Patent search row + envelope
# ---------------------------------------------------------------------------


class PatentSearchRow(BaseModel):
    """One row in the patent simple-search response.

    Returned by ``POST patents-search-api.prv.se/searchpatent/patentsimplesearch/``.
    The ``status`` block carries the numeric status code; multilingual
    display text resolves on the patent-get endpoint.
    """

    id_patent: int | None = Field(default=None, alias="idPatent")
    application_number_formatted: str | None = Field(
        default=None, alias="applicationNumberFormatted"
    )
    application_type: str | None = Field(default=None, alias="applicationType")
    title: str | None = None
    filing_date: date | None = Field(default=None, alias="filingDate")
    publication_date: date | None = Field(default=None, alias="publicationDate")
    grant_date: date | None = Field(default=None, alias="grantDate")
    publication_number: str | None = Field(default=None, alias="publicationNumber")
    reference: str | None = None
    applicants: list[Party] = Field(default_factory=list)
    inventors: list[Party] = Field(default_factory=list)
    representatives: list[Party] = Field(default_factory=list)
    cpc_classes: list[str] = Field(default_factory=list, alias="cpcClasses")
    ipc_classes: list[str] = Field(default_factory=list, alias="ipcClasses")
    dpk_classes: list[str] = Field(default_factory=list, alias="dpkClasses")
    status: PublicationStatus | None = None

    model_config = _BASE_CONFIG

    @field_validator("filing_date", "publication_date", "grant_date", mode="before")
    @classmethod
    def _coerce_dates(cls, value: Any) -> Any:
        return _parse_iso_date(value)


class PatentSearchResponse(BaseModel):
    """Top-level envelope for patent simple-search responses."""

    total_hits: int = Field(default=0, alias="totalHits")
    total_pages: int = Field(default=0, alias="totalPages")
    hits: int = 0
    page: int = 0
    search_patent_dtos: list[PatentSearchRow] = Field(
        default_factory=list, alias="searchPatentDTOS"
    )

    model_config = _BASE_CONFIG


# ---------------------------------------------------------------------------
# Patent get record (api.prv.se per-record)
# ---------------------------------------------------------------------------


class PatentGetRecord(BaseModel):
    """Full patent record from ``GET api.prv.se/patents/applications/{n}``.

    Carries the resolved status text (multilingual), prosecution
    timeline (``registry_entries_*``), and the first-drawing image (in
    base64, lean projection drops the image bytes).

    The ``applicants`` / ``inventors`` / ``representatives`` fields are
    flat strings on this endpoint (the search endpoint returns dicts).
    """

    application_number: str | None = Field(default=None, alias="applicationNumber")
    application_number_formatted: str | None = Field(
        default=None, alias="applicationNumberFormatted"
    )
    application_type: str | None = Field(default=None, alias="applicationType")
    status: str | None = None
    status_text: str | None = Field(default=None, alias="statusText")
    status_sub_text: str | None = Field(default=None, alias="statusSubText")
    status_display_text_sv: str | None = Field(default=None, alias="statusDisplayTextSv")
    status_display_text_en: str | None = Field(default=None, alias="statusDisplayTextEn")
    status_display_sub_text_sv: str | None = Field(default=None, alias="statusDisplaySubTextSv")
    status_display_sub_text_en: str | None = Field(default=None, alias="statusDisplaySubTextEn")
    info_sv: str | None = Field(default=None, alias="infoSv")
    info_en: str | None = Field(default=None, alias="infoEn")
    filing_date: date | None = Field(default=None, alias="filingDate")
    available_to_the_public_date: date | None = Field(
        default=None, alias="availableToThePublicDate"
    )
    title: str | None = None
    reference: str | None = None
    applicants_short_format: str | None = Field(default=None, alias="applicantsShortFormat")
    applicants: list[str] = Field(default_factory=list)
    inventors: list[str] = Field(default_factory=list)
    representatives: list[str] = Field(default_factory=list)
    gazette_announcements_sv: list[GazetteAnnouncement] = Field(
        default_factory=list, alias="gazetteAnnouncementsSv"
    )
    gazette_announcements_en: list[GazetteAnnouncement] = Field(
        default_factory=list, alias="gazetteAnnouncementsEn"
    )
    electronic_announcements_sv: list[GazetteAnnouncement] = Field(
        default_factory=list, alias="electronicAnnouncementsSv"
    )
    electronic_announcements_en: list[GazetteAnnouncement] = Field(
        default_factory=list, alias="electronicAnnouncementsEn"
    )
    registry_entries_sv: list[RegistryEntry] = Field(
        default_factory=list, alias="registryEntriesSv"
    )
    registry_entries_en: list[RegistryEntry] = Field(
        default_factory=list, alias="registryEntriesEn"
    )
    mo_deposit: str | None = Field(default=None, alias="moDeposit")
    source: str | None = None
    updated: date | None = None
    md5: str | None = None
    next_payment_date: date | None = Field(default=None, alias="nextPaymentDate")
    increesed_fee: bool | None = Field(default=None, alias="IncreesedFee")
    first_drawing: Drawing | None = Field(default=None, alias="firstDrawing")
    number_of_drawing_pages: int | None = Field(default=None, alias="numberOfDrawingPages")
    publications: list[Publication] = Field(default_factory=list)

    model_config = _BASE_CONFIG

    @field_validator(
        "filing_date",
        "available_to_the_public_date",
        "updated",
        "next_payment_date",
        mode="before",
    )
    @classmethod
    def _coerce_dates(cls, value: Any) -> Any:
        return _parse_iso_date(value)


# ---------------------------------------------------------------------------
# Trademark search row + envelope
# ---------------------------------------------------------------------------


class TrademarkSearchRow(BaseModel):
    """One row in the trademark simple-search response.

    Returned by ``POST dv-search-api.prv.se/searchtrademark/tmsimplesearch/``.
    ``dossier_type_*`` discriminates national filings ("National
    trademark") from Madrid IRs designating SE.
    """

    id_trademark: int | None = Field(default=None, alias="idTrademark")
    application_number: str | None = Field(default=None, alias="applicationNumber")
    registration_number: str | None = Field(default=None, alias="registrationNumber")
    mark_specification: str | None = Field(default=None, alias="markSpecification")
    mark_feature_en: str | None = Field(default=None, alias="markFeatureEn")
    mark_feature_sv: str | None = Field(default=None, alias="markFeatureSv")
    dossier_type_en: str | None = Field(default=None, alias="dossierTypeEn")
    dossier_type_sv: str | None = Field(default=None, alias="dossierTypeSv")
    status_en: str | None = Field(default=None, alias="statusEn")
    status_sv: str | None = Field(default=None, alias="statusSv")
    filing_date: date | None = Field(default=None, alias="filingDate")
    expiry_date: date | None = Field(default=None, alias="expiryDate")
    classes: list[str] = Field(default_factory=list)
    applicants: list[Party] = Field(default_factory=list)
    representatives: list[str | Party] = Field(default_factory=list)

    model_config = _BASE_CONFIG

    @field_validator("filing_date", "expiry_date", mode="before")
    @classmethod
    def _coerce_dates(cls, value: Any) -> Any:
        return _parse_iso_date(value)


class TrademarkSearchResponse(BaseModel):
    """Top-level envelope for trademark simple-search responses."""

    total_hits: int = Field(default=0, alias="totalHits")
    total_pages: int = Field(default=0, alias="totalPages")
    hits: int = 0
    page: int = 0
    trademarks: list[TrademarkSearchRow] = Field(default_factory=list)

    model_config = _BASE_CONFIG


# ---------------------------------------------------------------------------
# Design search row + envelope
# ---------------------------------------------------------------------------


class DesignSearchRow(BaseModel):
    """One row in the design simple-search response.

    Returned by ``POST dv-search-api.prv.se/searchdesign/dssimplesearch/``.
    Each row represents one design within a multi-design application —
    ``design_number`` and ``designs_total`` indicate the embodiment
    position.
    """

    id_design: int | None = Field(default=None, alias="idDesign")
    application_number: str | None = Field(default=None, alias="applicationNumber")
    registration_number: str | None = Field(default=None, alias="registrationNumber")
    design_id: str | None = Field(default=None, alias="designId")
    design_number: int | None = Field(default=None, alias="designNumber")
    designs_total: int | None = Field(default=None, alias="designsTotal")
    product_title: str | None = Field(default=None, alias="productTitle")
    status_en: str | None = Field(default=None, alias="statusEn")
    status_sv: str | None = Field(default=None, alias="statusSv")
    filing_date: date | None = Field(default=None, alias="filingDate")
    expiry_date: date | None = Field(default=None, alias="expiryDate")
    classes: list[str] = Field(default_factory=list)
    applicants: list[Party] = Field(default_factory=list)
    representatives: list[Party] = Field(default_factory=list)

    model_config = _BASE_CONFIG

    @field_validator("filing_date", "expiry_date", mode="before")
    @classmethod
    def _coerce_dates(cls, value: Any) -> Any:
        return _parse_iso_date(value)


class DesignSearchResponse(BaseModel):
    """Top-level envelope for design simple-search responses."""

    total_hits: int = Field(default=0, alias="totalHits")
    total_pages: int = Field(default=0, alias="totalPages")
    hits: int = 0
    page: int = 0
    designs: list[DesignSearchRow] = Field(default_factory=list)

    model_config = _BASE_CONFIG


# ---------------------------------------------------------------------------
# SPC search row + envelope
# ---------------------------------------------------------------------------


class SpcSearchRow(BaseModel):
    """One row in the SPC search response.

    Returned by ``POST patents-search-api.prv.se/searchpatentspc/patentsearchspc/``.
    The ``application_number_formatted`` is the base patent
    (typically EP-route); ``application_number_spc_formatted`` is
    the SPC's own application number. ``valid_from_date`` /
    ``valid_until_date`` bracket the SPC term.
    """

    id_spc: int | None = Field(default=None, alias="idSpc")
    application_number_formatted: str | None = Field(
        default=None, alias="applicationNumberFormatted"
    )
    application_number_spc_formatted: str | None = Field(
        default=None, alias="applicationNumberSpcFormatted"
    )
    publication_number: str | None = Field(default=None, alias="publicationNumber")
    substance: str | None = None
    valid_from_date: date | None = Field(default=None, alias="validFromDate")
    valid_until_date: date | None = Field(default=None, alias="validUntilDate")
    applicants: list[Party] = Field(default_factory=list)

    model_config = _BASE_CONFIG

    @field_validator("valid_from_date", "valid_until_date", mode="before")
    @classmethod
    def _coerce_dates(cls, value: Any) -> Any:
        return _parse_iso_date(value)


class SpcSearchResponse(BaseModel):
    """Top-level envelope for SPC search responses."""

    total_hits: int = Field(default=0, alias="totalHits")
    total_pages: int = Field(default=0, alias="totalPages")
    hits: int = 0
    page: int = 0
    search_spc_dtos: list[SpcSearchRow] = Field(default_factory=list, alias="searchSpcDTOS")

    model_config = _BASE_CONFIG


__all__ = [
    "Party",
    "PublicationStatus",
    "Publication",
    "RegistryEntry",
    "GazetteAnnouncement",
    "Drawing",
    "PatentSearchRow",
    "PatentSearchResponse",
    "PatentGetRecord",
    "TrademarkSearchRow",
    "TrademarkSearchResponse",
    "DesignSearchRow",
    "DesignSearchResponse",
    "SpcSearchRow",
    "SpcSearchResponse",
]
