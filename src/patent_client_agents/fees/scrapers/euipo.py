"""EUIPO fee-schedule scrapers (trademarks + designs).

* **Trademarks** — https://www.euipo.europa.eu/en/trade-marks/before-applying/fees-payable-direct-to-the-euipo
  Next.js page. Fee rows are embedded in the SSR stream as JSON; we
  decode the ``self.__next_f.push([1, "..."])`` chunks, then extract
  every ``"value":"...","component":"_table_col"`` triplet (code,
  description, amount).

* **Designs (REUD)** — https://www.euipo.europa.eu/en/designs/before-applying/fees-payable-direct-to-the-euipo
  Same site, but the design page ships with clean ``<table>``
  blocks. lxml parses them directly. Reformed by Regulation (EU)
  2024/2822 — back-loaded renewal curve at periods 1/2/3/4 (years
  5/10/15/20), combined application+publication fee, late surcharges
  abolished.

Both endpoints serve over HTTP/2 and require a browser-style
``User-Agent`` to avoid a 403.
"""

from __future__ import annotations

import json
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

EUIPO_TM_URL = (
    "https://www.euipo.europa.eu/en/trade-marks/before-applying/fees-payable-direct-to-the-euipo"
)
EUIPO_DESIGN_URL = (
    "https://www.euipo.europa.eu/en/designs/before-applying/fees-payable-direct-to-the-euipo"
)


_BROWSERY_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}


class EUIPOFeesClient(BaseAsyncClient):
    """Tiny HTTP client for EUIPO fee pages."""

    DEFAULT_BASE_URL = "https://www.euipo.europa.eu"
    CACHE_NAME = "euipo_fees"
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_TTL_SECONDS = 7 * 24 * 3600
    HTTP2 = True

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("ttl_seconds", self.DEFAULT_TTL_SECONDS)
        existing = kwargs.get("headers") or {}
        merged = {**_BROWSERY_HEADERS, **(existing if isinstance(existing, dict) else {})}
        kwargs["headers"] = merged
        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def fetch_html(self, path: str) -> str:
        r = await self._request("GET", path, context="euipo_fees")
        return r.text


# ──────────────────────────────────────────────────────────────────────
# Amount parsing
# ──────────────────────────────────────────────────────────────────────

_AMOUNT_NUMBER_RE = re.compile(r"€\s*([\d ,.]+)")
_NON_BREAK_SPACE = " "


def _parse_euipo_money(raw: str) -> Decimal | None:
    """Parse EUIPO amount strings.

    EUIPO publishes amounts like '€1 000', '€850', '€60*', '€200\\n(max. €1 000)'.
    We take the *first* €N occurrence (the headline figure) and ignore any
    parenthetical caps or footnote markers. Returns None for non-numeric
    cells like '25%' or 'see below'.
    """
    cleaned = raw.replace(_NON_BREAK_SPACE, " ")
    m = _AMOUNT_NUMBER_RE.search(cleaned)
    if not m:
        return None
    digits = m.group(1).strip()
    # Strip footnote markers and trailing punctuation
    digits = re.sub(r"[^\d., ]", "", digits).strip()
    # Strip spaces (used as thousand separators) and convert comma→dot if present
    if "," in digits and "." not in digits:
        digits = digits.replace(",", ".")
    digits = digits.replace(" ", "").replace(",", "")
    try:
        return Decimal(digits)
    except Exception:
        logger.warning("EUIPO fees: could not parse amount %r", raw)
        return None


# ──────────────────────────────────────────────────────────────────────
# Trademarks (SSR-stream decoder)
# ──────────────────────────────────────────────────────────────────────

_NEXT_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')
_TABLE_COL_RE = re.compile(r'"value":"([^"]*)","component":"_table_col"')
_FEE_CODE_RE = re.compile(r"^[FM]-\d+$")


def _decode_next_stream(html_text: str) -> str:
    """Join every ``self.__next_f.push([1, "..."])`` chunk into one decoded string."""
    chunks = _NEXT_PUSH_RE.findall(html_text)
    out: list[str] = []
    for c in chunks:
        try:
            out.append(json.loads('"' + c + '"'))
        except json.JSONDecodeError:
            continue
    return "".join(out)


