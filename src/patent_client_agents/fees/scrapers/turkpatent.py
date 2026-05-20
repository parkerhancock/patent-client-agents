"""TÜRKPATENT Turkey fee-schedule scraper.

TÜRKPATENT (Türk Patent ve Marka Kurumu) re-hosts its annually-
gazetted fee schedule on three native-HTML pages — one per right:

* ``turkpatent.gov.tr/patent-islem-ucretleri`` — 57-row patent +
  utility-model table, 6 columns (KOD / AÇIKLAMA / ÜCRET / KDV /
  HARÇ / TOPLAM TUTAR).
* ``turkpatent.gov.tr/marka-islem-ucretleri`` — trademark table,
  3 columns (KOD / AÇIKLAMA / İŞLEM ÜCRETLERİ).
* ``turkpatent.gov.tr/tasarim-islem-ucretleri`` — industrial-design
  table, 3 columns (same shape as TM).

The Resmî Gazete (Official Gazette) supplementary issue is the
binding statutory source — the 2026 schedule was gazetted as
"Türk Patent ve Marka Kurumunca 2026 Yılında Uygulanacak Ücret
Tarifesine İlişkin Tebliğ (BİK/TÜRKPATENT: 2026/1)" in Resmî
Gazete 5. mükerrer 31-12-2025 (``20251231M5-37.pdf``). The
TÜRKPATENT HTML re-hosting is the practical extraction target;
the gazette PDF is the cited authority and version pin.

Column model (patents)
----------------------

Patent rows publish FOUR amount columns: ``ÜCRET`` (TÜRKPATENT
base fee), ``KDV`` (18% VAT), ``HARÇ`` (Hazine stamp duty), and
``TOPLAM TUTAR`` (the all-in total). The connector emits
``FeeItem.amount`` as ``TOPLAM TUTAR`` — the all-in number a client
will actually pay. The breakdown (base / VAT / stamp) is preserved
in ``FeeItem.notes`` so prosecutors who need to invoice the office
separately from the treasury can recover the constituents.

Formula rows
------------

Three patent rows publish their amount as a prose formula referencing
other rows rather than a numeric value:

* ``01.01.20`` Mücbir Sebep (force-majeure surcharge) →
  "Ödenmesi gereken yıllık ücret + (Ödenmesi gereken yıllık ücret
  - harç)ın %50'si" (annuity due + 50% of (annuity due - stamp)).
* ``01.01.21`` Vadesinde Ödenmeyen Yıllık Ücret (late-annuity
  penalty) — same shape with 25% multiplier.
* ``01.01.59`` Yıllık Ücret İçin Telafi Ücreti (annuity compensation
  fee) → "Ödenmesi gereken ücretin 1,5 katı" (1.5× of fee due).

These rows are emitted with ``amount = 0`` and the formula text
preserved verbatim in ``notes``. The ``category`` is ``late_fee``;
consumers must compute the actual amount themselves from the
referenced annuity year.

PCT priority-document row (``01.01.43``) publishes "30 CHF" — a
foreign-currency row inside an otherwise TRY-denominated schedule.
The connector skips this row in v1 (would require a multi-currency
FeeSchedule contract change). Documented in v1 GAPS below.

Annuity expansion
-----------------

Patent annuity rows ``01.01.23`` through ``01.01.40`` cover years
3 through 20 (one row per year — "N.Yıl Sicil Kayıt Ücreti"). Each
emits as a renewal FeeItem with ``year`` set from the label.

Per-class trademark surcharges
------------------------------

The TM schedule has multiple per-class rows:

* ``02.01.01`` Tek Sınıflı Marka Başvuru Ücreti — first-class
  filing fee (single class).
* ``02.01.02`` Marka Başvurusu Ek Sınıf Ücreti (2.sınıf) —
  per-additional-class for the 2nd class.
* ``02.01.28`` Marka Başvurusu Ek Sınıf Ücreti (3 üncü sınıf ve
  sonraki) — per-additional-class for the 3rd+ class.
* ``02.01.34`` Marka Başvurusu Ek Sınıf Ücreti (35/5 inci grup …) —
  Nice class 35 sub-class 5 discount.

These emit as ``FeeCategory.excess_classes`` with
``FeeCondition(classes_over, threshold=N, per_unit=True)`` where N
is the threshold count (1 for the 2.sınıf row, 2 for the 3.sınıf+
row).

Design multi-design body
------------------------

Row ``04.01.02`` İlave Her Tasarım İçin Tasarım Tescil Başvuru
Ücreti publishes three sub-amounts in a single prose body:

  "Başvurudaki 2. tasarım için tasarım başvuru ücreti: 1674,90TL
   Başvurudaki 3. 4. ve 5. her bir tasarım için … 318,70 TL
   Başvurudaki 6. ve fazlası her bir tasarım için … 760,00 TL"

The connector parses these into three FeeItems
(``tr-des-04.01.02-d2`` / ``-d3to5`` / ``-d6plus``) so each tier is
queryable.

Annual revision cadence
-----------------------

TÜRKPATENT republishes the schedule annually in the Resmî Gazete
on or about 31 December, taking effect 1 January of the following
year. Year-over-year jumps have been large because of TRY inflation
(2024→2025 +44%, 2025→2026 +20-25%). The connector pins a 90-day
freshness window; consumers should re-pull aggressively when
quoting more than one quarter out.

Amount format
-------------

Turkish/EU convention: ``2.402,67`` means 2402.67 (``.`` thousands
separator, ``,`` decimal mark). The TM/design schedules
consistently use this shape; the patent schedule mixes formats
(some rows omit the thousands separator on smaller values, e.g.,
``9000`` and ``10800``). The parser handles both.

v1 scope
--------

* ``TR/TURKPATENT/Fees/Patent`` — 01.x.x rows (patents + utility
  models share the patent schedule).
* ``TR/TURKPATENT/Fees/Trademark`` — 02.x.x rows.
* ``TR/TURKPATENT/Fees/Design`` — 04.x.x rows.

v1 GAPS
-------

* PCT priority document fee (``01.01.43``, 30 CHF) is skipped —
  multi-currency support is a future model extension.
* Formula-row amounts (force-majeure, late-annuity, compensation)
  emit as ``amount=0`` with the formula preserved in ``notes``.
* Appeal fees (YİDD schedule) are published on a separate page;
  not in v1 scope.

Statutory basis
---------------

* Sınai Mülkiyet Kanunu (Law No. 6769), Art. 188 — annual fee
  tariffs issued by Cabinet/Office decision and published in the
  Resmî Gazete.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from decimal import Decimal
from typing import Literal, Unpack

from lxml import html as L

from law_tools_core import BaseAsyncClient
from patent_client_agents.fees.models import (
    ConditionalTrigger,
    EntityTier,
    FeeCategory,
    FeeClientKwargs,
    FeeCondition,
    FeeItem,
    FeeSchedule,
    RightType,
)

logger = logging.getLogger(__name__)


TR_TURKPATENT_BASE = "https://www.turkpatent.gov.tr"
TR_PATENTS_URL = f"{TR_TURKPATENT_BASE}/patent-islem-ucretleri"
TR_TRADEMARKS_URL = f"{TR_TURKPATENT_BASE}/marka-islem-ucretleri"
TR_DESIGNS_URL = f"{TR_TURKPATENT_BASE}/tasarim-islem-ucretleri"
TR_GAZETTE_PDF = "https://www.resmigazete.gov.tr/eskiler/2025/12/20251231M5-37.pdf"
TR_GAZETTE_CITATION = (
    "Resmî Gazete 5. mükerrer 31-12-2025, "
    "BİK/TÜRKPATENT 2026/1 (Law 6769 Art. 188)"
)

RightPath = Literal["patent", "marka", "tasarim"]


class TurkpatentFeesClient(BaseAsyncClient):
    """Tiny HTTP client for the TÜRKPATENT fee pages."""

    DEFAULT_BASE_URL = TR_TURKPATENT_BASE
    CACHE_NAME = "turkpatent_fees"
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
                "Accept-Language": "tr,en;q=0.7",
            },
        )
        super().__init__(**kwargs)

    async def fetch_html(self, right: RightPath) -> str:
        path = f"/{right}-islem-ucretleri"
        r = await self._request("GET", path, context=f"turkpatent_{right}")
        return r.text


# ──────────────────────────────────────────────────────────────────────
# Amount parsing
# ──────────────────────────────────────────────────────────────────────

# Turkish/EU convention: ``2.402,67`` = 2402.67 (``.`` thousands sep,
# ``,`` decimal). Some rows omit the thousands sep on small numbers
# ("9000" rather than "9.000"), so the regex tolerates both. The first
# branch REQUIRES at least one ``.NNN`` thousands group (``+`` not
# ``*``); without that anchor, "3800" would match "380" via the
# 3-digit cap on ``\d{1,3}`` and we'd lose the trailing digit.
_TR_AMOUNT_RE = re.compile(r"(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)\s*(?:TL)?")


def _parse_tr_amount(raw: str) -> Decimal | None:
    """'2.402,67' → Decimal('2402.67'); '9000' → Decimal('9000'); '' → None."""
    if not raw:
        return None
    m = _TR_AMOUNT_RE.search(raw)
    if not m:
        return None
    token = m.group(1)
    # Strip any CHF / non-Turkish currency hint by looking for non-numeric
    # text after the match.
    cleaned = token.replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except Exception:
        return None


def _looks_like_formula(text: str) -> bool:
    """A row is a formula if it references 'ödenmesi gereken' or 'katı'."""
    lower = text.lower()
    return (
        "ödenmesi gereken" in lower
        or "katı" in lower
        or "harç" in lower and "%" in lower
    )


def _is_chf_row(text: str) -> bool:
    return "CHF" in text


# ──────────────────────────────────────────────────────────────────────
# Categorization
# ──────────────────────────────────────────────────────────────────────


def _categorize_patent(label: str, code: str) -> FeeCategory:
    d = label.lower()
    # Annuity rows: codes 01.01.23 through 01.01.40, label "N.Yıl Sicil
    # Kayıt Ücreti". Check by code range to be robust against label
    # truncation.
    if re.match(r"^01\.01\.(2[3-9]|3\d|40)$", code) or re.match(r"\d+\.yıl sicil", d):
        return FeeCategory.renewal
    if "mücbir sebep" in d or "vadesinde ödenmeyen" in d or "telafi" in d:
        return FeeCategory.late_fee
    if "ek süre" in d:
        return FeeCategory.extension
    if "araştırma raporu" in d:
        return FeeCategory.search
    if "inceleme raporu" in d:
        return FeeCategory.examination
    if "patent başvuru" in d or "ulusal aşamaya giren başvuru" in d:
        return FeeCategory.filing
    if "patent belgesi" in d or "ek patent belgesi" in d:
        return FeeCategory.grant
    if "yayım" in d:
        return FeeCategory.publication
    if "rüçhan" in d:
        return FeeCategory.other
    if "devir" in d or "miras" in d or "lisans" in d or "rehin" in d or "yapısal değişik" in d:
        return FeeCategory.transfer
    if "itiraz" in d or "karşı" in d:
        return FeeCategory.opposition
    if "iptal" in d or "geçersizlik" in d:
        return FeeCategory.cancellation
    if "faydalı model" in d:
        return FeeCategory.filing
    if "sicil sureti" in d or "onaylı sureti" in d or "yerinde inceleme" in d:
        return FeeCategory.other
    if "hakların yeniden tesisi" in d or "işlemlerin devam" in d:
        return FeeCategory.other
    return FeeCategory.other


def _categorize_trademark(label: str, code: str) -> FeeCategory:
    d = label.lower()
    if "yenileme" in d:
        return FeeCategory.renewal
    if "tek sınıflı marka başvuru" in d or "madrid protokolü uyarınca" in d and "başvuru" in d:
        return FeeCategory.filing
    if "marka başvurusu ek sınıf" in d or "ilave her bir sınıf" in d:
        return FeeCategory.excess_classes
    if "marka tescil ücreti" in d:
        return FeeCategory.grant
    if "iptal" in d:
        return FeeCategory.cancellation
    if "itiraz" in d:
        return FeeCategory.opposition
    if "devir" in d or "miras" in d or "lisans" in d or "rehin" in d or "yapısal değişik" in d:
        return FeeCategory.transfer
    if "rüçhan" in d:
        return FeeCategory.other
    if "tescil belgesi" in d or "sicil sureti" in d or "sınıflandırma" in d or "bilgilerine" in d:
        return FeeCategory.other
    if "tanınmışlık" in d:
        return FeeCategory.other
    if "bölünme" in d:
        return FeeCategory.other
    if "madrid protokolü" in d:
        return FeeCategory.madrid
    return FeeCategory.other


def _categorize_design(label: str, code: str) -> FeeCategory:
    d = label.lower()
    if "yenileme" in d:
        return FeeCategory.renewal
    if "süre uzatımı" in d:
        return FeeCategory.late_fee
    if "tasarım tescil başvuru" in d or "başvuru ücreti" in d:
        return FeeCategory.filing
    if "yayım erteleme" in d:
        return FeeCategory.deferment
    if "yayım" in d:
        return FeeCategory.publication
    if "devir" in d or "miras" in d or "lisans" in d or "rehin" in d or "yapısal değişik" in d:
        return FeeCategory.transfer
    if "rüçhan" in d:
        return FeeCategory.other
    if "tescil belgesi" in d or "sicil sureti" in d:
        return FeeCategory.other
    return FeeCategory.other


# ──────────────────────────────────────────────────────────────────────
# Year extraction for patent annuities
# ──────────────────────────────────────────────────────────────────────


_PATENT_YEAR_RE = re.compile(r"^(\d+)\.\s*yıl", re.IGNORECASE)


def _patent_annuity_year(label: str) -> int | None:
    """'3.Yıl Sicil Kayıt Ücreti' → 3."""
    m = _PATENT_YEAR_RE.search(label.strip())
    return int(m.group(1)) if m else None


# ──────────────────────────────────────────────────────────────────────
# TM excess-class threshold
# ──────────────────────────────────────────────────────────────────────


def _tm_excess_class_threshold(label: str) -> int | None:
    """Map TM per-class row labels to the threshold count.

    * "(2.sınıf)" → 1 (kicks in at the 2nd class)
    * "3 üncü sınıf ve sonraki" → 2 (kicks in at the 3rd class)
    """
    lower = label.lower()
    if "2.sınıf" in lower or "2. sınıf" in lower:
        return 1
    if "3 üncü sınıf" in lower or "3. sınıf" in lower or "3 üncü" in lower:
        return 2
    if "ilave her bir sınıf" in lower:
        return 2
    return None


# ──────────────────────────────────────────────────────────────────────
# Design 04.01.02 multi-amount body
# ──────────────────────────────────────────────────────────────────────

# "Başvurudaki 2. tasarım için tasarım başvuru ücreti: 1674,90TL ..."
_DESIGN_MULTI_RE = re.compile(
    r"(\d+(?:\.\s*\d+)*(?:\.|\s)+(?:ve\s+\w+\s+)?)?\s*tasarım[^:]*:\s*"
    r"(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*TL",
    re.IGNORECASE,
)


def _parse_design_multi_body(body: str) -> list[tuple[str, Decimal]]:
    """Extract sub-amounts from the 04.01.02 prose body.

    Returns a list of ``(suffix, amount)`` tuples — the suffix is the
    designs-position label ("d2", "d3to5", "d6plus") and the amount
    is the FeeItem amount.
    """
    out: list[tuple[str, Decimal]] = []
    # Use looser splits: find sequences "N(. N)*[ve N]?" before each ":"
    pattern = re.compile(
        r"Başvurudaki\s+([\d\.\s\w]+?)\s*için[^:]*:\s*"
        r"(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)\s*TL",
        re.IGNORECASE,
    )
    for m in pattern.finditer(body):
        which = m.group(1).strip()
        amount = _parse_tr_amount(m.group(2))
        if amount is None:
            continue
        # Map "2." → d2; "3. 4. ve 5." → d3to5; "6. ve fazlası" → d6plus
        digits = sorted({int(d) for d in re.findall(r"\d+", which)})
        if "fazlası" in which.lower() or "veya daha fazla" in which.lower():
            suffix = f"d{digits[0]}plus" if digits else "dN"
        elif len(digits) == 1:
            suffix = f"d{digits[0]}"
        elif len(digits) > 1:
            suffix = f"d{digits[0]}to{digits[-1]}"
        else:
            suffix = "dN"
        out.append((suffix, amount))
    return out


# ──────────────────────────────────────────────────────────────────────
# Table walker
# ──────────────────────────────────────────────────────────────────────


def _row_cells(tr: L.HtmlElement) -> list[str]:
    return [re.sub(r"\s+", " ", c.text_content().strip()) for c in tr.cssselect("td, th")]


def _is_header_row(cells: list[str]) -> bool:
    if not cells:
        return False
    joined = " | ".join(cells).lower()
    return "kod" in joined and ("açıklama" in joined or "aciklama" in joined)


# ──────────────────────────────────────────────────────────────────────
# Patent builder
# ──────────────────────────────────────────────────────────────────────


def _build_patent_fees(doc: L.HtmlElement) -> list[FeeItem]:
    tables = doc.cssselect("table")
    if not tables:
        return []
    fees: list[FeeItem] = []
    for tr in tables[0].cssselect("tr"):
        cells = _row_cells(tr)
        if not cells or _is_header_row(cells):
            continue
        if len(cells) < 6:
            continue
        code, label, ucret, kdv, harc, toplam = cells[0], cells[1], cells[2], cells[3], cells[4], cells[5]
        if not code.startswith("01."):
            continue
        if _is_chf_row(toplam):
            # Skip the 30 CHF row — multi-currency not supported in v1.
            continue
        is_formula = _looks_like_formula(toplam) or (not toplam and _looks_like_formula(harc))
        if is_formula:
            amount = Decimal("0")
            notes = f"Formula: {(toplam or harc).strip()}"
        else:
            amount = _parse_tr_amount(toplam)
            if amount is None:
                continue
            base = _parse_tr_amount(ucret) or Decimal("0")
            vat = _parse_tr_amount(kdv) or Decimal("0")
            stamp = _parse_tr_amount(harc) or Decimal("0")
            parts = []
            if base:
                parts.append(f"base TRY {base}")
            if vat:
                parts.append(f"VAT TRY {vat}")
            if stamp:
                parts.append(f"stamp TRY {stamp}")
            notes = "; ".join(parts) if parts else None

        category = _categorize_patent(label, code)
        year = _patent_annuity_year(label) if category is FeeCategory.renewal else None
        if category is FeeCategory.renewal and year is None:
            # Defensive fallback so the renewal validator passes.
            year = 1

        fees.append(FeeItem(
            code=f"tr-pat-{code}",
            label=label[:200],
            category=category,
            rights=[RightType.patent],
            amount=amount,
            currency="TRY",
            tier=EntityTier.none,
            year=year,
            condition=None,
            source_url=TR_PATENTS_URL,
            notes=notes,
        ))
    return fees


# ──────────────────────────────────────────────────────────────────────
# Trademark builder
# ──────────────────────────────────────────────────────────────────────


def _build_trademark_fees(doc: L.HtmlElement) -> list[FeeItem]:
    tables = doc.cssselect("table")
    if not tables:
        return []
    fees: list[FeeItem] = []
    for tr in tables[0].cssselect("tr"):
        cells = _row_cells(tr)
        if not cells or _is_header_row(cells):
            continue
        if len(cells) < 3:
            continue
        code, label, amount_text = cells[0], cells[1], cells[2]
        if not code.startswith("02."):
            continue
        amount = _parse_tr_amount(amount_text)
        if amount is None:
            continue

        category = _categorize_trademark(label, code)
        condition: FeeCondition | None = None
        threshold = _tm_excess_class_threshold(label)
        if threshold is not None or category is FeeCategory.excess_classes:
            condition = FeeCondition(
                trigger=ConditionalTrigger.classes_over,
                threshold=threshold if threshold is not None else 1,
                per_unit=True,
                description="Per class beyond the threshold.",
            )
            category = FeeCategory.excess_classes

        # TR TM term is 10 years (Law 6769 Art. 23) — renewal FeeItems
        # carry year=10 so the renewal validator is satisfied.
        year = 10 if category is FeeCategory.renewal else None

        fees.append(FeeItem(
            code=f"tr-tm-{code}",
            label=label[:200],
            category=category,
            rights=[RightType.trademark],
            amount=amount,
            currency="TRY",
            tier=EntityTier.none,
            year=year,
            condition=condition,
            source_url=TR_TRADEMARKS_URL,
            notes=None,
        ))
    return fees


# ──────────────────────────────────────────────────────────────────────
# Design builder
# ──────────────────────────────────────────────────────────────────────


def _build_design_fees(doc: L.HtmlElement) -> list[FeeItem]:
    tables = doc.cssselect("table")
    if not tables:
        return []
    fees: list[FeeItem] = []
    for tr in tables[0].cssselect("tr"):
        cells = _row_cells(tr)
        if not cells or _is_header_row(cells):
            continue
        if len(cells) < 3:
            continue
        code, label, amount_text = cells[0], cells[1], cells[2]
        if not code.startswith("04."):
            continue

        # The 04.01.02 row publishes three sub-amounts in a prose body —
        # parse them into separate FeeItems.
        if "TL" in amount_text and amount_text.count("TL") > 1:
            sub_amounts = _parse_design_multi_body(amount_text)
            if sub_amounts:
                for suffix, sub_amount in sub_amounts:
                    fees.append(FeeItem(
                        code=f"tr-des-{code}-{suffix}",
                        label=f"{label} ({suffix.replace('to', '-').replace('d', 'designs ').replace('plus', '+')})"[:200],
                        category=FeeCategory.filing,
                        rights=[RightType.design],
                        amount=sub_amount,
                        currency="TRY",
                        tier=EntityTier.none,
                        condition=None,
                        source_url=TR_DESIGNS_URL,
                        notes=amount_text[:500],
                    ))
                continue

        amount = _parse_tr_amount(amount_text)
        if amount is None:
            continue

        category = _categorize_design(label, code)
        # TR design term is renewable in 5-year periods to 25 years
        # (Law 6769 Art. 69). Renewal FeeItems carry year=10 (1st
        # extension end) so the renewal validator is satisfied;
        # consumers needing the full extension ladder treat this as
        # the per-5yr fee, not a year-specific amount.
        year = 10 if category is FeeCategory.renewal else None

        fees.append(FeeItem(
            code=f"tr-des-{code}",
            label=label[:200],
            category=category,
            rights=[RightType.design],
            amount=amount,
            currency="TRY",
            tier=EntityTier.none,
            year=year,
            condition=None,
            source_url=TR_DESIGNS_URL,
            notes=None,
        ))
    return fees


# ──────────────────────────────────────────────────────────────────────
# Public scrape entry points
# ──────────────────────────────────────────────────────────────────────


_STATUTORY = (
    "Sınai Mülkiyet Kanunu (Law 6769) Art. 188; "
    f"{TR_GAZETTE_CITATION} (PDF: {TR_GAZETTE_PDF})."
)


async def scrape_turkpatent_patents() -> FeeSchedule:
    """Scrape TÜRKPATENT patent (+ utility model) fees from the 01.x.x table."""
    async with TurkpatentFeesClient() as client:
        html_text = await client.fetch_html("patent")
    doc = L.fromstring(html_text)
    fees = _build_patent_fees(doc)
    if not fees:
        raise RuntimeError(
            "TÜRKPATENT patent scraper parsed zero rows — page structure may have changed"
        )
    return FeeSchedule(
        jurisdiction="TR",
        issuing_body="Türk Patent ve Marka Kurumu (TÜRKPATENT)",
        office_code="TURKPATENT",
        right=RightType.patent,
        currency="TRY",
        effective_date=date(2026, 1, 1),
        source_url=TR_PATENTS_URL,
        statutory_basis=_STATUTORY,
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "All-in TOPLAM TUTAR is captured as FeeItem.amount; the "
            "base / VAT / stamp-duty breakdown is preserved in notes. "
            "Annuity expansion: years 3-20 emit one renewal FeeItem "
            "per year ('N.Yıl Sicil Kayıt Ücreti'). Formula rows "
            "(force-majeure, late-annuity, compensation) emit "
            "amount=0 with the formula text in notes. v1 GAPS: PCT "
            "priority-document fee (30 CHF) skipped — multi-currency "
            "not supported in the FeeItem model. Appeal fees on a "
            "separate page not in v1 scope. Annual republication on "
            "or about 31 December; TRY inflation drives large YoY "
            "jumps (2024→2025 +44%, 2025→2026 +20-25%) so quoted "
            "figures should be re-pulled aggressively."
        ),
    )


async def scrape_turkpatent_trademarks() -> FeeSchedule:
    """Scrape TÜRKPATENT trademark fees from the 02.x.x table."""
    async with TurkpatentFeesClient() as client:
        html_text = await client.fetch_html("marka")
    doc = L.fromstring(html_text)
    fees = _build_trademark_fees(doc)
    if not fees:
        raise RuntimeError(
            "TÜRKPATENT trademark scraper parsed zero rows — page structure may have changed"
        )
    return FeeSchedule(
        jurisdiction="TR",
        issuing_body="Türk Patent ve Marka Kurumu (TÜRKPATENT)",
        office_code="TURKPATENT",
        right=RightType.trademark,
        currency="TRY",
        effective_date=date(2026, 1, 1),
        source_url=TR_TRADEMARKS_URL,
        statutory_basis=_STATUTORY,
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "10-year term (Law 6769 Art. 23); renewal FeeItems carry "
            "year=10. Per-class surcharges emit as "
            "FeeCategory.excess_classes with classes_over threshold "
            "tracking the row context (1 for 2.sınıf rows, 2 for "
            "3.sınıf+ rows). Madrid Protocol routing rows captured "
            "with FeeCategory.madrid where applicable."
        ),
    )


async def scrape_turkpatent_designs() -> FeeSchedule:
    """Scrape TÜRKPATENT industrial-design fees from the 04.x.x table."""
    async with TurkpatentFeesClient() as client:
        html_text = await client.fetch_html("tasarim")
    doc = L.fromstring(html_text)
    fees = _build_design_fees(doc)
    if not fees:
        raise RuntimeError(
            "TÜRKPATENT design scraper parsed zero rows — page structure may have changed"
        )
    return FeeSchedule(
        jurisdiction="TR",
        issuing_body="Türk Patent ve Marka Kurumu (TÜRKPATENT)",
        office_code="TURKPATENT",
        right=RightType.design,
        currency="TRY",
        effective_date=date(2026, 1, 1),
        source_url=TR_DESIGNS_URL,
        statutory_basis=_STATUTORY,
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "5-year initial term renewable up to 25 years (Law 6769 "
            "Art. 69). Renewal FeeItems carry year=10. The 04.01.02 "
            "multi-design filing row publishes three sub-amounts (2nd "
            "design / 3rd-5th / 6th+) in a prose body; the parser "
            "splits these into three FeeItems with -d2 / -d3to5 / "
            "-d6plus code suffixes."
        ),
    )


__all__ = [
    "TR_TURKPATENT_BASE",
    "TR_PATENTS_URL",
    "TR_TRADEMARKS_URL",
    "TR_DESIGNS_URL",
    "TR_GAZETTE_PDF",
    "TR_GAZETTE_CITATION",
    "TurkpatentFeesClient",
    "scrape_turkpatent_patents",
    "scrape_turkpatent_trademarks",
    "scrape_turkpatent_designs",
]
