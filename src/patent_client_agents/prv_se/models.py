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

from pydantic import BaseModel, ConfigDict, Field

from patent_client_agents.shared.models import ApiModel, YmdDate

_BASE_CONFIG: ConfigDict = ConfigDict(populate_by_name=True, extra="allow")


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


class PublicationStatus(ApiModel):
    """Status block on patent-search rows.

    Carries the numeric ``status`` code plus multilingual display-text
    slots. The slots are often ``null`` on freshly-filed applications;
    the patent-get response populates them.
    """

    status: str | None = None
    status_text: str | None = None
    status_display_text_en: str | None = None
    status_display_text_sv: str | None = None
    status_sub_text: str | None = None
    status_display_sub_text_en: str | None = None
    status_display_sub_text_sv: str | None = None

    model_config = _BASE_CONFIG


class Publication(BaseModel):
    """One publication on a patent-get record."""

    title: str | None = None
    url: str | None = None

    model_config = _BASE_CONFIG


class RegistryEntry(BaseModel):
    """One register timeline entry on a patent-get record."""

    entry_date: YmdDate = Field(default=None, alias="date")
    event: str | None = None

    model_config = _BASE_CONFIG


class GazetteAnnouncement(ApiModel):
    """One gazette announcement on a patent-get record."""

    issue: str | None = None
    type: str | None = None
    text: str | None = None
    announcement_date: YmdDate = None

    model_config = _BASE_CONFIG


class Drawing(ApiModel):
    """First-drawing block on a patent-get record.

    Carries the base64-encoded image bytes in ``data``. MCP lean
    projection drops ``data`` to keep the response under context
    budget; the metadata (application number, page number) is kept.
    """

    application_number: str | None = None
    page_number: int | None = None
    data: str | None = None

    model_config = _BASE_CONFIG


# ---------------------------------------------------------------------------
# Patent search row + envelope
# ---------------------------------------------------------------------------


class PatentSearchRow(ApiModel):
    """One row in the patent simple-search response.

    Returned by ``POST patents-search-api.prv.se/searchpatent/patentsimplesearch/``.
    The ``status`` block carries the numeric status code; multilingual
    display text resolves on the patent-get endpoint.
    """

    id_patent: int | None = None
    application_number_formatted: str | None = None
    application_type: str | None = None
    title: str | None = None
    filing_date: YmdDate = None
    publication_date: YmdDate = None
    grant_date: YmdDate = None
    publication_number: str | None = None
    reference: str | None = None
    applicants: list[Party] = Field(default_factory=list)
    inventors: list[Party] = Field(default_factory=list)
    representatives: list[Party] = Field(default_factory=list)
    cpc_classes: list[str] = Field(default_factory=list)
    ipc_classes: list[str] = Field(default_factory=list)
    dpk_classes: list[str] = Field(default_factory=list)
    status: PublicationStatus | None = None

    model_config = _BASE_CONFIG


class PatentSearchResponse(ApiModel):
    """Top-level envelope for patent simple-search responses."""

    total_hits: int = 0
    total_pages: int = 0
    hits: int = 0
    page: int = 0
    search_patent_dtos: list[PatentSearchRow] = Field(
        default_factory=list, alias="searchPatentDTOS"
    )

    model_config = _BASE_CONFIG


# ---------------------------------------------------------------------------
# Patent get record (api.prv.se per-record)
# ---------------------------------------------------------------------------


class PatentGetRecord(ApiModel):
    """Full patent record from ``GET api.prv.se/patents/applications/{n}``.

    Carries the resolved status text (multilingual), prosecution
    timeline (``registry_entries_*``), and the first-drawing image (in
    base64, lean projection drops the image bytes).

    The ``applicants`` / ``inventors`` / ``representatives`` fields are
    flat strings on this endpoint (the search endpoint returns dicts).
    """

    application_number: str | None = None
    application_number_formatted: str | None = None
    application_type: str | None = None
    status: str | None = None
    status_text: str | None = None
    status_sub_text: str | None = None
    status_display_text_sv: str | None = None
    status_display_text_en: str | None = None
    status_display_sub_text_sv: str | None = None
    status_display_sub_text_en: str | None = None
    info_sv: str | None = None
    info_en: str | None = None
    filing_date: YmdDate = None
    available_to_the_public_date: YmdDate = None
    title: str | None = None
    reference: str | None = None
    applicants_short_format: str | None = None
    applicants: list[str] = Field(default_factory=list)
    inventors: list[str] = Field(default_factory=list)
    representatives: list[str] = Field(default_factory=list)
    gazette_announcements_sv: list[GazetteAnnouncement] = Field(default_factory=list)
    gazette_announcements_en: list[GazetteAnnouncement] = Field(default_factory=list)
    electronic_announcements_sv: list[GazetteAnnouncement] = Field(default_factory=list)
    electronic_announcements_en: list[GazetteAnnouncement] = Field(default_factory=list)
    registry_entries_sv: list[RegistryEntry] = Field(default_factory=list)
    registry_entries_en: list[RegistryEntry] = Field(default_factory=list)
    mo_deposit: str | None = None
    source: str | None = None
    updated: YmdDate = None
    md5: str | None = None
    next_payment_date: YmdDate = None
    increesed_fee: bool | None = Field(default=None, alias="IncreesedFee")
    first_drawing: Drawing | None = None
    number_of_drawing_pages: int | None = None
    publications: list[Publication] = Field(default_factory=list)

    model_config = _BASE_CONFIG


