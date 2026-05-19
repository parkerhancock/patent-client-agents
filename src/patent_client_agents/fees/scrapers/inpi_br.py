"""INPI Brazil fee-schedule scraper.

INPI (Instituto Nacional da Propriedade Industrial) publishes the
official English-language fee schedules as PDF artifacts under
``gov.br/inpi/en/costs-and-payment/``:

* Patents — ``schedule-of-fees-patents.pdf``
* Trademarks — ``schedule-of-fees-trademarks.pdf``
* Software — ``schedule-of-fees-software.pdf`` (out of v1 scope)

The ``tabelas-de-retribuicao`` landing page in pt-BR is Plone
role-restricted ("Conteúdo Restrito") and serves a login wall to
public crawlers, but the English PDFs under ``/en/costs-and-payment/``
are anonymously accessible. Path discovered 2026-05-19.

Source schedule citation
------------------------
The current English PDFs cite:
* Ordinance No. 39 of 3/7/2014 (MDIC)
* ME Ordinance No. 516 of 9/24/2019
* INPI Resolution No. 251 of 10/2/2019

A newer schedule was set under Portaria MDIC 110/2025 + Portaria
INPI/PR 10/2025 with phased effective dates through late 2025, but
INPI has NOT yet published the English PDFs reflecting that update —
the live PDFs at the above URLs are the 2019/2020 schedule.

Layout
------
Each fee row reads as:

    <CODE> <Service description (possibly wrapping)> <Amount> <Discounted>

Amounts use Brazilian decimal format: ``1.595,00`` means 1595.00 (the
``.`` is a thousands separator, ``,`` is the decimal mark). Codes are
3-4 digits, occasionally with a ``-N`` suffix.

The discounted column applies the **up-to-60% reduction** under
Resolution 251/2019 §I.5 for:

* individuals with no corporate stake in the field
* micro-enterprises, sole proprietors, small-sized companies
  (Complementary Law 123/2006)
* cooperatives (Law 5,764/1971)
* educational and research institutions
* nonprofit entities, public bodies acting on their own account

We map the standard column to ``EntityTier.large`` and the discounted
column to ``EntityTier.small``. The schedule footnote notes "The
discount does not apply to all codes" — discounted amounts that match
the standard amount (i.e., no discount) are still emitted as the
``small`` tier so a caller filtering by tier always gets a result.

Year bands
----------
Patent of invention (20-yr term):
  ``222/223`` 3-6, ``224/225`` 7-10, ``226/227`` 11-15, ``228/229`` 16+
Utility model patent (15-yr term):
  ``242/243`` 3-6, ``244/245`` 7-10, ``246/247`` 11+
Certificate of addition (mirrors invention term):
  ``232/233`` 3-6, ``234/235`` 7-10, ``236/237`` 11-15, ``238/239`` 16+

``222/224/226/228`` are the **regular-term** rates;
``223/225/227/229`` are the **extended-term** rates (paid late). Both
get expanded per-year and both ship as renewal FeeItems with
``year=N``.

Trademark renewal cycle
-----------------------
Brazil follows the Madrid Protocol 10-year cycle. Codes ``374/375``
(renewal regular/extended terms) are emitted at ``year=10``.

Statutory basis
---------------
The fee structure is set by Lei 9.279/1996 (Brazilian IP Law) and
implemented by INPI resolutions + the underlying MDIC Ordinances.

v1 scope
--------
Direct fee codes only (60 codes for patents). Out of scope:

* Complex per-claim surcharges with multi-tier prose pricing
  (e.g., "additional R$100 per claim from the 11th to the 15th;
  R$200 per claim from the 16th to the 30th; R$500 from the 31st
  on") — these are documented in the patent PDF as paragraph
  prose, not column-cell amounts; capturing them requires bespoke
  prose parsing.
* PCT-section variable-amount rows ("Variable", "No charge").
* The 2025 Portaria 10 schedule (not yet published in EN PDF).

These gaps are documented in the schedule notes.
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

INPI_BR_PATENT_PDF_URL = "https://www.gov.br/inpi/en/costs-and-payment/schedule-of-fees-patents.pdf"
INPI_BR_TM_PDF_URL = "https://www.gov.br/inpi/en/costs-and-payment/schedule-of-fees-trademarks.pdf"
INPI_BR_LANDING_URL = "https://www.gov.br/inpi/en/costs-and-payment"


class INPIBrazilFeesClient(BaseAsyncClient):
    """HTTP client for the INPI Brazil English fee PDFs."""

    DEFAULT_BASE_URL = "https://www.gov.br"
    CACHE_NAME = "inpi_br_fees"
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
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/pdf,*/*",
                "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8",
            },
        )
        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def fetch_pdf(self, path: str) -> bytes:
        r = await self._request("GET", path, context=f"inpi_br_fees {path[:40]}")
        return r.content


# ──────────────────────────────────────────────────────────────────────
# Amount + PDF text helpers
# ──────────────────────────────────────────────────────────────────────

# Brazilian decimal format: "1.595,00" → 1595.00; "780,00" → 780.00
_AMOUNT_RE = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}")
# Amount pair separated by whitespace = (standard, discounted)
_PAIR_RE = re.compile(rf"({_AMOUNT_RE.pattern})\s+({_AMOUNT_RE.pattern})")
# A fee code: 3-4 digits, optionally with -N suffix. Must NOT be a
# decimal fragment (preceded or followed by digit/comma/period) and
# must not be a year (1990-2030).
_CODE_RE = re.compile(r"(?<![,\.\d])(\d{3}-\d|\d{3,4})(?![\d\.,])")


def _parse_br_amount(raw: str) -> Decimal | None:
    """Parse a Brazilian-format decimal '1.595,00' → Decimal('1595.00')."""
    if not raw:
        return None
    cleaned = raw.replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except Exception:
        return None


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Return whitespace-collapsed text of the fee PDF."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    parts = [page.extract_text() or "" for page in reader.pages]
    raw = "\n".join(parts)
    return re.sub(r"\s+", " ", raw).strip()


def _is_year(code: str) -> bool:
    return len(code) == 4 and code.isdigit() and 1990 <= int(code) <= 2030


# ──────────────────────────────────────────────────────────────────────
# Year-band expansion
# ──────────────────────────────────────────────────────────────────────

# Maps (code) → (right, year_start, year_end_or_None_for_open, term_cap)
# When ``year_end_or_None`` is None, the band is open-ended ("Nth year
# and on") and gets expanded up to the term_cap. The term cap follows
# Lei 9.279/1996 art. 40: invention 20 years, utility model 15 years.

_PATENT_TERM_CAP_INVENTION = 20
_PATENT_TERM_CAP_UTILITY_MODEL = 15

# Code → (band_start, band_end_or_open, term_cap, right_label)
_ANNUITY_BANDS: dict[str, tuple[int, int | None, int, str]] = {
    # Invention annuities — regular term
    "222": (3, 6, _PATENT_TERM_CAP_INVENTION, "invention (regular term)"),
    "224": (7, 10, _PATENT_TERM_CAP_INVENTION, "invention (regular term)"),
    "226": (11, 15, _PATENT_TERM_CAP_INVENTION, "invention (regular term)"),
    "228": (16, None, _PATENT_TERM_CAP_INVENTION, "invention (regular term)"),
    # Invention annuities — extended term (paid late surcharge)
    "223": (3, 6, _PATENT_TERM_CAP_INVENTION, "invention (extended term)"),
    "225": (7, 10, _PATENT_TERM_CAP_INVENTION, "invention (extended term)"),
    "227": (11, 15, _PATENT_TERM_CAP_INVENTION, "invention (extended term)"),
    "229": (16, None, _PATENT_TERM_CAP_INVENTION, "invention (extended term)"),
    # Certificate of addition — regular
    "232": (3, 6, _PATENT_TERM_CAP_INVENTION, "certificate of addition (regular term)"),
    "234": (7, 10, _PATENT_TERM_CAP_INVENTION, "certificate of addition (regular term)"),
    "236": (11, 15, _PATENT_TERM_CAP_INVENTION, "certificate of addition (regular term)"),
    "238": (16, None, _PATENT_TERM_CAP_INVENTION, "certificate of addition (regular term)"),
    # Certificate of addition — extended
    "233": (3, 6, _PATENT_TERM_CAP_INVENTION, "certificate of addition (extended term)"),
    "235": (7, 10, _PATENT_TERM_CAP_INVENTION, "certificate of addition (extended term)"),
    "237": (11, 15, _PATENT_TERM_CAP_INVENTION, "certificate of addition (extended term)"),
    "239": (16, None, _PATENT_TERM_CAP_INVENTION, "certificate of addition (extended term)"),
    # Utility model — regular
    "242": (3, 6, _PATENT_TERM_CAP_UTILITY_MODEL, "utility model (regular term)"),
    "244": (7, 10, _PATENT_TERM_CAP_UTILITY_MODEL, "utility model (regular term)"),
    "246": (11, None, _PATENT_TERM_CAP_UTILITY_MODEL, "utility model (regular term)"),
    # Utility model — extended
    "243": (3, 6, _PATENT_TERM_CAP_UTILITY_MODEL, "utility model (extended term)"),
    "245": (7, 10, _PATENT_TERM_CAP_UTILITY_MODEL, "utility model (extended term)"),
    "247": (11, None, _PATENT_TERM_CAP_UTILITY_MODEL, "utility model (extended term)"),
}


def _years_for_code(code: str) -> list[int]:
    """Return the list of anniversary years a given annuity code covers."""
    band = _ANNUITY_BANDS.get(code)
    if band is None:
        return []
    start, end, cap, _ = band
    return list(range(start, (end if end is not None else cap) + 1))


# ──────────────────────────────────────────────────────────────────────
# Categorization
# ──────────────────────────────────────────────────────────────────────


def _categorize_patent(code: str, desc: str) -> tuple[FeeCategory, FeeCondition | None]:
    """Map (code, description) → (FeeCategory, optional condition)."""
    d = desc.lower()
    if code in _ANNUITY_BANDS:
        return FeeCategory.renewal, None
    if code in ("220", "221", "230", "231", "240", "241"):
        # Annual fee for application (pending grant). These pay yearly
        # but pre-grant — we treat them as renewals indexed by the year
        # they apply to. The PDF lists single amounts (no year band),
        # so we leave year=None and downgrade to ``other`` since the
        # schema requires a year on renewal/maintenance rows.
        return FeeCategory.other, None
    if code in ("212", "213"):
        return FeeCategory.grant, None
    if code in ("200", "201", "202", "203", "204", "205", "207", "284"):
        return FeeCategory.filing, None
    if code in ("203", "207", "281", "285") or "examination" in d:
        return FeeCategory.examination, None
    if code in ("214",):
        return FeeCategory.appeal, None
    if code in ("215", "216", "294"):
        return FeeCategory.cancellation, None
    if code in ("208", "209"):
        return FeeCategory.petition, None
    if code in ("248", "249"):
        return FeeCategory.transfer, None
    if code in ("277", "278", "279", "263", "276", "286", "283"):
        return FeeCategory.examination, None
    return FeeCategory.other, None


def _categorize_trademark(code: str, desc: str) -> tuple[FeeCategory, FeeCondition | None]:
    """Map (code, description) → (FeeCategory, optional condition) for TM."""
    d = desc.lower()
    if code in ("372", "373"):
        # First 10-year term — filing/grant. Treat as filing since it's
        # the application-grant phase.
        return FeeCategory.grant, None
    if code in ("374", "375"):
        # Renewal of registration (10-year cycle).
        return FeeCategory.renewal, None
    if code in ("389", "394"):
        return FeeCategory.filing, None
    if code in ("332",):
        return FeeCategory.opposition, None
    if code in ("336", "337"):
        return FeeCategory.cancellation, None
    if code in ("333", "3000", "3015", "3003"):
        return FeeCategory.appeal, None
    if code in ("348", "249", "380"):
        return FeeCategory.transfer, None
    if code in ("3001", "3002", "3017", "3018"):
        return FeeCategory.other, None
    if "per class" in d or "amount per class" in d:
        # Multi-class surcharge signal
        pass
    return FeeCategory.other, None


def _detect_per_class(desc: str) -> FeeCondition | None:
    """If the description marks 'amount per class', emit a per-class condition."""
    if "amount per class" in desc.lower() or "per class" in desc.lower():
        return FeeCondition(
            trigger="classes_over",  # type: ignore[arg-type]
            threshold=1,
            per_unit=True,
            description="INPI Brazil per-class fee under Nice classification.",
        )
    return None


# ──────────────────────────────────────────────────────────────────────
# Row extraction
# ──────────────────────────────────────────────────────────────────────


def _extract_rows(text: str) -> list[tuple[str, Decimal, Decimal, str]]:
    """Walk the collapsed PDF text and return (code, std, disc, desc) tuples.

    For each amount pair found in the text, look backward up to 250
    chars for the nearest fee-code-shaped token (excluding years and
    decimal fragments). The token's offset into the window marks the
    start of the row's description.
    """
    rows: list[tuple[str, Decimal, Decimal, str]] = []
    for m in _PAIR_RE.finditer(text):
        pair_start = m.start()
        window_start = max(0, pair_start - 250)
        window = text[window_start:pair_start]
        codes = [c for c in _CODE_RE.finditer(window) if not _is_year(c.group(1))]
        if not codes:
            continue
        last_code = codes[-1]
        code = last_code.group(1)
        desc_start = window_start + last_code.end()
        desc = text[desc_start:pair_start].strip(" -.()")
        desc = re.sub(r"\s+", " ", desc).strip()
        if not desc or len(desc) < 4:
            continue
        std = _parse_br_amount(m.group(1))
        disc = _parse_br_amount(m.group(2))
        if std is None or disc is None:
            continue
        rows.append((code, std, disc, desc))
    return rows


def _dedupe_rows(
    rows: list[tuple[str, Decimal, Decimal, str]],
) -> list[tuple[str, Decimal, Decimal, str]]:
    """Keep the first occurrence of each code."""
    seen: dict[str, tuple[str, Decimal, Decimal, str]] = {}
    for code, std, disc, desc in rows:
        if code not in seen:
            seen[code] = (code, std, disc, desc)
    return list(seen.values())


# ──────────────────────────────────────────────────────────────────────
# Patent scraper
# ──────────────────────────────────────────────────────────────────────


def _build_patent_fees(text: str) -> list[FeeItem]:
    rows = _dedupe_rows(_extract_rows(text))
    fees: list[FeeItem] = []
    for code, std, disc, desc in rows:
        category, condition = _categorize_patent(code, desc)
        years = _years_for_code(code)
        if category == FeeCategory.renewal and not years:
            # Renewal-categorized but no year band → downgrade to 'other'
            category = FeeCategory.other
        year_list: list[int | None] = list(years) if years else [None]
        for year in year_list:
            for tier, amount in (
                (EntityTier.large, std),
                (EntityTier.small, disc),
            ):
                fees.append(
                    FeeItem(
                        code=f"inpi-br-{code}-{tier.value[0]}"
                        + (f"-y{year}" if year is not None else ""),
                        label=f"INPI BR code {code}: {desc[:120]}",
                        category=category,
                        rights=[RightType.patent],
                        amount=amount,
                        currency="BRL",
                        tier=tier,
                        year=year,
                        condition=condition,
                        source_url=INPI_BR_PATENT_PDF_URL,
                        notes=(
                            f"INPI BR fee code {code}. Source: 'Schedule of Fees "
                            f"for Services Provided by INPI' (Ordinance 39/2014 + "
                            f"ME Ordinance 516/2019 + INPI Resolution 251/2019). "
                            f"Discount per Resolution 251 §I.5 (up to 60% for "
                            f"individuals / micro-enterprises / SMEs / cooperatives "
                            f"/ ICTs / non-profits / public bodies)."
                        ),
                    )
                )
    return fees


async def scrape_inpi_br_patents() -> FeeSchedule:
    """Scrape INPI Brazil patent fee schedule (BRL, large + small tiers)."""
    async with INPIBrazilFeesClient() as client:
        pdf_bytes = await client.fetch_pdf(
            "/inpi/en/costs-and-payment/schedule-of-fees-patents.pdf"
        )
    text = _extract_pdf_text(pdf_bytes)
    fees = _build_patent_fees(text)
    if not fees:
        raise RuntimeError(
            "INPI Brazil patent scraper parsed zero rows — PDF structure likely changed"
        )
    return FeeSchedule(
        jurisdiction="BR",
        issuing_body="Instituto Nacional da Propriedade Industrial (INPI)",
        office_code="INPI-BR",
        right=RightType.patent,
        currency="BRL",
        # Resolution 251 of 2019-10-02 is the most recent statutory anchor
        # on the EN PDF. A 2025 Portaria 10/Portaria 110 update has been
        # announced but the EN PDF has not yet been rewritten.
        effective_date=date(2019, 10, 2),
        source_url=INPI_BR_PATENT_PDF_URL,
        statutory_basis=(
            "Lei 9.279/1996 (Brazilian IP Law); Ordinance MDIC 39/2014; "
            "ME Ordinance 516/2019; INPI Resolution 251/2019."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "INPI Brazil covers invention patents (20-yr), utility model "
            "patents (15-yr), and certificates of addition under a single "
            "fee schedule. The 'discounted' column (mapped to EntityTier.small) "
            "applies a reduction up to 60% to individuals, micro-enterprises, "
            "SMEs, cooperatives, ICTs, non-profits, and public bodies under "
            "Resolution 251/2019 §I.5. v1 GAPS: (a) multi-tier per-claim "
            "surcharges for examination requests are published as prose "
            "(R$100 from 11-15, R$200 from 16-30, R$500 from 31+) and "
            "not as numeric columns — not captured; (b) PCT-section "
            "variable-amount rows are skipped; (c) a 2025 Portaria 10 "
            "update is announced but INPI has not yet republished the "
            "English PDF at this URL — figures here are the 2019/2020 "
            "schedule. The pt-BR landing page at /inpi/pt-br/servicos/"
            "tabelas-de-retribuicao is Plone-role-restricted ('Conteúdo "
            "Restrito') and not crawlable; this scraper uses the "
            "/inpi/en/costs-and-payment/ PDFs which are anonymous-accessible."
        ),
    )


# ──────────────────────────────────────────────────────────────────────
# Trademark scraper
# ──────────────────────────────────────────────────────────────────────


def _build_tm_fees(text: str) -> list[FeeItem]:
    rows = _dedupe_rows(_extract_rows(text))
    fees: list[FeeItem] = []
    for code, std, disc, desc in rows:
        category, condition = _categorize_trademark(code, desc)
        if condition is None:
            condition = _detect_per_class(desc)
        year: int | None = 10 if category == FeeCategory.renewal else None
        for tier, amount in (
            (EntityTier.large, std),
            (EntityTier.small, disc),
        ):
            fees.append(
                FeeItem(
                    code=f"inpi-br-tm-{code}-{tier.value[0]}",
                    label=f"INPI BR code {code}: {desc[:120]}",
                    category=category,
                    rights=[RightType.trademark],
                    amount=amount,
                    currency="BRL",
                    tier=tier,
                    year=year,
                    condition=condition,
                    source_url=INPI_BR_TM_PDF_URL,
                    notes=(
                        f"INPI BR TM fee code {code}. Source: 'Schedule of Fees "
                        f"for Services Provided by INPI' (Ordinance 39/2014 + "
                        f"ME Ordinance 516/2019 + INPI Resolution 251/2019). "
                        f"Discount per Resolution 251 §I.5."
                    ),
                )
            )
    return fees


async def scrape_inpi_br_trademarks() -> FeeSchedule:
    """Scrape INPI Brazil trademark fee schedule (BRL, large + small tiers, 10-yr cycle)."""
    async with INPIBrazilFeesClient() as client:
        pdf_bytes = await client.fetch_pdf(
            "/inpi/en/costs-and-payment/schedule-of-fees-trademarks.pdf"
        )
    text = _extract_pdf_text(pdf_bytes)
    fees = _build_tm_fees(text)
    if not fees:
        raise RuntimeError(
            "INPI Brazil trademark scraper parsed zero rows — PDF structure likely changed"
        )
    return FeeSchedule(
        jurisdiction="BR",
        issuing_body="Instituto Nacional da Propriedade Industrial (INPI)",
        office_code="INPI-BR",
        right=RightType.trademark,
        currency="BRL",
        effective_date=date(2019, 10, 2),
        source_url=INPI_BR_TM_PDF_URL,
        statutory_basis=(
            "Lei 9.279/1996 (Brazilian IP Law); Ordinance MDIC 39/2014; "
            "ME Ordinance 516/2019; INPI Resolution 251/2019."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "INPI Brazil trademark fees are quoted per-class in BRL for "
            "application (pre-approved vs free specification), the first "
            "10-year term, renewal (10-yr cycle), opposition, cancellation, "
            "and administrative invalidation. Per-class amounts are flagged "
            "via FeeCondition(classes_over=1, per_unit=True). Up-to-60% "
            "discount applies per Resolution 251/2019 §I.5 for individuals, "
            "SMEs, cooperatives, ICTs, non-profits, and public bodies."
        ),
    )


__all__ = [
    "INPI_BR_PATENT_PDF_URL",
    "INPI_BR_TM_PDF_URL",
    "INPI_BR_LANDING_URL",
    "INPIBrazilFeesClient",
    "scrape_inpi_br_patents",
    "scrape_inpi_br_trademarks",
]
