"""USPTO fee-schedule scraper.

The USPTO publishes patents, trademarks, and design fees on one HTML
page derived from the canonical PDF schedule:

  https://www.uspto.gov/learning-and-resources/fees-and-payment/uspto-fee-schedule

The page is a series of ``<table>`` blocks, one per fee category. Patent
tables have columns ``[code, 37 CFR §, description, large, small, micro]``;
TM tables have ``[37 CFR §, description, e-fee, e-code, paper-fee, paper-code]``.
A description-keyword filter splits utility/design/plant subtypes.

37 CFR §§ 1.16, 1.17, 1.18, 1.20 — patents
37 CFR §§ 2.6, 2.7 — trademarks
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

USPTO_FEES_URL = "https://www.uspto.gov/learning-and-resources/fees-and-payment/uspto-fee-schedule"


class USPTOFeesClient(BaseAsyncClient):
    """Tiny HTTP client for the USPTO fee-schedule HTML page.

    Inherits hishel SQLite caching from :class:`BaseAsyncClient`. We
    override the cache TTL to 7 days — fee adjustments don't happen
    weekly, and a 7-day window keeps upstream load minimal.
    """

    DEFAULT_BASE_URL = "https://www.uspto.gov"
    CACHE_NAME = "uspto_fees"
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_TTL_SECONDS = 7 * 24 * 3600  # 7 days

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("ttl_seconds", self.DEFAULT_TTL_SECONDS)
        kwargs.setdefault(
            "headers",
            {
                "User-Agent": "patent-client-agents (https://patentclient.com)",
            },
        )
        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def fetch_html(self) -> str:
        response = await self._request(
            "GET",
            "/learning-and-resources/fees-and-payment/uspto-fee-schedule",
            context="uspto_fee_schedule",
        )
        return response.text


# ──────────────────────────────────────────────────────────────────────
# Parsing helpers
# ──────────────────────────────────────────────────────────────────────

_AMOUNT_RE = re.compile(r"^[\d,]+(?:\.\d+)?$")
_EFFECTIVE_RE = re.compile(
    r"Effective\s+(\w+\s+\d+,\s*\d{4})\s*\(Last revised\s+(\w+\s+\d+,\s*\d{4})",
    re.IGNORECASE,
)
_MAINT_YEAR_RE = re.compile(r"due at (\d+(?:\.\d+)?)\s*year", re.IGNORECASE)


def _parse_money(raw: str) -> Decimal | None:
    """Parse '2,150.00' → Decimal('2150.00'). Returns None for 'n/a' / empty."""
    cleaned = raw.strip().replace(",", "")
    if not cleaned or cleaned.lower() in {"n/a", "na", "-", "—"}:
        return None
    if not _AMOUNT_RE.match(cleaned):
        # Some rows have additional annotations like "$x + see note"
        # Strip everything after the first non-numeric segment.
        m = re.match(r"^[\$]?([\d,]+(?:\.\d+)?)", cleaned.lstrip("$"))
        if not m:
            return None
        cleaned = m.group(1).replace(",", "")
    return Decimal(cleaned)


def _parse_effective_date(doc: L.HtmlElement) -> date:
    """Pull the most-recent revision date from the page header.

    Format: ``"Effective January 19, 2025 (Last revised May 1, 2026, …)"``.
    We use the *last revised* date because that's when the figures we're
    scraping last changed; the original effective date stamps the
    legislative baseline. Falls back to today if the header changes shape.
    """
    text = doc.text_content()
    m = _EFFECTIVE_RE.search(text)
    if not m:
        logger.warning("USPTO fees: effective-date header not found; falling back to today")
        return date.today()
    revised_raw = m.group(2).strip()
    try:
        from datetime import datetime

        return datetime.strptime(revised_raw, "%B %d, %Y").date()
    except ValueError:
        logger.warning("USPTO fees: could not parse revised date %r", revised_raw)
        return date.today()


def _is_design_row(description: str) -> bool:
    """True if a description belongs to a design-patent line item."""
    d = description.lower()
    # The schedule uses "- Design" in filing/issue/post-issuance rows;
    # design CPA is also tagged. Plant fees use "- Plant"; everything
    # else without those markers is utility-or-shared.
    return "- design" in d or "design cpa" in d


def _is_plant_row(description: str) -> bool:
    return "- plant" in description.lower()


def _is_utility_only_row(description: str) -> bool:
    return "- utility" in description.lower()


def _split_codes(raw: str) -> dict[EntityTier, str]:
    """Patent fee codes are 'large/small/micro' (e.g. '1011/2011/3011').

    A few rows (e.g., 4011†) are single-tier; treat as small entity
    (electronic-filing discount) by default and document in notes.
    """
    raw = raw.strip().rstrip("†*").strip()
    parts = [p.strip() for p in raw.split("/") if p.strip()]
    if len(parts) == 3:
        return {
            EntityTier.large: parts[0],
            EntityTier.small: parts[1],
            EntityTier.micro: parts[2],
        }
    if len(parts) == 1:
        # Single-code rows: see "4011" annotation — small-entity electronic-filing
        return {EntityTier.small: parts[0]}
    # Unexpected shape — log and skip
    logger.warning("USPTO fees: unexpected fee-code cell %r", raw)
    return {}


def _categorize_patent_table(caption: str, description: str, cfr: str) -> FeeCategory:
    """Map a table header + row context onto our closed FeeCategory vocab."""
    cap = caption.lower()
    desc = description.lower()
    if "extension of time" in cap:
        return FeeCategory.extension
    if "maintenance" in cap:
        if "surcharge" in desc or "late payment" in desc:
            return FeeCategory.late_fee
        if "petition" in desc:
            return FeeCategory.petition
        return FeeCategory.maintenance
    if "trial and appeal" in cap:
        if "appeal" in desc:
            return FeeCategory.appeal
        return FeeCategory.ptab
    if "petition" in cap:
        return FeeCategory.petition
    if "post issuance" in cap:
        if "reissue" in desc:
            return FeeCategory.reissue
        return FeeCategory.other
    if "search" in cap:
        return FeeCategory.search
    if "examination" in cap:
        return FeeCategory.examination
    if "issue and publication" in cap:
        if "publication" in desc:
            return FeeCategory.publication
        return FeeCategory.grant
    if "miscellaneous" in cap:
        if "request for continued examination" in desc or "rce" in desc:
            return FeeCategory.rce
        return FeeCategory.other
    if "application filing" in cap:
        if "excess" in desc:
            if "independent" in desc:
                return FeeCategory.excess_claims
            return FeeCategory.excess_claims
        if "size fee" in desc or "application size" in desc:
            return FeeCategory.application_size
        return FeeCategory.filing
    if "pct" in cap or "hague" in cap:
        return FeeCategory.filing
    if "penalty" in cap:
        return FeeCategory.other
    return FeeCategory.other


def _maintenance_year(description: str) -> int | None:
    """USPTO maintenance fees describe due dates as '3.5 year' / '7.5 year' / '11.5 year'.

    We store year as the integer year in which payment is due (rounding
    up: 3.5 → 4, 7.5 → 8, 11.5 → 12). The exact due window is captured
    in the row's ``notes`` field.
    """
    m = _MAINT_YEAR_RE.search(description)
    if not m:
        return None
    raw = m.group(1)
    val = float(raw)
    return int(val) + 1 if val % 1 else int(val)


def _detect_condition(description: str) -> FeeCondition | None:
    """Extract a structured FeeCondition for surcharges that key off counts."""
    desc = description.lower()
    if "each independent claim in excess of" in desc:
        m = re.search(r"in excess of\s*(\d+)", desc)
        return FeeCondition(
            trigger="independent_claims_over",  # type: ignore[arg-type]
            threshold=int(m.group(1)) if m else 3,
            per_unit=True,
            description="Per independent claim over threshold.",
        )
    if "each claim in excess of" in desc and "independent" not in desc:
        m = re.search(r"in excess of\s*(\d+)", desc)
        return FeeCondition(
            trigger="claims_over",  # type: ignore[arg-type]
            threshold=int(m.group(1)) if m else 20,
            per_unit=True,
            description="Per claim (total) over threshold.",
        )
    if "size fee" in desc and "for each additional" in desc:
        m = re.search(r"for each additional\s*(\d+)", desc)
        return FeeCondition(
            trigger="sheets_over",  # type: ignore[arg-type]
            threshold=100,
            per_unit=True,
            description=(f"Per additional {m.group(1) if m else '50'} sheets over 100."),
        )
    return None


def _row_iter(table: L.HtmlElement) -> list[list[str]]:
    rows = []
    for tr in table.cssselect("tbody tr"):
        cells = [td.text_content().strip() for td in tr.cssselect("td")]
        if cells:
            rows.append(cells)
    return rows


def _table_caption(table: L.HtmlElement) -> str:
    """The page uses thead's first th as the section header (no <caption> element)."""
    ths = table.cssselect("thead th")
    if ths:
        return ths[0].text_content().strip()
    return ""


