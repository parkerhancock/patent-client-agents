"""PRV Sweden (Patent- och registreringsverket) fee-schedule scraper.

PRV publishes English-language fee schedules across three native-HTML
pages, all server-rendered, no auth, no CDN challenge:

* Patents — ``prv.se/en/patents/the-advanced-patent-guide/fees-and-payment/``
* Trademarks — ``prv.se/en/trademarks/prepare-for-the-trademark-application/fees-and-payment/``
* Designs — ``prv.se/en/designs/prepare-for-the-design-application/fees-for-designs/``

PRV last republished the 2025 fee tables in two waves:

* 2025-03-15 — patent application/grant/annuity changes (PRV news
  "Fee changes for patents and trademarks 2025").
* 2025-04-25 — trademark application + renewal changes.
* 2025-12-01 — basic fee for publication (grant fee) standardised at
  SEK 3 000 regardless of filing date.
* 2026-01-01 + 2026-04-01 — PCT-routed fees adjusted for SEK/CHF/EUR
  currency drift (PCT-1, PCT-2 etc.).

The connector pins ``effective_date`` to the most recent fee-event
applicable to the bulk of each right's schedule:

* Patents → 2025-03-15 (national + EP track baseline; the December 2025
  grant-fee normalisation and 2026 PCT currency adjustments are layered
  in via re-fetched amounts, with the December change noted in the
  schedule notes).
* Trademarks → 2025-04-25.
* Designs → 2025-04-25 (no separate design announcement; the design
  fee tables in the current site reflect the 2025 schedule).

Table model
-----------

Patent page — twelve HTML tables under the "Complete price list"
section, each prefixed with a stable ID column. The ID column
encodes the section context:

* ``SE-*`` — national filing + grant.
* ``N-*`` — annual fees, years 1-20. The 1st and 2nd annual fees are
  free (SEK 0) and "due together with the 3rd annual fee"; emitted
  with ``amount=0`` so the renewal validator sees them as part of the
  expanded annuity ladder.
* ``NM-*`` — national maintenance (re-establishment, pledge, owner
  change, licence).
* ``SE-10..18`` — granted-patent maintenance + International Type
  Search.
* ``NT-*`` — supplementary protection certificates (SPC) under EU
  Reg. 469/2009 / 1610/96.
* ``NPB-*`` — patent limitation / revocation requests.
* ``PCT-*`` — international (PCT) routing fees.
* ``EP-*`` — European patent validation fees.
* ``B-*`` — patent certificates.
* ``KT-*`` — consultancy services (novelty search, prior art, FTO).

Trademark + design pages — multiple smaller HTML tables organised by
section H2 with no ID column. Each table is two columns
(``description | amount``). For trademark and renewal tables PRV
publishes the e-service rate and a separate paper / other rate; we
walk tables in order under each H2 and tag the first table
``e-service`` and the second ``paper-or-other`` based on the
preceding paragraph hint.

Annuity expansion
-----------------

The N-* annuity table publishes regular and "Increased fee" (20%
late surcharge per Patents Act ch.4 §47). Each annuity year emits
TWO FeeItems:

* Regular renewal at ``FeeCategory.renewal`` with the year.
* Increased fee at ``FeeCategory.late_fee`` with the same year.

Per-claim / per-class / per-sheet surcharges
--------------------------------------------

* ``SE-3`` (patent additional fee for each claim beyond ten) emits as
  ``FeeCategory.excess_claims`` with
  ``FeeCondition(claims_over, threshold=10, per_unit=True)``.
* TM tables emit "For each additional class" as
  ``FeeCategory.excess_classes`` with
  ``FeeCondition(classes_over, threshold=1, per_unit=True)``.
* ``PCT-2`` (additional sheet fee) emits as ``FeeCategory.excess_pages``
  with ``FeeCondition(pages_over, threshold=30, per_unit=True)``.

Quotation-only rows
-------------------

KT-6..KT-15 publish "By quotation" rather than a fixed price. These
rows are skipped (no verifiable amount). The full Consultancy
services menu is documented in schedule notes.

Statutory basis
---------------

* Patents — Patentlagen (1967:837) + Patentkungörelsen (1967:838) +
  PRVFS fee orders.
* Trademarks — Varumärkeslagen (2010:1877) + Varumärkesförordningen
  (2018:10) + PRVFS fee orders.
* Designs — Mönsterskyddslagen (1970:485) + Mönsterskyddsförordningen
  (1970:486) + PRVFS fee orders.

v1 GAPS
-------

* KT-6..KT-15 consultancy rows priced "By quotation" are skipped.
* KT-17, KT-22 publish blank amounts (description-only / external
  link) and are skipped.
* PCT-5 and PCT-18 publish prose-formula amounts (50% surcharges,
  reductions); they emit with ``amount=0`` and the formula preserved
  in ``notes``.
* WIPO-administered Madrid (TM) and Hague (design) per-class /
  per-design fees are referenced but not duplicated here — those
  live in the WIPO-Madrid / WIPO-Hague schedules.
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


PRV_BASE = "https://www.prv.se"
PRV_PATENTS_URL = f"{PRV_BASE}/en/patents/the-advanced-patent-guide/fees-and-payment/"
PRV_TRADEMARKS_URL = (
    f"{PRV_BASE}/en/trademarks/prepare-for-the-trademark-application/fees-and-payment/"
)
PRV_DESIGNS_URL = f"{PRV_BASE}/en/designs/prepare-for-the-design-application/fees-for-designs/"

PRV_PATENTS_EFFECTIVE_DATE = date(2025, 3, 15)
PRV_TRADEMARKS_EFFECTIVE_DATE = date(2025, 4, 25)
PRV_DESIGNS_EFFECTIVE_DATE = date(2025, 4, 25)

RightPath = Literal["patents", "trademarks", "designs"]
_PATH_BY_RIGHT: dict[RightPath, str] = {
    "patents": "/en/patents/the-advanced-patent-guide/fees-and-payment/",
    "trademarks": "/en/trademarks/prepare-for-the-trademark-application/fees-and-payment/",
    "designs": "/en/designs/prepare-for-the-design-application/fees-for-designs/",
}


class PrvFeesClient(BaseAsyncClient):
    """Tiny HTTP client for the PRV fees pages."""

    DEFAULT_BASE_URL = PRV_BASE
    CACHE_NAME = "prv_se_fees"
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
                "Accept-Language": "en;q=0.9,sv;q=0.7",
            },
        )
        super().__init__(**kwargs)

    async def fetch_html(self, right: RightPath) -> str:
        r = await self._request("GET", _PATH_BY_RIGHT[right], context=f"prv_{right}")
        return r.text


# ──────────────────────────────────────────────────────────────────────
# Amount parsing
# ──────────────────────────────────────────────────────────────────────

# PRV publishes amounts in two equivalent forms:
#   "3 000 kr"     (Swedish convention: space thousands separator)
#   "2 700 SEK"
#   "2 000 kr"
# Some rows use the non-breaking-space U+00A0; the regex accepts any
# whitespace between digit groups via \s.
_SEK_AMOUNT_RE = re.compile(
    r"(\d{1,3}(?:\s\d{3})*|\d+)(?:[,.](\d{1,2}))?\s*(?:SEK|kr)",
    re.IGNORECASE,
)


def _parse_sek_amounts(raw: str) -> list[Decimal]:
    """Extract every ``N NNN kr`` / ``N NNN SEK`` amount from a cell.

    Non-breaking spaces are normalised first. Returns amounts in
    source order so multi-amount cells (rare on PRV — mainly the
    annuity "Regular / Increased" pair, which is split into two
    columns rather than one cell) preserve order.
    """
    if not raw:
        return []
    cleaned = raw.replace("\xa0", " ")
    out: list[Decimal] = []
    for m in _SEK_AMOUNT_RE.finditer(cleaned):
        digits = m.group(1).replace(" ", "")
        decimals = m.group(2) or ""
        token = f"{digits}.{decimals}" if decimals else digits
        try:
            out.append(Decimal(token))
        except Exception:
            pass
    return out


def _parse_single_amount(raw: str) -> Decimal | None:
    """First amount in a cell, or None."""
    amounts = _parse_sek_amounts(raw)
    return amounts[0] if amounts else None


def _is_zero_explicit(raw: str) -> bool:
    """'0 kr' / '0 SEK' is a real zero, not 'no fee found'."""
    return bool(re.match(r"^\s*0\s*(kr|SEK)\s*$", (raw or "").replace("\xa0", " "), re.IGNORECASE))


def _looks_like_formula(raw: str) -> bool:
    lower = (raw or "").lower()
    return "as described" in lower or "50% addition" in lower or "by quotation" in lower


# ──────────────────────────────────────────────────────────────────────
# Patent ID → section + category mapping
# ──────────────────────────────────────────────────────────────────────


_PATENT_ID_RE = re.compile(r"^([A-Z]+)-(\d+)$")
_ANNUITY_YEAR_RE = re.compile(r"^(\d+)(?:st|nd|rd|th)\s+annual fee", re.IGNORECASE)


def _patent_id_prefix(code: str) -> str | None:
    m = _PATENT_ID_RE.match(code.strip().upper())
    return m.group(1) if m else None


def _categorize_patent(code: str, label: str) -> FeeCategory:
    """Map PRV patent fee ID + label → FeeCategory.

    The ID prefix is the strongest signal — PRV groups every annuity
    under N-*, every SPC under NT-*, every PCT row under PCT-*, etc.
    Label text disambiguates within each section.
    """
    prefix = _patent_id_prefix(code) or ""
    lower = label.lower()

    if prefix == "N":  # annuity ladder, years 1-20
        return FeeCategory.renewal
    if prefix == "NT":
        if "annual" in lower:
            return FeeCategory.renewal
        return FeeCategory.other  # SPC application / extension fee
    if prefix == "NPB":
        return FeeCategory.cancellation
    if prefix == "PCT":
        if "late payment" in lower:
            return FeeCategory.late_fee
        if "search" in lower:
            return FeeCategory.search
        if "preliminary" in lower or "examination" in lower:
            return FeeCategory.examination
        if "filing" in lower or "transmission" in lower:
            return FeeCategory.filing
        if "additional fee for each additional sheet" in lower:
            return FeeCategory.excess_pages
        if "additional fee" in lower:
            return FeeCategory.examination
        if "reduction" in lower:
            return FeeCategory.other
        if "re-establishment" in lower or "reinstatement" in lower:
            return FeeCategory.other
        return FeeCategory.other
    if prefix == "EP":
        if "annual" in lower:
            return FeeCategory.renewal
        if "publication" in lower:
            return FeeCategory.publication
        return FeeCategory.other
    if prefix == "B":
        return FeeCategory.other  # certificates
    if prefix == "KT":
        return FeeCategory.search  # consultancy = search services
    if prefix == "NM":
        if "re-establishment" in lower or "reinstatement" in lower:
            return FeeCategory.other
        if (
            "pledge" in lower
            or "licence" in lower
            or "patent holder" in lower
            or "address" in lower
        ):
            return FeeCategory.transfer
        return FeeCategory.other
    if prefix == "SE":
        # SE-1..SE-9 — pre-grant; SE-10..SE-18 — granted-patent maint.
        # Order matters: SE-1's label includes both "Filing fee" and
        # "Search fee" — the row IS the filing-fee row, with a
        # parenthetical breakdown into the application + search
        # components. "Filing fee" prefix wins over a later "search"
        # mention in the same cell.
        if lower.startswith("filing fee"):
            return FeeCategory.filing
        if "fee for grant" in lower:
            return FeeCategory.grant
        if (
            "additional fee for each patent claim" in lower
            or "additional fee for patent claim" in lower
        ):
            return FeeCategory.excess_claims
        if "reinstatement" in lower or "re-establishment" in lower:
            return FeeCategory.other
        if "publication" in lower:
            return FeeCategory.publication
        if "search" in lower:
            return FeeCategory.search
        if "international type search" in lower:
            return FeeCategory.search
        if "pledge" in lower or "licence" in lower:
            return FeeCategory.transfer
        if "filing" in lower:
            return FeeCategory.filing
        if "additional fee" in lower:
            return FeeCategory.other
        if "fee payable to the patent authority" in lower:
            return FeeCategory.filing  # SE-6 — chapter 10 fee for national-phase
        return FeeCategory.other
    return FeeCategory.other


def _patent_annuity_year(label: str) -> int | None:
    """'3rd annual fee' → 3."""
    m = _ANNUITY_YEAR_RE.search(label.strip())
    return int(m.group(1)) if m else None


def _patent_condition(code: str, label: str) -> FeeCondition | None:
    """Surcharge condition for excess-claims / excess-sheets patent rows."""
    prefix = _patent_id_prefix(code) or ""
    lower = label.lower()
    if prefix == "SE" and (
        "each patent claim beyond the first ten" in lower
        or "additional fee for patent claim" in lower
    ):
        return FeeCondition(
            trigger=ConditionalTrigger.claims_over,
            threshold=10,
            per_unit=True,
            description="Per patent claim beyond the first 10 (Patentlagen ch.2 §3).",
        )
    if code.strip().upper() == "PCT-2" or "additional fee for each additional sheet" in lower:
        return FeeCondition(
            trigger=ConditionalTrigger.pages_over,
            threshold=30,
            per_unit=True,
            description="Per sheet beyond the first 30 (PCT Rule 15.2(b)).",
        )
    return None


# ──────────────────────────────────────────────────────────────────────
# Patent walker
# ──────────────────────────────────────────────────────────────────────


def _row_cells(tr: L.HtmlElement) -> list[str]:
    return [re.sub(r"\s+", " ", c.text_content().strip()) for c in tr.cssselect("td, th")]


def _is_patent_header(cells: list[str]) -> bool:
    if not cells:
        return False
    return cells[0].strip().lower() == "id"


def _build_patent_fees(doc: L.HtmlElement) -> list[FeeItem]:
    fees: list[FeeItem] = []
    seen_codes: set[str] = set()
    # PRV emits the entire patent table set multiple times (once per
    # accordion tab) — the unique-code guard prevents duplicate
    # FeeItems.
    seen_row_keys: set[tuple[str, str]] = set()

    for table in doc.cssselect("table"):
        rows = table.cssselect("tr")
        if not rows:
            continue
        header_cells = _row_cells(rows[0])
        if not _is_patent_header(header_cells):
            continue
        has_increased = len(header_cells) >= 5 and "increased" in header_cells[-1].lower()

        for tr in rows[1:]:
            cells = _row_cells(tr)
            if not cells or not cells[0] or cells[0].lower() == "inga träffar":
                continue
            if len(cells) < 4:
                continue
            code = cells[0].strip()
            label = cells[1].strip()
            # cells[2] = mandatory (Yes/No)
            fee_text = cells[3].strip()
            increased_text = cells[4].strip() if len(cells) >= 5 else ""
            row_key = (code, label[:60])
            if row_key in seen_row_keys:
                continue
            seen_row_keys.add(row_key)

            if not _PATENT_ID_RE.match(code.upper()):
                continue

            category = _categorize_patent(code, label)
            year: int | None = None
            if category is FeeCategory.renewal:
                year = _patent_annuity_year(label) or (
                    int(code.split("-")[1])
                    if "-" in code and code.split("-")[1].isdigit()
                    else None
                )
                if year is None:
                    year = 1

            condition = _patent_condition(code, label)

            # Parse the published amount. Some rows publish "0 kr"
            # (1st/2nd annuities) — that's a real zero, emit it. Others
            # publish "As described" / "By quotation" — skip (no
            # verifiable amount).
            if _looks_like_formula(fee_text):
                # PCT-5, PCT-18 prose-formula amounts → amount=0, formula in notes.
                amount = Decimal("0")
                base_notes = f"Formula: {fee_text}"
            elif _is_zero_explicit(fee_text):
                amount = Decimal("0")
                base_notes = None
            else:
                parsed = _parse_single_amount(fee_text)
                if parsed is None:
                    # No amount at all (KT-17 description-only / KT-22 external).
                    continue
                amount = parsed
                # Preserve per-unit hint from the raw cell.
                base_notes = None
                if "per sheet" in fee_text.lower():
                    base_notes = "Per sheet."
                elif "per hour" in fee_text.lower():
                    base_notes = "Per hour."
                elif "per search" in fee_text.lower():
                    base_notes = "Per search."
                elif "/each" in fee_text.lower():
                    base_notes = "Per each."

            slug = _slug("se", "pat", code.lower())
            slug = _unique(slug, seen_codes)
            fees.append(
                FeeItem(
                    code=slug,
                    label=f"{code}: {label}"[:200],
                    category=category,
                    rights=[RightType.patent],
                    amount=amount,
                    currency="SEK",
                    tier=EntityTier.none,
                    year=year,
                    condition=condition,
                    source_url=PRV_PATENTS_URL,
                    notes=base_notes,
                )
            )

            # Annuity "Increased fee" column → emit as a late_fee row
            # tied to the same year.
            if has_increased and increased_text:
                inc_amount = _parse_single_amount(increased_text)
                if inc_amount is not None and inc_amount > 0 and year is not None:
                    inc_slug = _unique(_slug("se", "pat", code.lower(), "increased"), seen_codes)
                    fees.append(
                        FeeItem(
                            code=inc_slug,
                            label=f"{code}: {label} (increased / late surcharge)"[:200],
                            category=FeeCategory.late_fee,
                            rights=[RightType.patent],
                            amount=inc_amount,
                            currency="SEK",
                            tier=EntityTier.none,
                            year=year,
                            condition=None,
                            source_url=PRV_PATENTS_URL,
                            notes="Increased annuity (20% surcharge) for late payment under Patentlagen ch.4.",
                        )
                    )
    return fees


# ──────────────────────────────────────────────────────────────────────
# Trademark / Design helpers
# ──────────────────────────────────────────────────────────────────────


_PER_CLASS_RE = re.compile(r"each additional class|for each additional class", re.IGNORECASE)


def _per_class_condition(label: str) -> FeeCondition | None:
    if _PER_CLASS_RE.search(label):
        return FeeCondition(
            trigger=ConditionalTrigger.classes_over,
            threshold=1,
            per_unit=True,
            description="Per class beyond the first.",
        )
    return None


def _categorize_trademark(label: str, h2: str) -> FeeCategory:
    d = label.lower()
    h = h2.lower()
    if "renewal" in d:
        if "late" in d or "increased fee" in d:
            return FeeCategory.late_fee
        return FeeCategory.renewal
    if "late renewal" in d:
        return FeeCategory.late_fee
    if "application for registration of a trademark" in d:
        return FeeCategory.filing
    if "each additional class" in d:
        return FeeCategory.excess_classes
    if "transfer" in d:
        return FeeCategory.transfer
    if "pledge" in d or "licence" in d or "license" in d:
        return FeeCategory.transfer
    if "division" in d:
        return FeeCategory.other
    if "revocation" in d:
        return FeeCategory.cancellation
    if "reinstatement" in d:
        return FeeCategory.late_fee
    if "international registration" in d or "international trademark" in d:
        return FeeCategory.madrid
    if "conversion" in d and "eu trademark" in d:
        return FeeCategory.madrid
    if "replacement" in d or "transformation" in d:
        return FeeCategory.madrid
    if "registration fee" in d:
        return FeeCategory.grant
    if "registration certificate" in d or "historical certificate" in d:
        return FeeCategory.other
    if "priority document" in d:
        return FeeCategory.other
    if "swedish official designation" in d:
        return FeeCategory.other
    if "change" in d:
        return FeeCategory.other
    if "international" in h:
        return FeeCategory.madrid
    return FeeCategory.other


def _categorize_design(label: str, h2: str) -> FeeCategory:
    d = label.lower()
    h = h2.lower()
    if "renewal" in d:
        return FeeCategory.renewal
    if "filing fee for registration" in d:
        return FeeCategory.filing
    if "additional five-year period" in d:
        # First-registration 2nd-period top-up — treat as filing add-on.
        return FeeCategory.filing
    if "multiple registration fee" in d:
        return FeeCategory.filing
    if "class fee" in d:
        return FeeCategory.excess_classes
    if "announcement fee" in d:
        return FeeCategory.publication
    if "storage fee" in d:
        return FeeCategory.other
    if "surcharge" in d and "after" in d:
        return FeeCategory.late_fee
    if "new owner" in d or "new license" in d or "licence" in d:
        return FeeCategory.transfer
    if "priority document" in d or "certificate of registered design" in d:
        return FeeCategory.other
    if "representative before euipo" in d:
        return FeeCategory.other
    if "community design" in h:
        return FeeCategory.other
    return FeeCategory.other


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
# Trademark / Design table walker (section-aware)
# ──────────────────────────────────────────────────────────────────────


def _iter_sectioned_tables(doc: L.HtmlElement) -> list[tuple[str, str, L.HtmlElement]]:
    """Yield ``(h2_text, channel_hint, table)`` for each fee table.

    PRV trademark + design pages organise tables by ``h2`` section
    with optional paragraph hints (e-service vs paper) between them.
    The walker tracks the nearest preceding ``h2`` and the index of
    the table inside that section to derive a channel hint:

    * First table under a section → ``"e-service"`` (PRV consistently
      lists the lower e-service rate first when there's an e-service /
      paper split).
    * Second table → ``"paper-or-other"``.
    * Third+ → ``""`` (no hint).

    The hint surfaces in the FeeItem ``notes`` and the slug suffix so
    e-service vs paper rates emit as distinct rows.
    """
    out: list[tuple[str, str, L.HtmlElement]] = []
    main = doc.cssselect("main") or [doc]
    current_h2 = ""
    tables_in_section = 0
    for el in main[0].iter():
        if el.tag == "h2":
            current_h2 = " ".join(el.text_content().split())
            tables_in_section = 0
        elif el.tag == "table":
            rows = el.cssselect("tr")
            if not rows:
                continue
            channel = ""
            section_lower = current_h2.lower()
            # Only apply the e-service / paper split where the section
            # itself implies it: application + renewal sections under
            # the Swedish track. Other sections (Other fees,
            # international protection) don't follow the pattern.
            if "swedish trademark" in section_lower or "changing, renewing" in section_lower:
                if tables_in_section == 0:
                    channel = "e-service"
                elif tables_in_section == 1:
                    channel = "paper-or-other"
            out.append((current_h2, channel, el))
            tables_in_section += 1
    return out


def _build_trademark_fees(doc: L.HtmlElement) -> list[FeeItem]:
    fees: list[FeeItem] = []
    seen_codes: set[str] = set()
    seen_keys: set[tuple[str, str, str]] = set()

    for h2, channel, table in _iter_sectioned_tables(doc):
        for tr in table.cssselect("tr"):
            cells = _row_cells(tr)
            if len(cells) < 2:
                continue
            label, fee_text = cells[0], cells[1]
            if not fee_text:
                continue
            amounts = _parse_sek_amounts(fee_text)
            if not amounts:
                continue
            amount = amounts[0]
            key = (h2, label[:60], channel)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            category = _categorize_trademark(label, h2)
            condition = _per_class_condition(label)
            # "For each additional class" overrides category.
            if condition is not None and "each additional class" in label.lower():
                category = FeeCategory.excess_classes

            year = 10 if category is FeeCategory.renewal else None

            notes_parts: list[str] = []
            if channel:
                notes_parts.append(
                    "Filed via PRV e-service (lower rate)."
                    if channel == "e-service"
                    else "Filed via paper / other channel."
                )
            if h2:
                notes_parts.append(f"Section: {h2}")
            notes = "; ".join(notes_parts) or None

            slug_bits = ["se", "tm"]
            if channel:
                slug_bits.append(channel)
            slug_bits.append(label[:50])
            base_slug = _slug(*slug_bits)
            slug = _unique(base_slug, seen_codes)

            fees.append(
                FeeItem(
                    code=slug,
                    label=label[:200],
                    category=category,
                    rights=[RightType.trademark],
                    amount=amount,
                    currency="SEK",
                    tier=EntityTier.none,
                    year=year,
                    condition=condition,
                    source_url=PRV_TRADEMARKS_URL,
                    notes=notes,
                )
            )
    return fees


def _build_design_fees(doc: L.HtmlElement) -> list[FeeItem]:
    fees: list[FeeItem] = []
    seen_codes: set[str] = set()
    seen_keys: set[tuple[str, str]] = set()

    # Design page uses single-table-per-paragraph organisation.
    # Channel hint: "electronic services" vs "paper" appears in the
    # row label itself, not as a section split, so we parse it from
    # the label directly.
    main = doc.cssselect("main") or [doc]
    current_h2 = ""
    for el in main[0].iter():
        if el.tag == "h2":
            current_h2 = " ".join(el.text_content().split())
            continue
        if el.tag != "table":
            continue
        for tr in el.cssselect("tr"):
            cells = _row_cells(tr)
            if len(cells) < 2:
                continue
            label, fee_text = cells[0], cells[1]
            amounts = _parse_sek_amounts(fee_text)
            if not amounts:
                continue
            amount = amounts[0]
            key = (current_h2, label[:60])
            if key in seen_keys:
                continue
            seen_keys.add(key)

            category = _categorize_design(label, current_h2)
            condition: FeeCondition | None = None
            lower = label.lower()
            if "class fee for each additional class" in lower:
                condition = FeeCondition(
                    trigger=ConditionalTrigger.classes_over,
                    threshold=1,
                    per_unit=True,
                    description="Per class beyond the first.",
                )
                category = FeeCategory.excess_classes

            # Design renewal carries the end-year of the 5-year period.
            # PRV labels do not encode period ordinals, so renewal
            # FeeItems carry year=10 (end of 1st 5-year extension)
            # as the v1 sentinel.
            year = 10 if category is FeeCategory.renewal else None

            # Channel hint from the label text itself.
            channel = ""
            if "electronic services" in lower or "using our electronic" in lower:
                channel = "e-service"
            elif "via paper" in lower or "paper och e-mail" in lower:
                channel = "paper-or-other"

            slug_bits = ["se", "des"]
            if channel:
                slug_bits.append(channel)
            slug_bits.append(label[:50])
            base_slug = _slug(*slug_bits)
            slug = _unique(base_slug, seen_codes)

            notes_parts: list[str] = []
            if channel:
                notes_parts.append(
                    "Filed via PRV e-service (lower rate)."
                    if channel == "e-service"
                    else "Filed via paper / other channel."
                )
            if current_h2:
                notes_parts.append(f"Section: {current_h2}")
            notes = "; ".join(notes_parts) or None

            fees.append(
                FeeItem(
                    code=slug,
                    label=label[:200],
                    category=category,
                    rights=[RightType.design],
                    amount=amount,
                    currency="SEK",
                    tier=EntityTier.none,
                    year=year,
                    condition=condition,
                    source_url=PRV_DESIGNS_URL,
                    notes=notes,
                )
            )
    return fees


# ──────────────────────────────────────────────────────────────────────
# Public scrape entry points
# ──────────────────────────────────────────────────────────────────────


_STATUTORY_PATENT = (
    "Patents Act 1967 (Patentlagen 1967:837) + Patent Decree "
    "(Patentkungörelsen 1967:838) + PRVFS fee orders. Fee changes "
    "effective 2025-03-15 (PRV news 2025-02-05); grant fee normalised "
    "to SEK 3000 effective 2025-12-01; PCT fees adjusted 2026-01-01 "
    "and 2026-04-01 for currency drift."
)
_STATUTORY_TRADEMARK = (
    "Trade Marks Act 2010 (Varumärkeslagen 2010:1877) + Trade Marks "
    "Ordinance (Varumärkesförordningen 2018:10) + PRVFS fee orders. "
    "Fee changes effective 2025-04-25."
)
_STATUTORY_DESIGN = (
    "Designs Protection Act 1970 (Mönsterskyddslagen 1970:485) + "
    "Designs Protection Ordinance (Mönsterskyddsförordningen 1970:486) "
    "+ PRVFS fee orders."
)


async def scrape_prv_patents() -> FeeSchedule:
    """Scrape PRV Sweden patent fees from the EN fees-and-payment page."""
    async with PrvFeesClient() as client:
        html_text = await client.fetch_html("patents")
    doc = L.fromstring(html_text)
    fees = _build_patent_fees(doc)
    if not fees:
        raise RuntimeError("PRV patent scraper parsed zero rows — page structure may have changed")
    return FeeSchedule(
        jurisdiction="SE",
        issuing_body="Patent- och registreringsverket (PRV)",
        office_code="PRV",
        right=RightType.patent,
        currency="SEK",
        effective_date=PRV_PATENTS_EFFECTIVE_DATE,
        source_url=PRV_PATENTS_URL,
        statutory_basis=_STATUTORY_PATENT,
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "PRV patent schedule. Annuity ladder (years 1-20) emits both "
            "regular and Increased-fee rows (20% surcharge for late "
            "payment under Patentlagen ch.4 §47). Years 1 + 2 publish "
            "SEK 0 'due together with 3rd annual fee'. SE-3 per-claim "
            "surcharge (SEK 150 per claim beyond 10) emits as "
            "excess_claims with classes_over threshold=10. PCT-2 per-"
            "sheet surcharge (SEK 180 per sheet) emits as excess_pages "
            "with pages_over threshold=30. SPC fees (NT-*) cover the "
            "Swedish portion under EU Reg. 469/2009. v1 GAPS: KT-6..KT-15 "
            "consultancy rows priced 'By quotation' are skipped (no "
            "verifiable amount); PCT-5 / PCT-18 prose-formula amounts "
            "emit amount=0 with formula preserved in notes. Sweden has "
            "no tiered entity discounts — all rows use EntityTier.none."
        ),
    )


async def scrape_prv_trademarks() -> FeeSchedule:
    """Scrape PRV Sweden trademark fees from the EN fees-and-payment page."""
    async with PrvFeesClient() as client:
        html_text = await client.fetch_html("trademarks")
    doc = L.fromstring(html_text)
    fees = _build_trademark_fees(doc)
    if not fees:
        raise RuntimeError(
            "PRV trademark scraper parsed zero rows — page structure may have changed"
        )
    return FeeSchedule(
        jurisdiction="SE",
        issuing_body="Patent- och registreringsverket (PRV)",
        office_code="PRV",
        right=RightType.trademark,
        currency="SEK",
        effective_date=PRV_TRADEMARKS_EFFECTIVE_DATE,
        source_url=PRV_TRADEMARKS_URL,
        statutory_basis=_STATUTORY_TRADEMARK,
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "PRV trademark schedule. The 'application' and 'changing/"
            "renewing' sections publish two tables apiece: the first is "
            "the PRV e-service rate (cheaper), the second is the paper / "
            "other-channel rate. Each rate emits as a separate FeeItem "
            "with -e-service / -paper-or-other slug suffixes. TM term "
            "is 10 years (Varumärkeslagen ch.2 §32); renewal FeeItems "
            "carry year=10. 'For each additional class' rows emit as "
            "excess_classes with classes_over threshold=1. International "
            "registration (Madrid Protocol) routing emits with "
            "FeeCategory.madrid; the WIPO-administered CHF portion is "
            "not duplicated here — see the WIPO-Madrid schedule. Sweden "
            "has no tiered entity discounts — all rows use "
            "EntityTier.none."
        ),
    )


async def scrape_prv_designs() -> FeeSchedule:
    """Scrape PRV Sweden design fees from the EN design fees page."""
    async with PrvFeesClient() as client:
        html_text = await client.fetch_html("designs")
    doc = L.fromstring(html_text)
    fees = _build_design_fees(doc)
    if not fees:
        raise RuntimeError("PRV design scraper parsed zero rows — page structure may have changed")
    return FeeSchedule(
        jurisdiction="SE",
        issuing_body="Patent- och registreringsverket (PRV)",
        office_code="PRV",
        right=RightType.design,
        currency="SEK",
        effective_date=PRV_DESIGNS_EFFECTIVE_DATE,
        source_url=PRV_DESIGNS_URL,
        statutory_basis=_STATUTORY_DESIGN,
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "PRV design schedule. Design term: 5-year initial period "
            "renewable up to 25 years (Mönsterskyddslagen ch.5 §24). "
            "Renewal FeeItems carry year=10 (end of 1st extension) as "
            "the v1 sentinel — PRV labels do not encode period ordinals "
            "on the EN page. E-service vs paper channel split is "
            "encoded in the row label itself (rather than as separate "
            "tables); the parser tags each FeeItem with the channel "
            "hint in notes + slug suffix. 'Class fee for each additional "
            "class' emits as excess_classes with classes_over "
            "threshold=1. Sweden has no tiered entity discounts — all "
            "rows use EntityTier.none."
        ),
    )


__all__ = [
    "PRV_BASE",
    "PRV_PATENTS_URL",
    "PRV_TRADEMARKS_URL",
    "PRV_DESIGNS_URL",
    "PRV_PATENTS_EFFECTIVE_DATE",
    "PRV_TRADEMARKS_EFFECTIVE_DATE",
    "PRV_DESIGNS_EFFECTIVE_DATE",
    "PrvFeesClient",
    "scrape_prv_patents",
    "scrape_prv_trademarks",
    "scrape_prv_designs",
]
