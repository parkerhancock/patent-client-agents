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
  Python attributes are snake_case (``application_number``). Rows
  subclass the shared ``ApiModel``, which generates the camelCase
  aliases, with ``model_config = ConfigDict(populate_by_name=True,
  extra="ignore")``.
* **Optional everywhere**: every field defaults to ``None`` — KIPRIS
  rows are very sparse, especially across the patent/utility/design/
  trademark life cycle (e.g. ``registerNumber`` is empty until grant,
  ``openNumber`` is empty for non-published apps, etc.).
* **Date parsing**: KIPRIS dates arrive as ``YYYYMMDD`` 8-digit strings
  (sometimes ``YYYY-MM-DD``). The shared ``IsoDate`` type
  coerces both forms (and empty strings) to ``date | None``.
* **Codes**: classification codes (IPC, Nice, Vienna, Locarno) and
  status flags are kept as strings — KIPRIS sometimes returns multiple
  semicolon-separated values in a single element.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field

from patent_client_agents.shared.models import ApiModel, EmptyStrNone, IsoDate


class _KiprisRowBase(ApiModel):
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
    application_number: EmptyStrNone = Field(
        default=None, description="Application number (e.g. '1020230012345')"
    )
    application_date: IsoDate = Field(default=None, description="Filing date")
    publication_number: EmptyStrNone = Field(
        default=None, description="Granted-patent publication number"
    )
    publication_date: IsoDate = Field(default=None, description="Granted-patent publication date")
    open_number: EmptyStrNone = Field(
        default=None, description="KOKAI / laid-open (pre-grant) publication number"
    )
    open_date: IsoDate = Field(default=None, description="KOKAI laid-open publication date")
    register_number: EmptyStrNone = Field(
        default=None, description="Registration number (post-grant)"
    )
    register_date: IsoDate = Field(default=None, description="Registration date (post-grant)")
    register_status: EmptyStrNone = Field(
        default=None,
        description=(
            "Registration status flag — one of '등록' (registered), '소멸' "
            "(extinguished), '공개' (published), '출원' (filed), etc."
        ),
    )

    # --- Title / abstract ---------------------------------------------
    invention_title: EmptyStrNone = Field(default=None, description="Invention title (Korean)")
    invention_title_english: EmptyStrNone = Field(
        default=None, description="Invention title (English machine translation)"
    )
    astrt_cont: EmptyStrNone = Field(default=None, description="Abstract content (Korean)")

    # --- Parties -------------------------------------------------------
    applicant_name: EmptyStrNone = Field(
        default=None, description="Applicant name(s) — may be semicolon-delimited"
    )
    inventor_name: EmptyStrNone = Field(
        default=None, description="Inventor name(s) — may be semicolon-delimited"
    )
    agent_name: EmptyStrNone = Field(default=None, description="Patent agent / attorney name")

    # --- Classification ------------------------------------------------
    ipc_number: EmptyStrNone = Field(
        default=None, description="IPC classification code(s) — may be semicolon-delimited"
    )


class TrademarkRow(_KiprisRowBase):
    """One row from ``trademarkInfoSearchService`` (Trademarks).

    Trademark records carry image URLs (``big_drawing``) plus Nice
    (goods/services) and Vienna (figurative-element) classification
    codes. The mark text itself is in ``title`` (KIPRIS convention,
    not to be confused with patent ``inventionTitle``).
    """

    # --- Identifiers ---------------------------------------------------
    application_number: EmptyStrNone = Field(default=None, description="Application number")
    application_date: IsoDate = Field(default=None, description="Filing date")
    registration_number: EmptyStrNone = Field(default=None, description="Registration number")
    registration_date: IsoDate = Field(default=None, description="Registration date")
    registration_public_number: EmptyStrNone = Field(
        default=None, description="Registration publication (gazette) number"
    )

    # --- Mark content -------------------------------------------------
    title: EmptyStrNone = Field(
        default=None,
        description="Mark text (the trademark itself)",
    )
    big_drawing: EmptyStrNone = Field(
        default=None,
        description=(
            "URL to the high-resolution mark image hosted on KIPRIS (empty for word-only marks)"
        ),
    )

    # --- Classification ------------------------------------------------
    classification_code: EmptyStrNone = Field(
        default=None,
        description=(
            "Nice classification code(s) for goods/services — may be "
            "semicolon-delimited (e.g. '09;42')"
        ),
    )
    vienna_code: EmptyStrNone = Field(
        default=None,
        description=(
            "Vienna figurative-element classification code(s) — may be semicolon-delimited"
        ),
    )

    # --- Parties -------------------------------------------------------
    applicant_name: EmptyStrNone = Field(default=None, description="Applicant name(s)")
    agent_name: EmptyStrNone = Field(default=None, description="Trademark agent / attorney name")
    reg_privilege_name: EmptyStrNone = Field(
        default=None, description="Current rights-holder (registered proprietor) name"
    )


class DesignRow(_KiprisRowBase):
    """One row from ``designInfoSearchService`` (Designs).

    Design records carry the article-name (the product the design is
    applied to), a Locarno classification code, an inventor (designer)
    field, and a drawing-image URL. The ``register_status`` field
    mirrors the patent service's status convention.
    """

    # --- Identifiers ---------------------------------------------------
    application_number: EmptyStrNone = Field(default=None, description="Application number")
    application_date: IsoDate = Field(default=None, description="Filing date")
    registration_number: EmptyStrNone = Field(default=None, description="Registration number")
    registration_date: IsoDate = Field(default=None, description="Registration date")
    register_status: EmptyStrNone = Field(
        default=None,
        description=(
            "Registration status flag — one of '등록' (registered), '소멸' "
            "(extinguished), '공개' (published), '출원' (filed), etc."
        ),
    )

    # --- Article / drawing --------------------------------------------
    article_name: EmptyStrNone = Field(
        default=None, description="Name of the article the design is applied to"
    )
    drawing: EmptyStrNone = Field(
        default=None,
        description="URL to the design drawing/image hosted on KIPRIS",
    )

    # --- Classification ------------------------------------------------
    loc_code: EmptyStrNone = Field(
        default=None,
        description=("Locarno design classification code(s) — may be semicolon-delimited"),
    )

    # --- Parties -------------------------------------------------------
    applicant_name: EmptyStrNone = Field(default=None, description="Applicant name(s)")
    inventor_name: EmptyStrNone = Field(
        default=None, description="Designer name(s) — KIPRIS uses 'inventor' field for designers"
    )
    agent_name: EmptyStrNone = Field(default=None, description="Design agent / attorney name")


__all__ = [
    "PatentUtilityRow",
    "TrademarkRow",
    "DesignRow",
]
