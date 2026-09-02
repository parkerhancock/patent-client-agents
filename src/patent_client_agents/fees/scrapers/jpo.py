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

Trademark coverage
------------------

Trademark fees live under the (4) Trademarks sub-sections of headings
1, 3, 4. Two structural quirks worth flagging:

* **Per-classification multiplier.** Every TM fee cell is either
  ``"¥X + ¥Y per classification"`` (application/opposition/appeal/
  trial) or ``"¥Z per classification"`` (registration/renewal). The
  scraper splits these into a base FeeItem plus a separate row
  carrying ``FeeCategory.excess_classes`` with
  ``FeeCondition(trigger=classes_over, threshold=0, per_unit=True)``.
* **Installment payment option.** TM registration and renewal fees
  publish both a full-term rate (10 years up-front) and a 5-year
  installment rate per class. Both emit as separate FeeItems with
  ``-installment`` suffix and a note clarifying the choice.

Design coverage
---------------

Design fees live under the (3) Designs sub-sections of headings 1,
3, 4. The annual-fee table has cohort overlap that needs care:

* **Term cohort split.** Pre-2007 applications terminate at year 15,
  2007-2020 applications terminate at year 20, post-2020 applications
  terminate at year 25. The per-year fee is ¥16,900 across all three
  cohorts for years 4-N; the only difference is N. The scraper emits
  rows for years 1-3 (¥8,500) and years 4-15 (¥16,900) covering all
  current designs, plus an extension band 16-25 at ¥16,900 tagged in
  ``notes`` as the post-2007 / post-2020 cohort.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from decimal import Decimal
from typing import Unpack

from lxml import html as L

from mcp_data_core import BaseAsyncClient
from patent_client_agents.fees.models import (
    EntityTier,
    FeeCategory,
    FeeClientKwargs,
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

    def __init__(self, **kwargs: Unpack[FeeClientKwargs]) -> None:
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
        super().__init__(**kwargs)

    async def fetch_html(self) -> bytes:
        r = await self._request(
            "GET",
            "/e/system/process/tesuryo/hyou.html",
            context="jpo_fees",
        )
        return r.content


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
            if band is not None:
                years_for_row: list[int | None] = list(range(band[0], band[1] + 1))
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
                                trigger="claims_over",
                                threshold=0,
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
        html_bytes = await client.fetch_html()
    doc = L.fromstring(html_bytes)
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
            "threshold=0, per_unit=True). Two annuity cohorts are emitted: "
            "'current' for patents filed/examined on or after the relevant "
            "cutoff dates, and 'legacy' for pre-cutoff patents (mostly "
            "expired by now but still in the schedule for completeness). "
            "Year bands 1-3, 4-6, 7-9, 10-25 expanded to per-year rows. "
            "Site has flaky connect behavior from some networks; client "
            "uses HTTP/2 and a 60s timeout."
        ),
    )


# ──────────────────────────────────────────────────────────────────────
# Trademark + design helpers
# ──────────────────────────────────────────────────────────────────────


_DESIGN_YEAR_RANGE_RE = re.compile(r"(\d+)\s*-\s*(\d+)(?:st|nd|rd|th)?\s+year", re.IGNORECASE)


def _split_base_and_per_class(raw: str) -> tuple[Decimal | None, Decimal | None]:
    """'¥3,400 + ¥8,600 per classification' → (Decimal('3400'), Decimal('8600')).

    Mirrors :func:`_split_base_and_per_claim` for the TM tables, which
    use "per classification" instead of "per claim". Returns
    ``(base, per_class)``. For cells that contain only a per-class
    amount ("¥32,900 per classification"), returns
    ``(None, Decimal('32900'))`` so the caller can choose to emit a
    pure per-class FeeItem.
    """
    per_m = _PER_CLASS_RE.search(raw)
    amts = list(_YEN_RE.finditer(raw))
    if not amts:
        return None, None
    if per_m and len(amts) >= 2:
        # "¥X + ¥Y per classification" — base is first, per-class is the per_m amount
        base = Decimal(amts[0].group(1).replace(",", ""))
        per = Decimal(per_m.group(1).replace(",", ""))
        return base, per
    if per_m and len(amts) == 1:
        # "¥X per classification" — purely per-class
        return None, Decimal(per_m.group(1).replace(",", ""))
    # No per-class language; treat as a fixed amount.
    return Decimal(amts[0].group(1).replace(",", "")), None


