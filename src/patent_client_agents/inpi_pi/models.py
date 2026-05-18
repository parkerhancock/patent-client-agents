"""Pydantic v2 row models for INPI France TM (ST.66 v1.0) + Design (ST.86 v1.0).

INPI France ``api-gateway.inpi.fr`` returns WIPO-standard notices: ST.66
v1.0 for trademarks (``/services/apidiffusion/api/marques/notice/...``)
and ST.86 v1.0 for designs
(``/services/apidiffusion/api/modeles/notice/...``). The search
endpoints (``/marques/search``, ``/modeles/search``) return a JSON
envelope by default (``Accept: application/json``); per the INPI tech
doc, the XML representation of each row mirrors the same element names.
The element names INPI uses are **PascalCase** ST.66/ST.86 names
(``ApplicationNumber``, ``Mark``, ``ClassNumber``,
``DesignApplicationNumber``, ``DesignTitle``, …), **not** generic
camelCase. We preserve those as Field aliases and expose Python
snake_case attributes.

Primary-source field discovery
------------------------------
Field lists are hand-curated from INPI primary-source documentation
fetched 2026-05-17 (no live API access in v1 — credentials require a
French ``data.inpi.fr`` account and chunk 4 falls back to synthesized
fixtures; see spec §6 open item):

* INPI Documentation Technique API PI v1.0 (PDF, 670 KB) —
  https://www.inpi.fr/sites/default/files/Inpi_doc_tech_API_PI_v1.0_0.pdf
  Sections §5 (API Marques) + §6 (API Dessins et Modèles): default
  ``fields`` lists for search responses, plus the SolR Lucene search
  index names — both reveal the actual element names INPI uses in the
  notice payloads.
* INPI Doc Technique « Dessins & Modèles français » v1.3 (PDF, 180 KB) —
  https://www.inpi.fr/sites/default/files/doctech_dmfr_v1_3_.pdf
  Section §3.C "Balises utilisées" — full enumeration of the ST.86
  element tree INPI emits: ``DesignApplicationDetails``,
  ``DesignDetails``, ``DesignRepresentationSheetDetails``,
  ``IndicationProductDetails``, ``DesignRecordDetails``,
  ``RelatedApplicationDetails``, ``PriorityDetails``,
  ``ApplicantDetails``, ``RepresentativeDetails`` — with
  ``ClassificationKindCode = Locarno`` for design classification.
* WIPO ST.66 / ST.86 standard pages were fetched but resolved to SPA
  shells (~12 KB each, identical JS bundles) and provided no usable
  content; ST.66 trademark field choice below relies on the INPI
  search-result default ``fields`` list (``ApplicationNumber``,
  ``Mark``, ``ClassNumber``, ``MarkCurrentStatusCode``,
  ``ApplicantIdentifier``, ``DEPOSANT``, ``DEPOTIT``,
  ``Representative_LastName``, ``ApplicationDate``, ``ExpiryDate``)
  combined with the ST.66 standard field set documented in the INPI
  tech doc §5 and the ``inpi_france.md`` detail survey.

Conventions
-----------
* **Aliases**: INPI element names use PascalCase (e.g.
  ``ApplicationNumber``); Python attributes are snake_case
  (``application_number``) with ``Field(alias="ApplicationNumber")``
  and ``model_config = ConfigDict(populate_by_name=True,
  extra="ignore")``. Chunk-3 client normalizes the (rarer)
  XML-element path through an XML→dict adapter before constructing
  rows, so a single alias suffices.
* **Optional everywhere**: every field defaults to ``None`` — INPI
  notices are sparse across lifecycle stages (e.g.
  ``RegistrationNumber`` empty pre-grant; ``ExpiryDate`` empty for
  lapsed marks).
* **Date parsing**: INPI emits dates as ``YYYY-MM-DD`` ISO 8601 in
  JSON responses and ``YYYYMMDD`` in XML notices. The
  ``_parse_iso_date`` validator accepts both forms (and empty
  strings) and coerces to ``date | None``.
* **Repeated fields**: ST.66/ST.86 elements like ``ApplicantDetails``
  and ``IndicationProductDetails/ClassDescription`` are inherently
  multi-row. We flatten them to ``list[str]`` (names / classes) and
  ``list[dict[str, str | None]]`` (priorities). The full structured
  objects remain reachable through the raw search/notice payload via
  the chunk-3 client's lean/full toggle.
* **Forward compat**: ``extra="ignore"`` — INPI occasionally adds
  fields, and we don't want unknown elements to raise validation
  errors. The spec §6 open issue notes field exhaustiveness depends
  on cassette validation in chunk 4 once credentials are available.

No patent model
---------------
**Per spec §3, NO ``InpiPatentRow`` class is defined.** FR patent
coverage is provided by ``patent_client_agents.epo_ops`` (country
code FR), which covers EP-routed FR designations and FR national-route
filings via INPADOC with adequate fidelity. The module-level docstring
in ``__init__.py`` documents this substitution.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _parse_iso_date(value: Any) -> date | None:
    """Coerce INPI date strings to ``date``.

    Accepted forms:

    * ``"2024-03-15"`` — ISO 8601 (default JSON response format)
    * ``"20240315"`` — 8-digit (XML notice format and SolR query format)
    * ``""`` / ``None`` / whitespace → ``None``
    * Already-parsed ``date`` / ``datetime`` → ``date`` (passthrough)
    * ``"00000000"`` or other sentinel-for-unknown → ``None``

    Anything else is returned as ``None`` rather than raising — INPI
    occasionally emits sentinel strings for "unknown" dates, and we
    treat all such cases as missing data.
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
    # ISO 8601 first (JSON default)
    try:
        return date.fromisoformat(cleaned)
    except ValueError:
        pass
    # 8-digit YYYYMMDD (XML notices)
    if len(cleaned) == 8 and cleaned.isdigit():
        try:
            return datetime.strptime(cleaned, "%Y%m%d").date()
        except ValueError:
            return None
    return None


