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

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from patent_client_agents.shared.models import ApiModel, YmdDate

_BASE_CONFIG: ConfigDict = ConfigDict(populate_by_name=True, extra="allow")


# ---------------------------------------------------------------------------
# Shared sub-row pieces
# ---------------------------------------------------------------------------


class Party(ApiModel):
    """One party (applicant, representative, inventor, owner).

    Two shapes appear across the surface:
    * TM/TMR/Design rows: ``{name, ordinal}``
    * Patent rows + GET: ``{name, companyName, ordinal}`` (``name`` is
      the person name; ``companyName`` is the legal entity).
    """

    name: str | None = None
    company_name: str | None = None
    ordinal: int | None = None

    model_config = _BASE_CONFIG


class GoodsAndServicesClass(ApiModel):
    """One Nice class entry on a trademark dossier."""

    class_number: int | None = None
    ordinal: int | None = None

    model_config = _BASE_CONFIG


class LocarnoClass(ApiModel):
    """One Locarno class entry on a design dossier."""

    class_number: str | None = None
    sub_class_number: str | None = None
    ordinal: int | None = None

    model_config = _BASE_CONFIG


class DesignEmbodiment(ApiModel):
    """One design embodiment within a design dossier's ``designs`` array."""

    title: str | None = None
    title_second_lng: str | None = None
    number: int | None = None
    dominant_view_number: int | None = None
    dominant_view_image_url: str | None = None
    dominant_view_small_thumbnail_url: str | None = None
    dominant_view_medium_thumbnail_url: str | None = None
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


class PatentPublication(ApiModel):
    """One publication entry on a patent search row."""

    publication_date: YmdDate = None
    type: str | None = None
    publication_section: str | None = None
    ordinal: int | None = None

    model_config = _BASE_CONFIG


class PriorityClaim(ApiModel):
    """One Paris priority claim on a patent GET record."""

    office_code: str | None = None
    filing_date: YmdDate = None
    application_number: str | None = None
    ordinal: int | None = None

    model_config = _BASE_CONFIG


class Examiner(ApiModel):
    """Named examiner on a patent GET record."""

    full_name: str | None = None

    model_config = _BASE_CONFIG


class DossierPriority(ApiModel):
    """One priority claim on a TM/design dossier row."""

    office_code: str | None = None
    application_date: YmdDate = None
    application_number: str | None = None
    ordinal: int | None = None

    model_config = _BASE_CONFIG


# ---------------------------------------------------------------------------
# Unified dossier row — TM, TMR (well-known), design (same 21-field shape)
# ---------------------------------------------------------------------------


class DossierSearchRow(ApiModel):
    """One row in the trademark, well-known-trademark, or design search.

    PRH ships an identical row shape across the three rights — what
    discriminates them is the endpoint (``/trademark``, ``/tmr``,
    ``/design``) and which optional slots populate (``locarnos`` +
    ``designs`` for designs; ``goodsAndServices`` + ``trademarkWord``
    + ``imageUrl`` for trademarks).
    """

    dossier_id: int | None = None
    application_number: str | None = None
    registration_number: str | None = None
    dossier_status: str | None = None
    dossier_sub_type: str | None = None
    application_date: YmdDate = None
    registration_date: YmdDate = None
    expiration_date: YmdDate = None
    applicants: list[Party] = Field(default_factory=list)
    representatives: list[Party] = Field(default_factory=list)
    priorities: list[DossierPriority] = Field(default_factory=list)
    trademark_word: str | None = None
    trademark_has_image: bool | None = None
    goods_and_services: list[GoodsAndServicesClass] = Field(default_factory=list)
    target_group: str | None = None
    locarnos: list[LocarnoClass] = Field(default_factory=list)
    designs: list[DesignEmbodiment] = Field(default_factory=list)
    image_url: str | None = None
    thumbnail_url: str | None = None
    large_thumbnail_url: str | None = None
    ordinal: int | None = None

    model_config = _BASE_CONFIG


class DossierSearchResponse(ApiModel):
    """Top-level envelope for TM, TMR, and design search responses."""

    total_results: int = 0
    results: list[DossierSearchRow] = Field(default_factory=list)

    model_config = _BASE_CONFIG


# ---------------------------------------------------------------------------
# Patent search row + envelope
# ---------------------------------------------------------------------------


class PatentSearchRow(ApiModel):
    """One row in the PRH patent corpus search.

    Covers FI-national patents (``dossierType=PatentDossier``), utility
    models (``PatentDossierUtilityModel``), EP-FI validations
    (``PatentEurope``), and supplementary protection certificates
    (``Spc``).
    """

    application_number: str | None = None
    registration_number: str | None = None
    dossier_status: str | None = None
    dossier_type: str | None = None
    application_date: YmdDate = None
    status_date: YmdDate = None
    applicants: list[Party] = Field(default_factory=list)
    owners: list[Party] = Field(default_factory=list)
    classifications: list[Classification] = Field(default_factory=list)
    titles: list[TitleTranslation] = Field(default_factory=list)
    appms: list[Any] = Field(default_factory=list)
    publications: list[PatentPublication] = Field(default_factory=list)
    ordinal: int | None = None

    model_config = _BASE_CONFIG


class PatentSearchResponse(ApiModel):
    """Top-level envelope for patent search responses."""

    total_results: int = 0
    results: list[PatentSearchRow] = Field(default_factory=list)

    model_config = _BASE_CONFIG


# ---------------------------------------------------------------------------
# Patent per-record GET
# ---------------------------------------------------------------------------


class PatentGetRecord(ApiModel):
    """Full patent register record from ``GET /patent/{appno}``.

    Carries the trilingual title + abstracts (FI/SV/EN), prosecution
    events, full file-history pointer list (``documents.document``),
    named examiner, payment timeline, and SPC authorizations. The
    ``relatedDossierType`` discriminates Paris-route national filings
    from PCT national-phase entries and EP-FI validations.
    """

    application_number: str | None = None
    application_type: str | None = None
    registration_number: str | None = None
    related_dossier_type: str | None = None
    base_patent_number: str | None = None
    t3_publication_date: YmdDate = None
    application_date: YmdDate = None
    filing_date: YmdDate = None
    grant_date: YmdDate = None
    publication_date: YmdDate = None
    dossier_status: str | None = None
    dossier_status_date: YmdDate = None
    filing_language: str | None = None
    patent_title: list[TitleTranslation] = Field(default_factory=list)
    abstracts: list[AbstractTranslation] = Field(default_factory=list)
    events: list[Any] = Field(default_factory=list)
    documents: Any | None = None
    examiner: Examiner | None = None
    inventors: list[Party] = Field(default_factory=list)
    applicants: list[Party] = Field(default_factory=list)
    owners: list[Party] = Field(default_factory=list)
    representatives: list[Party] = Field(default_factory=list)
    ipc_classifications: list[str] = Field(default_factory=list)
    cpc_classifications: list[str] = Field(default_factory=list)
    payment_details: Any | None = None
    priority_claims: list[PriorityClaim] = Field(default_factory=list)
    related_dossiers: list[Any] = Field(default_factory=list)
    spc_authorizations: list[Any] = Field(default_factory=list)
    image_url: str | None = None

    model_config = _BASE_CONFIG


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