def _section_heading_for(table: L.HtmlElement, target_tags: tuple[str, ...]) -> str:
    """Walk back from a table to find the nearest heading in ``target_tags``."""
    cur = table
    for _ in range(40):
        prev = cur.getprevious()
        while prev is not None:
            if isinstance(prev.tag, str) and prev.tag in target_tags:
                return re.sub(r"\s+", " ", prev.text_content()).strip()
            if isinstance(prev.tag, str):
                try:
                    inner = prev.cssselect(", ".join(target_tags))
                    if inner:
                        return re.sub(r"\s+", " ", inner[-1].text_content()).strip()
                except Exception:
                    pass
            prev = prev.getprevious()
        parent = cur.getparent()
        if parent is None:
            break
        cur = parent
    return ""


def _heading_matches(heading: str, *prefixes: str) -> bool:
    """True if the (3)/(4) sub-heading matches any of ``prefixes``.

    Handles the JPO whitespace inconsistency ("(3)Designs" vs
    "(3) Designs") and ignores trailing punctuation.
    """
    norm = re.sub(r"\s+", " ", heading.replace("　", " ")).strip().lower()
    return any(p.lower() in norm for p in prefixes)


def _design_year_band(description: str) -> tuple[int, int] | None:
    """'1-3rd year: annually' → (1, 3); '4-15th year' → (4, 15)."""
    m = _DESIGN_YEAR_RANGE_RE.search(description)
    if not m:
        return None
    start, end = int(m.group(1)), int(m.group(2))
    if start > end or end > 25:
        return None
    return start, end


def _find_transfer_of_right_fee(doc: L.HtmlElement, right_label: str) -> Decimal | None:
    """Pick the right-specific transfer-of-right fee from section 6.

    Section 6's "Registration of transfer of right:" table publishes
    one row per right type ("-Patents ¥15,000", "-Trademarks ¥30,000",
    etc.). The right-specific scrapers call this with their label
    ("Patents" / "Trademarks" / "Designs") to extract just their
    transfer fee.
    """
    target = right_label.strip().lower()
    for table in doc.cssselect("table"):
        h2 = _section_heading_for(table, ("h2",))
        if not h2.strip().startswith("6."):
            continue
        for tr in table.cssselect("tr"):
            cells = [
                re.sub(r"\s+", " ", td.text_content().strip()) for td in tr.cssselect("td, th")
            ]
            for cell in cells:
                # Cells look like "-Trademarks" / "-Patents" / "-Designs"
                if cell.lstrip("-").strip().lower() == target:
                    # The fee is the next cell with a ¥ amount
                    for c2 in cells:
                        amt = _parse_yen(c2)
                        if amt is not None:
                            return amt
    return None


# ──────────────────────────────────────────────────────────────────────
# Trademark builder
# ──────────────────────────────────────────────────────────────────────


def _categorize_trademark(h2: str, description: str) -> FeeCategory:
    h = h2.lower()
    d = description.lower()
    if "1. application" in h:
        return FeeCategory.filing
    if "2. request for examination" in h:
        return FeeCategory.examination
    if "3. annual fee" in h or "3.annual" in h or "registration fee" in h:
        if "renewal" in d:
            return FeeCategory.renewal
        return FeeCategory.grant
    if "4. opposition" in h:
        if "opposition" in d:
            return FeeCategory.opposition
        if "appeal" in d:
            return FeeCategory.appeal
        if "trial" in d:
            return FeeCategory.trial
        return FeeCategory.appeal
    if "5. others" in h:
        if "extension" in d:
            return FeeCategory.extension
        if "succession" in d:
            return FeeCategory.transfer
        return FeeCategory.other
    if "6. after registration" in h:
        return FeeCategory.transfer
    return FeeCategory.other