def _build_patent_fees(
    doc: L.HtmlElement,
    *,
    right: RightType,
) -> list[FeeItem]:
    """Walk every patent-section table (tables 0..16) and emit FeeItems for the given right.

    ``right`` is :class:`RightType.patent` for utility (default) or
    :class:`RightType.design` for design patents. Plant patents are
    skipped — they need their own scraper.
    """
    fees: list[FeeItem] = []
    tables = doc.cssselect("table")
    # Patent section ends just before the trademark section. The first TM table
    # is recognizable by its header row containing "Electronically filed". Stop
    # iterating when we hit it.
    for table in tables:
        ths = [th.text_content().strip() for th in table.cssselect("thead th")]
        if any("Electronically filed" in h for h in ths):
            break
        caption = _table_caption(table)
        if not caption:
            continue
        if caption.lower().startswith("patent enrollment"):
            continue  # USPTO enrollment fees — out of scope for IP fees
        if caption.lower().startswith("patent penalty"):
            continue
        for cells in _row_iter(table):
            if len(cells) < 6:
                # Some rows are headers or footnotes; skip silently
                continue
            code_cell, cfr, description, large, small, micro = cells[:6]
            if _is_plant_row(description):
                continue
            if right == RightType.patent and _is_design_row(description):
                continue
            if right == RightType.design and not _is_design_row(description):
                # For designs, keep only design-tagged rows. The user
                # is expected to call patents scraper for shared procedural fees.
                continue

            codes = _split_codes(code_cell)
            if not codes:
                continue
            category = _categorize_patent_table(caption, description, cfr)
            year = _maintenance_year(description) if category == FeeCategory.maintenance else None
            condition = _detect_condition(description)

            amounts: dict[EntityTier, Decimal | None] = {
                EntityTier.large: _parse_money(large),
                EntityTier.small: _parse_money(small),
                EntityTier.micro: _parse_money(micro),
            }
            for tier, amount in amounts.items():
                if amount is None:
                    continue
                if tier not in codes:
                    # Single-tier row only published one code — use it for that tier
                    code = next(iter(codes.values()))
                else:
                    code = codes[tier]
                fees.append(
                    FeeItem(
                        code=code,
                        label=description,
                        category=category,
                        rights=[right],
                        amount=amount,
                        currency="USD",
                        tier=tier,
                        year=year,
                        condition=condition,
                        source_url=USPTO_FEES_URL,
                        notes=f"37 CFR § {cfr}" if cfr else None,
                    )
                )
    return fees


