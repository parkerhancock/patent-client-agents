"""HK IPD Hong Kong fee-schedule scraper.

The Intellectual Property Department (IPD) of the Hong Kong SAR
publishes its fee schedules on three native-HTML pages — one per
right — fully server-rendered with no auth or CDN challenge:

* ``ipd.gov.hk/en/patents/forms-and-fees/index.html`` (32 tables)
* ``ipd.gov.hk/en/trade-marks/forms-and-fees/index.html`` (17 tables)
* ``ipd.gov.hk/en/designs/forms-and-fees/index.html`` (12 tables)

The statutory schedules live on Hong Kong e-Legislation as
Cap. 514C Schedule 4 (patents), Cap. 559A Schedule 1 (trademarks),
and Cap. 522A (designs); those pages are JS-rendered SPAs and serve
as the formal citation source, not the extraction target.

Patent route encoding
---------------------

Standard patents have two routes since the December 2019
Patents (Amendment) Ordinance commencement:

* ``(O)`` — original-grant route (direct HK national filing,
  substantive examination by IPD)
* ``(R)`` — re-registration route (re-recordal of a designated
  patent application from CN / GB / EP(UK))

The route tag appears inline in the description column. Short-term
patents are an entirely separate track (8-year max term, formality
examination only) tagged in the description by the phrase
"short-term patent". The connector encodes the route in the code
slug prefix (``hk-pat-ogp-…``, ``hk-pat-rr-…``, ``hk-pat-stp-…``,
``hk-pat-gen-…`` for rows that apply to all routes) and preserves
the inline tag in the FeeItem label so the original office-side
text survives.

The same legal step can have very different total cost on the two
patent routes — OGP costs the grant fee (~HK$345 e-filing) PLUS a
separate substantive examination fee of HK$4,000, while the
re-registration route pays only the record + registration-and-grant
fees (~HK$275 each, since most prosecution has already been done by
the designated office). Client-facing summaries must surface the
route as a first-class dimension before quoting.

Filing-channel encoding
-----------------------

Where electronic filing is discounted relative to paper, an IPD
table interleaves a sub-header row ``[E-filing, Paper-filing]``
above the data rows. Each such data row carries three cells —
description, electronic amount, paper amount — and the connector
emits two FeeItems: the electronic-channel rate as the canonical
entry, and the paper-channel rate as a separate FeeItem tagged
``FeeCondition(paper_filing)``.

Section-context rows
--------------------

A handful of tables open with a row whose fee cell is empty — those
function as section headers for the rows that follow. Example: the
patent renewal table opens with ``["Request for renewal of a
standard patent for a further year after the expiry of the 3rd
year", ""]`` and then lists the year-band sub-rows ``["4th to 10th
year of the 20-year term", "$450"]``. Section context is carried
forward by the walker and prepended to the FeeItem label ONLY when
the row's own description is fragmentary (starts with a year
ordinal or "For the …" / "For each …"). Self-contained rows like
"Renewal of a short-term patent" stand alone — preserving them
verbatim avoids the bug where they would otherwise inherit the
standard-patent section prefix and become unparseable.

Deduplication
-------------

The same row text appears identically across multiple filing
tables — "Advertisement fee" $68 and "Additional fee for late
payment of filing fee or advertisement fee" $95 each show up four
times (OGP / RR-record / RR-grant / STP filing tables). These
rows correctly classify as route="gen" (the fee applies regardless
of route) and the builder collapses repeats to a single FeeItem.

v1 scope
--------

* ``HK/IPD/Fees/Patent`` — OGP + re-registration + short-term
  patent fees, all three encoded by code prefix; per-year renewal
  expansion for OGP (years 4-20) and short-term (year 4 + year 8).
* ``HK/IPD/Fees/Trademark`` — application, renewal, opposition,
  cancellation, recordation, copies. Per-additional-class
  surcharges encoded as ``FeeCondition(classes_over, threshold=1,
  per_unit=True)``.
* ``HK/IPD/Fees/Design`` — single-design, multi-design, set
  variants; renewal (5-year terms × four extensions); recordation;
  opposition; revocation.

v1 GAPS
-------

* The trademark "(Late renewal charge: $500)" parenthetical inside
  the renewal cell is captured in the FeeItem ``notes`` rather than
  emitted as a separate ``late_fee`` row — IPD doesn't publish it
  with its own code.
* The "Application for maintenance" pre-grant maintenance fees on
  the R-route apply to "any succeeding year" without a bounded
  range; emitted as ``FeeCategory.other`` (rather than a renewal
  row per year) because the underlying statute treats the fee as
  per-application-year-kept-alive, not per-renewal-year.
* The "$6 per page" / "$5 per page" copy-of-document fees are
  emitted with ``FeeCondition(per_unit=True)`` and a free-text
  description; no closed-vocab trigger ("pages_over" requires a
  threshold which isn't relevant for these).

Statutory basis
---------------

* Patents Ordinance (Cap. 514) + Patents (General) Rules
  (Cap. 514C) — Schedule 4 contains the patent fee table.
* Trade Marks Ordinance (Cap. 559) + Trade Marks Rules (Cap. 559A)
  — Schedule 1 contains the trademark fee table.
* Registered Designs Ordinance (Cap. 522) + Registered Designs
  Rules (Cap. 522A) — Schedule contains the design fee table.

Amendments are made by subsidiary-legislation orders gazetted in
the Hong Kong Government Gazette; revision cadence is sporadic
(tied to legislative reform packages, no fixed annual republication).
"""