def _build_trademark_fees(doc: L.HtmlElement) -> list[FeeItem]:
    """Walk every (4) Trademarks table and emit FeeItems.

    Per-class language is everywhere on this page; the builder emits
    a base FeeItem plus an ``excess_classes`` FeeItem (threshold=0,
    per_unit=True) for every fee that publishes a per-class component.
    Registration/renewal installment rates emit as separate FeeItems
    with a ``-installment`` slug suffix.
    """
    fees: list[FeeItem] = []
    seen: set[str] = set()

    def _emit(
        *,
        slug_parts: list[str],
        label: str,
        category: FeeCategory,
        amount: Decimal,
        year: int | None = None,
        condition: FeeCondition | None = None,
        notes: str | None = None,
    ) -> None:
        code = _unique_slug(slug_parts, seen)
        fees.append(
            FeeItem(
                code=code,
                label=label[:200],
                category=category,
                rights=[RightType.trademark],
                amount=amount,
                currency="JPY",
                tier=EntityTier.none,
                year=year,
                condition=condition,
                source_url=JPO_FEES_URL,
                notes=notes,
            )
        )

    for table in doc.cssselect("table"):
        h2 = _section_heading_for(table, ("h2",))
        h3 = _section_heading_for(table, ("h3",))
        # Only walk tables under the (4)Trademarks sub-headings of
        # right-specific sections 1/2/3/4. Sections 5 ("Others") and
        # 6 ("After Registration") inherit the last h3 from page
        # render order — they actually apply across all rights and
        # would otherwise mix patent/UM/design transfer rows into
        # the TM schedule. The TM-specific transfer fee (¥30,000)
        # IS captured below via the curated section-6 walker.
        if not _heading_matches(h3, "(4)Trademark", "(4) Trademark", "Trademarks"):
            continue
        # h2 must be a right-specific numbered section
        if not re.match(r"^[1-4]\.", h2.strip()):
            continue

        for tr in table.cssselect("tr"):
            cells = [
                re.sub(r"\s+", " ", td.text_content().strip()) for td in tr.cssselect("td, th")
            ]
            if len(cells) < 2:
                continue
            description, fee_raw = cells[0], cells[1]
            if not description or not fee_raw:
                continue
            if fee_raw.strip().lower() == "fees":
                continue

            category = _categorize_trademark(h2, description)
            base, per_class = _split_base_and_per_class(fee_raw)

            # Description sub-marker: "Defensive mark" rows are
            # separate fee tracks. The slug carries it.
            is_defensive = "defensive" in description.lower()
            # Installment flag for registration / renewal rows.
            is_installment = (
                "installment" in description.lower() or "by installment" in description.lower()
            )
            # Renewal rows carry year=10 (TM term = 10 yrs, Japan TM Act art. 19).
            year = 10 if category is FeeCategory.renewal else None

            slug_label = description[:50]
            label = description

            if base is not None and per_class is not None:
                # "¥X + ¥Y per classification" — emit base + per-class surcharge
                slug = ["jp", "tm"]
                if is_defensive:
                    slug.append("defensive")
                slug.append(slug_label)
                if is_installment:
                    slug.append("installment")
                _emit(
                    slug_parts=slug,
                    label=label,
                    category=category,
                    amount=base,
                    year=year,
                    notes=f"JPO heading: {h2}",
                )
                _emit(
                    slug_parts=slug + ["per-class"],
                    label=f"{label} — per classification",
                    category=FeeCategory.excess_classes,
                    amount=per_class,
                    year=year,
                    condition=FeeCondition(
                        trigger="classes_over",
                        threshold=0,
                        per_unit=True,
                        description="JPO per-classification multiplier.",
                    ),
                    notes=f"JPO heading: {h2}",
                )
            elif per_class is not None and base is None:
                # "¥X per classification" — pure per-class fee. Emit a
                # single FeeItem carrying the per-class amount as the
                # canonical fee, with the classes_over condition.
                slug = ["jp", "tm"]
                if is_defensive:
                    slug.append("defensive")
                slug.append(slug_label)
                if is_installment:
                    slug.append("installment")
                _emit(
                    slug_parts=slug,
                    label=label,
                    category=category,
                    amount=per_class,
                    year=year,
                    condition=FeeCondition(
                        trigger="classes_over",
                        threshold=0,
                        per_unit=True,
                        description="JPO per-classification fee.",
                    ),
                    notes=f"JPO heading: {h2}",
                )
            elif base is not None:
                # Flat fee with no per-class component
                slug = ["jp", "tm", slug_label]
                _emit(
                    slug_parts=slug,
                    label=label,
                    category=category,
                    amount=base,
                    year=year,
                    notes=f"JPO heading: {h2}",
                )

    # Section 6 — the TM-specific transfer-of-right fee (¥30,000).
    transfer_amount = _find_transfer_of_right_fee(doc, "Trademarks")
    if transfer_amount is not None:
        _emit(
            slug_parts=["jp", "tm", "transfer-of-right"],
            label="Registration of transfer of right — Trademarks",
            category=FeeCategory.transfer,
            amount=transfer_amount,
            notes="JPO heading: 6. After Registration",
        )

    return fees


