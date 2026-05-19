"""CIPO Canada fee-schedule scraper.

CIPO publishes its patent fee schedule at:
https://www.ic.gc.ca/eic/site/cipointernet-internetopic.nsf/eng/wr00142.html

The page has 4 unique tables (rendered twice each for print/screen
viewport variants — we dedupe by index):

1. Fees for applying for an extension of time
2. Fees respecting applications (filing, RCE, maintenance for pending apps)
3. Fees in respect of international applications (PCT national phase)
4. Fees in respect of patents (post-grant maintenance, reissue, transfers)

All tables share the column layout::

    [Fee type | Additional description | Small entity fee – YYYY | Standard fee – YYYY]

When the "Fee type" cell is empty, the row continues the parent fee
type (sub-row pattern) — we track the parent across rows.

Year-banded maintenance fees ("For the dates of each of the second,
third and fourth anniversaries") are expanded to per-year FeeItem
instances so a downstream lookup by year works.

Statutory basis: Patent Rules SOR/2019-251, schedule of fees. CIPO
publishes annually with an effective date of January 1; we encode
2026-01-01 for the current schedule (which is what the table headers
explicitly label).
"""

from __future__ import annotations

import logging
import re
from datetime import date
from decimal import Decimal

from lxml import html as L

from law_tools_core import BaseAsyncClient
from patent_client_agents.fees.models import (
    EntityTier,
    FeeCategory,
    FeeCondition,
    FeeItem,
    FeeSchedule,
    RightType,
)

logger = logging.getLogger(__name__)

CIPO_FEES_URL = "https://www.ic.gc.ca/eic/site/cipointernet-internetopic.nsf/eng/wr00142.html"


