"""IP Australia fee-schedule scraper.

IP Australia publishes operational fees on:
https://www.ipaustralia.gov.au/patents/timeframes-and-fees

The page is organized as ~13 small 2-column ``Action | Fee`` tables
grouped by lifecycle stage (provisional, standard, search, examination,
acceptance, post-grant, etc.). Each table sits under its own h3
heading in tabs/accordions.

What this scraper covers:
* Filing, search, examination, acceptance, RCE-equivalent, opposition
  fees (everything published on the timeframes-and-fees page)

What this scraper does NOT cover (v1 gap):
* **Annual renewal fees** — IP Australia publishes the renewal fee
  schedule in Schedule 7 of the Patents Regulations 1991, not on the
  fees page. Years 5-20 renewal fees are not currently scraped. The
  schedule notes this gap explicitly and links to the regulations.
  A follow-up scraper can pull Schedule 7 from the AustLII federal
  register feed (https://www.legislation.gov.au/F2024L01237/latest).

Fees revised 2024-10-01 (full fee review); PCT fee equivalents
updated 2026-01-01.
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

IPA_FEES_URL = "https://www.ipaustralia.gov.au/patents/timeframes-and-fees"


class IPAustraliaFeesClient(BaseAsyncClient):
    """Tiny HTTP client for the IP Australia fees page."""

    DEFAULT_BASE_URL = "https://www.ipaustralia.gov.au"
    CACHE_NAME = "ipaustralia_fees"
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
                "Accept-Language": "en-AU,en;q=0.5",
            },
        )
        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def fetch_html(self) -> str:
        r = await self._request(
            "GET",
            "/patents/timeframes-and-fees",
            context="ipaustralia_fees",
        )
        return r.text


# ──────────────────────────────────────────────────────────────────────
# Parsing helpers
# ──────────────────────────────────────────────────────────────────────

_AMOUNT_RE = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)")


def _parse_money(raw: str) -> Decimal | None:
    """'$100' / '$1,100' / '$100 per month or part of month' → Decimal('100' etc).

    Takes the first dollar amount in the cell. Per-unit modifiers
    (e.g., '$100 per month', '$125 per claim') are captured as
    FeeConditions on the FeeItem.
    """
    m = _AMOUNT_RE.search(raw)
    if not m:
        return None
    cleaned = m.group(1).replace(",", "")
    try:
        return Decimal(cleaned)
    except Exception:
        return None


def _categorize(heading: str, description: str) -> FeeCategory:
    """Map IP Australia action labels onto our closed FeeCategory vocab.

    Heading comes from the section title preceding the table; description
    is the row's "Action" cell.
    """
    h = heading.lower()
    d = description.lower()
    if "extension of time" in h or "extension of time" in d:
        return FeeCategory.extension
    if "examination" in h or "examination" in d:
        if "more than" in d and "claim" in d:
            return FeeCategory.excess_claims
        if "re-examination" in d or "reexamination" in d:
            return FeeCategory.ptab
        return FeeCategory.examination
    if "acceptance" in h or "acceptance" in d:
        if "claim" in d and ("more than" in d or "contain" in d):
            return FeeCategory.excess_claims
        return FeeCategory.grant
    if "search" in h or "search" in d:
        return FeeCategory.search
    if "amend" in d:
        return FeeCategory.other
    if "provisional patent application" in d or "patent application" in d:
        return FeeCategory.filing
    if "document" in d or "copy of" in d:
        return FeeCategory.other
    if "opposition" in h or "opposition" in d:
        return FeeCategory.opposition
    return FeeCategory.other


def _detect_condition(description: str) -> FeeCondition | None:
    d = description.lower()
    if "per claim in that range" in d or "per added claim" in d or "per claim over" in d:
        # Try to extract the threshold
        m = re.search(r"more than (\d+)", d)
        threshold = int(m.group(1)) if m else 20
        return FeeCondition(
            trigger="claims_over",  # type: ignore[arg-type]
            threshold=threshold,
            per_unit=True,
            description="IP Australia per-claim surcharge above threshold.",
        )
    if "per month" in d:
        return FeeCondition(
            trigger="late_days",  # type: ignore[arg-type]
            per_unit=True,
            description="Per month (or part-month) of extension/late period.",
        )
    return None


def _slugify(heading: str, description: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", description.lower()).strip("-")[:50]
    h_slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")[:15]
    return f"au-{h_slug}-{base}" if h_slug else f"au-{base}"


# ──────────────────────────────────────────────────────────────────────
# Table walker
# ──────────────────────────────────────────────────────────────────────


def _preceding_heading(table: L.HtmlElement) -> str:
    """Walk up siblings + ancestors to find the closest h2/h3/h4 above the table."""
    cur = table
    for _ in range(20):
        prev = cur.getprevious()
        while prev is not None:
            if prev.tag in ("h2", "h3", "h4"):
                return prev.text_content().strip()
            # Look inside containers for headings
            hs = prev.cssselect("h2, h3, h4")
            if hs:
                return hs[-1].text_content().strip()
            prev = prev.getprevious()
        parent = cur.getparent()
        if parent is None:
            break
        cur = parent
    return ""


def _build_fees(doc: L.HtmlElement) -> list[FeeItem]:
    fees: list[FeeItem] = []
    seen_keys: set[str] = set()

    for table in doc.cssselect("table"):
        heading = _preceding_heading(table)
        for tr in table.cssselect("tr"):
            cells = [re.sub(r"\s+", " ", td.text_content().strip()) for td in tr.cssselect("td")]
            if len(cells) < 2:
                continue
            description, fee_raw = cells[0], cells[1]
            if not description or not fee_raw:
                continue
            amount = _parse_money(fee_raw)
            if amount is None:
                continue
            category = _categorize(heading, description)
            condition = _detect_condition(fee_raw + " " + description)
            key = f"{heading[:30]}|{description[:60]}|{amount}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            fees.append(
                FeeItem(
                    code=_slugify(heading, description),
                    label=description[:200],
                    category=category,
                    rights=[RightType.patent],
                    amount=amount,
                    currency="AUD",
                    tier=EntityTier.none,
                    condition=condition,
                    source_url=IPA_FEES_URL,
                    notes=(f"IP Australia section: {heading}" if heading else None),
                )
            )
    return fees


async def scrape_ipaustralia_patents() -> FeeSchedule:
    """Scrape IP Australia patent fees from the timeframes-and-fees page (AUD)."""
    async with IPAustraliaFeesClient() as client:
        html_text = await client.fetch_html()
    doc = L.fromstring(html_text)
    fees = _build_fees(doc)
    if not fees:
        raise RuntimeError(
            "IP Australia patent scraper parsed zero rows — page structure may have changed"
        )

    return FeeSchedule(
        jurisdiction="AU",
        issuing_body="IP Australia",
        office_code="IPAU",
        right=RightType.patent,
        currency="AUD",
        effective_date=date(2024, 10, 1),  # 2024 fee review commencement
        source_url=IPA_FEES_URL,
        statutory_basis=(
            "Patents Regulations 1991 (Cth) Schedule 7; fee review "
            "every 4 years, last full review effective 2024-10-01."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "Covers IP Australia's operational fees (filing, search, "
            "examination, acceptance, RCE-equivalent, opposition, "
            "extension-of-time, document requests). v1 GAP: annual "
            "renewal fees (years 5-20) are NOT included — they live in "
            "Schedule 7 of the Patents Regulations 1991 and are not "
            "published on the IP Australia fees page. A follow-up "
            "scraper can pull the regulation from the Federal Register "
            "of Legislation. Fees revised 2024-10-01 per the four-yearly "
            "fee review; PCT-fee AUD equivalents updated 2026-01-01."
        ),
    )


__all__ = [
    "IPA_FEES_URL",
    "IPAustraliaFeesClient",
    "scrape_ipaustralia_patents",
]
