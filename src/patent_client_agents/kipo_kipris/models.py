"""Pydantic models for KIPRIS Plus XML response rows.

KIPRIS Plus is the Korean Intellectual Property Information Service Plus
data API operated by KIPI on behalf of KIPO (Korea). Responses are XML
envelopes::

    <response>
      <header>
        <successYN>Y</successYN>
        <resultCode>00</resultCode>
        <resultMsg>NORMAL SERVICE</resultMsg>
      </header>
      <body>
        <items>
          <item>...row fields...</item>
          <item>...</item>
        </items>
        <numOfRows>10</numOfRows>
        <pageNo>1</pageNo>
        <totalCount>123</totalCount>
      </body>
    </response>

The three search services this connector targets are:

* ``patUtliInfoSearchService`` — Patents + Utility Models (same row shape;
  ``patent=Y/N`` and ``utility=Y/N`` filter flags select which subset).
  Models this connector exposes for this service: :class:`PatentUtilityRow`.
* ``trademarkInfoSearchService`` — Trademarks. Models: :class:`TrademarkRow`.
* ``designInfoSearchService`` — Designs. Models: :class:`DesignRow`.

Primary-source field discovery
------------------------------
Field lists were hand-curated from KIPRIS Plus service documentation:

* KIPRIS Plus patent/utility service page —
  https://plus.kipris.or.kr/eng/data/clas/DBII_000000000000001/view.do?menuNo=310000
  (fetched 2026-05-17, 656 KB)
* KIPRIS Plus trademark service page —
  https://plus.kipris.or.kr/eng/data/clas/DBII_000000000000002/view.do?menuNo=310000
  (fetched 2026-05-17, 600 KB)
* KIPRIS Plus design service page —
  https://plus.kipris.or.kr/eng/data/clas/DBII_000000000000003/view.do?menuNo=310000
  (fetched 2026-05-17, 600 KB)
* KIPRIS Plus leaflet —
  https://plus.kipris.or.kr/sampledata/KIPRISPlus%20leaflet.pdf
  (fetched 2026-05-17, 9.1 MB; converted via ``pdftotext``)

The public service pages describe data categories at a marketing level
rather than per-field XML schemas, so this initial field set is
informed by KIPO/KIPRIS service conventions documented in the spec
(``research/specs/kr-kipo-connector-spec.md`` §3) and the leaflet's
data-category descriptions. **Field exhaustiveness depends on cassette
validation in chunk 4** — once a real ``serviceKey`` is obtainable
(ToS §11 BYOK), live XML responses will reveal any KIPRIS-specific
fields not anticipated here, at which point this module gets extended
without breaking the existing surface (``extra="ignore"`` ensures
unknown fields don't error).

Conventions
-----------
* **Aliases**: KIPRIS XML elements use camelCase (``applicationNumber``);
  Python attributes are snake_case (``application_number``) with
  ``Field(alias="applicationNumber")`` and
  ``model_config = ConfigDict(populate_by_name=True, extra="ignore")``.
* **Optional everywhere**: every field defaults to ``None`` — KIPRIS
  rows are very sparse, especially across the patent/utility/design/
  trademark life cycle (e.g. ``registerNumber`` is empty until grant,
  ``openNumber`` is empty for non-published apps, etc.).
* **Date parsing**: KIPRIS dates arrive as ``YYYYMMDD`` 8-digit strings
  (sometimes ``YYYY-MM-DD``). The ``_parse_kipris_date`` validator
  coerces both forms (and empty strings) to ``date | None``.
* **Codes**: classification codes (IPC, Nice, Vienna, Locarno) and
  status flags are kept as strings — KIPRIS sometimes returns multiple
  semicolon-separated values in a single element.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _parse_kipris_date(value: Any) -> date | None:
    """Coerce KIPRIS date strings to ``date``.

    Accepted forms:

    * ``"20240315"`` (8-digit, the common KIPRIS form)
    * ``"2024-03-15"`` (ISO 8601, sometimes used in newer responses)
    * ``""`` / ``None`` / whitespace → ``None``
    * Already-parsed ``date`` / ``datetime`` → ``date`` (passthrough)

    Anything else is returned as ``None`` rather than raising — KIPRIS
    occasionally returns sentinel strings like ``"00000000"`` for
    "unknown" dates, and we treat all such cases as missing data.
    """
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or cleaned == "00000000":
        return None
    # Try ISO 8601 first (more common in newer KIPRIS responses)
    try:
        return date.fromisoformat(cleaned)
    except ValueError:
        pass
    # Try 8-digit YYYYMMDD
    if len(cleaned) == 8 and cleaned.isdigit():
        try:
            return datetime.strptime(cleaned, "%Y%m%d").date()
        except ValueError:
            return None
    return None


def _empty_str_to_none(value: Any) -> Any:
    """Coerce empty/whitespace strings to ``None`` for Optional[str] fields.

    KIPRIS regularly returns ``<applicantName></applicantName>`` for
    missing fields rather than omitting the element, which would
    otherwise leave us with ``""`` instead of ``None``.
    """
    if isinstance(value, str) and not value.strip():
        return None
    return value


class _KiprisRowBase(BaseModel):
    """Shared config for KIPRIS row models.

    ``extra="ignore"`` is critical: KIPRIS occasionally adds fields to
    responses (especially when service tiers upgrade dev → operation),
    and we don't want unknown elements to raise validation errors.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class PatentUtilityRow(_KiprisRowBase):
    """One row from ``patUtliInfoSearchService`` (Patents + Utility Models).

    KIPRIS uses one service for both patents and utility models; the
    ``right_type`` flag distinguishes them. Bibliographic fields cover
    application, publication (KOKAI "open"), and registration phases —
    most fields are populated at different lifecycle stages and remain
    empty until then.
    """

    # --- Identifiers ---------------------------------------------------
    application_number: str | None = Field(
        default=None,
        alias="applicationNumber",
        description="Application number (e.g. '1020230012345')",
    )
    application_date: date | None = Field(
        default=None,
        alias="applicationDate",
        description="Filing date",
    )
    publication_number: str | None = Field(
        default=None,
        alias="publicationNumber",
        description="Granted-patent publication number",
    )
    publication_date: date | None = Field(
        default=None,
        alias="publicationDate",
        description="Granted-patent publication date",
    )
    open_number: str | None = Field(
        default=None,
        alias="openNumber",
        description="KOKAI / laid-open (pre-grant) publication number",
    )
    open_date: date | None = Field(
        default=None,
        alias="openDate",
        description="KOKAI laid-open publication date",
    )
    register_number: str | None = Field(
        default=None,
        alias="registerNumber",
        description="Registration number (post-grant)",
    )
    register_date: date | None = Field(
        default=None,
        alias="registerDate",
        description="Registration date (post-grant)",
    )
    register_status: str | None = Field(
        default=None,
        alias="registerStatus",
        description=(
            "Registration status flag — one of '등록' (registered), '소멸' "
            "(extinguished), '공개' (published), '출원' (filed), etc."
        ),
    )

    # --- Title / abstract ---------------------------------------------
    invention_title: str | None = Field(
        default=None,
        alias="inventionTitle",
        description="Invention title (Korean)",
    )
    invention_title_english: str | None = Field(
        default=None,
        alias="inventionTitleEnglish",
        description="Invention title (English machine translation)",
    )
    astrt_cont: str | None = Field(
        default=None,
        alias="astrtCont",
        description="Abstract content (Korean)",
    )

    # --- Parties -------------------------------------------------------
    applicant_name: str | None = Field(
        default=None,
        alias="applicantName",
        description="Applicant name(s) — may be semicolon-delimited",
    )
    inventor_name: str | None = Field(
        default=None,
        alias="inventorName",
        description="Inventor name(s) — may be semicolon-delimited",
    )
    agent_name: str | None = Field(
        default=None,
        alias="agentName",
        description="Patent agent / attorney name",
    )

    # --- Classification ------------------------------------------------
    ipc_number: str | None = Field(
        default=None,
        alias="ipcNumber",
        description="IPC classification code(s) — may be semicolon-delimited",
    )

    # --- Date validators ----------------------------------------------
    @field_validator(
        "application_date",
        "publication_date",
        "open_date",
        "register_date",
        mode="before",
    )
    @classmethod
    def _coerce_date(cls, value: Any) -> Any:
        return _parse_kipris_date(value)

    # --- String validators (empty → None) -----------------------------
    @field_validator(
        "application_number",
        "publication_number",
        "open_number",
        "register_number",
        "register_status",
        "invention_title",
        "invention_title_english",
        "astrt_cont",
        "applicant_name",
        "inventor_name",
        "agent_name",
        "ipc_number",
        mode="before",
    )
    @classmethod
    def _coerce_empty(cls, value: Any) -> Any:
        return _empty_str_to_none(value)