def _build_trademark_fees(doc: L.HtmlElement) -> list[FeeItem]:
    """Parse the trademark section tables.

    TM tables have a different shape than patent tables — each row has
    BOTH an electronic and a paper price (with separate fee codes for
    each filing method). We expand each row into up to two FeeItems and
    use a ``FeeCondition(trigger=paper_filing)`` on the paper variant.
    """
    fees: list[FeeItem] = []
    in_tm = False
    for table in doc.cssselect("table"):
        ths = [th.text_content().strip() for th in table.cssselect("thead th")]
        if any("Electronically filed" in h for h in ths):
            in_tm = True
        if not in_tm:
            continue
        caption = _table_caption(table)
        if not caption:
            continue
        cap = caption.lower()
        if cap.startswith("general service") or cap.startswith("fastener"):
            continue  # general service / FQA are not TM fees
        for cells in _row_iter(table):
            # Schema: [cfr, description, e-fee, e-code, paper-fee, paper-code]
            if len(cells) < 6:
                continue
            cfr, description, e_fee, e_code, p_fee, p_code = cells[:6]
            category = _categorize_tm_table(cap, description)
            # USPTO TM renewals are 10-year recurring (no per-year cadence).
            # The schema requires year for renewal/maintenance fees; use 10 as
            # the canonical mark and document in notes.
            tm_year = 10 if category == FeeCategory.renewal else None
            e_amount = _parse_money(e_fee)
            p_amount = _parse_money(p_fee)
            base_notes = f"37 CFR § {cfr}" if cfr else None
            if e_amount is not None and e_code.strip():
                fees.append(
                    FeeItem(
                        code=e_code.strip(),
                        label=description,
                        category=category,
                        rights=[RightType.trademark],
                        amount=e_amount,
                        currency="USD",
                        tier=EntityTier.none,
                        year=tm_year,
                        condition=_detect_tm_condition(description),
                        source_url=USPTO_FEES_URL,
                        notes=base_notes,
                    )
                )
            if p_amount is not None and p_code.strip():
                fees.append(
                    FeeItem(
                        code=p_code.strip(),
                        label=f"{description} (paper)",
                        category=category,
                        rights=[RightType.trademark],
                        amount=p_amount,
                        currency="USD",
                        tier=EntityTier.none,
                        year=tm_year,
                        condition=FeeCondition(
                            trigger="paper_filing",  # type: ignore[arg-type]
                            description="Paper-filing surcharge — applies when not e-filed.",
                        ),
                        source_url=USPTO_FEES_URL,
                        notes=base_notes,
                    )
                )
    return fees


