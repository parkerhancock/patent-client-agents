"""Pydantic v2 row models for the TIPO Taiwan OpenData API.

Derived from the Swagger 2.0 specification at
``https://cloud.tipo.gov.tw/S220/opdata/api/file/oas`` (fetched
2026-05-16). The OAS wraps each row collection inside a versioned
envelope (``version``, ``status``, ``top``, ``skip``, ``total-count``,
plus a single nested object whose property name varies per endpoint
e.g. ``tw-patent-applI``, ``tmarkappl``, ``tw-patent-twins`` ...). The
nested object holds an array of "content" rows whose item shapes are
what this module models.

Conventions:
- INID-style kebab-case aliases map to snake_case Python attributes via
  ``Field(alias="appl-no")`` and ``populate_by_name=True``.
- Dates arrive as Gregorian ``YYYY/MM/DD`` strings (TIPO converts ROC
  years upstream for the public OpenData feed). Empty strings parse to
  ``None``; well-formed strings parse to ``datetime.date``.
- All fields default to ``None`` (or empty list) because real TIPO rows
  routinely omit Latin-script names and other optional INID fields.
- ``extra="allow"`` keeps row parsing forward-compatible with new
  fields TIPO ships outside the OAS.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

_BASE_CONFIG: ConfigDict = ConfigDict(populate_by_name=True, extra="allow")


def _parse_tipo_date(value: Any) -> date | None:
    """Parse a TIPO ``YYYY/MM/DD`` date string into a ``date``.

    TIPO converts Republic of China era dates to Gregorian for the
    public OpenData feed, so a value like ``"2017/03/03"`` is the
    canonical Gregorian year. Empty strings, whitespace, ``"0/0/0"``
    placeholders, and other non-parseable input return ``None`` so the
    row model still validates.
    """

    if value is None:
        return None
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw or raw in {"0/0/0", "0000/00/00"}:
        return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Shared sub-row pieces (kept loose — agents see them through ListEnvelope
# projections in chunk 3 rather than navigating these directly).
# ---------------------------------------------------------------------------


class IpcClassification(BaseModel):
    """One IPC classification entry inside ``classification-ipc[*].ipc[*]``."""

    sequence: int | None = None
    ipc_full: str | None = Field(default=None, alias="ipc-full")
    ipc_section: str | None = Field(default=None, alias="ipc-section")
    ipc_class: str | None = Field(default=None, alias="ipc-class")
    ipc_subclass: str | None = Field(default=None, alias="ipc-subclass")
    ipc_main_group: str | None = Field(default=None, alias="ipc-main-group")
    ipc_group: str | None = Field(default=None, alias="ipc-group")
    ipc_version: str | None = Field(default=None, alias="ipc-version")

    model_config = _BASE_CONFIG


class LocClassification(BaseModel):
    """One Locarno classification entry inside ``classification-loc[*].loc[*]``."""

    sequence: int | None = None
    loc_full: str | None = Field(default=None, alias="loc-full")
    loc_level1: str | None = Field(default=None, alias="loc-level1")
    loc_level2: str | None = Field(default=None, alias="loc-level2")
    loc_version: str | None = Field(default=None, alias="loc-version")

    model_config = _BASE_CONFIG


class PartyApplicant(BaseModel):
    """One applicant inside the ``parties.applicants[*].applicant`` array.

    Note that TIPO ships at least two applicant shapes:
    - patents use ``english-country`` / ``english-address``;
    - trademarks use ``country-code`` + ``japanese-name`` and have no
      ``english-address`` field.

    Both variants are unified here behind ``extra="allow"``.
    """

    sequence: int | None = None
    chinese_name: str | None = Field(default=None, alias="chinese-name")
    english_name: str | None = Field(default=None, alias="english-name")
    japanese_name: str | None = Field(default=None, alias="japanese-name")
    address: str | None = None
    english_address: str | None = Field(default=None, alias="english-address")
    english_country: str | None = Field(default=None, alias="english-country")
    chinese_country: str | None = Field(default=None, alias="chinese-country")
    country_code: str | None = Field(default=None, alias="country-code")
    chinese_country_name: str | None = Field(default=None, alias="chinese-country-name")

    model_config = _BASE_CONFIG


class PartyInventor(BaseModel):
    """One inventor inside the ``parties.inventors[*].inventor`` array."""

    sequence: int | None = None
    chinese_name: str | None = Field(default=None, alias="chinese-name")
    english_name: str | None = Field(default=None, alias="english-name")
    english_country: str | None = Field(default=None, alias="english-country")
    chinese_country: str | None = Field(default=None, alias="chinese-country")

    model_config = _BASE_CONFIG


class PartyAgent(BaseModel):
    """One agent inside the ``parties.agents[*].agent`` array.

    Patents typically have ``english-name`` and ``english-country``;
    trademarks usually only have ``chinese-name`` and ``address``. The
    OAS even uses the typo ``squence`` for trademark agents — kept as
    an alias so we can parse it.
    """

    sequence: int | None = Field(default=None, validation_alias="sequence")
    chinese_name: str | None = Field(default=None, alias="chinese-name")
    english_name: str | None = Field(default=None, alias="english-name")
    address: str | None = None
    english_country: str | None = Field(default=None, alias="english-country")
    chinese_country: str | None = Field(default=None, alias="chinese-country")

    model_config = _BASE_CONFIG


class PublicationReference(BaseModel):
    """``publication-reference`` sub-object on PatentPub / PatentRights."""

    notice_no: int | None = Field(default=None, alias="notice-no")
    notice_volno: int | None = Field(default=None, alias="notice-volno")
    notice_isuno: int | None = Field(default=None, alias="notice-isuno")
    notice_date: date | None = Field(default=None, alias="notice-date")

    model_config = _BASE_CONFIG

    @field_validator("notice_date", mode="before")
    @classmethod
    def _parse_notice_date(cls, value: Any) -> date | None:
        return _parse_tipo_date(value)


class ApplicationReference(BaseModel):
    """``application-reference`` sub-object on PatentPub / PatentRights.

    PatentRights adds the rich design / twins flags; PatentPub uses a
    leaner subset. All fields are optional so the same model covers
    both shapes.
    """

    appl_no: str | None = Field(default=None, alias="appl-no")
    appl_date: date | None = Field(default=None, alias="appl-date")
    first_date: date | None = Field(default=None, alias="first-date")
    foreign_language: str | None = Field(default=None, alias="foreign-language")
    foreign_language_desc: str | None = Field(default=None, alias="foreign-language-desc")
    desing_type: str | None = Field(default=None, alias="desing-type")
    desing_type_desc: str | None = Field(default=None, alias="desing-type-desc")
    appl_class: str | None = Field(default=None, alias="appl-class")
    appl_class_desc: str | None = Field(default=None, alias="appl-class-desc")
    material_appl_date: date | None = Field(default=None, alias="material-appl-date")
    material_flag: str | None = Field(default=None, alias="material-flag")
    faplexm_date: date | None = Field(default=None, alias="faplexm-date")
    reappl_date: date | None = Field(default=None, alias="reappl-date")
    raplexam_date: date | None = Field(default=None, alias="raplexam-date")
    agree_flag: str | None = Field(default=None, alias="agree-flag")
    twins_flag: str | None = Field(default=None, alias="twins-flag")

    model_config = _BASE_CONFIG

    @field_validator(
        "appl_date",
        "first_date",
        "material_appl_date",
        "faplexm_date",
        "reappl_date",
        "raplexam_date",
        mode="before",
    )
    @classmethod
    def _parse_dates(cls, value: Any) -> date | None:
        return _parse_tipo_date(value)


class PatentTitle(BaseModel):
    """``patent-title`` sub-object — Chinese + English title pair."""

    patent_name_chinese: str | None = Field(default=None, alias="patent-name-chinese")
    patent_name_english: str | None = Field(default=None, alias="patent-name-english")

    model_config = _BASE_CONFIG


class PatentRight(BaseModel):
    """``patent-right`` sub-object on PatentRightsRow."""

    licence_date: date | None = Field(default=None, alias="licence-date")
    relicence_date: date | None = Field(default=None, alias="relicence-date")
    patent_no: str | None = Field(default=None, alias="patent-no")
    patent_bdate: date | None = Field(default=None, alias="patent-bdate")
    patent_edate: date | None = Field(default=None, alias="patent-edate")
    charge_expir_date: date | None = Field(default=None, alias="charge-expir-date")
    charge_expir_year: str | None = Field(default=None, alias="charge-expir-year")
    rent_status: int | None = Field(default=None, alias="rent-status")
    mortgage_status: int | None = Field(default=None, alias="mortgage-status")
    transfer_status: int | None = Field(default=None, alias="transfer-status")
    inherit_status: int | None = Field(default=None, alias="inherit-status")
    trust_status: int | None = Field(default=None, alias="trust-status")
    opposition_status: int | None = Field(default=None, alias="opposition-status")
    nullity_status: int | None = Field(default=None, alias="nullity-status")
    continue_status: int | None = Field(default=None, alias="continue-status")
    expand_status: int | None = Field(default=None, alias="expand-status")
    cancel_date: date | None = Field(default=None, alias="cancel-date")
    cancel_result: str | None = Field(default=None, alias="cancel-result")
    revoke_date: date | None = Field(default=None, alias="revoke-date")
    revoke_code: str | None = Field(default=None, alias="revoke-code")
    dep_patent_class: str | None = Field(default=None, alias="dep-patent-class")
    dep_appl_no: str | None = Field(default=None, alias="dep-appl-no")

    model_config = _BASE_CONFIG

    @field_validator(
        "licence_date",
        "relicence_date",
        "patent_bdate",
        "patent_edate",
        "charge_expir_date",
        "cancel_date",
        "revoke_date",
        mode="before",
    )
    @classmethod
    def _parse_dates(cls, value: Any) -> date | None:
        return _parse_tipo_date(value)


# ---------------------------------------------------------------------------
# Top-level row models — one per endpoint per spec §3.
# ---------------------------------------------------------------------------


class PatentApplRow(BaseModel):
    """One ``patentcontent`` row from ``/PatentAppl``.

    Wraps the bibliographic application record (filing no, filing date,
    country of origin, IPC + Locarno classifications, and the
    ``publish-flag`` enum). Detailed applicants / inventors / agents
    don't surface on the application endpoint — they're on
    ``/PatentRights`` and ``/PatentPub``.
    """

    sequence: int | None = None
    appl_no: str | None = Field(default=None, alias="appl-no")
    appl_date: date | None = Field(default=None, alias="appl-date")
    appl_countrycode: str | None = Field(default=None, alias="appl-countrycode")
    appl_country: str | None = Field(default=None, alias="appl-country")
    publish_flag: str | None = Field(default=None, alias="publish-flag")
    classification_ipc: list[Any] = Field(default_factory=list, alias="classification-ipc")
    classification_loc: list[Any] = Field(default_factory=list, alias="classification-loc")

    model_config = _BASE_CONFIG

    @field_validator("appl_date", mode="before")
    @classmethod
    def _parse_appl_date(cls, value: Any) -> date | None:
        return _parse_tipo_date(value)


class PatentPubRow(BaseModel):
    """One ``patentcontent`` row from ``/PatentPub`` (KOKAI/KOKOKU pubs)."""

    sequence: int | None = None
    publication_reference: PublicationReference | None = Field(
        default=None, alias="publication-reference"
    )
    application_reference: ApplicationReference | None = Field(
        default=None, alias="application-reference"
    )
    patent_title: PatentTitle | None = Field(default=None, alias="patent-title")
    parties: dict[str, Any] | None = None
    classification_ipc: list[Any] = Field(default_factory=list, alias="classification-ipc")
    link: dict[str, Any] | None = None

    model_config = _BASE_CONFIG


class PatentRightsRow(BaseModel):
    """One ``patentcontent`` row from ``/PatentRights`` (grant + status).

    Carries the TW-specific ``twins-flag`` on the nested
    ``application-reference`` object (Article 32 dual-track invention /
    utility-model pairs).
    """

    sequence: int | None = None
    publication_reference: PublicationReference | None = Field(
        default=None, alias="publication-reference"
    )
    application_reference: ApplicationReference | None = Field(
        default=None, alias="application-reference"
    )
    patent_title: PatentTitle | None = Field(default=None, alias="patent-title")
    patent_right: PatentRight | None = Field(default=None, alias="patent-right")
    parties: dict[str, Any] | None = None
    classification_ipc: list[Any] = Field(default_factory=list, alias="classification-ipc")
    classification_loc: list[Any] = Field(default_factory=list, alias="classification-loc")
    link: dict[str, Any] | None = None

    model_config = _BASE_CONFIG


class PatentPriorityRow(BaseModel):
    """One row from ``/PatentPriority`` — Paris priority claims."""

    sequence: int | None = None
    appl_no: str | None = Field(default=None, alias="appl-no")
    prioritys: list[Any] = Field(default_factory=list)

    model_config = _BASE_CONFIG


class PatentAnnuityRow(BaseModel):
    """One row from ``/PatentAnnuity`` — annuity payment schedule."""

    sequence: int | None = None
    appl_no: str | None = Field(default=None, alias="appl-no")
    licence_date: date | None = Field(default=None, alias="licence-date")
    relicence_date: date | None = Field(default=None, alias="relicence-date")
    patent_no: str | None = Field(default=None, alias="patent-no")
    publish_no: str | None = Field(default=None, alias="publish-no")
    charge_expir_date: date | None = Field(default=None, alias="charge-expir-date")
    charge_expir_year: str | None = Field(default=None, alias="charge-expir-year")
    charges: list[Any] = Field(default_factory=list)

    model_config = _BASE_CONFIG

    @field_validator(
        "licence_date",
        "relicence_date",
        "charge_expir_date",
        mode="before",
    )
    @classmethod
    def _parse_dates(cls, value: Any) -> date | None:
        return _parse_tipo_date(value)


class PatentTwinsRow(BaseModel):
    """One row from ``/PatentTwins`` — Article 32 invention / UM pair.

    The OAS only exposes ``appl-no`` and ``sequence`` here. The twin
    partner's appl-no is conveyed via the surrounding ``twins-announced``
    grouping and surfaces as extra fields per ``extra="allow"``.
    """

    sequence: int | None = None
    appl_no: str | None = Field(default=None, alias="appl-no")

    model_config = _BASE_CONFIG


class PatentAlterationRow(BaseModel):
    """One row from ``/PatentAlteration`` — applicant / inventor / agent name changes."""

    sequence: int | None = None
    appl_no: str | None = Field(default=None, alias="appl-no")
    alteration: list[Any] = Field(default_factory=list)

    model_config = _BASE_CONFIG


class PatentChangeRow(BaseModel):
    """One row from ``/PatentChange`` — appl-no / appl-class changes.

    Distinct from ``PatentAlteration``: this tracks structural
    application-identifier changes (e.g. UM → invention conversions
    that mint a new ``appl-no``).
    """

    sequence: int | None = None
    appl_no: str | None = Field(default=None, alias="appl-no")
    appl_class: str | None = Field(default=None, alias="appl-class")
    new_appl_no: str | None = Field(default=None, alias="new-appl-no")
    new_appl_class: str | None = Field(default=None, alias="new-appl-class")

    model_config = _BASE_CONFIG


class PatentDivideRow(BaseModel):
    """One row from ``/PatentDivide`` — divisional applications.

    The OAS models ``new-appl-no`` as an object whose only property is
    ``patent-right-url`` (an XML attribute). We keep it as a free-form
    dict because real responses sometimes flatten this to a string.
    """

    sequence: int | None = None
    appl_no: str | None = Field(default=None, alias="appl-no")
    new_appl_no: dict[str, Any] | str | None = Field(default=None, alias="new-appl-no")

    model_config = _BASE_CONFIG


# ---------------------------------------------------------------------------
# Trademark rows
# ---------------------------------------------------------------------------


class TmarkApplRow(BaseModel):
    """One ``tmarkcontent`` row from ``/TmarkAppl`` — TM application biblio."""

    sequence: int | None = None
    appl_no: str | None = Field(default=None, alias="appl-no")
    appl_date: date | None = Field(default=None, alias="appl-date")
    tmark_name: str | None = Field(default=None, alias="tmark-name")
    tmark_class: str | None = Field(default=None, alias="tmark-class")
    tmark_class_desc: str | None = Field(default=None, alias="tmark-class-desc")
    tmark_image_url: list[Any] = Field(default_factory=list, alias="tmark-image-url")
    tmark_type: str | None = Field(default=None, alias="tmark-type")
    tmark_type_desc: str | None = Field(default=None, alias="tmark-type-desc")
    tmark_color: str | None = Field(default=None, alias="tmark-color")
    tmark_color_desc: str | None = Field(default=None, alias="tmark-color-desc")
    tmark_draft_c: str | None = Field(default=None, alias="tmark-draft-c")
    tmark_draft_e: str | None = Field(default=None, alias="tmark-draft-e")
    tmark_draft_j: str | None = Field(default=None, alias="tmark-draft-j")
    tmark_sign: str | None = Field(default=None, alias="tmark-sign")
    word_description: str | None = Field(default=None, alias="word-description")
    # TIPO sends ``goodsclasses``; accept the singular too in case an endpoint differs.
    goodsclass: list[Any] = Field(
        default_factory=list, validation_alias=AliasChoices("goodsclasses", "goodsclass")
    )
    receive_date: date | None = Field(default=None, alias="receive-date")
    parties: dict[str, Any] | None = None

    model_config = _BASE_CONFIG

    @field_validator("appl_date", "receive_date", mode="before")
    @classmethod
    def _parse_dates(cls, value: Any) -> date | None:
        return _parse_tipo_date(value)


class TmarkRightsRow(BaseModel):
    """One ``tmarkcontent`` row from ``/TmarkRights`` — TM registration + status."""

    sequence: int | None = None
    exam_no: str | None = Field(default=None, alias="exam-no")
    appl_no: str | None = Field(default=None, alias="appl-no")
    tmark_name: str | None = Field(default=None, alias="tmark-name")
    tmark_class: str | None = Field(default=None, alias="tmark-class")
    tmark_class_desc: str | None = Field(default=None, alias="tmark-class-desc")
    tmark_image_url: list[Any] = Field(default_factory=list, alias="tmark-image-url")
    tmark_type: str | None = Field(default=None, alias="tmark-type")
    tmark_type_desc: str | None = Field(default=None, alias="tmark-type-desc")
    tmark_color: str | None = Field(default=None, alias="tmark-color")
    tmark_color_desc: str | None = Field(default=None, alias="tmark-color-desc")
    tmark_draft_c: str | None = Field(default=None, alias="tmark-draft-c")
    tmark_draft_e: str | None = Field(default=None, alias="tmark-draft-e")
    tmark_draft_j: str | None = Field(default=None, alias="tmark-draft-j")
    tmark_sign: str | None = Field(default=None, alias="tmark-sign")
    word_description: str | None = Field(default=None, alias="word-description")
    # TIPO sends ``goodsclasses``; accept the singular too in case an endpoint differs.
    goodsclass: list[Any] = Field(
        default_factory=list, validation_alias=AliasChoices("goodsclasses", "goodsclass")
    )
    deadline: date | None = None
    receive_date: date | None = Field(default=None, alias="receive-date")
    appl_date: date | None = Field(default=None, alias="appl-date")
    reg_date: date | None = Field(default=None, alias="reg-date")
    reg_notice_date: date | None = Field(default=None, alias="reg-notice-date")
    exam_notice_date: date | None = Field(default=None, alias="exam-notice-date")
    del_reason: str | None = Field(default=None, alias="del-reason")
    vol_no1: str | None = Field(default=None, alias="vol-no1")
    vol_no2: str | None = Field(default=None, alias="vol-no2")
    processor_name: str | None = Field(default=None, alias="processor-name")
    opposition_status: int | None = Field(default=None, alias="opposition-status")
    exam_status: int | None = Field(default=None, alias="exam-status")
    nullity_act_status: int | None = Field(default=None, alias="nullity-act-status")
    appl_del_status: int | None = Field(default=None, alias="appl-del-status")
    aut_status: int | None = Field(default=None, alias="aut-status")
    aga_aut_status: int | None = Field(default=None, alias="aga-aut-status")
    extended_status: int | None = Field(default=None, alias="extended-status")
    amedment_status: int | None = Field(default=None, alias="amedment-status")
    transfer_status: int | None = Field(default=None, alias="transfer-status")
    issue_opp_status: int | None = Field(default=None, alias="issue-opp-status")
    issue_del_status: int | None = Field(default=None, alias="issue-del-status")
    quota_status: int | None = Field(default=None, alias="quota-status")
    unable_use_status: int | None = Field(default=None, alias="unable-use-status")
    parties: dict[str, Any] | None = None

    model_config = _BASE_CONFIG

    @field_validator(
        "deadline",
        "receive_date",
        "appl_date",
        "reg_date",
        "reg_notice_date",
        "exam_notice_date",
        mode="before",
    )
    @classmethod
    def _parse_dates(cls, value: Any) -> date | None:
        return _parse_tipo_date(value)


class TmarkPriorityRow(BaseModel):
    """One row from ``/TmarkPriority`` — trademark priority claims.

    The OAS nests an additional ``tmarkcontent`` array under each
    ``tmarkrightscontents`` item; we surface that array directly along
    with the link URL to the parent rights record.
    """

    sequence: int | None = None
    tmark_right_url: str | None = Field(default=None, alias="tmark-right-url")
    tmarkcontent: list[Any] = Field(default_factory=list)

    model_config = _BASE_CONFIG


class TmarkPicsRow(BaseModel):
    """One row from ``/TmarkPics`` — image URLs for a trademark.

    Per spec §3 the tool returns URLs only — Pillow rendering is out of
    scope for v1. The image URL array elements carry up to six image
    fragments plus an audio filename (sound marks).
    """

    sequence: int | None = None
    appl_no: str | None = Field(default=None, alias="appl-no")
    tmark_image_url: list[Any] = Field(default_factory=list, alias="tmark-image-url")

    model_config = _BASE_CONFIG


class TmarkChangeRow(BaseModel):
    """One row from ``/TmarkChange`` — TM transfer / name-change events."""

    sequence: int | None = None
    tmark_class: str | None = Field(default=None, alias="tmark-class")
    tmark_class_desc: str | None = Field(default=None, alias="tmark-class-desc")
    exam_no: str | None = Field(default=None, alias="exam-no")
    tmark_name: str | None = Field(default=None, alias="tmark-name")
    alteration: list[Any] = Field(default_factory=list)

    model_config = _BASE_CONFIG


class TmarkDivideRow(BaseModel):
    """One row from ``/TmarkDivide`` — TM application divisions.

    The OAS models ``origin-exam-no`` as an empty-properties object
    carrying a ``-tmark-right-url`` XML attribute. We accept either a
    dict or a string here.
    """

    sequence: int | None = None
    tmark_class: str | None = Field(default=None, alias="tmark-class")
    tmark_class_desc: str | None = Field(default=None, alias="tmark-class-desc")
    exam_no: str | None = Field(default=None, alias="exam-no")
    tmark_name: str | None = Field(default=None, alias="tmark-name")
    # TIPO sends ``goodsclasses``; accept the singular too in case an endpoint differs.
    goodsclass: list[Any] = Field(
        default_factory=list, validation_alias=AliasChoices("goodsclasses", "goodsclass")
    )
    divide_date: date | None = Field(default=None, alias="divide-date")
    origin_exam_no: dict[str, Any] | str | None = Field(default=None, alias="origin-exam-no")
    origin_tmark_class: str | None = Field(default=None, alias="origin-tmark-class")
    origin_tmark_class_desc: str | None = Field(default=None, alias="origin-tmark-class-desc")
    divide_count: int | None = Field(default=None, alias="divide-count")

    model_config = _BASE_CONFIG

    @field_validator("divide_date", mode="before")
    @classmethod
    def _parse_divide_date(cls, value: Any) -> date | None:
        return _parse_tipo_date(value)


__all__ = [
    # patent rows
    "PatentApplRow",
    "PatentPubRow",
    "PatentRightsRow",
    "PatentPriorityRow",
    "PatentAnnuityRow",
    "PatentTwinsRow",
    "PatentAlterationRow",
    "PatentChangeRow",
    "PatentDivideRow",
    # trademark rows
    "TmarkApplRow",
    "TmarkRightsRow",
    "TmarkPriorityRow",
    "TmarkPicsRow",
    "TmarkChangeRow",
    "TmarkDivideRow",
    # nested sub-models
    "ApplicationReference",
    "IpcClassification",
    "LocClassification",
    "PartyAgent",
    "PartyApplicant",
    "PartyInventor",
    "PatentRight",
    "PatentTitle",
    "PublicationReference",
]
