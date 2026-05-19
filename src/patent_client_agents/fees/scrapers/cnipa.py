"""CNIPA China fee-schedule scraper.

CNIPA publishes patent fees on a single hierarchical page (English
mirror) at:
https://english.cnipa.gov.cn/col/col3000/index.html

The page contains one large 2-column table (description | amount) with
Roman-numeral sections (I-XIV) and Arabic sub-sections. Patent fees
cover invention, utility model, and design patents — all under the
Chinese Patent Law — but each has its own filing/reexam/annuity row.

v1 scope: scrape only invention rows for the patent route. Utility
model and design ship as follow-ups via additional routes:

* ``CN/CNIPA/patents``       — invention patents (current)
* ``CN/CNIPA/utility_model`` — UM patents (future)
* ``CN/CNIPA/design``        — design patents (future)

Annuities are published as banded ranges
(``"1-3 Years (Each Year) | 900"``); the scraper expands each band to
per-year :class:`FeeItem` instances so lookup-by-year works.

Statutory basis: Patent Law of the PRC + Implementing Regulations; the
fee schedule itself is set by the State Council Pricing Bureau.
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

CNIPA_FEES_URL = "https://english.cnipa.gov.cn/col/col3000/index.html"


class CNIPAFeesClient(BaseAsyncClient):
    """Tiny HTTP client for the CNIPA English fee page."""

    DEFAULT_BASE_URL = "https://english.cnipa.gov.cn"
    CACHE_NAME = "cnipa_fees"
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
            },
        )
        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def fetch_html(self) -> str:
        r = await self._request("GET", "/col/col3000/index.html", context="cnipa_fees")
        return r.text


# ──────────────────────────────────────────────────────────────────────
# Parsing helpers
# ──────────────────────────────────────────────────────────────────────

_AMOUNT_RE = re.compile(r"^[\d,]+(?:\.\d+)?$")
_ROMAN_RE = re.compile(r"^(I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII|XIV|XV)\.")
_YEAR_RANGE_RE = re.compile(r"(\d+)\s*-\s*(\d+)\s*Years?", re.IGNORECASE)
_RIGHT_ROW_RE = re.compile(r"^\d+\.\s*(invention|utility\s*model|design)\b", re.IGNORECASE)


def _parse_money(raw: str) -> Decimal | None:
    cleaned = raw.strip().replace(",", "")
    if not cleaned or not _AMOUNT_RE.match(cleaned):
        return None
    return Decimal(cleaned)


_RIGHT_MAP = {
    "invention": RightType.patent,
    "utility model": RightType.utility_model,
    "utilitymodel": RightType.utility_model,
    "design": RightType.design,
}


def _detect_row_right(label: str) -> RightType | None:
    """If a row label names a specific right ('1. Invention'), return it."""
    m = _RIGHT_ROW_RE.match(label.strip())
    if not m:
        return None
    key = m.group(1).lower().replace(" ", "")
    return _RIGHT_MAP.get(key) or _RIGHT_MAP.get(m.group(1).lower())


def _category_for_section(roman: str, label: str = "") -> FeeCategory:
    """Map a Roman-numeral CNIPA section header to our closed vocab."""
    r = roman.upper()
    d = label.lower()
    if r == "I":
        return FeeCategory.filing
    if r == "II":
        if "claim" in d:
            return FeeCategory.excess_claims
        if "page" in d:
            return FeeCategory.excess_pages
        return FeeCategory.filing  # additional filing fee
    if r == "III":
        return FeeCategory.publication
    if r == "IV":
        return FeeCategory.other  # priority claim — closest analog
    if r == "V":
        return FeeCategory.examination
    if r == "VI":
        return FeeCategory.ptab  # reexamination is closest to PTAB
    if r == "VII":
        return FeeCategory.maintenance
    if r == "VIII":
        return FeeCategory.late_fee
    if r == "IX":
        return FeeCategory.petition  # restoration of right
    if r == "X":
        return FeeCategory.extension
    if r == "XI":
        return FeeCategory.transfer  # bibliographic change
    if r == "XII":
        return FeeCategory.other  # evaluation report (UM/design only)
    if r == "XIII":
        return FeeCategory.ptab  # invalidation announcement
    if r == "XIV":
        return FeeCategory.other  # certified copies
    return FeeCategory.other


def _detect_condition(roman: str, label: str) -> FeeCondition | None:
    d = label.lower()
    if roman == "II":
        if "each claim" in d and "exceeds 10" in d:
            return FeeCondition(
                trigger="claims_over",  # type: ignore[arg-type]
                threshold=10,
                per_unit=True,
                description="CNIPA per-claim excess over 10.",
            )
        if "each page" in d:
            return FeeCondition(
                trigger="pages_over",  # type: ignore[arg-type]
                threshold=30,  # CNIPA charges per page over 30 (50 CNY) then over 300 (100 CNY)
                per_unit=True,
                description=(
                    "CNIPA per-page excess. First tier (over 30 pages): 50 CNY/page. "
                    "Second tier (over 300 pages): 100 CNY/page."
                ),
            )
    return None


def _slugify(roman: str, label: str, year: int | None) -> str:
    """Synthesize a stable fee code since CNIPA publishes none."""
    base = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:40]
    suffix = f"-y{year}" if year is not None else ""
    return f"cn-{roman.lower()}-{base}{suffix}"


def _walk_table_rows(table: L.HtmlElement) -> list[tuple[str, str | None]]:
    """Flatten the CNIPA table to ``(label, amount_or_None)`` tuples."""
    rows: list[tuple[str, str | None]] = []
    for tr in table.cssselect("tr"):
        cells = [td.text_content().strip() for td in tr.cssselect("td, th")]
        if not cells:
            continue
        if len(cells) == 1:
            rows.append((cells[0], None))
        else:
            label, amount = cells[0], cells[1]
            rows.append((label, amount if amount else None))
    return rows


def _build_fees(doc: L.HtmlElement) -> list[FeeItem]:
    """Build the full set of invention-applicable patent fees from CNIPA's table."""
    # Find the fee table. CNIPA's page has nav tables + the data table;
    # the data table is the one that contains "Filing Fee" or "I." rows.
    target_table: L.HtmlElement | None = None
    for t in doc.cssselect("table"):
        text = t.text_content()
        if "Filing Fee" in text and "Annual Fee" in text:
            target_table = t
            break
    if target_table is None:
        raise RuntimeError("CNIPA fee table not found on page")

    rows = _walk_table_rows(target_table)

    # State machine
    current_roman: str | None = None
    current_section_label: str = ""
    current_right_for_subsection: RightType | None = None  # set when a sub-row names a right
    fees: list[FeeItem] = []

    for label, amount_str in rows:
        # New Roman section header? ("I.Filing Fee", "VII.Annual Fee")
        rm = _ROMAN_RE.match(label.strip())
        if rm:
            current_roman = rm.group(1)
            current_section_label = label.strip()
            current_right_for_subsection = None
            # Some section headers ALSO carry an amount (one-shot section,
            # e.g. "III.Printing Fee for Publishing the Application | 50",
            # "V.Fee for Substantive Examination ... | 2500"). Emit a fee
            # for those — the section header IS the line item.
            if amount_str:
                amount = _parse_money(amount_str)
                if amount is not None:
                    condition = _detect_condition(current_roman, current_section_label)
                    fees.append(
                        _make_fee(
                            roman=current_roman,
                            label=current_section_label,
                            amount=amount,
                            year=None,
                            condition=condition,
                        )
                    )
            continue

        # Sub-row that names a right ("1. Invention", "2. Utility Model")
        # — sets the subsection right for following sub-band rows.
        detected_right = _detect_row_right(label)
        if detected_right is not None:
            current_right_for_subsection = detected_right
            # Some "1. Invention" rows directly carry an amount (e.g., section I).
            if amount_str:
                amount = _parse_money(amount_str)
                if amount is not None and current_roman and detected_right == RightType.patent:
                    fees.append(
                        _make_fee(
                            roman=current_roman,
                            label=label,
                            amount=amount,
                            year=None,
                            condition=None,
                        )
                    )
            continue

        # Plain data row
        if amount_str is None:
            continue
        amount = _parse_money(amount_str)
        if amount is None or current_roman is None:
            continue

        # Year-banded annuity rows under section VII
        if current_roman == "VII":
            yr = _YEAR_RANGE_RE.search(label)
            if not yr:
                continue
            # Skip bands not under the invention subsection
            if current_right_for_subsection != RightType.patent:
                continue
            start, end = int(yr.group(1)), int(yr.group(2))
            for year in range(start, end + 1):
                fees.append(
                    _make_fee(
                        roman=current_roman,
                        label=label,
                        amount=amount,
                        year=year,
                        condition=None,
                    )
                )
            continue

        # Section VI (reexamination) is right-discriminated; only emit invention rows
        if current_roman == "VI" and current_right_for_subsection not in (
            None,
            RightType.patent,
        ):
            continue
        # Section XII (evaluation report) is UM/Design only — skip for patent
        if current_roman == "XII":
            continue
        # Section XIII (invalidation) is also right-discriminated when followed by
        # "1. Invention / 2. UM / 3. Design" rows. Skip non-invention.
        if current_roman == "XIII" and current_right_for_subsection not in (
            None,
            RightType.patent,
        ):
            continue

        condition = _detect_condition(current_roman, label)
        fees.append(
            _make_fee(
                roman=current_roman,
                label=label,
                amount=amount,
                year=None,
                condition=condition,
            )
        )

    return fees


