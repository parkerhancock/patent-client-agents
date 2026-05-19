"""DPMA Germany fee-schedule scraper.

DPMA's complete fee schedule lives in the official PDF
*"Information Concerning Costs, Fees and Expenses of the German Patent
and Trade Mark Office"* (form A 9510.1):

  https://www.dpma.de/docs/english/formulare/allg_eng/a9510_1.pdf

The HTML page (``/english/services/fees/patents/index.html``) only
covers years 3-6 of the annual fee schedule, then defers to the PDF
for years 7-20. To get a complete schedule we scrape the PDF using
``pypdf``.

The PDF format is regular::

    312 030    for the 3rd year of the patent ........................ 70
    312 040    for the 4th year of the patent ........................ 70
    ...
    312 200    for the 20th year of the patent ...................... 2 030

Fee numbers use a 6-digit code split as ``<class> <subclass>``. The
``31x`` range is patents:

  * 311 xxx — application + claim/page surcharges
  * 312 xxx — annual maintenance fees (year embedded in description)
  * 313 xxx — search
  * 314 xxx — examination / further processing
  * 315 xxx — opposition / appeal
  * 316-318  — recordation / restitutio / misc

v1 scope: patents only. UM, TM, and design ship under separate routes
when needed (they live at codes 32x / 33x / 34x in the same PDF).

Statutory basis: PatKostG (Patentkostengesetz) — Patent Cost Act —
plus accompanying ordinance setting the fee amounts.
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

DPMA_FEES_PDF_URL = "https://www.dpma.de/docs/english/formulare/allg_eng/a9510_1.pdf"
DPMA_FEES_HTML_URL = "https://www.dpma.de/english/services/fees/patents/index.html"


class DPMAFeesClient(BaseAsyncClient):
    """Tiny HTTP client for the DPMA cost-info PDF."""

    DEFAULT_BASE_URL = "https://www.dpma.de"
    CACHE_NAME = "dpma_fees"
    DEFAULT_TIMEOUT = 60.0
    DEFAULT_TTL_SECONDS = 7 * 24 * 3600

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
            "/docs/english/formulare/allg_eng/a9510_1.pdf",
            context="dpma_fees_pdf",
        )
        return r.content


# ──────────────────────────────────────────────────────────────────────
# PDF text extraction
# ──────────────────────────────────────────────────────────────────────


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Pull text out of the DPMA cost-info PDF via pypdf."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────
# Row regex
# ──────────────────────────────────────────────────────────────────────
# Each line item in the PDF looks like:
#   <3-digit class> <3-digit subclass>  <description ........>  <amount>
# Amounts use a non-breaking space as thousands separator: "1 130".

_FEE_ROW_RE = re.compile(
    r"""
    (?P<class>\d{3})\s+(?P<sub>\d{3})\s+        # 6-digit fee number
    (?P<desc>[A-Za-z\-][^\n]{4,250}?)\s*          # description (may start with 'for' or '-')
    \.{3,}\s*                                     # dot leader (always >= 3 dots in DPMA)
    (?P<amount>\d[\d ]*(?:[.,]\d+)?)\s*$          # amount; may have NBSP/space thousands
    """,
    re.MULTILINE | re.VERBOSE,
)

_YEAR_IN_DESC_RE = re.compile(
    r"for\s+the\s+(\d+)(?:st|nd|rd|th)\s+year\s+of\s+the\s+patent",
    re.IGNORECASE,
)


def _parse_amount(raw: str) -> Decimal | None:
    """'1 130' / '70' / '2 030' → Decimal. NBSP and regular space accepted."""
    cleaned = raw.strip().replace(" ", "").replace(" ", "").replace(",", ".")
    if not cleaned or not re.match(r"^\d+(\.\d+)?$", cleaned):
        return None
    return Decimal(cleaned)


# ──────────────────────────────────────────────────────────────────────
# Categorization
# ──────────────────────────────────────────────────────────────────────


def _is_patent_code(class_code: str) -> bool:
    """31x codes are patents in the DPMA fee schedule.

    320-329 are utility models, 33x are trademarks, 34x are designs.
    """
    return class_code.startswith("31")


def _categorize(class_code: str, description: str) -> FeeCategory:
    """DPMA fee codes mix categories within prefixes — categorize by description.

    Prefix 311 covers filing + search request + examination + SPC; 312 is
    annuities (year encoded in description); 313 is post-grant procedures.
    The closed vocab maps DPMA's PatKostG fee numbers to our categories.
    """
    d = description.lower()
    # Annuities (312) — always recurring
    if class_code.startswith("312"):
        if "surcharge" in d and "late payment" in d:
            return FeeCategory.late_fee
        return FeeCategory.maintenance
    # Claim surcharges
    if "more than ten patent claims" in d or "more than ten claims" in d:
        return FeeCategory.excess_claims
    if "for the eleventh and each further" in d:
        return FeeCategory.excess_claims
    # Specific descriptions
    if "containing up to ten patent claims" in d:
        return FeeCategory.filing
    if "search" in d and "section 43" in d:
        return FeeCategory.search
    if "when a request under section 43 has" in d:
        return FeeCategory.examination
    if "opposition" in d:
        return FeeCategory.opposition
    if "appeal" in d:
        return FeeCategory.appeal
    if "further processing" in d:
        return FeeCategory.late_fee
    if "restitutio" in d or "reinstatement" in d or "re-establishment" in d:
        return FeeCategory.petition
    if "limit or revoke the patent" in d:
        return FeeCategory.ptab
    if "entry of grant of licence" in d or "cancellation of the entry" in d or "licence" in d:
        return FeeCategory.transfer
    if (
        "supplementary protection" in d
        or "extension of duration" in d
        or "rectification of duration" in d
    ):
        return FeeCategory.extension
    if "search regarding an extended patent" in d:
        return FeeCategory.examination
    if "procedure for alteration" in d or "assessment procedure" in d:
        return FeeCategory.other
    return FeeCategory.other


def _detect_condition(description: str) -> FeeCondition | None:
    d = description.lower()
    if "for each further claim" in d:
        return FeeCondition(
            trigger="claims_over",  # type: ignore[arg-type]
            threshold=10,
            per_unit=True,
            description="DPMA per-claim excess over 10.",
        )
    if "for the eleventh and each further" in d:
        return FeeCondition(
            trigger="claims_over",  # type: ignore[arg-type]
            threshold=10,
            per_unit=True,
            description="DPMA per-claim excess over 10 (PCT national-phase form).",
        )
    return None


def _extract_year(description: str) -> int | None:
    m = _YEAR_IN_DESC_RE.search(description)
    return int(m.group(1)) if m else None


# ──────────────────────────────────────────────────────────────────────
# Public scraper
# ──────────────────────────────────────────────────────────────────────


def _build_fees(pdf_text: str) -> list[FeeItem]:
    fees: list[FeeItem] = []
    seen_codes: set[str] = set()
    for m in _FEE_ROW_RE.finditer(pdf_text):
        class_code = m.group("class")
        sub_code = m.group("sub")
        if not _is_patent_code(class_code):
            continue
        full_code = f"{class_code} {sub_code}"
        if full_code in seen_codes:
            continue
        description = re.sub(r"\s+", " ", m.group("desc")).strip()
        amount = _parse_amount(m.group("amount"))
        if amount is None:
            continue
        category = _categorize(class_code, description)
        year = (
            _extract_year(description)
            if category in (FeeCategory.maintenance, FeeCategory.late_fee)
            else None
        )
        # Skip non-year-tagged maintenance rows that aren't half-rate variants
        # of a year-tagged row — they end up as Other.
        if category == FeeCategory.maintenance and year is None:
            category = FeeCategory.other
        seen_codes.add(full_code)
        fees.append(
            FeeItem(
                code=full_code,
                label=description[:200],
                category=category,
                rights=[RightType.patent],
                amount=amount,
                currency="EUR",
                tier=EntityTier.none,
                year=year,
                condition=_detect_condition(description),
                source_url=DPMA_FEES_PDF_URL,
                notes=f"DPMA fee code {full_code}; PatKostG / Schedule of Fees",
            )
        )
    return fees


async def scrape_dpma_patents() -> FeeSchedule:
    """Scrape DPMA Germany patent fee schedule from the official cost-info PDF (EUR)."""
    async with DPMAFeesClient() as client:
        pdf_bytes = await client.fetch_pdf()
    text = _extract_pdf_text(pdf_bytes)
    fees = _build_fees(text)
    if not fees:
        raise RuntimeError("DPMA patent scraper parsed zero rows — PDF structure may have changed")

    return FeeSchedule(
        jurisdiction="DE",
        issuing_body="Deutsches Patent- und Markenamt (DPMA)",
        office_code="DPMA",
        right=RightType.patent,
        currency="EUR",
        # DPMA does not stamp a revision date in the PDF metadata; we
        # treat the schedule as current-as-of-fetch. PatKostG amendments
        # are gazetted and bind the office, so the operative effective
        # date is the most-recent PatKostG amendment.
        effective_date=date.today(),
        source_url=DPMA_FEES_HTML_URL,
        statutory_basis=(
            "Patentkostengesetz (PatKostG) and the accompanying ordinance "
            "setting fee amounts; published as form A 9510.1."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "Scraped from the DPMA cost-info PDF (form A 9510.1) "
            "because the English HTML fee page only lists years 3-6 of "
            "the annual fee schedule and punts to the PDF for years "
            "7-20. PDF parsing uses pypdf with regex extraction of the "
            "uniform '<6-digit code> <description> ... <amount>' row "
            "format. Fee numbers in the 31x range are patents; UM (32x), "
            "TM (33x), design (34x) live in the same PDF but under "
            "separate routes when implemented. Half-rate 'willingness "
            "to license' variants are included as separate maintenance "
            "rows with the same year."
        ),
    )


__all__ = [
    "DPMA_FEES_PDF_URL",
    "DPMA_FEES_HTML_URL",
    "DPMAFeesClient",
    "scrape_dpma_patents",
]