class TrademarkRow(_KiprisRowBase):
    """One row from ``trademarkInfoSearchService`` (Trademarks).

    Trademark records carry image URLs (``big_drawing``) plus Nice
    (goods/services) and Vienna (figurative-element) classification
    codes. The mark text itself is in ``title`` (KIPRIS convention,
    not to be confused with patent ``inventionTitle``).
    """

    # --- Identifiers ---------------------------------------------------
    application_number: str | None = Field(
        default=None,
        alias="applicationNumber",
        description="Application number",
    )
    application_date: date | None = Field(
        default=None,
        alias="applicationDate",
        description="Filing date",
    )
    registration_number: str | None = Field(
        default=None,
        alias="registrationNumber",
        description="Registration number",
    )
    registration_date: date | None = Field(
        default=None,
        alias="registrationDate",
        description="Registration date",
    )
    registration_public_number: str | None = Field(
        default=None,
        alias="registrationPublicNumber",
        description="Registration publication (gazette) number",
    )

    # --- Mark content -------------------------------------------------
    title: str | None = Field(
        default=None,
        description="Mark text (the trademark itself)",
    )
    big_drawing: str | None = Field(
        default=None,
        alias="bigDrawing",
        description=(
            "URL to the high-resolution mark image hosted on KIPRIS (empty for word-only marks)"
        ),
    )

    # --- Classification ------------------------------------------------
    classification_code: str | None = Field(
        default=None,
        alias="classificationCode",
        description=(
            "Nice classification code(s) for goods/services — may be "
            "semicolon-delimited (e.g. '09;42')"
        ),
    )
    vienna_code: str | None = Field(
        default=None,
        alias="viennaCode",
        description=(
            "Vienna figurative-element classification code(s) — may be semicolon-delimited"
        ),
    )

    # --- Parties -------------------------------------------------------
    applicant_name: str | None = Field(
        default=None,
        alias="applicantName",
        description="Applicant name(s)",
    )
    agent_name: str | None = Field(
        default=None,
        alias="agentName",
        description="Trademark agent / attorney name",
    )
    reg_privilege_name: str | None = Field(
        default=None,
        alias="regPrivilegeName",
        description="Current rights-holder (registered proprietor) name",
    )

    # --- Date validators ----------------------------------------------
    @field_validator(
        "application_date",
        "registration_date",
        mode="before",
    )
    @classmethod
    def _coerce_date(cls, value: Any) -> Any:
        return _parse_kipris_date(value)

    # --- String validators (empty → None) -----------------------------
    @field_validator(
        "application_number",
        "registration_number",
        "registration_public_number",
        "title",
        "big_drawing",
        "classification_code",
        "vienna_code",
        "applicant_name",
        "agent_name",
        "reg_privilege_name",
        mode="before",
    )
    @classmethod
    def _coerce_empty(cls, value: Any) -> Any:
        return _empty_str_to_none(value)


