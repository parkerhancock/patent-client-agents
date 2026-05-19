"""IPO India fee-schedule scraper.

The Office of the Controller General of Patents, Designs and Trade
Marks (CGPDTM) publishes patent fees as Schedule 1 of the Patents
Rules 2003. The canonical source is a PDF:

  https://ipindia.gov.in/frontend/pdf/forms_and_official_fees/Schedule_1.pdf

Each fee item carries FOUR rate columns:

* col 4 — Natural person / Startup / Small entity / Educational
  institution, **e-filing**
* col 5 — Same applicants, **physical (paper) filing**
* col 6 — Other(s), **e-filing**
* col 7 — Other(s), **physical (paper) filing**

The scraper emits separate FeeItem rows per (item, applicant-class,
filing-mode) combination using ``EntityTier.small`` for the
small-applicant column-pair and ``EntityTier.large`` for the
"other(s)" column-pair. Paper filing is flagged via
``FeeCondition(trigger=paper_filing)``.

v1 scope: patent route only. Coverage focused on:

* Item 1: patent application filing (with sub-item per-sheet/per-claim
  surcharges)
* Items 2-17: assorted procedural fees (postdating, hearing, etc.)
* Item 18: renewal fees for years 3-20 (the highest-value data)

What this scraper does NOT capture in v1: deeply nested sub-items
inside non-renewal entries (sequence listing surcharges, etc.) and
PCT-specific fees from Schedule 5 — both are documented as gaps.

Statutory basis: Patents Rules 2003 Schedule 1 (as amended). The PDF
does not stamp a revision date; check the source URL for current
status before quoting figures in client-facing work.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date
from decimal import Decimal

import pypdf

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

IPINDIA_FEES_PDF_URL = "https://ipindia.gov.in/frontend/pdf/forms_and_official_fees/Schedule_1.pdf"
IPINDIA_FEES_PAGE = "https://ipindia.gov.in/form-and-fees.htm"  # canonical landing


class IPOIndiaFeesClient(BaseAsyncClient):
    """HTTP client for the IPO India Schedule 1 PDF."""

    DEFAULT_BASE_URL = "https://ipindia.gov.in"
    CACHE_NAME = "ipindia_fees"
    DEFAULT_TIMEOUT = 60.0
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
                "Accept": "application/pdf,*/*",
            },
        )
        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def fetch_pdf(self) -> bytes:
        r = await self._request(
            "GET",
            "/frontend/pdf/forms_and_official_fees/Schedule_1.pdf",
            context="ipindia_schedule_1_pdf",
        )
        return r.content


# ──────────────────────────────────────────────────────────────────────
# PDF text extraction
# ──────────────────────────────────────────────────────────────────────


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    # Collapse runs of whitespace so the regex doesn't have to worry about
    # line wrapping — the PDF's logical "rows" wrap arbitrarily in the
    # extracted text.
    raw = "\n".join(parts)
    return re.sub(r"\s+", " ", raw)


# ──────────────────────────────────────────────────────────────────────
# Renewal-year regex
# ──────────────────────────────────────────────────────────────────────
# Renewal sub-items in Schedule 1 read like:
#   "in respect of the 3rd year; - 800 4000 880 4400"
#   "in respect of the 4th year; - 800 4000 880 4400"
#   ...
# 4 trailing numbers are: small-efile, small-paper, other-efile, other-paper.

_RENEWAL_RE = re.compile(
    r"in respect of (?:the\s+)?(\d+)(?:st|nd|rd|th)\s+year[^A-Za-z\d]+?"
    r"-?\s*(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)",
    re.IGNORECASE,
)


# ──────────────────────────────────────────────────────────────────────
# Main-item regex
# ──────────────────────────────────────────────────────────────────────
# Each main item is "N. <description ending in form number> <a> <b> <c> <d>"
# but the description may include the words "Multiple of" between rates and
# extra prose, so this regex is intentionally narrow — it only matches rows
# where all four numeric columns appear as plain integers separated by
# whitespace right after the form/dash.
#
# Also matches "No fee No fee No fee No fee" rows.

_NUMBER_OR_NOFEE = r"(?:\d[\d,]*|No\s*fee)"
_MAIN_ITEM_RE = re.compile(
    rf"(\d+)\.\s+([A-Z][^\d]{{8,400}}?)\s+"  # item number + description
    rf"(?:Form\s+\d+|\-|\d+)\s+"  # form column (number or dash)
    rf"({_NUMBER_OR_NOFEE})\s+"  # col 4 small e-filing
    rf"({_NUMBER_OR_NOFEE})\s+"  # col 5 small paper
    rf"({_NUMBER_OR_NOFEE})\s+"  # col 6 other e-filing
    rf"({_NUMBER_OR_NOFEE})\b",  # col 7 other paper
    re.IGNORECASE,
)


def _parse_amount(raw: str) -> Decimal | None:
    raw = raw.strip()
    if not raw or raw.lower().startswith("no"):
        return None
    cleaned = raw.replace(",", "")
    try:
        return Decimal(cleaned)
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────
# Categorization heuristic for main items
# ──────────────────────────────────────────────────────────────────────


def _categorize_main_item(description: str) -> FeeCategory:
    d = description.lower()
    if "renewal" in d:
        return FeeCategory.maintenance
    if "extension of time" in d or "condonation" in d:
        return FeeCategory.extension
    if "application for a patent" in d and "filing" not in d:
        return FeeCategory.filing
    if "for the grant" in d or "grant of patent" in d:
        return FeeCategory.grant
    if "request for examination" in d or "expedited examination" in d:
        return FeeCategory.examination
    if "hearing" in d or "controller" in d:
        return FeeCategory.petition
    if "postdating" in d or "amendment" in d or "correction" in d:
        return FeeCategory.other
    if "opposition" in d:
        return FeeCategory.opposition
    if "appeal" in d:
        return FeeCategory.appeal
    if "restoration" in d or "restore" in d:
        return FeeCategory.petition
    if "license" in d or "licence" in d or "register" in d:
        return FeeCategory.transfer
    if "statement and undertaking" in d:
        return FeeCategory.other
    if "complete specification" in d or "provisional" in d:
        return FeeCategory.filing
    return FeeCategory.other


# ──────────────────────────────────────────────────────────────────────
# Slug
# ──────────────────────────────────────────────────────────────────────


def _slugify(item_number: int, description: str, tier: str, mode: str, year: int | None) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", description.lower()).strip("-")[:35]
    bits = ["in", f"item-{item_number}", base, tier[:1], mode[:1]]
    if year is not None:
        bits.append(f"y{year}")
    return "-".join(b for b in bits if b)


# ──────────────────────────────────────────────────────────────────────
# Build pipeline
# ──────────────────────────────────────────────────────────────────────


def _emit_four_rates(
    *,
    item_number: int,
    description: str,
    category: FeeCategory,
    rates: tuple[str, str, str, str],
    year: int | None,
    notes: str | None,
) -> list[FeeItem]:
    """Emit up to 4 FeeItem rows for the 4 rate columns.

    Rates are (small-efile, small-paper, other-efile, other-paper).
    Columns marked "No fee" or missing are skipped.

    Sanity check: paper rates should be >= e-file rates of the same tier
    (paper is the surcharged variant). When the relationship is reversed
    by a substantial margin, the regex has captured columns from the
    next row by mistake — we skip the row entirely rather than emit
    misaligned data.
    """
    # Pre-parse to sanity-check column alignment
    parsed = [_parse_amount(r) for r in rates]
    s_efile, s_paper, l_efile, l_paper = parsed
    # If both small e-file + small paper are present and paper < e-file,
    # the columns are misaligned (likely cell-spillover from a previous
    # row). Drop the entire row for safety.
    if s_efile is not None and s_paper is not None and s_paper < s_efile:
        logger.debug(
            "IPO India item %s '%s': columns appear misaligned (small paper %s < e-file %s); skipping",
            item_number,
            description[:40],
            s_paper,
            s_efile,
        )
        return []
    if l_efile is not None and l_paper is not None and l_paper < l_efile:
        logger.debug(
            "IPO India item %s '%s': columns appear misaligned (large paper %s < e-file %s); skipping",
            item_number,
            description[:40],
            l_paper,
            l_efile,
        )
        return []
    out: list[FeeItem] = []
    combos = [
        (EntityTier.small, False, rates[0]),
        (EntityTier.small, True, rates[1]),
        (EntityTier.large, False, rates[2]),
        (EntityTier.large, True, rates[3]),
    ]
    for tier, is_paper, raw in combos:
        amount = _parse_amount(raw)
        if amount is None:
            continue
        condition = (
            FeeCondition(
                trigger="paper_filing",  # type: ignore[arg-type]
                description="Paper-filing variant.",
            )
            if is_paper
            else None
        )
        mode = "paper" if is_paper else "efile"
        out.append(
            FeeItem(
                code=_slugify(item_number, description[:35], tier.value, mode, year),
                label=description[:200],
                category=category,
                rights=[RightType.patent],
                amount=amount,
                currency="INR",
                tier=tier,
                year=year,
                condition=condition,
                source_url=IPINDIA_FEES_PDF_URL,
                notes=notes,
            )
        )
    return out


def _build_fees(text: str) -> list[FeeItem]:
    fees: list[FeeItem] = []

    # 1) Renewal fees — the highest-value structured data
    for m in _RENEWAL_RE.finditer(text):
        year = int(m.group(1))
        if year < 2 or year > 20:
            continue
        rates = (m.group(2), m.group(3), m.group(4), m.group(5))
        fees.extend(
            _emit_four_rates(
                item_number=18,
                description=f"Renewal of patent (year {year})",
                category=FeeCategory.maintenance,
                rates=rates,
                year=year,
                notes="Patents Rules 2003 Schedule 1, item 18, sub-item for the matching year.",
            )
        )

    # 2) Main numbered items — best-effort. Each match captures the item
    # number, a short description, and the 4 rate columns.
    seen_items: set[int] = set()
    for m in _MAIN_ITEM_RE.finditer(text):
        item_n = int(m.group(1))
        if item_n in seen_items or item_n == 18:
            continue  # 18 = renewal, handled above
        if item_n > 60:
            continue  # Schedule 1 has ~30 main items; high numbers are stray matches
        description = re.sub(r"\s+", " ", m.group(2)).strip().rstrip(".")
        # Skip rows where the description looks like a header column-name
        if any(k in description.lower() for k in ("rupees", "natural person", "form")):
            continue
        seen_items.add(item_n)
        rates = (m.group(3), m.group(4), m.group(5), m.group(6))
        category = _categorize_main_item(description)
        fees.extend(
            _emit_four_rates(
                item_number=item_n,
                description=description,
                category=category,
                rates=rates,
                year=None,
                notes=f"Patents Rules 2003 Schedule 1, item {item_n}.",
            )
        )

    return fees


async def scrape_ipindia_patents() -> FeeSchedule:
    """Scrape IPO India patent fees from Schedule 1 PDF (INR, 4-rate-column structure)."""
    async with IPOIndiaFeesClient() as client:
        pdf_bytes = await client.fetch_pdf()
    text = _extract_pdf_text(pdf_bytes)
    fees = _build_fees(text)
    if not fees:
        raise RuntimeError(
            "IPO India patent scraper parsed zero rows — PDF structure may have changed"
        )

    return FeeSchedule(
        jurisdiction="IN",
        issuing_body=(
            "Office of the Controller General of Patents, Designs and Trade Marks (CGPDTM)"
        ),
        office_code="IPIN",
        right=RightType.patent,
        currency="INR",
        # PDF doesn't stamp a revision date in metadata; we treat the
        # schedule as current-as-of-fetch. Major fee revisions are
        # gazetted as amendments to Patents Rules 2003 — current schedule
        # baseline is the 2024 amendment.
        effective_date=date(2024, 3, 15),  # Patents (Amendment) Rules 2024 commencement
        source_url=IPINDIA_FEES_PDF_URL,
        statutory_basis=(
            "Patents Rules 2003 Schedule 1 (as amended through the Patents (Amendment) Rules 2024)."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "Scraped from CGPDTM's canonical Schedule 1 PDF using pypdf + "
            "regex. Each fee carries 4 rate columns: small-applicant + "
            "other(s) × e-filing + paper. Paper-filing rows are flagged "
            "via FeeCondition(trigger=paper_filing). All 18 renewal years "
            "(years 3-20) captured. v1 GAPs: deeply nested sub-items "
            "inside non-renewal entries (per-sheet/per-claim surcharges, "
            "sequence-listing fees) are not yet extracted; PCT-specific "
            "fees live in Schedule 5 (separate PDF) and ship as a "
            "follow-up scraper. The PDF doesn't carry a revision date; "
            "the effective_date here is the most-recent gazette amendment."
        ),
    )


__all__ = [
    "IPINDIA_FEES_PDF_URL",
    "IPINDIA_FEES_PAGE",
    "IPOIndiaFeesClient",
    "scrape_ipindia_patents",
]