def _empty_str_to_none(value: Any) -> Any:
    """Coerce empty/whitespace strings to ``None`` for ``Optional[str]`` fields.

    INPI regularly emits empty XML elements (``<Mark></Mark>``) for
    missing fields rather than omitting them, which would otherwise
    leave us with ``""`` instead of ``None``.
    """
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _coerce_to_list(value: Any) -> Any:
    """Coerce scalars / None to lists for repeated-element fields.

    INPI's XML representation collapses single-occurrence repeated
    elements (e.g. ``<ClassNumber>9</ClassNumber>`` appearing once)
    into a scalar via :func:`InpiPiClient._xml_to_dict`. The same
    field is a JSON array (``["9", "42"]``) in the JSON envelope.
    Empty XML elements (``<HolderName></HolderName>``) come through
    as ``None`` and must round-trip to ``[]``. We normalize all three
    shapes — scalar / None / list — to a list so the row models stay
    one-shape on the Python side.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


class _InpiRowBase(BaseModel):
    """Shared config for INPI row models.

    ``extra="ignore"`` is critical: INPI occasionally adds fields to
    notices (especially ST.66/ST.86 minor-version bumps) and we don't
    want unknown elements to raise validation errors.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


# =============================================================================
# Trademark — ST.66 v1.0
# =============================================================================