class CIPOFeesClient(BaseAsyncClient):
    """Tiny HTTP client for the CIPO fee-schedule HTML page."""

    DEFAULT_BASE_URL = "https://www.ic.gc.ca"
    CACHE_NAME = "cipo_fees"
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_TTL_SECONDS = 7 * 24 * 3600
    HTTP2 = True

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("ttl_seconds", self.DEFAULT_TTL_SECONDS)
        kwargs.setdefault(
            "headers",
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,*/*",
                "Accept-Language": "en-CA,en;q=0.5",
            },
        )
        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def fetch_html(self) -> str:
        r = await self._request(
            "GET",
            "/eic/site/cipointernet-internetopic.nsf/eng/wr00142.html",
            context="cipo_fees",
        )
        return r.text


# ──────────────────────────────────────────────────────────────────────
# Amount parsing
# ──────────────────────────────────────────────────────────────────────

_AMOUNT_RE = re.compile(r"^[\d,]+(?:\.\d+)?$")


def _parse_money(raw: str) -> Decimal | None:
    """Parse '1,027.00' / '297.00' / '8.58' → Decimal.

    'See description' (PCT rule-dependent fees) and similar non-numeric
    cells return None so they're skipped — we cannot synthesize a
    figure the office doesn't publish.
    """
    cleaned = raw.strip().replace(",", "")
    if not cleaned or "see description" in cleaned.lower():
        return None
    if not _AMOUNT_RE.match(cleaned):
        return None
    return Decimal(cleaned)


# ──────────────────────────────────────────────────────────────────────
# Year-band expansion
# ──────────────────────────────────────────────────────────────────────
# CIPO writes maintenance bands as English ordinals:
#   "second, third and fourth"             → [2,3,4]
#   "fifth, sixth, seventh, eighth and ninth" → [5,6,7,8,9]
#   "10th, 11th, 12th, 13th and 14th"      → [10,11,12,13,14]
#   "15th, 16th, 17th, 18th and 19th"      → [15,16,17,18,19]
#   "20th and each subsequent"             → [20]

_WORD_ORDINALS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}
_ORDINAL_RE = re.compile(r"(\d+)(?:st|nd|rd|th)", re.IGNORECASE)


def _parse_year_band(description: str) -> list[int]:
    """Extract the list of anniversary years described in a CIPO band row.

    Returns [] when the description doesn't look like a year band (which
    means the row is a one-shot fee, not a maintenance band).
    """
    desc = description.lower()
    years: set[int] = set()
    # Numeric ordinals: '10th', '11th', '12th', ...
    for m in _ORDINAL_RE.finditer(desc):
        years.add(int(m.group(1)))
    # English-word ordinals
    for word, n in _WORD_ORDINALS.items():
        # Match as a whole word
        if re.search(rf"\b{word}\b", desc):
            years.add(n)
    if not years:
        return []
    # If the band ends with "and each subsequent anniversary", keep
    # only the explicit year(s) — we don't expand past 20 because the
    # Patent Act caps the term.
    return sorted(years)


# ──────────────────────────────────────────────────────────────────────
# Categorization
# ──────────────────────────────────────────────────────────────────────


def _categorize(caption: str, fee_type: str, description: str) -> FeeCategory:
    cap = caption.lower()
    ft = fee_type.lower()
    d = description.lower()

    if "extension of time" in cap:
        return FeeCategory.extension
    if "international application" in cap:
        # PCT national-phase / transmittal / etc.
        return FeeCategory.filing
    if "fees respecting applications" in cap:
        if "application fee" in ft:
            return FeeCategory.filing
        if "late fee" in ft:
            return FeeCategory.late_fee
        if "maintenance" in ft:
            return FeeCategory.maintenance
        if "request for examination" in ft or "examination fee" in ft:
            if "excess of 20" in d:
                return FeeCategory.excess_claims
            return FeeCategory.examination
        if "advanced examination" in ft:
            return FeeCategory.examination
        if "continued examination" in ft:
            return FeeCategory.rce
        if "final fee" in ft:
            if "excess of 20" in d:
                return FeeCategory.excess_claims
            if "page" in d:
                return FeeCategory.excess_pages
            return FeeCategory.grant
        if "reinstatement" in ft:
            return FeeCategory.petition
        return FeeCategory.other
    if "in respect of patents" in cap:
        if "maintenance" in ft:
            return FeeCategory.maintenance
        if "late fee" in ft:
            return FeeCategory.late_fee
        if "reversal of deemed expiry" in ft:
            return FeeCategory.petition
        if "reissue" in ft:
            return FeeCategory.reissue
        if "re-examination" in ft:
            return FeeCategory.ptab  # closest analog
        if "registration of a document" in ft or "transfer" in ft or "change of name" in ft:
            return FeeCategory.transfer
        if "additional term" in ft or "reconsideration" in ft:
            return FeeCategory.other
        if "disclaimer" in ft:
            return FeeCategory.other
        if "correction of an error" in ft:
            return FeeCategory.petition
        return FeeCategory.other
    return FeeCategory.other


def _detect_condition(description: str) -> FeeCondition | None:
    d = description.lower()
    if "excess of 20" in d and "claim" in d:
        return FeeCondition(
            trigger="claims_over",  # type: ignore[arg-type]
            threshold=20,
            per_unit=True,
            description="CIPO per-claim excess over 20.",
        )
    if "each page of specification" in d:
        return FeeCondition(
            trigger="pages_over",  # type: ignore[arg-type]
            threshold=0,
            per_unit=True,
            description="Per page of specification + drawings (final-fee component).",
        )
    return None


# ──────────────────────────────────────────────────────────────────────
# Row walker
# ──────────────────────────────────────────────────────────────────────


def _build_fees(doc: L.HtmlElement) -> list[FeeItem]:
    """Walk every unique CIPO patent-fee table and emit FeeItems."""
    fees: list[FeeItem] = []
    seen_keys: set[str] = set()

    # The page repeats each table for print-vs-screen viewports; the
    # first occurrence of each caption is sufficient.
    seen_captions: set[str] = set()
    for table in doc.cssselect("table"):
        cap = table.cssselect("caption")
        caption = cap[0].text_content().strip() if cap else ""
        if not caption or caption in seen_captions:
            continue
        seen_captions.add(caption)

        rows = table.cssselect("tbody tr") or table.cssselect("tr")
        current_fee_type = ""
        for tr in rows:
            cells = [td.text_content().strip() for td in tr.cssselect("td")]
            if len(cells) < 4:
                continue
            fee_type, description, small_raw, std_raw = cells[:4]
            if fee_type:
                current_fee_type = fee_type
            effective_ft = current_fee_type or fee_type
            if not effective_ft or not description:
                continue
            small = _parse_money(small_raw)
            std = _parse_money(std_raw)
            if small is None and std is None:
                continue

            category = _categorize(caption, effective_ft, description)
            condition = _detect_condition(description)

            # Year-band expansion for maintenance fees
            years_for_row: list[int | None]
            if category == FeeCategory.maintenance:
                band = _parse_year_band(description)
                years_for_row = list(band) if band else [None]
            else:
                years_for_row = [None]

            label_base = (
                effective_ft if not description else f"{effective_ft} — {description[:120]}"
            )

            for year in years_for_row:
                # Maintenance rows must have a year per the schema
                if category == FeeCategory.maintenance and year is None:
                    continue
                for tier, amount in (
                    (EntityTier.small, small),
                    (EntityTier.large, std),
                ):
                    if amount is None:
                        continue
                    # Dedupe: same caption + fee_type + description + year + tier
                    key = f"{caption}|{effective_ft}|{description[:80]}|{year}|{tier.value}"
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    # Synthesize a code since CIPO doesn't publish numeric codes
                    code = _slugify(effective_ft, description, year, tier)
                    fees.append(
                        FeeItem(
                            code=code,
                            label=label_base,
                            category=category,
                            rights=[RightType.patent],
                            amount=amount,
                            currency="CAD",
                            tier=tier,
                            year=year,
                            condition=condition,
                            source_url=CIPO_FEES_URL,
                            notes=f"Patent Rules SOR/2019-251, schedule. Caption: {caption!r}",
                        )
                    )
    return fees


def _slugify(fee_type: str, description: str, year: int | None, tier: EntityTier) -> str:
    """CIPO publishes no numeric fee codes; synthesize a stable slug.

    Format: ``<fee-type-slug>[-y<year>]-<tier>``.
    Keeps within ~40 chars so MCP responses stay legible.
    """
    base = re.sub(r"[^a-z0-9]+", "-", fee_type.lower()).strip("-")[:30]
    suffix = f"-y{year}" if year is not None else ""
    return f"{base}{suffix}-{tier.value[0]}"


async def scrape_cipo_patents() -> FeeSchedule:
    """Scrape CIPO Canada patent fee schedule (CAD, small + standard tiers)."""
    async with CIPOFeesClient() as client:
        html_text = await client.fetch_html()
    doc = L.fromstring(html_text)
    fees = _build_fees(doc)
    if not fees:
        raise RuntimeError("CIPO patent scraper parsed zero rows — page structure likely changed")

    return FeeSchedule(
        jurisdiction="CA",
        issuing_body="Canadian Intellectual Property Office",
        office_code="CIPO",
        right=RightType.patent,
        currency="CAD",
        # CIPO column headers explicitly say "Small entity fee – YYYY".
        # The current schedule's year is hard-coded for now; a future
        # iteration could parse the year out of the column headers.
        effective_date=date(2026, 1, 1),
        source_url=CIPO_FEES_URL,
        statutory_basis="Patent Rules SOR/2019-251, Schedule of Fees",
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "CIPO publishes annually with January 1 effective date. The "
            "small-entity discount applies under Patent Act §44.1. "
            "Maintenance fees use English-band descriptions (e.g., 'second, "
            "third and fourth anniversaries') which the scraper expands "
            "into per-year FeeItem rows so lookup-by-year works. CIPO does "
            "not publish numeric fee codes; codes here are synthesized slugs."
        ),
    )


__all__ = [
    "CIPO_FEES_URL",
    "CIPOFeesClient",
    "scrape_cipo_patents",
]