def _categorize_tm(code: str, description: str) -> FeeCategory:
    """Map an EUIPO TM fee code + description to our closed FeeCategory vocab."""
    code_u = code.upper()
    d = description.lower()
    if code_u.startswith("M-"):
        return FeeCategory.madrid
    if "renewal" in d:
        return FeeCategory.renewal
    if "opposition" in d:
        return FeeCategory.opposition
    if "appeal" in d:
        return FeeCategory.appeal
    if "revocation" in d or "declaration of invalidity" in d:
        return FeeCategory.cancellation
    if "conversion" in d:
        return FeeCategory.transfer
    if "restitutio" in d or "re-establishment" in d:
        return FeeCategory.petition
    if "search" in d:
        return FeeCategory.search
    if (
        "transfer" in d
        or "registration of a licen" in d
        or "cancellation of the registration of a licen" in d
    ):
        return FeeCategory.transfer
    if "second class" in d or "each class" in d or "beyond the first" in d:
        return FeeCategory.excess_classes
    if (
        "alteration" in d
        or "issuing a copy" in d
        or "inspection of files" in d
        or "issuing copies" in d
        or "communicating data" in d
    ):
        return FeeCategory.other
    if "basic fee" in d and "application" in d:
        return FeeCategory.filing
    if "additional fee" in d and "late payment" in d:
        return FeeCategory.late_fee
    return FeeCategory.other


def _detect_tm_condition(description: str) -> FeeCondition | None:
    d = description.lower()
    if "second class" in d:
        return FeeCondition(
            trigger="classes_over",  # type: ignore[arg-type]
            threshold=1,
            per_unit=False,
            description="Flat fee for the second class.",
        )
    if "each class" in d and ("beyond" in d or "additional" in d):
        return FeeCondition(
            trigger="classes_over",  # type: ignore[arg-type]
            threshold=2,
            per_unit=True,
            description="Per class beyond the first two.",
        )
    if "electronic" in d:
        # Lower e-filing rate vs paper isn't a 'paper_filing' surcharge per se,
        # but the existence of two rows for the same code (basic vs electronic)
        # is a discount, not a surcharge. We don't model it as a condition;
        # the label distinguishes the rows.
        return None
    return None


def _extract_tm_rows(decoded: str) -> list[tuple[str, str, str]]:
    """Extract (code, description, amount) triplets from the decoded SSR text.

    Uses a sliding-window approach: every group of 3 consecutive
    ``_table_col`` values where the first looks like a fee code is a row.
    Non-fee ``_table_col`` triples are skipped.
    """
    vals = _TABLE_COL_RE.findall(decoded)
    rows: list[tuple[str, str, str]] = []
    i = 0
    while i + 2 < len(vals):
        if _FEE_CODE_RE.match(vals[i].strip()):
            rows.append((vals[i].strip(), vals[i + 1].strip(), vals[i + 2].strip()))
            i += 3
        else:
            i += 1
    return rows


async def scrape_euipo_trademarks() -> FeeSchedule:
    """Scrape EUIPO trademark fees from the EUTM fees page (Next.js SSR)."""
    async with EUIPOFeesClient() as client:
        html_text = await client.fetch_html(
            "/en/trade-marks/before-applying/fees-payable-direct-to-the-euipo"
        )
    decoded = _decode_next_stream(html_text)
    rows = _extract_tm_rows(decoded)
    if not rows:
        raise RuntimeError(
            "EUIPO TM scraper extracted zero rows — SSR-stream structure may have changed"
        )

    fees: list[FeeItem] = []
    for code, description, amount_str in rows:
        amount = _parse_euipo_money(amount_str)
        if amount is None:
            continue
        category = _categorize_tm(code, description)
        year = 10 if category == FeeCategory.renewal else None
        fees.append(
            FeeItem(
                code=code,
                label=description,
                category=category,
                rights=[RightType.trademark],
                amount=amount,
                currency="EUR",
                tier=EntityTier.none,
                year=year,
                condition=_detect_tm_condition(description),
                source_url=EUIPO_TM_URL,
            )
        )

    return FeeSchedule(
        jurisdiction="EP",
        issuing_body="European Union Intellectual Property Office",
        office_code="EUIPO",
        right=RightType.trademark,
        currency="EUR",
        effective_date=date.today(),  # EUIPO page does not expose a per-revision date
        source_url=EUIPO_TM_URL,
        statutory_basis="EU Trade Mark Regulation (EUTMR) Annex I; Articles 31(2), 46(3), 53(3), 68(1), 104(3)",
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "Sourced from the EUIPO EUTM fees page. F-xxx codes are EUTM "
            "fees; M-xxx codes are Madrid Protocol fees handled through "
            "EUIPO. Renewals are 10-year recurring (year=10). Many fees "
            "have separate 'basic' and 'electronic' rates; both are "
            "captured as distinct rows under the same code."
        ),
    )


# ──────────────────────────────────────────────────────────────────────
# Designs (REUD) — direct HTML table scraping
# ──────────────────────────────────────────────────────────────────────