# ──────────────────────────────────────────────────────────────────────
# Design builder
# ──────────────────────────────────────────────────────────────────────


def _categorize_design(h2: str, description: str) -> FeeCategory:
    h = h2.lower()
    d = description.lower()
    if "1. application" in h:
        if "secret design" in d:
            return FeeCategory.other
        return FeeCategory.filing
    if "3. annual fee" in h or "registration fee" in h:
        return FeeCategory.renewal
    if "4. opposition" in h:
        if "appeal" in d:
            return FeeCategory.appeal
        if "trial" in d:
            return FeeCategory.trial
        return FeeCategory.appeal
    if "5. others" in h:
        if "extension" in d:
            return FeeCategory.extension
        if "succession" in d:
            return FeeCategory.transfer
        return FeeCategory.other
    if "6. after registration" in h:
        return FeeCategory.transfer
    return FeeCategory.other


def _build_design_fees(doc: L.HtmlElement) -> list[FeeItem]:
    """Walk every (3) Designs table and emit FeeItems.

    Design annuities expand across the maximum 25-year term, tagged
    with cohort notes for the 16-25 extension band.
    """
    fees: list[FeeItem] = []
    seen: set[str] = set()

    def _emit(
        *,
        slug_parts: list[str],
        label: str,
        category: FeeCategory,
        amount: Decimal,
        year: int | None = None,
        notes: str | None = None,
    ) -> None:
        code = _unique_slug(slug_parts, seen)
        fees.append(
            FeeItem(
                code=code,
                label=label[:200],
                category=category,
                rights=[RightType.design],
                amount=amount,
                currency="JPY",
                tier=EntityTier.none,
                year=year,
                condition=None,
                source_url=JPO_FEES_URL,
                notes=notes,
            )
        )

    # Track the latest 4-N renewal cell so we can extend the "1-3 + 4-15"
    # tables out to year 25 for the post-2020 cohort (statutory max term).
    latest_renewal_amount: Decimal | None = None
    latest_renewal_end: int = 0

    for table in doc.cssselect("table"):
        h2 = _section_heading_for(table, ("h2",))
        h3 = _section_heading_for(table, ("h3",))
        # Same scoping rule as TM: only the (3)Designs sub-section of
        # right-specific numbered sections; sections 5/6 are shared and
        # handled below as a curated transfer row.
        if not _heading_matches(h3, "(3)Design", "(3) Design", "Designs"):
            continue
        if not re.match(r"^[1-4]\.", h2.strip()):
            continue

        for tr in table.cssselect("tr"):
            cells = [
                re.sub(r"\s+", " ", td.text_content().strip()) for td in tr.cssselect("td, th")
            ]
            if not cells:
                continue
            # Single-cell row: cohort marker like "4-20th year: annually,※1"
            # — extends the latest renewal band to the new end year.
            if len(cells) == 1:
                if (
                    "annual" in h2.lower()
                    and latest_renewal_amount is not None
                    and "year" in cells[0].lower()
                ):
                    band = _design_year_band(cells[0])
                    if band is not None and band[1] > latest_renewal_end:
                        for yr in range(latest_renewal_end + 1, band[1] + 1):
                            slug = ["jp", "des", "renewal-extension", f"y{yr}"]
                            _emit(
                                slug_parts=slug,
                                label=f"Design annuity year {yr} (extension cohort)",
                                category=FeeCategory.renewal,
                                amount=latest_renewal_amount,
                                year=yr,
                                notes=(
                                    f"JPO heading: {h2}; cohort marker "
                                    f"{cells[0]!r} extends the 4-15 rate "
                                    "for newer cohorts. Applies to "
                                    "applications filed on or after "
                                    "April 1, 2007 (extension to year "
                                    "20) and on or after April 1, 2020 "
                                    "(extension to year 25)."
                                ),
                            )
                        latest_renewal_end = band[1]
                continue
            description, fee_raw = cells[0], cells[1]
            if not description:
                continue
            if fee_raw.strip().lower() == "fees":
                continue
            # Empty fee cell — should have already been handled by the
            # 1-cell branch above; defensive skip.
            if not fee_raw or _parse_yen(fee_raw) is None:
                continue

            category = _categorize_design(h2, description)
            amount = _parse_yen(fee_raw)
            if amount is None:
                continue

            year_band = _design_year_band(description) if category is FeeCategory.renewal else None
            if category is FeeCategory.renewal and year_band is None:
                # Renewal row with no parseable year band — skip rather
                # than emit a renewal FeeItem with year=None (validator
                # rejects).
                continue

            label = description
            if year_band is None:
                slug = ["jp", "des", label[:50]]
                _emit(
                    slug_parts=slug,
                    label=label,
                    category=category,
                    amount=amount,
                    year=None,
                    notes=f"JPO heading: {h2}",
                )
            else:
                start, end = year_band
                for yr in range(start, end + 1):
                    slug = ["jp", "des", label[:30], f"y{yr}"]
                    _emit(
                        slug_parts=slug,
                        label=label,
                        category=category,
                        amount=amount,
                        year=yr,
                        notes=f"JPO heading: {h2}; year band {start}-{end}",
                    )
                # Track the latest band so the cohort-marker rows
                # (4-20, 4-25) can extend it.
                latest_renewal_amount = amount
                latest_renewal_end = max(latest_renewal_end, end)

    # Section 6 — the design-specific transfer-of-right fee (¥9,000).
    transfer_amount = _find_transfer_of_right_fee(doc, "Designs")
    if transfer_amount is not None:
        _emit(
            slug_parts=["jp", "des", "transfer-of-right"],
            label="Registration of transfer of right — Designs",
            category=FeeCategory.transfer,
            amount=transfer_amount,
            notes="JPO heading: 6. After Registration",
        )

    return fees