# ---------------------------------------------------------------------------
# Trademark search row + envelope
# ---------------------------------------------------------------------------


class TrademarkSearchRow(ApiModel):
    """One row in the trademark simple-search response.

    Returned by ``POST dv-search-api.prv.se/searchtrademark/tmsimplesearch/``.
    ``dossier_type_*`` discriminates national filings ("National
    trademark") from Madrid IRs designating SE.
    """

    id_trademark: int | None = None
    application_number: str | None = None
    registration_number: str | None = None
    mark_specification: str | None = None
    mark_feature_en: str | None = None
    mark_feature_sv: str | None = None
    dossier_type_en: str | None = None
    dossier_type_sv: str | None = None
    status_en: str | None = None
    status_sv: str | None = None
    filing_date: YmdDate = None
    expiry_date: YmdDate = None
    classes: list[str] = Field(default_factory=list)
    applicants: list[Party] = Field(default_factory=list)
    representatives: list[str | Party] = Field(default_factory=list)

    model_config = _BASE_CONFIG


class TrademarkSearchResponse(ApiModel):
    """Top-level envelope for trademark simple-search responses."""

    total_hits: int = 0
    total_pages: int = 0
    hits: int = 0
    page: int = 0
    trademarks: list[TrademarkSearchRow] = Field(default_factory=list)

    model_config = _BASE_CONFIG


# ---------------------------------------------------------------------------
# Design search row + envelope
# ---------------------------------------------------------------------------


class DesignSearchRow(ApiModel):
    """One row in the design simple-search response.

    Returned by ``POST dv-search-api.prv.se/searchdesign/dssimplesearch/``.
    Each row represents one design within a multi-design application —
    ``design_number`` and ``designs_total`` indicate the embodiment
    position.
    """

    id_design: int | None = None
    application_number: str | None = None
    registration_number: str | None = None
    design_id: str | None = None
    design_number: int | None = None
    designs_total: int | None = None
    product_title: str | None = None
    status_en: str | None = None
    status_sv: str | None = None
    filing_date: YmdDate = None
    expiry_date: YmdDate = None
    classes: list[str] = Field(default_factory=list)
    applicants: list[Party] = Field(default_factory=list)
    representatives: list[Party] = Field(default_factory=list)

    model_config = _BASE_CONFIG


class DesignSearchResponse(ApiModel):
    """Top-level envelope for design simple-search responses."""

    total_hits: int = 0
    total_pages: int = 0
    hits: int = 0
    page: int = 0
    designs: list[DesignSearchRow] = Field(default_factory=list)

    model_config = _BASE_CONFIG


# ---------------------------------------------------------------------------
# SPC search row + envelope
# ---------------------------------------------------------------------------


class SpcSearchRow(ApiModel):
    """One row in the SPC search response.

    Returned by ``POST patents-search-api.prv.se/searchpatentspc/patentsearchspc/``.
    The ``application_number_formatted`` is the base patent
    (typically EP-route); ``application_number_spc_formatted`` is
    the SPC's own application number. ``valid_from_date`` /
    ``valid_until_date`` bracket the SPC term.
    """

    id_spc: int | None = None
    application_number_formatted: str | None = None
    application_number_spc_formatted: str | None = None
    publication_number: str | None = None
    substance: str | None = None
    valid_from_date: YmdDate = None
    valid_until_date: YmdDate = None
    applicants: list[Party] = Field(default_factory=list)

    model_config = _BASE_CONFIG


class SpcSearchResponse(ApiModel):
    """Top-level envelope for SPC search responses."""

    total_hits: int = 0
    total_pages: int = 0
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