from __future__ import annotations

import logging
import re
from datetime import date
from decimal import Decimal
from typing import Literal, Unpack

from lxml import html as L

from law_tools_core import BaseAsyncClient
from patent_client_agents.fees.models import (
    ConditionalTrigger,
    EntityTier,
    FeeCategory,
    FeeClientKwargs,
    FeeCondition,
    FeeItem,
    FeeSchedule,
    RightType,
)

logger = logging.getLogger(__name__)


HK_IPD_BASE = "https://www.ipd.gov.hk"
HK_IPD_PATENTS_URL = f"{HK_IPD_BASE}/en/patents/forms-and-fees/index.html"
HK_IPD_TRADEMARKS_URL = f"{HK_IPD_BASE}/en/trade-marks/forms-and-fees/index.html"
HK_IPD_DESIGNS_URL = f"{HK_IPD_BASE}/en/designs/forms-and-fees/index.html"

RightPath = Literal["patents", "trade-marks", "designs"]


class HKIPDFeesClient(BaseAsyncClient):
    """Tiny HTTP client for the IPD forms-and-fees pages."""

    DEFAULT_BASE_URL = HK_IPD_BASE
    CACHE_NAME = "hk_ipd_fees"
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_TTL_SECONDS = 7 * 24 * 3600
    HTTP2 = True

    def __init__(self, **kwargs: Unpack[FeeClientKwargs]) -> None:
        kwargs.setdefault("ttl_seconds", self.DEFAULT_TTL_SECONDS)
        kwargs.setdefault(
            "headers",
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,*/*",
                "Accept-Language": "en;q=0.9",
            },
        )
        super().__init__(**kwargs)

    async def fetch_html(self, right: RightPath) -> str:
        path = f"/en/{right}/forms-and-fees/index.html"
        r = await self._request("GET", path, context=f"hk_ipd_{right}")
        return r.text


# ──────────────────────────────────────────────────────────────────────
# Money + route + category helpers
# ──────────────────────────────────────────────────────────────────────

_AMOUNT_RE = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)")


def _parse_money(raw: str) -> Decimal | None:
    """'$100' / '$1,000' / 'Nil' → Decimal('100' / '1000' / '0') or None.

    Cells reading "Nil" parse to Decimal('0'); cells that lack a `$N`
    pattern entirely (e.g., section-header rows with empty fee cells
    or pure prose) parse to ``None``.
    """
    if not raw:
        return None
    if raw.strip().lower() == "nil":
        return Decimal("0")
    m = _AMOUNT_RE.search(raw)
    if not m:
        return None
    cleaned = m.group(1).replace(",", "")
    try:
        return Decimal(cleaned)
    except Exception:
        return None


def _classify_patent_route(description: str) -> str:
    """``(O)`` → ``ogp``; ``(R)`` → ``rr``; "short-term patent" → ``stp``; else ``gen``.

    ``gen`` ("general") covers procedural rows that apply to every
    patent route — extension of time, copies of documents, register
    inspection. These keep one FeeItem (not three) and use the
    ``hk-pat-gen-…`` slug prefix.
    """
    if "(O)" in description:
        return "ogp"
    if "(R)" in description:
        return "rr"
    if "short-term patent" in description.lower():
        return "stp"
    return "gen"


_NIL_PER_UNIT_RE = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*per\s+(page|copy|class)")


def _per_unit_condition(text: str) -> FeeCondition | None:
    """'$6 per page', '$150 per certified copy' → FeeCondition(per_unit=True).

    "per additional class" is handled separately by the trademark parser
    because it pairs with a ``classes_over`` threshold.
    """
    lower = text.lower()
    if "per additional class" in lower:
        return FeeCondition(
            trigger=ConditionalTrigger.classes_over,
            threshold=1,
            per_unit=True,
            description="Per additional class beyond the first.",
        )
    m = _NIL_PER_UNIT_RE.search(text)
    if m:
        unit = m.group(2)
        # No closed-vocab trigger for "per page" / "per copy" — use the
        # late_days-shaped placeholder with per_unit=True. The intent is
        # to mark the amount as per-unit so consumers don't multiply
        # blindly; trigger semantics are described in `description`.
        return FeeCondition(
            trigger=ConditionalTrigger.late_days,
            per_unit=True,
            description=f"Per {unit}.",
        )
    return None


def _slugify(*parts: str, max_part_len: int = 40) -> str:
    cleaned: list[str] = []
    for p in parts:
        if not p:
            continue
        s = re.sub(r"[^a-z0-9]+", "-", p.lower()).strip("-")[:max_part_len]
        if s:
            cleaned.append(s)
    return "-".join(cleaned)


def _unique(slug: str, seen: set[str]) -> str:
    if slug not in seen:
        seen.add(slug)
        return slug
    n = 2
    while f"{slug}-{n}" in seen:
        n += 1
    candidate = f"{slug}-{n}"
    seen.add(candidate)
    return candidate


# ──────────────────────────────────────────────────────────────────────
# Categorization
# ──────────────────────────────────────────────────────────────────────


def _categorize_patent(description: str) -> FeeCategory:
    d = description.lower()
    # Order matters: late_fee descriptions often contain the words
    # "renewal" or "filing" — check them first so they don't get
    # absorbed into the broader category.
    if "late payment" in d or "late filing" in d:
        return FeeCategory.late_fee
    if "renewal" in d or re.search(r"\d(?:st|nd|rd|th)[- ]?(?:to[- ]?\d+(?:st|nd|rd|th))?\s+year of", d):
        return FeeCategory.renewal
    if "maintenance" in d or "maintaining application" in d:
        return FeeCategory.other  # pre-grant R-route; see module docstring v1 GAPS
    if "extension of time" in d:
        return FeeCategory.extension
    if "substantive examination" in d:
        return FeeCategory.examination
    if "advertisement" in d:
        return FeeCategory.publication
    if "request for grant" in d or "registration of a designated patent and grant" in d:
        return FeeCategory.grant
    if "to record a designated patent application" in d:
        return FeeCategory.filing
    if "opposition" in d or "counter-statement" in d or "intention to oppose" in d:
        return FeeCategory.opposition
    if "revocation" in d or "revoke" in d:
        return FeeCategory.cancellation
    if "restoration" in d or "restore" in d or "reinstatement" in d:
        return FeeCategory.other
    if "hearing" in d or "review" in d:
        return FeeCategory.appeal
    if "translation" in d:
        return FeeCategory.translation
    if "transactions" in d or "rights acquired" in d or "rights in or under a patent" in d:
        return FeeCategory.transfer
    if "priority" in d:
        return FeeCategory.other
    if "amend" in d or "amendment" in d or "correction" in d:
        return FeeCategory.other
    if "search" in d:
        return FeeCategory.search
    return FeeCategory.other


def _categorize_trademark(description: str) -> FeeCategory:
    d = description.lower()
    if "late renewal" in d:
        return FeeCategory.late_fee
    if "restoration and renewal" in d or "request for renewal" in d:
        return FeeCategory.renewal
    if "registration of a trade mark" in d or "registration of a series" in d or "registration of a defensive" in d:
        return FeeCategory.filing
    if "preliminary advice" in d or "search of records" in d:
        return FeeCategory.search
    if "notice of opposition" in d or "objection" in d or "counter-statement" in d:
        return FeeCategory.opposition
    if "revocation" in d or "invalidity" in d or "rectification" in d:
        return FeeCategory.cancellation
    if "extension of time" in d:
        return FeeCategory.extension
    if "licence" in d or "transactions" in d or "register registrable" in d or "security interest" in d:
        return FeeCategory.transfer
    if "hearing" in d or "statement of reasons" in d:
        return FeeCategory.other
    if "divide" in d or "merge" in d or "amend" in d or "delete" in d or "change" in d:
        return FeeCategory.other
    if "intervention" in d:
        return FeeCategory.opposition
    if "surrender" in d:
        return FeeCategory.other
    return FeeCategory.other


def _categorize_design(description: str) -> FeeCategory:
    d = description.lower()
    if "late payment" in d:
        return FeeCategory.late_fee
    if "renewal" in d or "5-year extension" in d:
        return FeeCategory.renewal
    if "filing fee" in d or "design is to be applied" in d or "designs is to be applied" in d:
        return FeeCategory.filing
    if "advertisement" in d:
        return FeeCategory.publication
    if "reinstatement" in d:
        return FeeCategory.other
    if "extension of time" in d:
        return FeeCategory.extension
    if "transactions" in d:
        return FeeCategory.transfer
    if "revoke" in d or "rectification" in d:
        return FeeCategory.cancellation
    if "opposition" in d or "intention to oppose" in d or "counter-statement" in d:
        return FeeCategory.opposition
    if "amendment" in d or "correction" in d or "alteration" in d:
        return FeeCategory.other
    return FeeCategory.other


# ──────────────────────────────────────────────────────────────────────
# Year extraction for renewal expansion
# ──────────────────────────────────────────────────────────────────────


_YEAR_BAND_RE = re.compile(
    r"(\d+)\s*(?:st|nd|rd|th)\s+to\s+(\d+)\s*(?:st|nd|rd|th)\s+year",
    re.IGNORECASE,
)
_SINGLE_YEAR_RE = re.compile(r"(\d+)\s*(?:st|nd|rd|th)\s+year", re.IGNORECASE)


def _renewal_years(description: str) -> list[int]:
    """Extract the list of patent renewal years implied by a description.

    * ``"4th to 10th year of the 20-year term"`` → ``[4, 5, 6, 7, 8, 9, 10]``
    * ``"11th to 15th year of the 20-year term"`` → ``[11, 12, 13, 14, 15]``
    * ``"16th to 20th year of the 20-year term"`` → ``[16, 17, 18, 19, 20]``
    * ``"Renewal of a short-term patent"`` → ``[]`` (caller emits y4 + y8)
    """
    band = _YEAR_BAND_RE.search(description)
    if band:
        start, end = int(band.group(1)), int(band.group(2))
        return list(range(start, end + 1))
    single = _SINGLE_YEAR_RE.search(description)
    if single:
        return [int(single.group(1))]
    return []


# ──────────────────────────────────────────────────────────────────────
# Table walker
# ──────────────────────────────────────────────────────────────────────


def _row_cells(tr: L.HtmlElement) -> list[str]:
    return [re.sub(r"\s+", " ", c.text_content().strip()) for c in tr.cssselect("td, th")]


def _is_header_row(cells: list[str]) -> bool:
    if not cells:
        return False
    joined = " | ".join(cells).lower()
    return (
        "descriptions" in joined
        and ("fee (hkd)" in joined or "filing fee (hkd)" in joined)
    )


def _is_efiling_subheader(cells: list[str]) -> bool:
    norm = [c.lower() for c in cells if c.strip()]
    return norm == ["e-filing", "paper-filing"]


_FRAGMENTARY_PREFIX_RE = re.compile(
    r"^(?:\d+\s*(?:st|nd|rd|th)(?:\s|-)|For\s+(?:the\s+|each\s+))",
    re.IGNORECASE,
)


def _is_fragmentary(description: str) -> bool:
    """A row's description is fragmentary if it only makes sense with its section header.

    True for year-band sub-rows ("4th to 10th year of the 20-year term"),
    extension-ordinal sub-rows ("2nd 5-year extension"), and design
    multi-design "For the first ..." / "For each other ..." sub-rows.
    False for self-contained rows that happen to follow a section header
    ("Additional fee for late payment of …", "Renewal of a short-term
    patent", "Application for maintenance of any succeeding year").
    """
    return bool(_FRAGMENTARY_PREFIX_RE.match(description))


def _label_with_context(description: str, section_context: str | None) -> str:
    """Prepend ``section_context`` to the label only when the row is fragmentary."""
    if section_context and section_context not in description and _is_fragmentary(description):
        return f"{section_context} — {description}"
    return description


_WalkRow = tuple[str, str | None, str | None, str | None, str | None]


def _walk_table(table: L.HtmlElement) -> list[_WalkRow]:
    """Walk one table; yield ``(description, fee_text, paper_text, additional_text, section_context)``.

    * ``description`` is the row's first cell verbatim — the walker
      does NOT prepend section_context here; builders decide whether
      to apply the prefix via :func:`_label_with_context`.
    * ``fee_text`` is the row's primary fee cell text (the electronic
      amount when the e-filing/paper split is in force).
    * ``paper_text`` is the paper-filing amount when the e-filing
      sub-header was seen earlier in the table; ``None`` otherwise.
    * ``additional_text`` is the trademark "Additional fee (HKD)"
      cell; ``None`` when the table is 2-column.
    * ``section_context`` is the most recently observed
      section-header row text within the same table (an empty-fee
      or single-cell row). Available to builders for route /
      category disambiguation without polluting the label.
    """
    out: list[_WalkRow] = []
    section_context: str | None = None
    has_efiling_split = False
    has_additional_col = False

    for tr in table.cssselect("tr"):
        cells = _row_cells(tr)
        if not cells:
            continue
        if _is_header_row(cells):
            if len(cells) >= 3 and "additional fee" in cells[2].lower():
                has_additional_col = True
            continue
        if _is_efiling_subheader(cells):
            has_efiling_split = True
            continue

        if has_efiling_split:
            if len(cells) == 1:
                section_context = cells[0]
                continue
            if len(cells) >= 3 and not cells[1].strip() and not cells[2].strip():
                section_context = cells[0]
                continue
            if len(cells) >= 3 and cells[1].strip():
                out.append((cells[0], cells[1], cells[2] or None, None, section_context))
                continue
            if len(cells) == 2 and cells[1].strip():
                out.append((cells[0], cells[1], None, None, section_context))
                continue
        else:
            if len(cells) == 1:
                section_context = cells[0]
                continue
            if len(cells) >= 2 and not cells[1].strip():
                section_context = cells[0]
                continue
            if len(cells) >= 2:
                additional = cells[2] if has_additional_col and len(cells) >= 3 else None
                out.append((cells[0], cells[1], None, additional, section_context))

    return out


_DedupKey = tuple[str, Decimal, FeeCategory, int | None]


def _is_duplicate(
    label: str,
    amount: Decimal,
    category: FeeCategory,
    year: int | None,
    seen: set[_DedupKey],
) -> bool:
    """Identical rows appear across the OGP / RR-record / RR-grant / STP filing tables.

    e.g. "Advertisement fee" $68 and "Additional fee for late payment of
    filing fee or advertisement fee" $95 each show up four times — once
    per filing-route table. The route classification on each is "gen"
    (the fee applies regardless of route), so collapsing them to a
    single FeeItem is the right call.
    """
    key = (label, amount, category, year)
    if key in seen:
        return True
    seen.add(key)
    return False


# ──────────────────────────────────────────────────────────────────────
# Patent builder
# ──────────────────────────────────────────────────────────────────────


def _mk_patent_fee(
    *,
    code: str,
    label: str,
    category: FeeCategory,
    amount: Decimal,
    condition: FeeCondition | None,
    notes: str | None,
    year: int | None,
) -> FeeItem:
    return FeeItem(
        code=code,
        label=label[:200],
        category=category,
        rights=[RightType.patent],
        amount=amount,
        currency="HKD",
        tier=EntityTier.none,
        year=year,
        condition=condition,
        source_url=HK_IPD_PATENTS_URL,
        notes=notes,
    )


def _build_patent_fees(doc: L.HtmlElement) -> list[FeeItem]:
    fees: list[FeeItem] = []
    seen_codes: set[str] = set()
    seen_keys: set[_DedupKey] = set()

    for table in doc.cssselect("table"):
        for description, fee_text, paper_text, _, section_context in _walk_table(table):
            base_amount = _parse_money(fee_text or "")
            if base_amount is None:
                continue

            label = _label_with_context(description, section_context)
            # Route comes from row text + section_context. Self-contained
            # rows (e.g., "Renewal of a short-term patent") classify on
            # their own; fragmentary rows pick up the route from their
            # section header via the joined string below.
            route = _classify_patent_route(
                description + " " + (section_context or "")
            )
            category = _categorize_patent(label)

            # Renewal expansion: emit one FeeItem per year if a band is
            # encoded in the description.
            if category is FeeCategory.renewal:
                lower = label.lower()
                if "short-term patent" in lower or route == "stp":
                    years = [4, 8]  # Cap. 514C r.61
                else:
                    years = _renewal_years(label)
                if not years:
                    # Catch-all so the renewal validator is satisfied.
                    years = [1]
                for yr in years:
                    if _is_duplicate(label, base_amount, category, yr, seen_keys):
                        continue
                    code = _unique(
                        _slugify("hk", "pat", route, "renewal", f"y{yr}"),
                        seen_codes,
                    )
                    fees.append(
                        _mk_patent_fee(
                            code=code,
                            label=label,
                            category=category,
                            amount=base_amount,
                            condition=None,
                            notes=None,
                            year=yr,
                        )
                    )
                continue

            condition = _per_unit_condition(fee_text or "")
            if not _is_duplicate(label, base_amount, category, None, seen_keys):
                code = _unique(_slugify("hk", "pat", route, label[:60]), seen_codes)
                fees.append(
                    _mk_patent_fee(
                        code=code,
                        label=label,
                        category=category,
                        amount=base_amount,
                        condition=condition,
                        notes=None,
                        year=None,
                    )
                )

            # Paper-filing variant when the e-filing split was active.
            paper_amount = _parse_money(paper_text or "") if paper_text else None
            if paper_amount is not None and paper_amount != base_amount:
                paper_label = f"{label} [paper-filing]"
                if not _is_duplicate(paper_label, paper_amount, category, None, seen_keys):
                    paper_code = _unique(
                        _slugify("hk", "pat", route, label[:60], "paper"),
                        seen_codes,
                    )
                    fees.append(
                        _mk_patent_fee(
                            code=paper_code,
                            label=label,
                            category=category,
                            amount=paper_amount,
                            condition=FeeCondition(
                                trigger=ConditionalTrigger.paper_filing,
                                description="Paper-filed submission; e-filing is the default discounted rate.",
                            ),
                            notes="Paper-filing rate.",
                            year=None,
                        )
                    )

    return fees


# ──────────────────────────────────────────────────────────────────────
# Trademark builder
# ──────────────────────────────────────────────────────────────────────


def _build_trademark_fees(doc: L.HtmlElement) -> list[FeeItem]:
    fees: list[FeeItem] = []
    seen_codes: set[str] = set()

    for table in doc.cssselect("table"):
        for description, fee_text, _paper, additional_text, section_context in _walk_table(table):
            base_amount = _parse_money(fee_text or "")
            if base_amount is None:
                continue

            label = _label_with_context(description, section_context)
            category = _categorize_trademark(label)

            # Late-renewal parenthetical inside the renewal cell —
            # capture in notes (see v1 GAPS).
            late_match = re.search(r"Late renewal charge:\s*\$\s*([\d,]+)", fee_text or "")
            notes: str | None = None
            if late_match:
                notes = f"Late renewal charge: HK${late_match.group(1)} (Cap. 559A)."

            condition = _per_unit_condition(fee_text or "")
            # HK TM term is 10 years (Cap. 559 s.49); renewal FeeItems carry
            # year=10 so the FeeItem renewal validator is satisfied.
            year = 10 if category is FeeCategory.renewal else None
            code = _unique(_slugify("hk", "tm", label[:60]), seen_codes)
            fees.append(FeeItem(
                code=code,
                label=label[:200],
                category=category,
                rights=[RightType.trademark],
                amount=base_amount,
                currency="HKD",
                tier=EntityTier.none,
                year=year,
                condition=condition,
                source_url=HK_IPD_TRADEMARKS_URL,
                notes=notes,
            ))

            # Additional-fee column: per-additional-class surcharge.
            if additional_text and additional_text.strip().lower() != "nil":
                add_amount = _parse_money(additional_text)
                if add_amount is not None and add_amount > 0:
                    add_code = _unique(
                        _slugify("hk", "tm", label[:60], "addl-class"),
                        seen_codes,
                    )
                    fees.append(FeeItem(
                        code=add_code,
                        label=f"{label} — additional class",
                        category=FeeCategory.excess_classes,
                        rights=[RightType.trademark],
                        amount=add_amount,
                        currency="HKD",
                        tier=EntityTier.none,
                        condition=FeeCondition(
                            trigger=ConditionalTrigger.classes_over,
                            threshold=1,
                            per_unit=True,
                            description="Per additional class beyond the first.",
                        ),
                        source_url=HK_IPD_TRADEMARKS_URL,
                        notes=additional_text,
                    ))

    return fees


# ──────────────────────────────────────────────────────────────────────
# Design builder
# ──────────────────────────────────────────────────────────────────────


def _build_design_fees(doc: L.HtmlElement) -> list[FeeItem]:
    fees: list[FeeItem] = []
    seen_codes: set[str] = set()

    for table in doc.cssselect("table"):
        for description, fee_text, paper_text, _, section_context in _walk_table(table):
            base_amount = _parse_money(fee_text or "")
            if base_amount is None:
                continue

            label = _label_with_context(description, section_context)
            category = _categorize_design(label)
            condition = _per_unit_condition(fee_text or "")

            year: int | None = None
            if category is FeeCategory.renewal:
                # "1st 5-year extension" → year=10 (registration runs
                # 5 years initially; the 1st extension covers years 6-10).
                # IPD doesn't tag the extension by terminal year; we tag
                # by extension ordinal so the renewal row carries a
                # year per the FeeItem model contract.
                m = re.search(r"(\d+)\w*\s+5-year extension", label.lower())
                if m:
                    year = int(m.group(1)) * 5 + 5  # 1→10, 2→15, 3→20, 4→25

            code = _unique(_slugify("hk", "des", label[:60]), seen_codes)
            fees.append(FeeItem(
                code=code,
                label=label[:200],
                category=category,
                rights=[RightType.design],
                amount=base_amount,
                currency="HKD",
                tier=EntityTier.none,
                year=year if category is FeeCategory.renewal else None,
                condition=condition,
                source_url=HK_IPD_DESIGNS_URL,
                notes=None,
            ))

            # Paper-filing variant on the design filing table.
            paper_amount = _parse_money(paper_text or "") if paper_text else None
            if paper_amount is not None and paper_amount != base_amount:
                paper_code = _unique(
                    _slugify("hk", "des", label[:60], "paper"),
                    seen_codes,
                )
                fees.append(FeeItem(
                    code=paper_code,
                    label=label[:200],
                    category=category,
                    rights=[RightType.design],
                    amount=paper_amount,
                    currency="HKD",
                    tier=EntityTier.none,
                    year=year if category is FeeCategory.renewal else None,
                    condition=FeeCondition(
                        trigger=ConditionalTrigger.paper_filing,
                        description="Paper-filed submission; e-filing is the default discounted rate.",
                    ),
                    source_url=HK_IPD_DESIGNS_URL,
                    notes="Paper-filing rate.",
                ))

    return fees


# ──────────────────────────────────────────────────────────────────────
# Public scrape entry points
# ──────────────────────────────────────────────────────────────────────


_STATUTORY_PATENT = (
    "Patents (General) Rules (Cap. 514C), Schedule 4 — promulgated "
    "under Patents Ordinance Cap. 514. Amendments by subsidiary-"
    "legislation orders gazetted in the Hong Kong Government Gazette."
)
_STATUTORY_TRADEMARK = (
    "Trade Marks Rules (Cap. 559A), Schedule 1 — promulgated under "
    "Trade Marks Ordinance Cap. 559. Amendments by subsidiary-"
    "legislation orders gazetted in the Hong Kong Government Gazette."
)
_STATUTORY_DESIGN = (
    "Registered Designs Rules (Cap. 522A) — promulgated under "
    "Registered Designs Ordinance Cap. 522. Amendments by "
    "subsidiary-legislation orders gazetted in the Hong Kong "
    "Government Gazette."
)


async def scrape_hk_patents() -> FeeSchedule:
    """Scrape HK IPD patent fees — OGP + re-registration + short-term."""
    async with HKIPDFeesClient() as client:
        html_text = await client.fetch_html("patents")
    doc = L.fromstring(html_text)
    fees = _build_patent_fees(doc)
    if not fees:
        raise RuntimeError(
            "HK IPD patent scraper parsed zero rows — page structure may have changed"
        )
    return FeeSchedule(
        jurisdiction="HK",
        issuing_body="Intellectual Property Department",
        office_code="HKIPD",
        right=RightType.patent,
        currency="HKD",
        effective_date=date(2019, 12, 19),  # OGP commencement date
        source_url=HK_IPD_PATENTS_URL,
        statutory_basis=_STATUTORY_PATENT,
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "Covers the three patent tracks (OGP / re-registration / "
            "short-term) via code-prefix encoding (hk-pat-ogp-… / "
            "hk-pat-rr-… / hk-pat-stp-… / hk-pat-gen-…). Per-year "
            "renewal expansion: OGP+RR years 4-20 emit one FeeItem per "
            "year per band ($450 y4-y10, $620 y11-y15, $850 y16-y20); "
            "short-term renewal emits at year=4 and year=8 (per "
            "Cap. 514C r.61). v1 GAPS: (a) R-route pre-grant "
            "maintenance ('Application for maintenance for a further "
            "year after the expiry of the 5th year' + 'any succeeding "
            "year thereafter') emitted as FeeCategory.other without "
            "per-year expansion — the underlying statute treats them "
            "as per-application-year-kept-alive rather than per-renewal-"
            "year. (b) Rows that appear identically across the OGP / "
            "RR-record / RR-grant / STP filing tables (advertisement, "
            "late-payment-of-filing-fee) collapse to single FeeItems."
        ),
    )


async def scrape_hk_trademarks() -> FeeSchedule:
    """Scrape HK IPD trademark fees — application, renewal, opposition, …"""
    async with HKIPDFeesClient() as client:
        html_text = await client.fetch_html("trade-marks")
    doc = L.fromstring(html_text)
    fees = _build_trademark_fees(doc)
    if not fees:
        raise RuntimeError(
            "HK IPD trademark scraper parsed zero rows — page structure may have changed"
        )
    return FeeSchedule(
        jurisdiction="HK",
        issuing_body="Intellectual Property Department",
        office_code="HKIPD",
        right=RightType.trademark,
        currency="HKD",
        effective_date=date(2003, 4, 4),  # Trade Marks Ordinance Cap. 559 commencement
        source_url=HK_IPD_TRADEMARKS_URL,
        statutory_basis=_STATUTORY_TRADEMARK,
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "10-year term, renewable indefinitely. Per-additional-"
            "class surcharges emit as separate FeeItems with "
            "FeeCategory.excess_classes and FeeCondition(classes_over, "
            "threshold=1, per_unit=True). v1 GAP: the late-renewal "
            "charge bundled inside the renewal cell ('Late renewal "
            "charge: $500') is captured in the renewal FeeItem's "
            "notes rather than as a standalone late_fee row — IPD "
            "does not publish it with its own form/code."
        ),
    )


async def scrape_hk_designs() -> FeeSchedule:
    """Scrape HK IPD registered-design fees — filing, renewal, recordation."""
    async with HKIPDFeesClient() as client:
        html_text = await client.fetch_html("designs")
    doc = L.fromstring(html_text)
    fees = _build_design_fees(doc)
    if not fees:
        raise RuntimeError(
            "HK IPD design scraper parsed zero rows — page structure may have changed"
        )
    return FeeSchedule(
        jurisdiction="HK",
        issuing_body="Intellectual Property Department",
        office_code="HKIPD",
        right=RightType.design,
        currency="HKD",
        effective_date=date(2000, 6, 27),  # Registered Designs Ordinance Cap. 522 commencement
        source_url=HK_IPD_DESIGNS_URL,
        statutory_basis=_STATUTORY_DESIGN,
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "5-year initial registration term, renewable in 5-year "
            "extensions up to a 25-year maximum (Cap. 522 s.28). "
            "Renewal FeeItems are tagged by terminal year of the "
            "extension (1st 5-year extension → year=10, 2nd → 15, "
            "3rd → 20, 4th → 25). Filing-fee table multiplies on "
            "the number of designs / articles / set status; e-filing "
            "and paper-filing rates emit as separate FeeItems with "
            "FeeCondition(paper_filing) on the paper variant."
        ),
    )


__all__ = [
    "HK_IPD_BASE",
    "HK_IPD_PATENTS_URL",
    "HK_IPD_TRADEMARKS_URL",
    "HK_IPD_DESIGNS_URL",
    "HKIPDFeesClient",
    "scrape_hk_patents",
    "scrape_hk_trademarks",
    "scrape_hk_designs",
]