def _categorize_tm_table(caption_lower: str, description: str) -> FeeCategory:
    desc = description.lower()
    if "post registration" in caption_lower:
        if "renewal" in desc:
            return FeeCategory.renewal
        if "declaration of use" in desc or "section 8" in desc or "section 71" in desc:
            return FeeCategory.declaration_of_use
        return FeeCategory.other
    if "trial and appeal" in caption_lower:
        if "opposition" in desc:
            return FeeCategory.opposition
        if "cancellation" in desc:
            return FeeCategory.cancellation
        if "appeal" in desc:
            return FeeCategory.appeal
        return FeeCategory.other
    if "madrid" in caption_lower:
        return FeeCategory.madrid
    if "petition" in caption_lower or "letter of protest" in caption_lower:
        return FeeCategory.petition
    if "application-related" in caption_lower or "application" in caption_lower:
        if "statement of use" in desc:
            return FeeCategory.statement_of_use
        if "intent to use" in desc or "extension" in desc:
            return FeeCategory.extension
        if "additional class" in desc:
            return FeeCategory.excess_classes
        if "insufficient information" in desc or "free-form" in desc or "free-text" in desc:
            return FeeCategory.filing
        return FeeCategory.filing
    if "service" in caption_lower:
        return FeeCategory.other
    return FeeCategory.other


def _detect_tm_condition(description: str) -> FeeCondition | None:
    desc = description.lower()
    if "per class" in desc or "additional class" in desc:
        return FeeCondition(
            trigger="classes_over",  # type: ignore[arg-type]
            threshold=1,
            per_unit=True,
            description="Per class — multi-class surcharge.",
        )
    return None


def _build_renewal_year_for_tm(_descr: str) -> int | None:
    # TM renewals are not year-indexed by USPTO (10-year term, recurring).
    # Returning None means we skip the year-iff-renewal validator's "renewal needs year" check.
    return None


# ──────────────────────────────────────────────────────────────────────
# Public scraper entry points
# ──────────────────────────────────────────────────────────────────────


async def _fetch_doc() -> tuple[L.HtmlElement, date]:
    """Fetch and parse the USPTO fee schedule, returning (doc, effective_date)."""
    async with USPTOFeesClient() as client:
        html_text = await client.fetch_html()
    doc = L.fromstring(html_text)
    effective = _parse_effective_date(doc)
    return doc, effective


def _wrap(
    fees: list[FeeItem],
    *,
    right: RightType,
    effective_date: date,
) -> FeeSchedule:
    return FeeSchedule(
        jurisdiction="US",
        issuing_body="U.S. Patent and Trademark Office",
        office_code="USPTO",
        right=right,
        currency="USD",
        effective_date=effective_date,
        source_url=USPTO_FEES_URL,
        statutory_basis="37 CFR Part 1 (patents); 37 CFR Part 2 (trademarks); 35 USC §§ 41, 376",
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "USPTO maintenance fees are due at the 3.5, 7.5, and 11.5 year "
            "marks; our schema rounds the year up (4, 8, 12). Paper-filing "
            "surcharges on TM fees are flagged via FeeCondition(trigger="
            "paper_filing). Some single-tier rows (e.g., '4011') represent "
            "tier-specific electronic-filing discounts and carry a single "
            "FeeItem under the applicable tier."
        ),
    )


async def scrape_uspto_patents() -> FeeSchedule:
    """Scrape the USPTO utility-patent fee schedule (excludes design + plant rows)."""
    doc, effective = await _fetch_doc()
    fees = _build_patent_fees(doc, right=RightType.patent)
    if not fees:
        raise RuntimeError("USPTO patent scraper parsed zero rows — page structure likely changed")
    return _wrap(fees, right=RightType.patent, effective_date=effective)


async def scrape_uspto_trademarks() -> FeeSchedule:
    """Scrape the USPTO trademark fee schedule."""
    doc, effective = await _fetch_doc()
    fees = _build_trademark_fees(doc)
    if not fees:
        raise RuntimeError(
            "USPTO trademark scraper parsed zero rows — page structure likely changed"
        )
    return _wrap(fees, right=RightType.trademark, effective_date=effective)


async def scrape_uspto_designs() -> FeeSchedule:
    """Scrape USPTO design-patent-specific fee rows.

    Returns only rows tagged as "Design" in the schedule (filing, issue,
    design CPA). Shared procedural fees (extensions, appeals, petitions)
    are NOT included — call :func:`scrape_uspto_patents` for those.
    """
    doc, effective = await _fetch_doc()
    fees = _build_patent_fees(doc, right=RightType.design)
    if not fees:
        raise RuntimeError("USPTO design scraper parsed zero rows — page structure likely changed")
    return _wrap(fees, right=RightType.design, effective_date=effective)


__all__ = [
    "USPTO_FEES_URL",
    "USPTOFeesClient",
    "scrape_uspto_patents",
    "scrape_uspto_trademarks",
    "scrape_uspto_designs",
]