def _make_fee(
    *,
    roman: str,
    label: str,
    amount: Decimal,
    year: int | None,
    condition: FeeCondition | None,
) -> FeeItem:
    category = _category_for_section(roman, label)
    return FeeItem(
        code=_slugify(roman, label, year),
        label=label[:200],
        category=category,
        rights=[RightType.patent],
        amount=amount,
        currency="CNY",
        tier=EntityTier.none,
        year=year,
        condition=condition,
        source_url=CNIPA_FEES_URL,
        notes=f"CNIPA section {roman}",
    )


async def scrape_cnipa_patents() -> FeeSchedule:
    """Scrape CNIPA China invention-patent fee schedule (CNY, no entity tiers)."""
    async with CNIPAFeesClient() as client:
        html_text = await client.fetch_html()
    doc = L.fromstring(html_text)
    fees = _build_fees(doc)
    if not fees:
        raise RuntimeError("CNIPA patent scraper parsed zero rows — page structure likely changed")

    return FeeSchedule(
        jurisdiction="CN",
        issuing_body="China National Intellectual Property Administration",
        office_code="CNIPA",
        right=RightType.patent,
        currency="CNY",
        # CNIPA's English page does not surface a per-revision date; we
        # treat the schedule as "current as of fetch" with the office's
        # publication-date convention being the official PRC State
        # Council pricing bureau notice.
        effective_date=date.today(),
        source_url=CNIPA_FEES_URL,
        statutory_basis=(
            "Patent Law of the People's Republic of China and Implementing "
            "Regulations; fee schedule set by State Council Pricing Bureau "
            "and CNIPA."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "Covers invention patents only in v1. Utility-model and "
            "design fees ship under separate routes when needed "
            "(CN/CNIPA/utility_model, CN/CNIPA/design). CNIPA publishes "
            "annuities as banded ranges (1-3yr, 4-6yr, etc.); the "
            "scraper expands each band into per-year rows so a "
            "downstream lookup by year works. Excess-page fee has a "
            "two-tier structure (50 CNY/page over 30 pages, 100 CNY/page "
            "over 300 pages) — both rows are emitted with their own "
            "FeeCondition. CNIPA does not differentiate by entity size "
            "on the schedule itself; small entities apply for reductions "
            "through a separate process (per the Note in section XV)."
        ),
    )


__all__ = [
    "CNIPA_FEES_URL",
    "CNIPAFeesClient",
    "scrape_cnipa_patents",
]