_DESIGN_RENEWAL_PERIOD_RE = re.compile(
    r"(first|second|third|fourth)\s+period\s+of\s+renewal",
    re.IGNORECASE,
)
_PERIOD_TO_YEAR = {"first": 5, "second": 10, "third": 15, "fourth": 20}


def _categorize_design(description: str) -> FeeCategory:
    d = description.lower()
    if "renewal" in d:
        if "late payment" in d:
            return FeeCategory.late_fee
        return FeeCategory.renewal
    if "application fee" in d:
        return FeeCategory.filing
    if "second design onwards" in d:
        return FeeCategory.other  # multi-design discount tier — not a separate category
    if "deferment" in d:
        return FeeCategory.deferment
    if "declaration of invalidity" in d:
        return FeeCategory.cancellation
    if "appeal" in d:
        return FeeCategory.appeal
    if "restitutio" in d:
        return FeeCategory.petition
    if "registration of a licence" in d:
        return FeeCategory.transfer
    if "review" in d and "procedural costs" in d:
        return FeeCategory.other
    if "individual designation" in d:
        return FeeCategory.designation
    return FeeCategory.other


def _detect_design_condition(description: str) -> FeeCondition | None:
    d = description.lower()
    if "second design onwards" in d:
        return FeeCondition(
            trigger="multi_design",  # type: ignore[arg-type]
            threshold=1,
            per_unit=True,
            description="Per design beyond the first.",
        )
    return None


def _design_year(description: str) -> int | None:
    m = _DESIGN_RENEWAL_PERIOD_RE.search(description)
    if not m:
        return None
    return _PERIOD_TO_YEAR.get(m.group(1).lower())


async def scrape_euipo_designs() -> FeeSchedule:
    """Scrape EUIPO design (REUD) fees from the direct-fees page."""
    async with EUIPOFeesClient() as client:
        html_text = await client.fetch_html(
            "/en/designs/before-applying/fees-payable-direct-to-the-euipo"
        )
    doc = L.fromstring(html_text)
    tables = doc.cssselect("table")
    if not tables:
        raise RuntimeError(
            "EUIPO design scraper found no <table> elements — page structure may have changed"
        )

    fees: list[FeeItem] = []
    seen_codes: set[str] = set()
    for t in tables:
        for tr in t.cssselect("tr"):
            cells = [td.text_content().strip() for td in tr.cssselect("td")]
            if len(cells) < 3:
                continue
            code, description, amount_str = cells[0], cells[1], cells[2]
            if not code or not description:
                continue
            # First column is sometimes empty for sub-rows that share the
            # parent's fee code; skip those to avoid pydantic complaining
            # about empty code strings.
            if not code:
                continue
            amount = _parse_euipo_money(amount_str)
            if amount is None:
                continue
            category = _categorize_design(description)
            year = (
                _design_year(description)
                if category in (FeeCategory.renewal, FeeCategory.late_fee)
                else None
            )
            # Dedupe — design tables have some rows that appear twice in
            # different sections (e.g., the per-design rows in Table 5).
            dedupe_key = f"{code}|{description[:40]}|{amount}"
            if dedupe_key in seen_codes:
                continue
            seen_codes.add(dedupe_key)
            fees.append(
                FeeItem(
                    code=code,
                    label=description,
                    category=category,
                    rights=[RightType.design],
                    amount=amount,
                    currency="EUR",
                    tier=EntityTier.none,
                    year=year,
                    condition=_detect_design_condition(description),
                    source_url=EUIPO_DESIGN_URL,
                )
            )

    if not fees:
        raise RuntimeError("EUIPO design scraper parsed zero fees from page tables")

    return FeeSchedule(
        jurisdiction="EP",
        issuing_body="European Union Intellectual Property Office",
        office_code="EUIPO",
        right=RightType.design,
        currency="EUR",
        effective_date=date(2025, 5, 1),  # REUD reform Phase I commencement
        source_url=EUIPO_DESIGN_URL,
        statutory_basis=(
            "Council Regulation (EC) No 6/2002 (CDR) Article 36(4); "
            "Regulation (EU) 2024/2822 (REUD reform Phase I); "
            "Article 35(3) of Regulation (EU) No 386/2012."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "EUIPO REUD design fees post-Regulation 2024/2822 reform. "
            "Renewal periods 1/2/3/4 map to years 5/10/15/20 with the "
            "back-loaded curve confirmed by the page (€150 / €250 / "
            "€400 / €700). Late-payment surcharges were abolished by "
            "the same reform. The 'per design' rows in Table 5 capture "
            "the multi-design renewal discount."
        ),
    )


__all__ = [
    "EUIPO_TM_URL",
    "EUIPO_DESIGN_URL",
    "EUIPOFeesClient",
    "scrape_euipo_trademarks",
    "scrape_euipo_designs",
]