# ──────────────────────────────────────────────────────────────────────
# Slug helpers
# ──────────────────────────────────────────────────────────────────────


def _unique_slug(parts: list[str], seen: set[str]) -> str:
    bits: list[str] = []
    for p in parts:
        if not p:
            continue
        s = re.sub(r"[^a-z0-9]+", "-", p.lower()).strip("-")[:40]
        if s:
            bits.append(s)
    base = "-".join(bits)
    if base not in seen:
        seen.add(base)
        return base
    n = 2
    while f"{base}-{n}" in seen:
        n += 1
    out = f"{base}-{n}"
    seen.add(out)
    return out


# ──────────────────────────────────────────────────────────────────────
# Public scrape entry points (TM + Design)
# ──────────────────────────────────────────────────────────────────────


async def scrape_jpo_trademarks() -> FeeSchedule:
    """Scrape JPO Japan trademark fees from the English fee table."""
    async with JPOFeesClient() as client:
        html_bytes = await client.fetch_html()
    doc = L.fromstring(html_bytes)
    fees = _build_trademark_fees(doc)
    if not fees:
        raise RuntimeError(
            "JPO trademark scraper parsed zero rows — page structure may have changed"
        )
    return FeeSchedule(
        jurisdiction="JP",
        issuing_body="Japan Patent Office",
        office_code="JPO",
        right=RightType.trademark,
        currency="JPY",
        effective_date=date(2022, 4, 1),  # JPO page footer: Last updated 1 April 2022
        source_url=JPO_FEES_URL,
        statutory_basis=(
            "Trademark Act of Japan (Act No. 127 of 1959). Fees set "
            "under Article 76 + the Order for Enforcement of the "
            "Trademark Act."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "JPO trademark fees are universally per-classification. "
            "Each '¥X + ¥Y per classification' row emits a base "
            "FeeItem plus a separate excess_classes FeeItem with "
            "FeeCondition(trigger=classes_over, threshold=0, "
            "per_unit=True) — the classes_over threshold is 0 "
            "because the per-class component is charged for EVERY "
            "class (not just classes over the first). For pure "
            "'¥Z per classification' rows (registration, renewal), "
            "a single FeeItem emits with the per-class amount + the "
            "same FeeCondition. Trademark term is 10 years (Trademark "
            "Act Art. 19); renewal rows carry year=10. Defensive mark "
            "rows are emitted with a -defensive slug suffix. "
            "Registration + renewal publish a 10-year up-front rate "
            "and a 5-year installment rate; both are emitted, the "
            "installment row with -installment suffix."
        ),
    )


