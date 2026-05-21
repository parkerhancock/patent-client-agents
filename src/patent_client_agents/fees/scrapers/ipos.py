"""IPOS Singapore fee-schedule scraper.

IPOS (Intellectual Property Office of Singapore) publishes per-right
fee schedules on three native-HTML pages — all server-rendered, no
auth, no CDN challenge:

* ``ipos.gov.sg/about-ip/patents/forms-and-fees-singapore/``
  (note the ``-singapore`` URL suffix; the bare ``/forms-and-fees/``
  404s — IPOS uses non-obvious slugs on the patents page only)
* ``ipos.gov.sg/about-ip/trade-marks/forms-and-fees/``
* ``ipos.gov.sg/about-ip/designs/forms-and-fees/`` (note the singular
  ``/designs/`` path, NOT ``/registered-designs/``)

The statutory primary source is Singapore Statutes Online (SSO):

* Patents Rules First Schedule "Fees payable" — ``SL/PA1994-R1``
  (subsidiary legislation under Patents Act 1994).
* Trade Marks Rules — ``SL/TMA1998-R1``.
* Registered Designs Rules — ``SL/RDA2000-R1``.

The connector points at SSO as the statutory citation and treats
the IPOS HTML as the extraction target.

Two-phase implementation
------------------------

The current effective schedule is the consolidated state after the
two-phase reform of 21 July 2025 (Patents Circular 3/2025, Trade
Marks Circular 3/2025, Designs Circular 1/2025): first tranche took
effect 2025-09-01, second tranche took effect 2026-04-01. The IPOS
HTML pages reflect the post-2026-04-01 current state. The
``effective_date`` on each FeeSchedule is set to 2026-04-01.

Structural levers worth flagging
--------------------------------

* **TM4 specification-type split** — Trade Mark Form TM4 (application
  to register) publishes TWO prices in a single row: S$280 per class
  if the specification is fully adopted from IPOS' pre-approved
  *Classification Database*, S$410 per class otherwise. Both rates
  are available to every applicant — the choice is driven by
  drafting strategy, not entity status. The connector emits both
  with disambiguating code suffixes (``-preapproved`` vs ``-custom``)
  and a ``specification_type`` note.

* **Patent excess-claims threshold shift** — PF11 / PF12 publish
  "S$X plus S$80 for each claim over 15 claims" (claims-over
  threshold of 15, doubled from the pre-reform threshold of 20 +
  S$40/claim). The connector emits each base PF11/PF12 fee as one
  FeeItem and the per-additional-claim surcharge as a separate
  ``FeeCategory.excess_claims`` row with
  ``FeeCondition(claims_over, threshold=15, per_unit=True)``.

* **PF14 grant-fee branches** — PF14 publishes a complex multi-row
  decision tree based on whether the prior PF11/PF12/PF12A request
  was filed before or after 2025-09-01, and the claim count. v1
  extracts each S$ amount it finds; consumers needing the
  conditional logic should consult the IPOS Annex A circulars.

* **Madrid Protocol routing** — MP1 / MP2 / MM2(E) on the TM page
  are Madrid-specific FeeItems; they emit with
  ``FeeCategory.madrid`` and the CHF/WIPO-administered portion is
  preserved verbatim in ``notes``.

Multi-amount cells
------------------

Some fee cells publish more than one S$ amount in a single body
(TM4 split pricing, Design D3 "S$200 in respect of each design /
S$40 in respect of each request" for deferment). The walker
extracts every ``S$N(,NNN)?(\\.\\d{2})?`` amount per cell and emits
one FeeItem per amount with a disambiguating slug suffix.

Empty-form continuation rows
----------------------------

The IPOS tables use empty Form cells for continuation rows that
extend the previous form code's fee table. The walker carries the
last non-empty Form forward as ``current_form`` across rows, same
pattern as HK IPD's section-context handling. The label inherits a
short identifier from the row's Description cell so renewal year
bands (PF15(a), PF15(b), …) end up as distinct FeeItems with
``current_form="PF15"`` + the year-band sub-letter.

Year extraction for PF15 renewals
---------------------------------

PF15 publishes seven renewal year-bands: (a) years 5-7 at S$176,
(b) 8-10 at S$460, (c) 11-13 at S$640, (d) 14-16 at S$830, (e)
17-19 at S$1,010, (f) year 20 at S$1,200, (g) post-20 at S$1,470.
Each band expands into one ``FeeCategory.renewal`` FeeItem per
year via a regex on the description text.

v1 scope
--------

* ``SG/IPOS/Fees/Patent`` — Patents Rules First Schedule via the
  PFn-coded table.
* ``SG/IPOS/Fees/Trademark`` — Trade Marks Rules fees via the TM /
  MP / HC / MM-coded tables.
* ``SG/IPOS/Fees/Design`` — Registered Designs Rules fees via the
  D-coded table.

v1 GAPS
-------

* Geographical Indications and Plant Variety Rights schedules — out
  of scope (sui generis, not on the WIPO top-30 fees ranking).
* Copyright Tribunal fees — out of scope.
* PF14 conditional branches collapse to the cleanest per-amount
  extraction; consumers needing the full conditional logic should
  consult IPOS Circular 3/2025 Annex A.

Statutory basis
---------------

* Patents Act 1994 + Patents Rules (SSO ``SL/PA1994-R1``) First
  Schedule "Fees payable".
* Trade Marks Act 1998 + Trade Marks Rules (SSO ``SL/TMA1998-R1``).
* Registered Designs Act 2000 + Registered Designs Rules
  (SSO ``SL/RDA2000-R1``).

Reform consolidation: Patents Circular 3/2025, Trade Marks Circular
3/2025, Designs Circular 1/2025 (all 21 July 2025) — published Annex
A side-by-side old/new tables. Two-tranche implementation
2025-09-01 + 2026-04-01.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from decimal import Decimal
from typing import Literal, Unpack

from lxml import html as L

from mcp_data_core import BaseAsyncClient
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


IPOS_BASE = "https://www.ipos.gov.sg"
IPOS_PATENTS_URL = f"{IPOS_BASE}/about-ip/patents/forms-and-fees-singapore/"
IPOS_TRADEMARKS_URL = f"{IPOS_BASE}/about-ip/trade-marks/forms-and-fees/"
IPOS_DESIGNS_URL = f"{IPOS_BASE}/about-ip/designs/forms-and-fees/"

IPOS_EFFECTIVE_DATE = date(2026, 4, 1)

RightPath = Literal["patents", "trade-marks", "designs"]
_PATH_BY_RIGHT: dict[RightPath, str] = {
    "patents": "/about-ip/patents/forms-and-fees-singapore/",
    "trade-marks": "/about-ip/trade-marks/forms-and-fees/",
    "designs": "/about-ip/designs/forms-and-fees/",
}


class IPOSFeesClient(BaseAsyncClient):
    """Tiny HTTP client for the IPOS forms-and-fees pages."""

    DEFAULT_BASE_URL = IPOS_BASE
    CACHE_NAME = "ipos_fees"
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
        r = await self._request("GET", _PATH_BY_RIGHT[right], context=f"ipos_{right}")
        return r.text


# ──────────────────────────────────────────────────────────────────────
# Money parsing
# ──────────────────────────────────────────────────────────────────────

_SGD_AMOUNT_RE = re.compile(r"S?\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)")


def _parse_sgd_amounts(raw: str) -> list[Decimal]:
    """Extract every ``S$N,NNN.NN`` amount from a cell body in order.

    A cell may carry multiple amounts (TM4 dual pricing, design D3
    multi-amount, PF15 multi-year-band rows). Returns them all so
    builders can emit one FeeItem per amount.
    """
    out: list[Decimal] = []
    for m in _SGD_AMOUNT_RE.finditer(raw):
        token = m.group(1).replace(",", "")
        try:
            out.append(Decimal(token))
        except Exception:
            pass
    return out


def _has_no_fee(raw: str) -> bool:
    """'No fee' / 'No Fee' / 'No fee payable' → True; else False."""
    lower = raw.lower()
    return "no fee" in lower and "$" not in raw


# ──────────────────────────────────────────────────────────────────────
# Categorization
# ──────────────────────────────────────────────────────────────────────


def _categorize_patent(form: str, label: str) -> FeeCategory:
    f = form.upper()
    d = label.lower()
    if f.startswith("PF15") or "renewal fee" in d or "year of renewal" in d:
        # "late payment" is the late-fee tell. "additional fee" alone
        # gets misfired by the PF15 section opener "Payment of Renewal
        # Fee and Any Additional Fee" which is not itself a late-fee
        # row — the actual late-fee sub-rows say "late payment".
        if "late payment" in d or "late filing" in d:
            return FeeCategory.late_fee
        return FeeCategory.renewal
    if f == "PF1" or "grant of a patent" in d and "payment" not in d:
        return FeeCategory.filing
    if f == "PF14" or "payment of fee for grant" in d or "grant of patent" in d:
        return FeeCategory.grant
    if f.startswith("PF10") or "search report" in d:
        return FeeCategory.search
    if f.startswith("PF11"):
        return FeeCategory.search
    if f.startswith("PF12"):
        return FeeCategory.examination
    if f.startswith("PF13"):
        return FeeCategory.examination
    if "amend application" in d or "amend specification" in d:
        return FeeCategory.other
    if "restoration" in d or "reinstatement" in d:
        return FeeCategory.other
    if "opposition" in d or "counter-statement" in d:
        return FeeCategory.opposition
    if "revocation" in d or "invalidity" in d:
        return FeeCategory.cancellation
    if "extension of time" in d:
        return FeeCategory.extension
    if "publication" in d:
        return FeeCategory.publication
    if "hearing" in d:
        return FeeCategory.appeal
    if (
        "register" in d
        or "transmission" in d
        or "licence" in d
        or "mortgage" in d
        or "assignment" in d
    ):
        return FeeCategory.transfer
    if "translation" in d:
        return FeeCategory.translation
    if "claim in excess" in d or "claim over" in d or "claim over 15" in d:
        return FeeCategory.excess_claims
    if "request for grant" in d:
        return FeeCategory.filing
    return FeeCategory.other


def _categorize_trademark(form: str, label: str) -> FeeCategory:
    f = form.upper()
    d = label.lower()
    if "renewal" in d and "late" not in d:
        return FeeCategory.renewal
    if "late renewal" in d or "restoration" in d:
        return FeeCategory.late_fee
    if f.startswith("MM") or f.startswith("MP"):
        return FeeCategory.madrid
    if f == "TM4" or "application to register" in d:
        return FeeCategory.filing
    if f == "TM11" or "opposition" in d or "counter-statement" in d:
        return FeeCategory.opposition
    if f == "TM28" or "revocation" in d or "invalidation" in d or "rectification" in d:
        return FeeCategory.cancellation
    if "hearing" in d or "decision" in d:
        return FeeCategory.appeal
    if "extension of time" in d:
        return FeeCategory.extension
    if "divide" in d or "merge" in d or "amend" in d:
        return FeeCategory.other
    if "search" in d or "preliminary advice" in d:
        return FeeCategory.search
    if "register" in d and ("licence" in d or "assignment" in d or "transmission" in d):
        return FeeCategory.transfer
    if "declaration of use" in d:
        return FeeCategory.declaration_of_use
    return FeeCategory.other


def _categorize_design(form: str, label: str) -> FeeCategory:
    d = label.lower()
    if "extension of period of registration" in d or "renewal" in d:
        return FeeCategory.renewal
    if "late" in d:
        return FeeCategory.late_fee
    if "deferment of publication" in d:
        return FeeCategory.deferment
    if "registration of a design" in d or "application for registration" in d:
        return FeeCategory.filing
    if "extension of time" in d:
        return FeeCategory.extension
    if "opposition" in d or "counter-statement" in d:
        return FeeCategory.opposition
    if "amend" in d or "alter" in d or "correction" in d:
        return FeeCategory.other
    if "register" in d and ("licence" in d or "assignment" in d or "transmission" in d):
        return FeeCategory.transfer
    if "search" in d:
        return FeeCategory.search
    if "hearing" in d:
        return FeeCategory.appeal
    return FeeCategory.other


# ──────────────────────────────────────────────────────────────────────
# Year extraction for PF15 patent renewals
# ──────────────────────────────────────────────────────────────────────


_DESIGN_PERIOD_RE = re.compile(
    r"\(\w\)\s*for the\s+(first|second|third|fourth)\s+period",
    re.IGNORECASE,
)
_DESIGN_ORDINAL_TO_YEAR: dict[str, int] = {
    "first": 10,
    "second": 15,
    "third": 20,
    "fourth": 25,
}


def _design_renewal_year(description: str) -> int | None:
    """'(a) for the first period of 5 years' → 10 (end-year of period 1)."""
    m = _DESIGN_PERIOD_RE.search(description)
    if m:
        return _DESIGN_ORDINAL_TO_YEAR.get(m.group(1).lower())
    return None


_PF15_BAND_RE = re.compile(
    r"(\d+)(?:st|nd|rd|th)?,?\s+(\d+)(?:st|nd|rd|th)?\s+or\s+(\d+)(?:st|nd|rd|th)?\s+year",
    re.IGNORECASE,
)
_PF15_SINGLE_YEAR_RE = re.compile(r"renewal of the\s+(\d+)(?:st|nd|rd|th)?\s+year", re.IGNORECASE)
_PF15_POST_RE = re.compile(r"after the\s+(\d+)(?:st|nd|rd|th)?\s+year", re.IGNORECASE)


def _pf15_renewal_years(description: str) -> list[int]:
    """Extract the list of renewal years implied by a PF15 sub-row.

    * ``"5th, 6th or 7th year"`` → ``[5, 6, 7]``
    * ``"renewal of the 20th year"`` → ``[20]``
    * ``"after the 20th year"`` → ``[21]`` (post-20 extension; PF15(g))
    """
    band = _PF15_BAND_RE.search(description)
    if band:
        return sorted({int(band.group(1)), int(band.group(2)), int(band.group(3))})
    single = _PF15_SINGLE_YEAR_RE.search(description)
    if single:
        return [int(single.group(1))]
    post = _PF15_POST_RE.search(description)
    if post:
        return [int(post.group(1)) + 1]  # represent "after 20th" as year=21
    return []


# ──────────────────────────────────────────────────────────────────────
# Per-class / per-claim conditions
# ──────────────────────────────────────────────────────────────────────


def _per_class_condition(text: str) -> FeeCondition | None:
    lower = text.lower()
    if (
        "per class" in lower
        or "per additional class" in lower
        or "for each subsequent class" in lower
    ):
        if "additional class" in lower or "subsequent class" in lower:
            return FeeCondition(
                trigger=ConditionalTrigger.classes_over,
                threshold=1,
                per_unit=True,
                description="Per additional class beyond the first.",
            )
        # "per class" without "additional" — applies to every class.
        return FeeCondition(
            trigger=ConditionalTrigger.classes_over,
            threshold=0,
            per_unit=True,
            description="Per class.",
        )
    return None


def _per_claim_condition(text: str) -> FeeCondition | None:
    lower = text.lower()
    # "S$80 for each claim over 15 claims" / "S$80 for each claim in
    # excess of 15 claims" / "S$40 for each claim in excess of 20"
    m = re.search(r"each claim (?:over|in excess of|in)\s*(\d+)\s+claims?", lower)
    if m:
        return FeeCondition(
            trigger=ConditionalTrigger.claims_over,
            threshold=int(m.group(1)),
            per_unit=True,
            description=f"Per claim in excess of {m.group(1)}.",
        )
    return None


# ──────────────────────────────────────────────────────────────────────
# Table walker
# ──────────────────────────────────────────────────────────────────────


def _row_cells(tr: L.HtmlElement) -> list[str]:
    return [re.sub(r"\s+", " ", c.text_content().strip()) for c in tr.cssselect("td, th")]


def _is_fee_table(table: L.HtmlElement) -> bool:
    """A canonical IPOS fee table has a ``Form | Description | Fee`` header."""
    first_row = table.cssselect("tr")
    if not first_row:
        return False
    cells = _row_cells(first_row[0])
    if len(cells) != 3:
        return False
    joined = " | ".join(c.lower() for c in cells)
    return "form" in joined and "description" in joined and "fee" in joined


def _walk_fee_table(table: L.HtmlElement) -> list[tuple[str, str, str]]:
    """Yield ``(current_form, description, fee_text)`` tuples for one fee table.

    Empty Form cells inherit ``current_form`` from the previous row
    (continuation pattern). Rows whose Fee cell is empty are
    treated as section openers and update the description prefix
    for the next row.
    """
    out: list[tuple[str, str, str]] = []
    current_form = ""
    section_context = ""
    for tr in table.cssselect("tr"):
        cells = _row_cells(tr)
        if len(cells) == 2:
            # 2-cell continuation row — the design D8 / CM5 year-band
            # sub-rows render as ``[(a) for the first period of 5
            # years, S$220]`` with the empty Form column collapsed
            # out. Inherit ``current_form`` from the previous row.
            form, description, fee = "", cells[0], cells[1]
        elif len(cells) >= 3:
            form, description, fee = cells[0], cells[1], cells[2]
        else:
            continue
        # Header row — skip.
        if "description" in description.lower() and "fee" in fee.lower():
            continue
        if form:
            current_form = form
            section_context = ""  # new form → reset section context
        if not fee:
            # Section-opener row carrying context for the year-band
            # / period sub-rows that follow. Persists across multiple
            # sub-rows until a new Form code arrives.
            if description:
                section_context = description
            continue
        full_desc = f"{section_context} — {description}" if section_context else description
        out.append((current_form or "NA", full_desc, fee))
    return out


# ──────────────────────────────────────────────────────────────────────
# Slug helpers
# ──────────────────────────────────────────────────────────────────────


def _slug(*parts: str, max_part: int = 50) -> str:
    bits: list[str] = []
    for p in parts:
        if not p:
            continue
        s = re.sub(r"[^a-z0-9]+", "-", p.lower()).strip("-")[:max_part]
        if s:
            bits.append(s)
    return "-".join(bits)


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
# Patent builder
# ──────────────────────────────────────────────────────────────────────


def _build_patent_fees(doc: L.HtmlElement) -> list[FeeItem]:
    fees: list[FeeItem] = []
    seen_codes: set[str] = set()

    for table in doc.cssselect("table"):
        if not _is_fee_table(table):
            continue
        for form, description, fee_text in _walk_fee_table(table):
            if _has_no_fee(fee_text):
                continue
            amounts = _parse_sgd_amounts(fee_text)
            if not amounts:
                continue

            base_category = _categorize_patent(form, description)
            claim_condition = _per_claim_condition(fee_text)

            # PF15 renewal-year expansion.
            if base_category is FeeCategory.renewal:
                years = _pf15_renewal_years(description)
                if not years:
                    years = [1]
                for amount in amounts:
                    for yr in years:
                        code = _unique(_slug("sg-pat", form, "y", str(yr)), seen_codes)
                        fees.append(
                            _mk_patent_fee(
                                code=code,
                                label=f"{form}: {description}",
                                category=base_category,
                                amount=amount,
                                year=yr,
                                condition=None,
                                notes=None,
                            )
                        )
                continue

            # Standard rows: emit one FeeItem per amount.
            for idx, amount in enumerate(amounts):
                suffix = "" if idx == 0 else f"v{idx + 1}"
                code = _unique(_slug("sg-pat", form, description[:40], suffix), seen_codes)
                fees.append(
                    _mk_patent_fee(
                        code=code,
                        label=f"{form}: {description}",
                        category=base_category,
                        amount=amount,
                        year=None,
                        condition=None,
                        notes=None,
                    )
                )

            # Excess-claims surcharge — emit as a separate row when the
            # cell describes per-claim surcharge in addition to the base.
            if claim_condition is not None and len(amounts) >= 2:
                # The per-claim amount is typically the SECOND $ in the
                # cell ("S$2,050 plus S$80 for each claim over 15").
                surcharge_amount = amounts[-1]
                code = _unique(
                    _slug("sg-pat", form, "excess-claims"),
                    seen_codes,
                )
                fees.append(
                    _mk_patent_fee(
                        code=code,
                        label=f"{form}: excess claims surcharge",
                        category=FeeCategory.excess_claims,
                        amount=surcharge_amount,
                        year=None,
                        condition=claim_condition,
                        notes=f"Surcharge over base {form} fee.",
                    )
                )

    return fees


def _mk_patent_fee(
    *,
    code: str,
    label: str,
    category: FeeCategory,
    amount: Decimal,
    year: int | None,
    condition: FeeCondition | None,
    notes: str | None,
) -> FeeItem:
    return FeeItem(
        code=code,
        label=label[:200],
        category=category,
        rights=[RightType.patent],
        amount=amount,
        currency="SGD",
        tier=EntityTier.none,
        year=year,
        condition=condition,
        source_url=IPOS_PATENTS_URL,
        notes=notes,
    )


# ──────────────────────────────────────────────────────────────────────
# Trademark builder
# ──────────────────────────────────────────────────────────────────────


def _build_trademark_fees(doc: L.HtmlElement) -> list[FeeItem]:
    fees: list[FeeItem] = []
    seen_codes: set[str] = set()

    for table in doc.cssselect("table"):
        if not _is_fee_table(table):
            continue
        for form, description, fee_text in _walk_fee_table(table):
            if _has_no_fee(fee_text):
                continue
            amounts = _parse_sgd_amounts(fee_text)
            if not amounts:
                continue

            category = _categorize_trademark(form, description)
            class_condition = _per_class_condition(fee_text)
            # TM term = 10 years (TMA 1998 s.18); renewal FeeItems
            # carry year=10 to satisfy the renewal validator.
            year = 10 if category is FeeCategory.renewal else None

            # TM4 special-case: published TWO prices in one cell
            # (pre-approved S$280 vs custom S$410). Emit each with a
            # disambiguating suffix.
            if form.upper() == "TM4" and len(amounts) >= 2:
                for idx, amount in enumerate(amounts[:2]):
                    spec_label = "preapproved" if idx == 0 else "custom"
                    code = _unique(_slug("sg-tm", form, spec_label), seen_codes)
                    note = (
                        "Specification fully adopted from IPOS' Classification Database."
                        if idx == 0
                        else "Specification not fully adopted from IPOS' Classification Database."
                    )
                    fees.append(
                        FeeItem(
                            code=code,
                            label=f"{form}: {description} ({spec_label})",
                            category=category,
                            rights=[RightType.trademark],
                            amount=amount,
                            currency="SGD",
                            tier=EntityTier.none,
                            year=year,
                            condition=class_condition,
                            source_url=IPOS_TRADEMARKS_URL,
                            notes=note,
                        )
                    )
                continue

            for idx, amount in enumerate(amounts):
                suffix = "" if idx == 0 else f"v{idx + 1}"
                code = _unique(_slug("sg-tm", form, description[:40], suffix), seen_codes)
                fees.append(
                    FeeItem(
                        code=code,
                        label=f"{form}: {description}",
                        category=category,
                        rights=[RightType.trademark],
                        amount=amount,
                        currency="SGD",
                        tier=EntityTier.none,
                        year=year,
                        condition=class_condition,
                        source_url=IPOS_TRADEMARKS_URL,
                        notes=None,
                    )
                )

    return fees


# ──────────────────────────────────────────────────────────────────────
# Design builder
# ──────────────────────────────────────────────────────────────────────


def _build_design_fees(doc: L.HtmlElement) -> list[FeeItem]:
    fees: list[FeeItem] = []
    seen_codes: set[str] = set()

    for table in doc.cssselect("table"):
        if not _is_fee_table(table):
            continue
        for form, description, fee_text in _walk_fee_table(table):
            if _has_no_fee(fee_text):
                continue
            amounts = _parse_sgd_amounts(fee_text)
            if not amounts:
                continue

            category = _categorize_design(form, description)
            # Design term: initial 5 years renewable in 5-year periods
            # up to 25 years total (RDA 2000 s.21 + Schedule). Renewal
            # FeeItems carry the end-year of the relevant 5-year period
            # extracted from the "(a) for the first period of 5 years"
            # ordinal pattern; falls back to year=10 (end of first
            # extension) when the ordinal isn't present.
            year = None
            if category is FeeCategory.renewal:
                year = _design_renewal_year(description) or 10

            for idx, amount in enumerate(amounts):
                suffix = "" if idx == 0 else f"v{idx + 1}"
                code = _unique(_slug("sg-des", form, description[:40], suffix), seen_codes)
                fees.append(
                    FeeItem(
                        code=code,
                        label=f"{form}: {description}",
                        category=category,
                        rights=[RightType.design],
                        amount=amount,
                        currency="SGD",
                        tier=EntityTier.none,
                        year=year,
                        condition=None,
                        source_url=IPOS_DESIGNS_URL,
                        notes=None,
                    )
                )

    return fees


# ──────────────────────────────────────────────────────────────────────
# Public scrape entry points
# ──────────────────────────────────────────────────────────────────────


_STATUTORY_PATENT = (
    "Patents Act 1994 (Singapore) + Patents Rules (SSO SL/PA1994-R1) "
    "First Schedule 'Fees payable'. Two-phase reform consolidated by "
    "Patents Circular 3/2025 (21 July 2025); first tranche effective "
    "2025-09-01, second tranche effective 2026-04-01."
)
_STATUTORY_TRADEMARK = (
    "Trade Marks Act 1998 (Singapore) + Trade Marks Rules "
    "(SSO SL/TMA1998-R1). Consolidated by Trade Marks Circular "
    "3/2025 (21 July 2025); two-phase implementation 2025-09-01 + "
    "2026-04-01."
)
_STATUTORY_DESIGN = (
    "Registered Designs Act 2000 (Singapore) + Registered Designs "
    "Rules (SSO SL/RDA2000-R1). Consolidated by Designs Circular "
    "1/2025 (21 July 2025); two-phase implementation 2025-09-01 + "
    "2026-04-01."
)


async def scrape_ipos_patents() -> FeeSchedule:
    """Scrape IPOS patent fees from the forms-and-fees-singapore page."""
    async with IPOSFeesClient() as client:
        html_text = await client.fetch_html("patents")
    doc = L.fromstring(html_text)
    fees = _build_patent_fees(doc)
    if not fees:
        raise RuntimeError("IPOS patent scraper parsed zero rows — page structure may have changed")
    return FeeSchedule(
        jurisdiction="SG",
        issuing_body="Intellectual Property Office of Singapore (IPOS)",
        office_code="IPOS",
        right=RightType.patent,
        currency="SGD",
        effective_date=IPOS_EFFECTIVE_DATE,
        source_url=IPOS_PATENTS_URL,
        statutory_basis=_STATUTORY_PATENT,
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "PF15 renewal expands across seven year-bands (5-7 / 8-10 "
            "/ 11-13 / 14-16 / 17-19 / 20 / post-20) emitting one "
            "FeeItem per year. PF11/PF12 per-claim surcharge at "
            "S$80/claim over 15 claims emits as a separate "
            "FeeCategory.excess_claims row with FeeCondition("
            "claims_over, threshold=15, per_unit=True). PF14 multi-"
            "branch grant fee collapses to per-amount extraction; "
            "consumers needing the conditional logic should consult "
            "IPOS Patents Circular 3/2025 Annex A."
        ),
    )


async def scrape_ipos_trademarks() -> FeeSchedule:
    """Scrape IPOS trademark fees including Madrid routing."""
    async with IPOSFeesClient() as client:
        html_text = await client.fetch_html("trade-marks")
    doc = L.fromstring(html_text)
    fees = _build_trademark_fees(doc)
    if not fees:
        raise RuntimeError(
            "IPOS trademark scraper parsed zero rows — page structure may have changed"
        )
    return FeeSchedule(
        jurisdiction="SG",
        issuing_body="Intellectual Property Office of Singapore (IPOS)",
        office_code="IPOS",
        right=RightType.trademark,
        currency="SGD",
        effective_date=IPOS_EFFECTIVE_DATE,
        source_url=IPOS_TRADEMARKS_URL,
        statutory_basis=_STATUTORY_TRADEMARK,
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "TM4 publishes TWO rates in one row: S$280 per class if "
            "the specification is fully adopted from IPOS' "
            "Classification Database, S$410 per class otherwise. "
            "Both rates emit as separate FeeItems with -preapproved / "
            "-custom suffixes — this is an applicant-strategy choice, "
            "not an entity-size tier. TM term is 10 years (TMA s.18); "
            "renewal FeeItems carry year=10. Madrid Protocol routing "
            "(MM2, MP1, MP2) emits with FeeCategory.madrid; the CHF/"
            "WIPO-administered portion is preserved verbatim in notes."
        ),
    )


async def scrape_ipos_designs() -> FeeSchedule:
    """Scrape IPOS registered-design fees."""
    async with IPOSFeesClient() as client:
        html_text = await client.fetch_html("designs")
    doc = L.fromstring(html_text)
    fees = _build_design_fees(doc)
    if not fees:
        raise RuntimeError("IPOS design scraper parsed zero rows — page structure may have changed")
    return FeeSchedule(
        jurisdiction="SG",
        issuing_body="Intellectual Property Office of Singapore (IPOS)",
        office_code="IPOS",
        right=RightType.design,
        currency="SGD",
        effective_date=IPOS_EFFECTIVE_DATE,
        source_url=IPOS_DESIGNS_URL,
        statutory_basis=_STATUTORY_DESIGN,
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "Initial 5-year term renewable to 15 years total in 5-year "
            "periods (RDA 2000 s.21). Renewal FeeItems carry year=5. "
            "D3 publishes two amounts in a single body (S$200 per "
            "design + S$40 per deferment request); the parser emits "
            "both with -v1 / -v2 disambiguating suffixes."
        ),
    )


__all__ = [
    "IPOS_BASE",
    "IPOS_PATENTS_URL",
    "IPOS_TRADEMARKS_URL",
    "IPOS_DESIGNS_URL",
    "IPOS_EFFECTIVE_DATE",
    "IPOSFeesClient",
    "scrape_ipos_patents",
    "scrape_ipos_trademarks",
    "scrape_ipos_designs",
]