class DesignRow(_KiprisRowBase):
    """One row from ``designInfoSearchService`` (Designs).

    Design records carry the article-name (the product the design is
    applied to), a Locarno classification code, an inventor (designer)
    field, and a drawing-image URL. The ``register_status`` field
    mirrors the patent service's status convention.
    """

    # --- Identifiers ---------------------------------------------------
    application_number: str | None = Field(
        default=None,
        alias="applicationNumber",
        description="Application number",
    )
    application_date: date | None = Field(
        default=None,
        alias="applicationDate",
        description="Filing date",
    )
    registration_number: str | None = Field(
        default=None,
        alias="registrationNumber",
        description="Registration number",
    )
    registration_date: date | None = Field(
        default=None,
        alias="registrationDate",
        description="Registration date",
    )
    register_status: str | None = Field(
        default=None,
        alias="registerStatus",
        description=(
            "Registration status flag — one of '등록' (registered), '소멸' "
            "(extinguished), '공개' (published), '출원' (filed), etc."
        ),
    )

    # --- Article / drawing --------------------------------------------
    article_name: str | None = Field(
        default=None,
        alias="articleName",
        description="Name of the article the design is applied to",
    )
    drawing: str | None = Field(
        default=None,
        description="URL to the design drawing/image hosted on KIPRIS",
    )

    # --- Classification ------------------------------------------------
    loc_code: str | None = Field(
        default=None,
        alias="locCode",
        description=("Locarno design classification code(s) — may be semicolon-delimited"),
    )

    # --- Parties -------------------------------------------------------
    applicant_name: str | None = Field(
        default=None,
        alias="applicantName",
        description="Applicant name(s)",
    )
    inventor_name: str | None = Field(
        default=None,
        alias="inventorName",
        description="Designer name(s) — KIPRIS uses 'inventor' field for designers",
    )
    agent_name: str | None = Field(
        default=None,
        alias="agentName",
        description="Design agent / attorney name",
    )

    # --- Date validators ----------------------------------------------
    @field_validator(
        "application_date",
        "registration_date",
        mode="before",
    )
    @classmethod
    def _coerce_date(cls, value: Any) -> Any:
        return _parse_kipris_date(value)

    # --- String validators (empty → None) -----------------------------
    @field_validator(
        "application_number",
        "registration_number",
        "register_status",
        "article_name",
        "drawing",
        "loc_code",
        "applicant_name",
        "inventor_name",
        "agent_name",
        mode="before",
    )
    @classmethod
    def _coerce_empty(cls, value: Any) -> Any:
        return _empty_str_to_none(value)


__all__ = [
    "PatentUtilityRow",
    "TrademarkRow",
    "DesignRow",
]
