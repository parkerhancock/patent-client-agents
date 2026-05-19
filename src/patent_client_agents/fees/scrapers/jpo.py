"""JPO Japan fee-schedule scraper.

JPO publishes patent, utility-model, design, and trademark fees on a
single English page:
https://www.jpo.go.jp/e/system/process/tesuryo/hyou.html

The page has 20 tables organized by heading. Patents involve several
structural quirks worth knowing before reading the code:

* **Every patent fee is claim-count-dependent.** Annuity and
  examination-request cells are uniformly ``"¥X + ¥Y per claim"`` —
  the base amount + a per-claim surcharge. The scraper splits both
  into the FeeItem amount (the base) plus a FeeCondition with
  trigger=claims_over (the per-claim part stored as a separate row
  with category=excess_claims).
* **Two annuity cohorts** with different rates depending on whether
  the patent was filed on/after vs on/before April 1, 2004 (a
  historical fee-revision cutoff). The scraper emits both as
  separate FeeItem rows, tagged via the ``notes`` field. The current
  cohort (post-cutoff) carries the standard rates; the legacy cohort
  applies only to patents granted from pre-2004 applications, which
  are mostly expired by now.
* **Year bands** for patents: 1-3, 4-6, 7-9, 10-25 (Japanese patents
  have a 25-year term for some categories — pharmaceutical etc.; the
  scraper expands to all 25 years).
* **Examination request** has its own pre/post-2019 split (different
  cutoff date), captured the same way.

v1 scope: patent route only. UM, design, and trademark ship under
separate routes when needed; their fee tables are in the same file.
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

JPO_FEES_URL = "https://www.jpo.go.jp/e/system/process/tesuryo/hyou.html"


class JPOFeesClient(BaseAsyncClient):
    """HTTP client for the JPO English fees page.

    JPO's site has flaky connect behavior from some networks; we use a
    longer connect timeout and HTTP/2 (which empirically completes more
    reliably on this endpoint than HTTP/1.1).
    """

    DEFAULT_BASE_URL = "https://www.jpo.go.jp"
    CACHE_NAME = "jpo_fees"
    DEFAULT_TIMEOUT = 60.0
    DEFAULT_TTL_SECONDS = 7 * 24 * 3600
    HTTP2 = True

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("ttl_seconds", self.DEFAULT_TTL_SECONDS)
        # JPO drops requests that don't look like a real browser — needs
        # the full Sec-Fetch-* set or you get ReadTimeout/ReadError. The
        # bare 'Mozilla/5.0' UA alone is not enough.
        kwargs.setdefault(
            "headers",
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                "Accept-Language": "ja-JP,ja;q=0.9,en-US,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
            },
        )
        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def fetch_html(self) -> str:
        r = await self._request(
            "GET",
            "/e/system/process/tesuryo/hyou.html",
            context="jpo_fees",
        )
        return r.text


# ──────────────────────────────────────────────────────────────────────
# Amount parsing
# ──────────────────────────────────────────────────────────────────────

_YEN_RE = re.compile(r"¥\s*([\d,]+(?:\.\d+)?)")
_PER_CLAIM_RE = re.compile(r"¥\s*([\d,]+)\s*per\s*claim", re.IGNORECASE)
_PER_CLASS_RE = re.compile(r"¥\s*([\d,]+)\s*per\s*classification", re.IGNORECASE)
_YEAR_RANGE_RE = re.compile(r"(\d+)\s*-\s*(\d+)(?:st|nd|rd|th)?\s+year", re.IGNORECASE)


def _parse_yen(raw: str) -> Decimal | None:
    m = _YEN_RE.search(raw)
    if not m:
        return None
    cleaned = m.group(1).replace(",", "")
    try:
        return Decimal(cleaned)
    except Exception:
        return None


def _split_base_and_per_claim(raw: str) -> tuple[Decimal | None, Decimal | None]:
    """'¥4,300 + ¥300 per claim' → (Decimal('4300'), Decimal('300'))."""
    base_m = _YEN_RE.search(raw)
    per_m = _PER_CLAIM_RE.search(raw)
    base = Decimal(base_m.group(1).replace(",", "")) if base_m and not per_m else None
    # When both exist, the FIRST ¥ is the base
    if base_m and per_m:
        # Find the first ¥-amount that's NOT followed by 'per claim'
        amts = list(_YEN_RE.finditer(raw))
        base = Decimal(amts[0].group(1).replace(",", "")) if len(amts) >= 2 else None
    per = Decimal(per_m.group(1).replace(",", "")) if per_m else None
    return base, per


def _table_section_heading(table: L.HtmlElement) -> str:
    """Walk back through siblings + ancestors to find the nearest h2/h3/h4."""
    cur = table
    for _ in range(20):
        prev = cur.getprevious()
        while prev is not None:
            if prev.tag in ("h2", "h3", "h4"):
                return prev.text_content().strip()
            inner = prev.cssselect("h2, h3, h4")
            if inner:
                return inner[-1].text_content().strip()
            prev = prev.getprevious()
        parent = cur.getparent()
        if parent is None:
            break
        cur = parent
    return ""


def _table_caption(table: L.HtmlElement) -> str:
    cap = table.cssselect("caption")
    return cap[0].text_content().strip() if cap else ""


# ──────────────────────────────────────────────────────────────────────
# Categorization
# ──────────────────────────────────────────────────────────────────────


def _categorize(heading: str, caption: str, description: str) -> FeeCategory:
    h = (heading + " " + caption).lower()
    d = description.lower()
    if "annuity" in h or "annual fee" in h or "annual fees" in h or "annually" in d:
        return FeeCategory.maintenance
    if "request for examination" in d or "request for examination" in h:
        return FeeCategory.examination
    if "registrability report" in d:
        return FeeCategory.examination
    if "request for correction" in d:
        return FeeCategory.petition
    if "appeal" in d:
        return FeeCategory.appeal
    if "trial" in d or "retrial" in d:
        return FeeCategory.ptab
    if "opposition" in d:
        return FeeCategory.opposition
    if "registration of transfer" in d or "transfer of right" in d:
        return FeeCategory.transfer
    if "registration fee" in d:
        return FeeCategory.grant
    if "extension" in d or "extension of a period" in d:
        return FeeCategory.extension
    if "succession" in d:
        return FeeCategory.transfer
    if "patent application" in h or "patent application" in d:
        if "filing" in h or "application" in d:
            return FeeCategory.filing
        return FeeCategory.filing
    if "filing" in d:
        return FeeCategory.filing
    return FeeCategory.other


def _extract_year_band(description: str) -> tuple[int, int] | None:
    """'1-3rd year: annually' → (1, 3); '10-25th year' → (10, 25)."""
    m = _YEAR_RANGE_RE.search(description)
    if not m:
        return None
    start, end = int(m.group(1)), int(m.group(2))
    if start > end or end > 30:
        return None
    return start, end


def _slugify(heading: str, description: str, year: int | None, suffix: str = "") -> str:
    base = re.sub(r"[^a-z0-9]+", "-", description.lower()).strip("-")[:40]
    h_slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")[:15]
    bits = ["jp"]
    if h_slug:
        bits.append(h_slug)
    bits.append(base)
    if year is not None:
        bits.append(f"y{year}")
    if suffix:
        bits.append(suffix)
    return "-".join(b for b in bits if b)


# ──────────────────────────────────────────────────────────────────────
# Table walker
# ──────────────────────────────────────────────────────────────────────


_PATENT_HEADINGS = {
    "(1)Patents",
    "(1) Patents",
    "1. Filing",
    "2. Request for examination",
    "3. Patent fees / Registration fees",
    "4. Appeals, Trial",
    "5. Others",
    "6. After Registration",
}


def _heading_relates_to_patents(heading: str, caption: str) -> bool:
    h = heading.strip()
    # Numbered top-level sections always apply to patents
    if re.match(r"^\d+\.", h):
        return True
    # Sub-section "(1)Patents" / "(1) Patents"
    if re.match(r"^\(?1\)?\s*Patents?", h):
        return True
    if re.match(r"^1\)\s*For patent applications", h):
        return True
    # PCT and similar
    if "patent" in h.lower():
        return True
    # If the heading is for UM/design/TM, skip
    if re.match(r"^\(?[234]\)?", h):
        return False
    return False


def _build_patent_fees(doc: L.HtmlElement) -> list[FeeItem]:
    """Walk every JPO table that belongs to patents and emit FeeItems."""
    fees: list[FeeItem] = []
    seen: set[str] = set()

    for table in doc.cssselect("table"):
        heading = _table_section_heading(table)
        caption = _table_caption(table)
        if not _heading_relates_to_patents(heading, caption):
            continue

        # Tag cohort suffix (pre-2004 vs post-2004 etc.) from caption
        cohort_suffix = ""
        if "on or after" in caption.lower():
            cohort_suffix = "current"
        elif "on or before" in caption.lower():
            cohort_suffix = "legacy"

        for tr in table.cssselect("tr"):
            cells = [
                re.sub(r"\s+", " ", td.text_content().strip()) for td in tr.cssselect("td, th")
            ]
            if len(cells) < 2:
                continue
            # The JPO format is "<description> | <fee text>".
            description, fee_raw = cells[0], cells[1]
            # Header rows have th cells but no $ amount
            if not description or not fee_raw:
                continue
            # Skip header rows ("| Fees")
            if fee_raw.strip().lower() == "fees":
                continue

            category = _categorize(heading, caption, description)
            band = _extract_year_band(description) if category == FeeCategory.maintenance else None
            base, per_claim = _split_base_and_per_claim(fee_raw)
            if base is None:
                # Maybe the cell is just one ¥ amount with no "per claim"
                base = _parse_yen(fee_raw)
            if base is None:
                continue

            # Year-banded annuities → expand to per-year rows
            years_for_row: list[int | None]
            if band is not None:
                years_for_row = list(range(band[0], band[1] + 1))
            elif category == FeeCategory.maintenance:
                # Maintenance row that didn't match a year band — skip to
                # avoid the year-required validator failing.
                continue
            else:
                years_for_row = [None]

            for year in years_for_row:
                key = f"{heading[:30]}|{caption[:30]}|{description[:60]}|{year}|{cohort_suffix}"
                if key in seen:
                    continue
                seen.add(key)
                notes_bits = [f"JPO heading: {heading}"] if heading else []
                if caption:
                    notes_bits.append(f"Cohort: {caption}")
                fees.append(
                    FeeItem(
                        code=_slugify(heading, description, year, cohort_suffix),
                        label=description[:200],
                        category=category,
                        rights=[RightType.patent],
                        amount=base,
                        currency="JPY",
                        tier=EntityTier.none,
                        year=year,
                        condition=None,
                        source_url=JPO_FEES_URL,
                        notes="; ".join(notes_bits) if notes_bits else None,
                    )
                )
                if per_claim is not None and per_claim > 0:
                    key2 = key + "|perclaim"
                    if key2 in seen:
                        continue
                    seen.add(key2)
                    fees.append(
                        FeeItem(
                            code=_slugify(heading, description, year, cohort_suffix + "-perclaim"),
                            label=f"{description[:180]} — per claim",
                            category=FeeCategory.excess_claims,
                            rights=[RightType.patent],
                            amount=per_claim,
                            currency="JPY",
                            tier=EntityTier.none,
                            year=year,
                            condition=FeeCondition(
                                trigger="claims_over",  # type: ignore[arg-type]
                                threshold=1,
                                per_unit=True,
                                description="JPO per-claim surcharge.",
                            ),
                            source_url=JPO_FEES_URL,
                            notes="; ".join(notes_bits) if notes_bits else None,
                        )
                    )

    return fees


async def scrape_jpo_patents() -> FeeSchedule:
    """Scrape JPO Japan patent fees (JPY, claim-count-dependent at every band)."""
    async with JPOFeesClient() as client:
        html_text = await client.fetch_html()
    doc = L.fromstring(html_text)
    fees = _build_patent_fees(doc)
    if not fees:
        raise RuntimeError("JPO patent scraper parsed zero rows — page structure may have changed")

    return FeeSchedule(
        jurisdiction="JP",
        issuing_body="Japan Patent Office",
        office_code="JPO",
        right=RightType.patent,
        currency="JPY",
        effective_date=date(2022, 4, 1),  # Most recent comprehensive JPO fee revision
        source_url=JPO_FEES_URL,
        statutory_basis=(
            "Patent Act of Japan; supplementary fee tables under the "
            "Patent Act, Utility Model Act, Design Act, and Trademark Act."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "JPO patent annuities and examination requests are uniformly "
            "claim-count-dependent: every cell is '¥X + ¥Y per claim'. "
            "The scraper splits these into a base FeeItem plus a separate "
            "excess_claims FeeItem with FeeCondition(trigger=claims_over, "
            "threshold=1, per_unit=True). Two annuity cohorts are emitted: "
            "'current' for patents filed/examined on or after the relevant "
            "cutoff dates, and 'legacy' for pre-cutoff patents (mostly "
            "expired by now but still in the schedule for completeness). "
            "Year bands 1-3, 4-6, 7-9, 10-25 expanded to per-year rows. "
            "Site has flaky connect behavior from some networks; client "
            "uses HTTP/2 and a 60s timeout."
        ),
    )


__all__ = [
    "JPO_FEES_URL",
    "JPOFeesClient",
    "scrape_jpo_patents",
]
