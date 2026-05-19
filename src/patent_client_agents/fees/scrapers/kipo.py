"""KIPO Korea fee-schedule scraper.

KIPO publishes patent fees on the English IP-system page:
https://www.kipo.go.kr/en/HtmlApp?c=92004&catmenu=ek03_04_01

The page contains 3 tables: Patent fees, Utility model fees, PCT fees.
Each is a 2-column ``Description | Fee(KRW)`` table with several
quirks that the parser handles:

* **Section headers** appear as single-cell rows ("Application Fee",
  "Examination Fee", "Annual Fee", "Others") that set the parser's
  current category state.
* **Embedded multi-part fees** — the page sometimes packs "a. Basic
  fee" + "b. Per claim" into adjacent rows; the description ends with
  "a. Basic fee" and the next row has just the "b." amount. We treat
  the second row as a per-claim surcharge (excess_claims).
* **Year-banded annuities** like CNIPA: "1 to 3 years", "4 to 6 years",
  ..., "16 to 25 years". The scraper expands each band into per-year
  FeeItem rows.

v1 scope: patent route only. Utility-model fees ship as a separate
route when needed (KIPO has substantial UM filings under separate
right=utility_model).

Effective date: 2023-08-01 per the most recent KIPO Enforcement Rule
amendment. KRW.
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

KIPO_FEES_URL = "https://www.kipo.go.kr/en/HtmlApp?c=92004&catmenu=ek03_04_01"


class KIPOFeesClient(BaseAsyncClient):
    """Tiny HTTP client for the KIPO English fees page."""

    DEFAULT_BASE_URL = "https://www.kipo.go.kr"
    CACHE_NAME = "kipo_fees"
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
                "Accept-Language": "en-US,en;q=0.5,ko;q=0.3",
            },
        )
        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def fetch_html(self) -> str:
        r = await self._request(
            "GET",
            "/en/HtmlApp",
            params={"c": "92004", "catmenu": "ek03_04_01"},
            context="kipo_fees",
        )
        return r.text


# ──────────────────────────────────────────────────────────────────────
# Parsing helpers
# ──────────────────────────────────────────────────────────────────────

_AMOUNT_RE = re.compile(r"^[\d,]+$")
_YEAR_RANGE_RE = re.compile(r"(\d+)\s*to\s*(\d+)\s*years?", re.IGNORECASE)


def _parse_money(raw: str) -> Decimal | None:
    """Pull the first integer amount out of a KIPO fee cell.

    Cells sometimes contain multiple values (e.g. "18,000(electronic)
    20,000(paper-based)"); we take the first (electronic) and treat
    the paper variant as a separate row when present.
    """
    m = re.search(r"([\d,]+)", raw)
    if not m:
        return None
    cleaned = m.group(1).replace(",", "")
    if not _AMOUNT_RE.match(cleaned):
        return None
    try:
        return Decimal(cleaned)
    except Exception:
        return None


def _section_to_category(section: str, description: str = "") -> FeeCategory:
    s = section.lower()
    d = description.lower()
    if "application fee" in s:
        if "extension" in d:
            return FeeCategory.extension
        return FeeCategory.filing
    if "examination" in s:
        if "preferential" in d:
            return FeeCategory.petition
        if "reexamination" in d:
            return FeeCategory.ptab
        if "priority" in d:
            return FeeCategory.other
        return FeeCategory.examination
    if "annual" in s:
        return FeeCategory.maintenance
    if "others" in s:
        if "converted" in d:
            return FeeCategory.other
        return FeeCategory.other
    return FeeCategory.other


def _detect_condition(description: str) -> FeeCondition | None:
    d = description.lower()
    if "per claim" in d or "per additional" in d:
        return FeeCondition(
            trigger="claims_over",  # type: ignore[arg-type]
            threshold=1,
            per_unit=True,
            description="KIPO per-claim surcharge.",
        )
    return None


def _slugify(section: str, description: str, year: int | None) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (description or section).lower()).strip("-")[:40]
    suffix = f"-y{year}" if year is not None else ""
    return f"kr-{base}{suffix}"


# ──────────────────────────────────────────────────────────────────────
# Table walker
# ──────────────────────────────────────────────────────────────────────


def _table_caption(table: L.HtmlElement) -> str:
    cap = table.cssselect("caption")
    return cap[0].text_content().strip() if cap else ""


def _row_cells(tr: L.HtmlElement) -> list[str]:
    return [re.sub(r"\s+", " ", td.text_content().strip()) for td in tr.cssselect("td, th")]


def _build_fees(doc: L.HtmlElement) -> list[FeeItem]:
    """Walk KIPO's patent-fees table and emit FeeItems for invention patents only."""
    target_table: L.HtmlElement | None = None
    for t in doc.cssselect("table"):
        if "Patent fees" in _table_caption(t):
            target_table = t
            break
    if target_table is None:
        raise RuntimeError("KIPO patent fees table not found on page")

    fees: list[FeeItem] = []
    current_section = ""
    pending_basic_label: str | None = None  # for "b. Per claim" follow-ons

    for tr in target_table.cssselect("tr")[1:]:  # skip header row
        cells = _row_cells(tr)
        if not cells:
            continue
        if len(cells) == 1:
            text = cells[0].strip()
            # A purely numeric single-cell row is a per-claim continuation
            # for the preceding "a. Basic fee" or "a. Annual basic fee" row.
            if re.match(r"^[\d,]+$", text):
                amount = _parse_money(text)
                if amount is not None and pending_basic_label is not None:
                    fees.append(
                        FeeItem(
                            code=_slugify(
                                current_section, pending_basic_label + " per-claim", None
                            ),
                            label=f"{pending_basic_label} — additional per-claim fee",
                            category=FeeCategory.excess_claims,
                            rights=[RightType.patent],
                            amount=amount,
                            currency="KRW",
                            tier=EntityTier.none,
                            condition=FeeCondition(
                                trigger="claims_over",  # type: ignore[arg-type]
                                threshold=1,
                                per_unit=True,
                                description="KIPO additional per-claim fee.",
                            ),
                            source_url=KIPO_FEES_URL,
                            notes=f"KIPO section: {current_section}",
                        )
                    )
                continue
            # Non-numeric single-cell row: section header
            current_section = text
            pending_basic_label = None
            continue
        if len(cells) >= 2:
            description, amount_raw = cells[0], cells[1]
            amount = _parse_money(amount_raw)
            if amount is None:
                continue

            # Year-banded annuity row?
            yr = _YEAR_RANGE_RE.search(description)
            if yr and "Annual" in current_section:
                start, end = int(yr.group(1)), int(yr.group(2))
                for year in range(start, end + 1):
                    fees.append(
                        FeeItem(
                            code=_slugify(current_section, description, year),
                            label=f"{description} (year {year})",
                            category=FeeCategory.maintenance,
                            rights=[RightType.patent],
                            amount=amount,
                            currency="KRW",
                            tier=EntityTier.none,
                            year=year,
                            condition=None,
                            source_url=KIPO_FEES_URL,
                            notes=f"KIPO section: {current_section}",
                        )
                    )
                # Note: KIPO annuity rows are followed by a per-claim row;
                # mark the pending basic for the next iteration.
                pending_basic_label = description
                continue

            # Standard data row
            category = _section_to_category(current_section, description)
            condition = _detect_condition(description)
            fees.append(
                FeeItem(
                    code=_slugify(current_section, description, None),
                    label=description[:200],
                    category=category,
                    rights=[RightType.patent],
                    amount=amount,
                    currency="KRW",
                    tier=EntityTier.none,
                    condition=condition,
                    source_url=KIPO_FEES_URL,
                    notes=f"KIPO section: {current_section}",
                )
            )
            # If this row ends with "Basic fee", note it so the next
            # bare-amount row can be tagged as per-claim.
            if description.lower().endswith("basic fee"):
                pending_basic_label = description
            else:
                pending_basic_label = None
    return fees


async def scrape_kipo_patents() -> FeeSchedule:
    """Scrape KIPO Korea patent fees (KRW, no entity tiers on the schedule itself)."""
    async with KIPOFeesClient() as client:
        html_text = await client.fetch_html()
    doc = L.fromstring(html_text)
    fees = _build_fees(doc)
    if not fees:
        raise RuntimeError("KIPO patent scraper parsed zero rows — page structure may have changed")

    return FeeSchedule(
        jurisdiction="KR",
        issuing_body="Korean Intellectual Property Office",
        office_code="KIPO",
        right=RightType.patent,
        currency="KRW",
        effective_date=date(2023, 8, 1),  # KIPO Enforcement Rule amendment
        source_url=KIPO_FEES_URL,
        statutory_basis=(
            "Enforcement Rule of the Korean Patent Act on Collection of "
            "Patent Fees (Korean MOIP / KIPO)."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "KIPO publishes fees in KRW with electronic + paper rate "
            "variants. Annuity bands (1-3, 4-6, 7-9, 10-12, 13-15, "
            "16-25 years) are expanded to per-year rows. Section "
            "headers ('Application Fee', 'Examination Fee', 'Annual "
            "Fee', 'Others') drive categorization. Per-claim surcharges "
            "appear as bare-amount rows immediately following a 'Basic "
            "fee' row — the scraper pairs them. KIPO entity discounts "
            "are administered through a separate refund program, not "
            "on the published schedule. v1 covers patents only; utility "
            "models ship under a separate route when needed."
        ),
    )


__all__ = [
    "KIPO_FEES_URL",
    "KIPOFeesClient",
    "scrape_kipo_patents",
]