class InpiTrademarkRow(_InpiRowBase):
    """One row from ``marques/search`` or ``marques/notice/{n}`` (ST.66 v1.0).

    Bibliographic fields cover application, publication, and
    registration phases — most fields are populated at different
    lifecycle stages and remain empty until then. INPI element names
    follow the WIPO ST.66 PascalCase convention; we preserve those as
    aliases.

    INID codes are noted where applicable (WIPO ST.9):
        * 111 - Registration number
        * 151 - Registration date
        * 156 - Expiry date
        * 220 - Application number / filing date
        * 300 - Priority data (foreign filing)
        * 442 - Publication of application
        * 511 - Nice classification
        * 540 - Reproduction of the mark
        * 550 - Indication relating to nature/kind of mark
        * 561 - Vienna classification
        * 730 - Name of applicant
        * 740 - Name of representative/agent
    """

    # --- Identifiers (INID 220, 111) ----------------------------------
    application_number: str | None = Field(
        default=None,
        alias="ApplicationNumber",
        description="National application number, e.g. '4216963' (INID 220)",
    )
    application_date: date | None = Field(
        default=None,
        alias="ApplicationDate",
        description="Filing date (INID 220 date)",
    )
    registration_number: str | None = Field(
        default=None,
        alias="RegistrationNumber",
        description="Registration number once granted (INID 111)",
    )
    registration_date: date | None = Field(
        default=None,
        alias="RegistrationDate",
        description="Registration date (INID 151)",
    )
    expiry_date: date | None = Field(
        default=None,
        alias="ExpiryDate",
        description="Expiry / next-renewal-deadline date (INID 156)",
    )
    publication_date: date | None = Field(
        default=None,
        alias="PublicationDate",
        description="Publication-of-application date (INID 442 date)",
    )

    # --- Mark representation (INID 540, 550) --------------------------
    mark_text: str | None = Field(
        default=None,
        alias="Mark",
        description=(
            "Verbal element of the mark (INID 540) — INPI emits this "
            "as ``Mark`` for both word marks and figurative marks "
            "with text; figurative-only marks may have an empty value"
        ),
    )
    mark_image_url: str | None = Field(
        default=None,
        alias="MarkImageURI",
        description=(
            "URL to figurative reproduction (INID 540) — populated for "
            "(semi-)figurative marks; resolves to "
            "``/marques/image/{appl_no}/std`` on the INPI API gateway"
        ),
    )
    kind_of_mark: str | None = Field(
        default=None,
        alias="KindMark",
        description=(
            "Kind of mark (INID 550): Individual / Collective / "
            "Certification / Three-Dimensional / Sound / Hologram / "
            "Position / Motion / etc."
        ),
    )

    # --- Classification (INID 511, 561) -------------------------------
    nice_classes: list[str] = Field(
        default_factory=list,
        alias="ClassNumber",
        description=(
            "Nice classification class numbers (INID 511) — list of "
            "1-45 integer-strings; INPI may emit a single "
            "semicolon-delimited string or a JSON array depending on "
            "endpoint"
        ),
    )
    vienna_codes: list[str] = Field(
        default_factory=list,
        alias="ViennaClass",
        description=(
            "Vienna classification codes (INID 561) — figurative-element "
            "codes, dot-separated (e.g. '03.07.17'); empty for "
            "word marks"
        ),
    )

    # --- Parties (INID 730, 740) --------------------------------------
    applicant_names: list[str] = Field(
        default_factory=list,
        alias="ApplicantName",
        description=(
            "Applicant name(s) (INID 730) — INPI element ``DEPOSANT`` "
            "in some surfaces; may be multiple"
        ),
    )
    holder_names: list[str] = Field(
        default_factory=list,
        alias="HolderName",
        description=(
            "Current holder name(s) (INID 732) — ``DEPOTIT`` in INPI "
            "search index; populated when ownership has transferred "
            "from the original applicant"
        ),
    )
    agent_name: str | None = Field(
        default=None,
        alias="RepresentativeName",
        description=(
            "Representative / agent name (INID 740) — ``MANDATAIRE`` / "
            "``Representative_LastName`` in INPI search index"
        ),
    )

    # --- Priority (INID 300/320) --------------------------------------
    priority_claims: list[dict[str, str | None]] = Field(
        default_factory=list,
        alias="PriorityDetails",
        description=(
            "Priority claims (INID 300/320) — list of dicts with "
            "``country`` (ST.3 code), ``number``, ``date`` (ISO). "
            "Empty when no foreign priority is claimed"
        ),
    )

    # --- Status (INID 442 related) ------------------------------------
    status: str | None = Field(
        default=None,
        alias="MarkCurrentStatusCode",
        description=(
            "Current mark status — INPI emits values like 'registered', "
            "'filed', 'opposed', 'lapsed', 'expired', 'withdrawn'. The "
            "exact controlled vocabulary is INPI-specific and not yet "
            "validated against live responses (spec §6 open item)"
        ),
    )

    # --- Date validators ----------------------------------------------
    @field_validator(
        "application_date",
        "registration_date",
        "expiry_date",
        "publication_date",
        mode="before",
    )
    @classmethod
    def _coerce_date(cls, value: Any) -> Any:
        return _parse_iso_date(value)

    # --- String validators (empty → None) -----------------------------
    @field_validator(
        "application_number",
        "registration_number",
        "mark_text",
        "mark_image_url",
        "kind_of_mark",
        "agent_name",
        "status",
        mode="before",
    )
    @classmethod
    def _coerce_empty(cls, value: Any) -> Any:
        return _empty_str_to_none(value)

    # --- List validators (scalar/None → list) -------------------------
    @field_validator(
        "nice_classes",
        "vienna_codes",
        "applicant_names",
        "holder_names",
        "priority_claims",
        mode="before",
    )
    @classmethod
    def _coerce_list_field(cls, value: Any) -> Any:
        return _coerce_to_list(value)