async def scrape_jpo_designs() -> FeeSchedule:
    """Scrape JPO Japan design fees from the English fee table."""
    async with JPOFeesClient() as client:
        html_bytes = await client.fetch_html()
    doc = L.fromstring(html_bytes)
    fees = _build_design_fees(doc)
    if not fees:
        raise RuntimeError("JPO design scraper parsed zero rows — page structure may have changed")
    return FeeSchedule(
        jurisdiction="JP",
        issuing_body="Japan Patent Office",
        office_code="JPO",
        right=RightType.design,
        currency="JPY",
        effective_date=date(2022, 4, 1),  # JPO page footer: Last updated 1 April 2022
        source_url=JPO_FEES_URL,
        statutory_basis=(
            "Design Act of Japan (Act No. 125 of 1959). Fees set "
            "under Article 67 + the Order for Enforcement of the "
            "Design Act."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "Design annuities published in two bands: 1-3rd year "
            "at ¥8,500/year and 4-15th year at ¥16,900/year. The "
            "scraper expands the 1-3 band across years 1-3 and the "
            "4-15 band across years 4-15 (¥16,900/year applies to all "
            "current designs). Design term cohorts: applications "
            "filed before April 1, 2007 expire at year 15; "
            "applications filed 2007-04-01 through 2020-03-31 expire "
            "at year 20; applications filed on or after April 1, 2020 "
            "expire at year 25. The JPO page publishes empty 4-20 / "
            "4-25 marker rows that share the ¥16,900/year rate — "
            "those rows carry no fee value and are skipped by the "
            "parser; the year-25 cap is the statutory maximum. "
            "Design 'Request for secret design' (¥5,100) is a "
            "voluntary publication-deferral request, categorized as "
            "'other' since FeeCategory.deferment is reserved for "
            "Singapore-style design deferment."
        ),
    )


__all__ = [
    "JPO_FEES_URL",
    "JPOFeesClient",
    "scrape_jpo_patents",
    "scrape_jpo_trademarks",
    "scrape_jpo_designs",
]
