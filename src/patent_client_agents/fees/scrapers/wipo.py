"""WIPO international fee schedules (PCT + Madrid + Hague).

Three international IP-registration systems, each with its own
schedule of fees published as the canonical statutory annex on
``wipo.int``. All amounts in CHF (Swiss francs).

* **PCT** (patents) — https://www.wipo.int/en/web/pct-system/texts/rules/rtax
* **Madrid** (trademarks) — https://www.wipo.int/en/web/madrid-system/fees/sched
* **Hague** (designs) — https://www.wipo.int/hague/en/fees/sched.html

The three pages share a similar structure: each row is an item with a
hierarchical numbering scheme (1, 1.1, 1.2, ..., 2.1.1, etc.), a
human description, and a CHF amount. Per-country designation fees
(handled separately) are out of scope for v1 — those are large
per-jurisdiction tables and would deserve their own route(s).

Schedule scope:

* PCT: international filing fee, supplementary search handling fee,
  handling fee, e-filing reductions, applicant-type reductions
* Madrid: basic application fee, supplementary class fee, complementary
  designation fee, subsequent designation, renewal, irregularity fees
* Hague: basic fee, publication fee, standard designation fee (3
  levels), additional-design fee, renewal-by-period fees

Per-country designation fees (Madrid's 126 contracting parties, Hague's
~50 contracting parties) are accessible from the same pages but live
in separate per-country tables. Those ship as a follow-up scraper if
the data is high-value enough.
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

WIPO_PCT_URL = "https://www.wipo.int/en/web/pct-system/texts/rules/rtax"
WIPO_MADRID_URL = "https://www.wipo.int/en/web/madrid-system/fees/sched"
WIPO_HAGUE_URL = "https://www.wipo.int/hague/en/fees/sched.html"


class WIPOFeesClient(BaseAsyncClient):
    """HTTP client for WIPO fee schedule pages.

    Single client used for all three systems (PCT/Madrid/Hague).
    Constructed with the full browser header set in case WIPO ever
    adopts JPO-style fingerprint protection (it doesn't today).
    """

    DEFAULT_BASE_URL = "https://www.wipo.int"
    CACHE_NAME = "wipo_fees"
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
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def fetch(self, url: str) -> str:
        # Convert full URL to path for the base-URL-relative request
        path = url.replace(self.DEFAULT_BASE_URL, "")
        r = await self._request("GET", path, context=f"wipo {path[:40]}")
        return r.text


# ──────────────────────────────────────────────────────────────────────
# Shared parsing helpers
# ──────────────────────────────────────────────────────────────────────

_AMOUNT_RE = re.compile(r"(\d[\d,]*)")
_ITEM_NUM_RE = re.compile(r"^(\d+(?:\.\d+)*)$")


def _parse_chf(raw: str) -> Decimal | None:
    """Pull the FIRST integer amount out of a CHF-labeled cell.

    Cells sometimes contain multiple numbers like '1,330 15' (basic
    fee + per-sheet) or '653' (single amount). We take the first
    figure as the headline amount; the per-sheet/per-class component
    is captured separately via FeeCondition when detectable.
    """
    m = _AMOUNT_RE.search(raw)
    if not m:
        return None
    cleaned = m.group(1).replace(",", "")
    try:
        val = Decimal(cleaned)
    except Exception:
        return None
    # Skip obviously-non-amount captures like item numbers ("1", "2.1")
    # — those have a corresponding text label we want to keep separate.
    if val <= 0:
        return None
    return val


def _is_item_number(text: str) -> bool:
    return bool(_ITEM_NUM_RE.match(text.strip()))


def _row_cells(tr: L.HtmlElement) -> list[str]:
    return [re.sub(r"\s+", " ", td.text_content().strip()) for td in tr.cssselect("td, th")]


# ──────────────────────────────────────────────────────────────────────
# PCT
# ──────────────────────────────────────────────────────────────────────


def _categorize_pct(item: str, description: str) -> FeeCategory:
    d = description.lower()
    if "international filing fee" in d:
        return FeeCategory.filing
    if "supplementary search" in d:
        return FeeCategory.search
    if "handling fee" in d:
        return FeeCategory.examination
    if "reduction" in d or "reduced" in d:
        return FeeCategory.other  # reduction modifiers are informational
    return FeeCategory.other


def _build_pct_fees(doc: L.HtmlElement) -> list[FeeItem]:
    fees: list[FeeItem] = []
    seen: set[str] = set()
    for table in doc.cssselect("table")[:1]:  # First table is the Schedule of Fees
        for tr in table.cssselect("tr"):
            cells = _row_cells(tr)
            if len(cells) < 3:
                continue
            # PCT layout: [item-num, description, ...amount-cells...]
            # Some rows have padding cells. Find the first numeric item-number
            # cell and treat the next non-empty cell as description.
            item_num = ""
            description = ""
            amount_text = ""
            non_empty = [c for c in cells if c]
            if len(non_empty) < 2:
                continue
            # First non-empty might be "1.", "2." style — treat as item
            if non_empty[0].rstrip(".").replace(".", "").isdigit() and len(non_empty[0]) <= 4:
                item_num = non_empty[0].rstrip(".")
                description = non_empty[1] if len(non_empty) > 1 else ""
                amount_text = " ".join(non_empty[2:]) if len(non_empty) > 2 else ""
            else:
                # Header or reduction row — skip
                continue
            if not description:
                continue
            amount = _parse_chf(amount_text)
            if amount is None:
                continue
            category = _categorize_pct(item_num, description)
            key = f"{item_num}|{description[:60]}"
            if key in seen:
                continue
            seen.add(key)
            fees.append(
                FeeItem(
                    code=f"wo-pct-{item_num.replace('.', '-')}",
                    label=description[:200],
                    category=category,
                    rights=[RightType.patent],
                    amount=amount,
                    currency="CHF",
                    tier=EntityTier.none,
                    condition=None,
                    source_url=WIPO_PCT_URL,
                    notes=f"PCT Schedule of Fees, item {item_num}",
                )
            )
    return fees


async def scrape_wipo_pct() -> FeeSchedule:
    """Scrape the PCT international fee schedule (CHF, applies to all PCT applicants)."""
    async with WIPOFeesClient() as client:
        html_text = await client.fetch(WIPO_PCT_URL)
    doc = L.fromstring(html_text)
    fees = _build_pct_fees(doc)
    if not fees:
        raise RuntimeError("WIPO PCT scraper parsed zero rows — page structure may have changed")

    return FeeSchedule(
        jurisdiction="WO",
        issuing_body="World Intellectual Property Organization (WIPO) — International Bureau",
        office_code="WIPO-PCT",
        right=RightType.patent,
        currency="CHF",
        effective_date=date(2026, 4, 1),  # Most recent PCT fee revision
        source_url=WIPO_PCT_URL,
        statutory_basis=(
            "Schedule of Fees annexed to the Regulations under the Patent Cooperation Treaty (PCT)."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "PCT international fees paid to the WIPO International "
            "Bureau, in CHF. Per-RO transmittal and search fees are "
            "NOT covered here — those vary by Receiving Office and "
            "ISA and are documented in the PCT Fee Tables PDF. v1 "
            "covers the three universal IB fees: international filing, "
            "supplementary search handling, and handling. E-filing "
            "reductions (CHF 100/200/300) and 90% applicant-type "
            "reductions are documented in the source page but not "
            "expanded as separate FeeItem rows in v1."
        ),
    )


# ──────────────────────────────────────────────────────────────────────
# Madrid
# ──────────────────────────────────────────────────────────────────────


def _categorize_madrid(item: str, description: str) -> FeeCategory:
    d = description.lower()
    # Leading-digit dispatch first (item number encodes category in the
    # Madrid schedule):
    #   1.x = [deleted]      2.x = international application
    #   3.x = [deleted]      4.x = irregularity classification
    #   5.x = subsequent designation
    #   6.x = renewal        7.x = changes / cancellations / corrections
    if item.startswith("2."):
        # 2.1.x = basic fee (color variants); 2.2 = supplementary class;
        # 2.3 = complementary designation; 2.4 = individual designation
        if item.startswith("2.1"):
            return FeeCategory.filing
        if item.startswith("2.2"):
            return FeeCategory.excess_classes
        if item.startswith("2.3") or item.startswith("2.4"):
            return FeeCategory.designation
    if item.startswith("4."):
        return FeeCategory.other  # classification irregularities
    if item.startswith("5."):
        return FeeCategory.designation  # subsequent designation
    if item.startswith("6."):
        return FeeCategory.renewal
    if item.startswith("7."):
        return FeeCategory.transfer
    # Fallback to description-based matching
    if "renewal" in d:
        return FeeCategory.renewal
    if "supplementary fee" in d and "class" in d:
        return FeeCategory.excess_classes
    if "designation" in d:
        return FeeCategory.designation
    if "basic fee" in d:
        return FeeCategory.filing
    return FeeCategory.other


def _split_madrid_row(text: str) -> tuple[str, str]:
    """Split a Madrid row's leading cell like '2.1.1 where no representation' → ('2.1.1', '...').

    Madrid rows put the item number + description in the same cell,
    separated by whitespace. The item number is one or more dotted
    integers at the start.
    """
    m = re.match(r"^(\d+(?:\.\d+)*)\s+(.+)$", text.strip())
    if m:
        return m.group(1), m.group(2)
    return "", text.strip()


def _build_madrid_fees(doc: L.HtmlElement) -> list[FeeItem]:
    fees: list[FeeItem] = []
    seen: set[str] = set()
    for table in doc.cssselect("table")[:1]:
        for tr in table.cssselect("tr"):
            cells = _row_cells(tr)
            if len(cells) < 2:
                continue
            label_cell = cells[0]
            amount_cell = cells[-1]  # last cell carries the CHF amount
            item, description = _split_madrid_row(label_cell)
            if not item:
                continue
            amount = _parse_chf(amount_cell)
            if amount is None:
                continue
            category = _categorize_madrid(item, description)
            # Renewal cycle = 10 years per the Madrid Protocol
            year = 10 if category == FeeCategory.renewal else None
            condition: FeeCondition | None = None
            if "per class" in description.lower() or ("for each class" in description.lower()):
                condition = FeeCondition(
                    trigger="classes_over",  # type: ignore[arg-type]
                    threshold=3,
                    per_unit=True,
                    description=(
                        "Madrid supplementary fee per class beyond the "
                        "first three (Madrid Protocol Article 8(2)(ii))."
                    ),
                )
            key = f"{item}|{description[:60]}"
            if key in seen:
                continue
            seen.add(key)
            fees.append(
                FeeItem(
                    code=f"wo-madrid-{item.replace('.', '-')}",
                    label=description[:200],
                    category=category,
                    rights=[RightType.trademark],
                    amount=amount,
                    currency="CHF",
                    tier=EntityTier.none,
                    year=year,
                    condition=condition,
                    source_url=WIPO_MADRID_URL,
                    notes=f"Madrid Schedule of Fees, item {item}",
                )
            )
    return fees


async def scrape_wipo_madrid() -> FeeSchedule:
    """Scrape the Madrid Protocol international fee schedule (CHF)."""
    async with WIPOFeesClient() as client:
        html_text = await client.fetch(WIPO_MADRID_URL)
    doc = L.fromstring(html_text)
    fees = _build_madrid_fees(doc)
    if not fees:
        raise RuntimeError("WIPO Madrid scraper parsed zero rows — page structure may have changed")

    return FeeSchedule(
        jurisdiction="WO",
        issuing_body="World Intellectual Property Organization (WIPO) — International Bureau",
        office_code="WIPO-MADRID",
        right=RightType.trademark,
        currency="CHF",
        effective_date=date(2024, 11, 11),  # Most recent Madrid fee revision
        source_url=WIPO_MADRID_URL,
        statutory_basis=(
            "Schedule of Fees annexed to the Common Regulations under "
            "the Madrid Agreement and the Madrid Protocol."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "Madrid Protocol international trademark fees paid to the "
            "WIPO International Bureau, in CHF. Per-country individual "
            "designation fees (set by each Contracting Party) are NOT "
            "covered here — those live in a separate 126-row table on "
            "wipo.int/madrid/en/fees/. v1 covers basic application, "
            "supplementary/complementary fees, subsequent designations, "
            "renewal (10-year cycle), and irregularity fees. The basic "
            "fee differs based on whether the mark contains color "
            "representation (Articles 8(2)(i) of the Protocol)."
        ),
    )


# ──────────────────────────────────────────────────────────────────────
# Hague
# ──────────────────────────────────────────────────────────────────────


def _categorize_hague(item: str, description: str) -> FeeCategory:
    d = description.lower()
    # Leading-digit dispatch (Hague's item numbers encode category):
    #   1.x = basic fee       2.x = publication fee
    #   3   = description-over-100-words surcharge
    #   4.x = standard designation (3 levels)
    #   5   = individual designation
    #   6   = [deleted]       7.x = renewal
    if item.startswith("7"):
        return FeeCategory.renewal
    if item.startswith("1"):
        return FeeCategory.filing
    if item.startswith("2"):
        return FeeCategory.publication
    if item.startswith("4") or item.startswith("5"):
        return FeeCategory.designation
    if "renewal" in d:
        return FeeCategory.renewal
    if "publication" in d:
        return FeeCategory.publication
    if "designation" in d:
        return FeeCategory.designation
    return FeeCategory.other


def _build_hague_fees(doc: L.HtmlElement) -> list[FeeItem]:
    fees: list[FeeItem] = []
    seen: set[str] = set()
    current_section: str = ""  # "I." / "III." (Roman numerals)
    for table in doc.cssselect("table")[:1]:
        for tr in table.cssselect("tr"):
            cells = _row_cells(tr)
            if not cells:
                continue
            # Section header (Roman numerals + section name + maybe header text)
            if len(cells) >= 2 and re.match(r"^(I|II|III|IV|V|VI)\.?$", cells[0].strip()):
                current_section = cells[1] if len(cells) > 1 else ""
                continue
            if len(cells) < 3:
                continue
            item_num, description, amount_cell = cells[0].strip().rstrip("."), cells[1], cells[-1]
            if not item_num or not _is_item_number(item_num):
                continue
            amount = _parse_chf(amount_cell)
            if amount is None:
                continue
            category = _categorize_hague(item_num, description)
            # Hague renewal periods: 1st (year 5), 2nd (year 10), 3rd (year 15), etc.
            year: int | None = None
            if category == FeeCategory.renewal:
                m = re.search(r"(first|second|third|fourth|fifth)", description, re.IGNORECASE)
                periods = {"first": 5, "second": 10, "third": 15, "fourth": 20, "fifth": 25}
                if m:
                    year = periods.get(m.group(1).lower())
            if category == FeeCategory.renewal and year is None:
                # Hague has a 5-year renewal cycle for each period; default to year 10
                year = 10
            condition: FeeCondition | None = None
            if "additional design" in description.lower():
                condition = FeeCondition(
                    trigger="multi_design",  # type: ignore[arg-type]
                    threshold=1,
                    per_unit=True,
                    description="Per additional design beyond the first.",
                )
            key = f"{current_section}|{item_num}|{description[:60]}"
            if key in seen:
                continue
            seen.add(key)
            section_label = f"Section: {current_section}" if current_section else None
            note_bits = ["Hague Schedule of Fees", f"item {item_num}"]
            if section_label:
                note_bits.append(section_label)
            fees.append(
                FeeItem(
                    code=f"wo-hague-{item_num.replace('.', '-')}",
                    label=description[:200],
                    category=category,
                    rights=[RightType.design],
                    amount=amount,
                    currency="CHF",
                    tier=EntityTier.none,
                    year=year,
                    condition=condition,
                    source_url=WIPO_HAGUE_URL,
                    notes="; ".join(note_bits),
                )
            )
    return fees


async def scrape_wipo_hague() -> FeeSchedule:
    """Scrape the Hague System international design fee schedule (CHF)."""
    async with WIPOFeesClient() as client:
        html_text = await client.fetch(WIPO_HAGUE_URL)
    doc = L.fromstring(html_text)
    fees = _build_hague_fees(doc)
    if not fees:
        raise RuntimeError("WIPO Hague scraper parsed zero rows — page structure may have changed")

    return FeeSchedule(
        jurisdiction="WO",
        issuing_body="World Intellectual Property Organization (WIPO) — International Bureau",
        office_code="WIPO-HAGUE",
        right=RightType.design,
        currency="CHF",
        effective_date=date(2025, 1, 1),  # Most recent Hague fee revision
        source_url=WIPO_HAGUE_URL,
        statutory_basis=(
            "Schedule of Fees annexed to the Common Regulations under "
            "the 1999 Act and the 1960 Act of the Hague Agreement."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "Hague System international design fees paid to the WIPO "
            "International Bureau, in CHF. Per-country designation fees "
            "(standard designation 3-level + individual designation per "
            "Contracting Party) are partially covered (the 3 standard "
            "levels are emitted); per-country individual fees live in "
            "a separate 48-row table on wipo.int/hague/en/fees/. v1 "
            "covers basic + publication + standard designation + "
            "additional-design + renewal-by-period. Renewal periods "
            "map: first=year 5, second=year 10, third=year 15, "
            "fourth=year 20, fifth=year 25."
        ),
    )


__all__ = [
    "WIPO_PCT_URL",
    "WIPO_MADRID_URL",
    "WIPO_HAGUE_URL",
    "WIPOFeesClient",
    "scrape_wipo_pct",
    "scrape_wipo_madrid",
    "scrape_wipo_hague",
]