# =============================================================================
# Design — ST.86 v1.0
# =============================================================================


class InpiDesignRow(_InpiRowBase):
    """One row from ``modeles/search`` or ``modeles/notice/{n}`` (ST.86 v1.0).

    INPI ST.86 v1.0 element names per the INPI "Dessins & Modèles
    français" tech doc v1.3 §3.C "Balises utilisées". An INPI design
    *application* (``DesignApplicationDetails``) may contain up to 100
    individual *designs* (``DesignDetails``), each with multiple
    *reproductions*/views (``DesignRepresentationSheetDetails``). This
    row represents a single design within an application — the
    ``application_number`` repeats across sibling designs sharing the
    same deposit, while ``design_reference`` distinguishes them.

    INID codes (WIPO ST.80 for designs):
        * 11 - Registration number
        * 18 - Expected expiry date
        * 21 - Application number
        * 22 - Application date
        * 30/31/32 - Priority data
        * 45 - Publication date
        * 51 - Locarno classification
        * 54 - Title indication of product
        * 57 - Reproduction(s) of the design
        * 71 - Applicant name
        * 72 - Designer name (creator)
        * 74 - Representative / agent
    """

    # --- Identifiers (INID 21, 11, 22) --------------------------------
    application_number: str | None = Field(
        default=None,
        alias="DesignApplicationNumber",
        description=(
            "National application / deposit number (INID 21) — e.g. "
            "'FR20140182'. One application may contain up to 100 "
            "individual designs"
        ),
    )
    design_reference: str | None = Field(
        default=None,
        alias="DesignReference",
        description=(
            "Per-design reference within the application (typically "
            "001-100). Distinguishes sibling designs sharing one "
            "``application_number``"
        ),
    )
    application_date: date | None = Field(
        default=None,
        alias="DesignApplicationDate",
        description="Filing date (INID 22)",
    )
    registration_number: str | None = Field(
        default=None,
        alias="RegistrationNumber",
        description=(
            "Registration number (INID 11) — for FR designs registered "
            "post-application; legacy filings may reuse the application "
            "number"
        ),
    )
    registration_date: date | None = Field(
        default=None,
        alias="RegistrationDate",
        description="Registration date (INID 11 date)",
    )
    expiry_date: date | None = Field(
        default=None,
        alias="ExpiryDate",
        description=(
            "Expected expiry date (INID 18) — for designs filed on or "
            "after 1 October 2001, this is the next renewal deadline; "
            "may be extended 4 × 5 years to a 25-year maximum"
        ),
    )
    publication_date: date | None = Field(
        default=None,
        alias="PublicationDate",
        description="Publication date (INID 45) — BOPI publication",
    )

    # --- Title / representation (INID 54, 57) -------------------------
    design_title: str | None = Field(
        default=None,
        alias="DesignTitle",
        description=(
            "Indication of product / design title (INID 54) — French "
            "by default; non-FR designs (Hague WO route) may include "
            "multilingual titles which v1 takes the FR variant of"
        ),
    )
    image_urls: list[str] = Field(
        default_factory=list,
        alias="DesignRepresentationSheetURIs",
        description=(
            "URLs to design reproductions / views (INID 57) — one "
            "design may have multiple views (per "
            "``ViewSequenceNumber`` / ``ViewNumber`` in ST.86); "
            "resolves to ``/modeles/image/{appl_no}/{design}/{view}/"
            "std`` on the INPI API gateway"
        ),
    )

    # --- Classification (INID 51) -------------------------------------
    loc_classes: list[str] = Field(
        default_factory=list,
        alias="ClassNumber",
        description=(
            "Locarno classification codes (INID 51) — INPI uses "
            "``ClassificationKindCode='Locarno'``; values are "
            "4-digit (e.g. '0701') or 2-digit class only (e.g. '07')"
        ),
    )

    # --- Parties (INID 71, 72, 74) ------------------------------------
    applicant_names: list[str] = Field(
        default_factory=list,
        alias="ApplicantName",
        description=(
            "Applicant / depositor name(s) (INID 71) — INPI element "
            "``DEPOSANT`` in some surfaces; ``ApplicantDetails`` in "
            "ST.86 notice XML"
        ),
    )
    holder_names: list[str] = Field(
        default_factory=list,
        alias="HolderName",
        description=(
            "Current holder name(s) — ``DEPOTIT`` in INPI search "
            "index; populated when ownership has transferred"
        ),
    )
    designer_names: list[str] = Field(
        default_factory=list,
        alias="DesignerName",
        description=(
            "Designer / creator name(s) (INID 72) — INPI does NOT "
            "always populate this; ST.86 allows the field but FR "
            "national filings frequently omit it"
        ),
    )
    agent_name: str | None = Field(
        default=None,
        alias="RepresentativeName",
        description=("Representative / agent name (INID 74) — ``MANDATAIRE`` in INPI search index"),
    )

    # --- Priority (INID 30/31/32) -------------------------------------
    priority_claims: list[dict[str, str | None]] = Field(
        default_factory=list,
        alias="PriorityDetails",
        description=(
            "Priority claims (INID 30/31/32) — list of dicts with "
            "``country`` (ST.3 code), ``number``, ``date`` (ISO), "
            "and optional ``holder_name``. Empty when no foreign "
            "priority is claimed"
        ),
    )

    # --- Status (INID 18 related) -------------------------------------
    status: str | None = Field(
        default=None,
        alias="DesignCurrentStatusCode",
        description=(
            "Current design status — INPI emits values like "
            "'registered', 'published', 'lapsed', 'expired', "
            "'renounced'. Controlled vocabulary is INPI-specific and "
            "not yet validated against live responses (spec §6 open "
            "item)"
        ),
    )

    # --- Date validators ----------------------------------------------
    @field_validator(
        "application_date",
        "registration_date",
        "expiry_date",
        "publication_date",
        mode="before",
    )
    @classmethod
    def _coerce_date(cls, value: Any) -> Any:
        return _parse_iso_date(value)

    # --- String validators (empty → None) -----------------------------
    @field_validator(
        "application_number",
        "design_reference",
        "registration_number",
        "design_title",
        "agent_name",
        "status",
        mode="before",
    )
    @classmethod
    def _coerce_empty(cls, value: Any) -> Any:
        return _empty_str_to_none(value)

    # --- List validators (scalar/None → list) -------------------------
    @field_validator(
        "image_urls",
        "loc_classes",
        "applicant_names",
        "holder_names",
        "designer_names",
        "priority_claims",
        mode="before",
    )
    @classmethod
    def _coerce_list_field(cls, value: Any) -> Any:
        return _coerce_to_list(value)


__all__ = [
    "InpiTrademarkRow",
    "InpiDesignRow",
]
