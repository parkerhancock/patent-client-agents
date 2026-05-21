"""KIPO Korea fee-schedule scraper.

KIPO publishes fees across two English IP-system pages:

* Patents & Utility Models:
  ``https://www.kipo.go.kr/en/HtmlApp?c=92004&catmenu=ek03_04_01``
  (3 tables — Patent fees, Utility model fees, PCT fees).
* Trademarks & Designs:
  ``https://www.kipo.go.kr/en/HtmlApp?c=93006&catmenu=ek04_04_01``
  (2 tables — Trademark fees, Design fees).

Each table is a 2-column ``Description | Fee(KRW)`` shape with the
following quirks the parsers handle:

* **Section headers** appear as single-cell rows ("Application Fee",
  "Examination Fee", "Registration Fee", "Annual Fee", "Others") and
  drive ``FeeCategory`` assignment.
* **Embedded multi-part fees** — KIPO routinely packs "a. Basic fee"
  + "b. Two installments" sub-items into a single description cell,
  with the matching amounts split across the same row's fee cell
  (multi-line) and a single-cell continuation row immediately
  following. The trademark table uses this pattern aggressively
  (single lump sum + two installments + per-class additional).
* **Year-banded annuities** like CNIPA: "1 to 3 years", "4 to 6 years",
  ..., "16 to 25 years" for patents; "1 to 3", "4 to 6", "7 to 9",
  "10 to 12", "13 to 20" for designs. The scrapers expand each band
  into per-year FeeItem rows so design annuity year=N rows resolve
  uniformly.
* **Electronic vs paper variants** — KIPO publishes both rates in a
  single cell as ``"18,000(electronic application) 20,000(paper-based
  application)"``. The patent parser keeps only the electronic
  (first) rate; the trademark/design parsers emit both, with the
  paper variant as a separate FeeItem (``-paper`` slug suffix).

Effective date for all three KIPO routes is **2023-08-01** per the
KIPO Enforcement Rule amendment (Patent Act / Trademark Act /
Design Protection Act Collection of Fees Rule).

KIPO does NOT publish entity-tier discounts on the fee schedule
itself — SME / micro / individual discounts are administered through
a separate post-payment refund program (Rule on Refund and Reduction
of Fees) and are out of scope for the schedule corpus. Every FeeItem
emits with ``tier=EntityTier.none``.

v1 scope: patent, trademark, design. Utility-model fees ship as a
separate route when needed.
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

KIPO_FEES_URL = "https://www.kipo.go.kr/en/HtmlApp?c=92004&catmenu=ek03_04_01"
KIPO_TM_DES_FEES_URL = "https://www.kipo.go.kr/en/HtmlApp?c=93006&catmenu=ek04_04_01"

KIPO_EFFECTIVE_DATE = date(2023, 8, 1)


class KIPOFeesClient(BaseAsyncClient):
    """Tiny HTTP client for the KIPO English fees pages.

    KIPO splits fees across two pages — patents/UM/PCT under
    ``c=92004`` and trademarks+designs under ``c=93006``. Both pages
    are server-rendered HTML; no auth, no API key.
    """

    DEFAULT_BASE_URL = "https://www.kipo.go.kr"
    CACHE_NAME = "kipo_fees"
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_TTL_SECONDS = 7 * 24 * 3600
    HTTP2 = True

    def __init__(self, **kwargs: Unpack[FeeClientKwargs]) -> None:
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
        super().__init__(**kwargs)

    async def fetch_html(self) -> str:
        """Fetch the patents + utility models + PCT fees page."""
        r = await self._request(
            "GET",
            "/en/HtmlApp",
            params={"c": "92004", "catmenu": "ek03_04_01"},
            context="kipo_fees",
        )
        return r.text

    async def fetch_tm_des_html(self) -> str:
        """Fetch the trademarks + designs fees page."""
        r = await self._request(
            "GET",
            "/en/HtmlApp",
            params={"c": "93006", "catmenu": "ek04_04_01"},
            context="kipo_tm_des_fees",
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
            trigger="claims_over",
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
                                trigger="claims_over",
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
        effective_date=KIPO_EFFECTIVE_DATE,  # KIPO Enforcement Rule amendment
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


# ──────────────────────────────────────────────────────────────────────
# Trademark + Design builders (page c=93006)
# ──────────────────────────────────────────────────────────────────────

_TM_DESIGN_AMOUNT_RE = re.compile(r"([\d,]+)")
_ELECTRONIC_RE = re.compile(r"electronic", re.IGNORECASE)
_PAPER_RE = re.compile(r"paper", re.IGNORECASE)


def _extract_amounts(raw: str) -> list[Decimal]:
    """Return every comma-formatted integer amount in the order it appears."""
    out: list[Decimal] = []
    for m in _TM_DESIGN_AMOUNT_RE.finditer(raw):
        token = m.group(1).replace(",", "")
        if not token or not token.isdigit():
            continue
        # Ignore tiny numbers like "10" in "exceeding 10 designated goods"
        # — those aren't fee amounts. The smallest real KIPO fee in
        # either table is 1,000 KRW (per-class additional during the
        # second installment), so we filter on length>=3 + the
        # value-1000 floor.
        if len(token) < 4:
            continue
        try:
            value = Decimal(token)
        except Exception:
            continue
        if value < Decimal("1000"):
            continue
        out.append(value)
    return out


def _electronic_paper_amounts(raw: str) -> tuple[Decimal | None, Decimal | None]:
    """Split a cell of the shape ``"18,000(electronic) 20,000(paper)"``.

    Returns ``(electronic_amount, paper_amount)``. Either may be
    ``None`` when the cell has only one amount.
    """
    # Find "<amount>(...electronic...)" / "<amount>(...paper...)" pairs.
    electronic: Decimal | None = None
    paper: Decimal | None = None
    # Pattern: "12,345 (...electronic...)" OR "12,345(electronic)"
    pair_re = re.compile(r"([\d,]+)\s*\(([^)]*)\)")
    for m in pair_re.finditer(raw):
        token = m.group(1).replace(",", "")
        label = m.group(2).lower()
        if not token.isdigit() or len(token) < 4:
            continue
        try:
            value = Decimal(token)
        except Exception:
            continue
        if "electronic" in label and electronic is None:
            electronic = value
        elif "paper" in label and paper is None:
            paper = value
    return electronic, paper


def _section_to_tm_category(section: str, description: str) -> FeeCategory:
    s = section.lower()
    d = description.lower()
    if "application fee" in s:
        if "opposition" in d:
            return FeeCategory.opposition
        if "converted" in d:
            return FeeCategory.other
        return FeeCategory.filing
    if "examination" in s:
        if "preferential" in d:
            return FeeCategory.petition
        if "priority" in d:
            return FeeCategory.other
        return FeeCategory.examination
    if "registration fee" in s:
        if "late renewal" in d:
            return FeeCategory.late_fee
        if "renewal" in d:
            return FeeCategory.renewal
        return FeeCategory.grant  # registration-establishment fee
    if "others" in s:
        if "opposition" in d:
            return FeeCategory.opposition
        if "divide" in d or "divisional" in d:
            return FeeCategory.other
        if "converted" in d or "converting" in d:
            return FeeCategory.other
        return FeeCategory.other
    return FeeCategory.other


def _section_to_design_category(section: str, description: str) -> FeeCategory:
    s = section.lower()
    d = description.lower()
    if "application fee" in s:
        return FeeCategory.filing
    if "examination" in s:
        if "preferential" in d:
            return FeeCategory.petition
        if "priority" in d:
            return FeeCategory.other
        if "reexamination" in d:
            return FeeCategory.examination
        return FeeCategory.examination
    if "annual" in s:
        return FeeCategory.renewal
    if "others" in s:
        if "opposition" in d:
            return FeeCategory.opposition
        if "divisional" in d:
            return FeeCategory.other
        return FeeCategory.other
    return FeeCategory.other


_DESIGN_BAND_RE = re.compile(
    r"([a-z])\.\s*(\d+)\s*to\s*(\d+)\s*years?,?\s*annually",
    re.IGNORECASE,
)


def _design_annuity_bands(description: str) -> list[tuple[int, int]]:
    """Extract every ``"a. 1 to 3 years, annually"`` band as ``(start, end)``.

    KIPO design annuities pack multiple bands into one description
    cell:
    ``"Substantive examination
        a. 1 to 3 years, annually, for each design (Grant fee is included)
        b. 4 to 6 years, annually, for each design
        c. 7 to 9 years, annually, for each design
        d. 10 to 12 years, annually, for each design
        e. 13 to 20 years, annually, for each design"``
    """
    return [(int(m.group(2)), int(m.group(3))) for m in _DESIGN_BAND_RE.finditer(description)]


def _short_desc(description: str, max_words: int = 8) -> str:
    """Collapse multi-line KIPO descriptions to a slug-friendly prefix."""
    flat = re.sub(r"\s+", " ", description).strip()
    # Strip leading bullets like "a. " before slugifying
    flat = re.sub(r"^[a-z]\.\s*", "", flat, flags=re.IGNORECASE)
    words = flat.split(" ")
    return " ".join(words[:max_words])


def _kr_slug(prefix: str, *parts: str) -> str:
    bits = [prefix]
    for p in parts:
        if not p:
            continue
        s = re.sub(r"[^a-z0-9]+", "-", p.lower()).strip("-")[:40]
        if s:
            bits.append(s)
    return "-".join(bits)


def _unique_kr(slug: str, seen: set[str]) -> str:
    if slug not in seen:
        seen.add(slug)
        return slug
    n = 2
    while f"{slug}-{n}" in seen:
        n += 1
    candidate = f"{slug}-{n}"
    seen.add(candidate)
    return candidate


def _find_table(doc: L.HtmlElement, caption_match: str) -> L.HtmlElement | None:
    for t in doc.cssselect("table"):
        if caption_match in _table_caption(t):
            return t
    return None


def _cell_text(cell: L.HtmlElement) -> str:
    """Extract text from a cell, converting ``<br>`` to newlines.

    KIPO renders multi-amount fee cells as ``<td><br>201,000<br>2,000
    <br></td>`` — the default ``text_content()`` collapses these into
    ``"201,0002,000"`` which corrupts the amount parser. We rewrite
    every ``<br>`` to a newline first so amounts stay separated.
    """
    # Clone the cell so we don't mutate the original tree.
    work = L.fromstring(L.tostring(cell))
    for br in work.cssselect("br"):
        br.tail = "\n" + (br.tail or "")
    text = work.text_content()
    # Normalize horizontal whitespace but preserve newlines.
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def _walk_kipo_2col(table: L.HtmlElement) -> list[tuple[str, str, str]]:
    """Yield ``(current_section, description, fee_text)`` for a 2-col KIPO table.

    The KIPO trademark + design tables share two structural quirks:

    1. **Multi-amount fee cells use ``<br>`` separators** — the
       default ``text_content()`` collapses
       ``<td><br>201,000<br>2,000<br></td>`` into ``"201,0002,000"``.
       :func:`_cell_text` rewrites each ``<br>`` to a newline first.
    2. **1-cell continuation rows extend the previous 2-cell row.**
       Design row 2 (sub-amount 94,000 for "a. Electronic") spills
       its "b. Paper" amount (104,000) into the next row as a
       1-cell numeric block. The walker appends continuation amounts
       to the previous row's fee_text on a newline so the builder
       sees both amounts on one row.

    Single-cell rows whose text is a section header (e.g.
    "Application Fee") update ``current_section`` instead of
    extending the previous row.
    """
    out: list[tuple[str, str, str]] = []
    current_section = ""
    for tr in table.cssselect("tr"):
        cells_raw = tr.cssselect("td, th")
        if not cells_raw:
            continue
        cells = [_cell_text(c) for c in cells_raw]
        # Header row.
        if (
            len(cells) == 2
            and cells[0].lower() == "description"
            and cells[1].lower().startswith("fee")
        ):
            continue
        if len(cells) == 1:
            text = cells[0].strip()
            if not text:
                continue
            # If the cell looks like a fee amount (digits + KRW-style
            # thousands comma, possibly with electronic/paper labels in
            # parens) it's a continuation of the previous 2-cell row.
            # KIPO amounts always carry a thousands comma (≥ 1,000 KRW),
            # so the comma is the reliable discriminator from a
            # section header like "Application Fee".
            if "," in text and re.search(r"\d", text) and out:
                prev_section, prev_desc, prev_fee = out[-1]
                out[-1] = (prev_section, prev_desc, prev_fee + "\n" + text)
                continue
            # Otherwise treat as a section header
            current_section = text
            continue
        if len(cells) >= 2:
            description, fee_text = cells[0], cells[1]
            out.append((current_section, description, fee_text))
    return out


# ──────────────────────────────────────────────────────────────────────
# Trademark builder
# ──────────────────────────────────────────────────────────────────────


def _emit_tm_fee(
    *,
    fees: list[FeeItem],
    seen: set[str],
    section: str,
    description: str,
    payment_form: str,
    pay_kind: str,
    amount: Decimal,
    category: FeeCategory,
    condition: FeeCondition | None,
) -> None:
    """Emit one trademark FeeItem with disambiguating slug parts."""
    is_renewal = category is FeeCategory.renewal
    is_late = category is FeeCategory.late_fee
    code = _unique_kr(
        _kr_slug(
            "kr-tm",
            section,
            _short_desc(description),
            payment_form,
            pay_kind,
        ),
        seen,
    )
    label_bits = [description]
    if payment_form:
        label_bits.append(f"({payment_form.replace('-', ' ')})")
    if pay_kind in ("electronic", "paper"):
        label_bits.append(f"({pay_kind})")
    label = " ".join(label_bits)[:200]
    fees.append(
        FeeItem(
            code=code,
            label=label,
            category=category,
            rights=[RightType.trademark],
            amount=amount,
            currency="KRW",
            tier=EntityTier.none,
            year=10 if (is_renewal or is_late) else None,
            condition=condition,
            source_url=KIPO_TM_DES_FEES_URL,
            notes=f"KIPO section: {section}",
        )
    )


def _build_trademark_fees(doc: L.HtmlElement) -> list[FeeItem]:
    """Build trademark FeeItems from the KIPO TM table.

    The KIPO trademark table publishes four structural patterns:

    1. Single-amount rows (simple application fee).
    2. Electronic + paper paired rows (separate amount per filing
       channel, both annotated in the cell).
    3. Base + per-goods-surcharge rows (e.g. application fee for each
       class + 2,000 per goods over 10).
    4. Lump-sum + installment compound rows (registration /
       renewal / late renewal) — the cell carries FOUR amounts in
       order: lump-sum basic, lump-sum goods-surcharge,
       installment basic, installment goods-surcharge.

    TM term is 10 years (Trademark Act §83); renewal FeeItems carry
    ``year=10``.
    """
    table = _find_table(doc, "Trademark fees")
    if table is None:
        raise RuntimeError("KIPO trademark fees table not found on page")

    fees: list[FeeItem] = []
    seen: set[str] = set()

    per_class_cond = FeeCondition(
        trigger="classes_over",
        threshold=0,
        per_unit=True,
        description="Per class.",
    )
    excess_goods_cond = FeeCondition(
        trigger="classes_over",
        threshold=10,
        per_unit=True,
        description="Per designated good in excess of 10 per class.",
    )

    for section, description, fee_text in _walk_kipo_2col(table):
        if not section:
            continue
        category = _section_to_tm_category(section, description)
        dlow = description.lower()
        per_class = "for each class" in dlow or "per class" in dlow
        has_installment = "two installments" in dlow or "installment" in dlow
        has_goods_surcharge = "exceeding 10" in dlow or "additional charge" in dlow

        # Pattern 2: electronic/paper paired (the cell labels both).
        electronic, paper = _electronic_paper_amounts(fee_text)
        if electronic is not None or paper is not None:
            for label_kind, value in (("electronic", electronic), ("paper", paper)):
                if value is None:
                    continue
                _emit_tm_fee(
                    fees=fees,
                    seen=seen,
                    section=section,
                    description=description,
                    payment_form="",
                    pay_kind=label_kind,
                    amount=value,
                    category=category,
                    condition=per_class_cond if per_class else None,
                )
            continue

        amounts = _extract_amounts(fee_text)
        if not amounts:
            continue

        # Pattern 4: lump-sum + installment compound row.
        if has_installment and has_goods_surcharge and len(amounts) >= 4:
            quads = [
                (
                    "single-lump-sum",
                    "base",
                    amounts[0],
                    category,
                    per_class_cond if per_class else None,
                ),
                (
                    "single-lump-sum",
                    "goods-surcharge",
                    amounts[1],
                    FeeCategory.excess_classes,
                    excess_goods_cond,
                ),
                (
                    "two-installments",
                    "base",
                    amounts[2],
                    category,
                    per_class_cond if per_class else None,
                ),
                (
                    "two-installments",
                    "goods-surcharge",
                    amounts[3],
                    FeeCategory.excess_classes,
                    excess_goods_cond,
                ),
            ]
            for payment_form, pay_kind, amount, cat, cond in quads:
                _emit_tm_fee(
                    fees=fees,
                    seen=seen,
                    section=section,
                    description=description,
                    payment_form=payment_form,
                    pay_kind=pay_kind,
                    amount=amount,
                    category=cat,
                    condition=cond,
                )
            continue

        # Pattern 3: base + goods-surcharge (two amounts in one row).
        if has_goods_surcharge and len(amounts) >= 2:
            _emit_tm_fee(
                fees=fees,
                seen=seen,
                section=section,
                description=description,
                payment_form="",
                pay_kind="base",
                amount=amounts[0],
                category=category,
                condition=per_class_cond if per_class else None,
            )
            _emit_tm_fee(
                fees=fees,
                seen=seen,
                section=section,
                description=description,
                payment_form="",
                pay_kind="goods-surcharge",
                amount=amounts[1],
                category=FeeCategory.excess_classes,
                condition=excess_goods_cond,
            )
            continue

        # Pattern 1: simple single-amount row (or multi-amount with no
        # known semantic — emit one item per amount with -v suffixes).
        for idx, amount in enumerate(amounts):
            _emit_tm_fee(
                fees=fees,
                seen=seen,
                section=section,
                description=description,
                payment_form="",
                pay_kind="base" if idx == 0 else f"v{idx + 1}",
                amount=amount,
                category=category,
                condition=per_class_cond if (per_class and idx == 0) else None,
            )

    return fees


# ──────────────────────────────────────────────────────────────────────
# Design builder
# ──────────────────────────────────────────────────────────────────────


def _build_design_fees(doc: L.HtmlElement) -> list[FeeItem]:
    table = _find_table(doc, "Design fees")
    if table is None:
        raise RuntimeError("KIPO design fees table not found on page")

    fees: list[FeeItem] = []
    seen: set[str] = set()

    for section, description, fee_text in _walk_kipo_2col(table):
        if not section:
            continue
        category = _section_to_design_category(section, description)

        # Annuity rows — multiple year-band sub-items packed into one
        # description cell with one amount per band in the fee cell.
        if category is FeeCategory.renewal:
            bands = _design_annuity_bands(description)
            amounts = _extract_amounts(fee_text)
            if bands and amounts:
                # Pair each band to one amount (KIPO publishes them in
                # the same order; e.g. "a." 25k / "b." 35k / "c." 70k).
                for (band_start, band_end), amount in zip(bands, amounts, strict=False):
                    for year in range(band_start, band_end + 1):
                        # Distinguish substantive-examination annuity
                        # from partial-substantive — both render in the
                        # same row but description leads with the
                        # examination type.
                        head = description.split(" a.")[0].strip() or "Annual fee"
                        code = _unique_kr(
                            _kr_slug(
                                "kr-des",
                                "annuity",
                                head[:30],
                                f"y{year}",
                            ),
                            seen,
                        )
                        fees.append(
                            FeeItem(
                                code=code,
                                label=f"{head} (year {year})"[:200],
                                category=FeeCategory.renewal,
                                rights=[RightType.design],
                                amount=amount,
                                currency="KRW",
                                tier=EntityTier.none,
                                year=year,
                                condition=None,
                                source_url=KIPO_TM_DES_FEES_URL,
                                notes=(
                                    f"KIPO section: {section}. Band {band_start}-{band_end} years."
                                ),
                            )
                        )
                continue

        # Electronic vs paper split when both rates appear.
        electronic, paper = _electronic_paper_amounts(fee_text)
        if electronic is not None or paper is not None:
            for label_kind, value in (("electronic", electronic), ("paper", paper)):
                if value is None:
                    continue
                code = _unique_kr(
                    _kr_slug("kr-des", section, _short_desc(description), label_kind),
                    seen,
                )
                fees.append(
                    FeeItem(
                        code=code,
                        label=f"{description} ({label_kind})"[:200],
                        category=category,
                        rights=[RightType.design],
                        amount=value,
                        currency="KRW",
                        tier=EntityTier.none,
                        condition=None,
                        source_url=KIPO_TM_DES_FEES_URL,
                        notes=f"KIPO section: {section}",
                    )
                )
            continue

        # Fee-cell-only e/paper split (description doesn't repeat the
        # label, but the fee cell does — e.g. design application fee
        # row 2 in the table is two side-by-side amounts where the
        # description carries "a. Design application fee (Electronic)"
        # and "b. Design application fee (Paper)" sub-items).
        amounts = _extract_amounts(fee_text)
        if not amounts:
            continue

        # Multi-sub-item rows: when description packs "a. ... (Electronic)
        # b. ... (Paper)" we emit one FeeItem per sub-item paired to
        # one amount.
        sub_items = re.findall(
            r"([ab])\.\s+([^\n]+?(?:Electronic|Paper)[^\n]*)",
            description,
        )
        if sub_items and len(sub_items) == len(amounts):
            for (_letter, sub_desc), amount in zip(sub_items, amounts, strict=False):
                label_kind = "electronic" if "electronic" in sub_desc.lower() else "paper"
                code = _unique_kr(
                    _kr_slug("kr-des", section, _short_desc(sub_desc), label_kind),
                    seen,
                )
                fees.append(
                    FeeItem(
                        code=code,
                        label=sub_desc.strip()[:200],
                        category=category,
                        rights=[RightType.design],
                        amount=amount,
                        currency="KRW",
                        tier=EntityTier.none,
                        condition=None,
                        source_url=KIPO_TM_DES_FEES_URL,
                        notes=f"KIPO section: {section}",
                    )
                )
            continue

        # Single-amount or homogenous rows: emit one FeeItem per amount.
        for idx, amount in enumerate(amounts):
            suffix = "" if idx == 0 else f"v{idx + 1}"
            code = _unique_kr(
                _kr_slug("kr-des", section, _short_desc(description), suffix),
                seen,
            )
            fees.append(
                FeeItem(
                    code=code,
                    label=description[:200],
                    category=category,
                    rights=[RightType.design],
                    amount=amount,
                    currency="KRW",
                    tier=EntityTier.none,
                    condition=None,
                    source_url=KIPO_TM_DES_FEES_URL,
                    notes=f"KIPO section: {section}",
                )
            )
    return fees


# ──────────────────────────────────────────────────────────────────────
# Public scrape entry points
# ──────────────────────────────────────────────────────────────────────


_TM_STATUTORY = (
    "Enforcement Rule of the Korean Trademark Act on Collection of "
    "Trademark Fees (Korean MOIP / KIPO)."
)
_DES_STATUTORY = (
    "Enforcement Rule of the Korean Design Protection Act on "
    "Collection of Design Fees (Korean MOIP / KIPO)."
)


async def scrape_kipo_trademarks() -> FeeSchedule:
    """Scrape KIPO Korea trademark fees (KRW, no entity tiers on the schedule)."""
    async with KIPOFeesClient() as client:
        html_text = await client.fetch_tm_des_html()
    doc = L.fromstring(html_text)
    fees = _build_trademark_fees(doc)
    if not fees:
        raise RuntimeError(
            "KIPO trademark scraper parsed zero rows — page structure may have changed"
        )

    return FeeSchedule(
        jurisdiction="KR",
        issuing_body="Korean Intellectual Property Office",
        office_code="KIPO",
        right=RightType.trademark,
        currency="KRW",
        effective_date=KIPO_EFFECTIVE_DATE,
        source_url=KIPO_TM_DES_FEES_URL,
        statutory_basis=_TM_STATUTORY,
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "KIPO publishes trademark fees in KRW with electronic + "
            "paper rate variants — both emit as separate FeeItems "
            "(``-electronic`` / ``-paper`` slug suffix). Per-class "
            "language on the row drives ``FeeCondition(classes_over, "
            "threshold=0, per_unit=True)``; additional designated-"
            "goods surcharges (per goods over 10 per class) emit as "
            "separate ``FeeCategory.excess_classes`` rows. KIPO splits "
            "Registration Fee into a single lump sum and a two-"
            "installment option — both are extracted (the second "
            "installment renders as a 1-cell continuation row, "
            "synthesized via the walker's ``pending_desc`` carry-"
            "forward). TM term is 10 years (Trademark Act §83); "
            "renewal FeeItems carry year=10. KIPO entity discounts "
            "(SME / micro / individual refunds) live in a separate "
            "post-payment program and are NOT on this schedule."
        ),
    )


async def scrape_kipo_designs() -> FeeSchedule:
    """Scrape KIPO Korea design fees (KRW, no entity tiers on the schedule)."""
    async with KIPOFeesClient() as client:
        html_text = await client.fetch_tm_des_html()
    doc = L.fromstring(html_text)
    fees = _build_design_fees(doc)
    if not fees:
        raise RuntimeError("KIPO design scraper parsed zero rows — page structure may have changed")

    return FeeSchedule(
        jurisdiction="KR",
        issuing_body="Korean Intellectual Property Office",
        office_code="KIPO",
        right=RightType.design,
        currency="KRW",
        effective_date=KIPO_EFFECTIVE_DATE,
        source_url=KIPO_TM_DES_FEES_URL,
        statutory_basis=_DES_STATUTORY,
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "KIPO publishes design fees in KRW with electronic + paper "
            "rate variants — both emit as separate FeeItems. The "
            "Annual Fee table packs multiple year-bands into one row "
            "(``a. 1 to 3 years`` ... ``e. 13 to 20 years``) with one "
            "amount per band in the fee cell; the parser expands each "
            "band into per-year ``FeeCategory.renewal`` FeeItems with "
            "year=N (1..20). Partial-substantive-examination annuity "
            "track and substantive-examination annuity track emit as "
            "separate rows (description prefix disambiguates the "
            "slug). Design term is 20 years from filing (Design "
            "Protection Act §91). KIPO entity discounts (SME / micro "
            "/ individual refunds) live in a separate post-payment "
            "program and are NOT on this schedule."
        ),
    )


__all__ = [
    "KIPO_EFFECTIVE_DATE",
    "KIPO_FEES_URL",
    "KIPO_TM_DES_FEES_URL",
    "KIPOFeesClient",
    "scrape_kipo_designs",
    "scrape_kipo_patents",
    "scrape_kipo_trademarks",
]
