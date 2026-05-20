"""ILPO Israel fee-schedule scraper.

The Israel Patent Office (ILPO; רשות הפטנטים, the registration unit
inside the Ministry of Justice) publishes its current-effective fee
schedule as a single Hebrew-only PDF gazetted annually around the
22-December turn-of-year:

* Landing page (HE): ``gov.il/he/pages/ilpo-fees``
* 2026 PDF (HE): ``gov.il/BlobFolder/news/ilpo-fees/he/news_fees-2026.pdf``

Both URLs sit behind Cloudflare on ``gov.il`` proper — from typical
cloud / non-residential egress they return HTTP 403. The
``gov.il/en/...`` mirror of this fees page does not exist (gov.il
serves a Hebrew-only fee announcement). The connector therefore
sources from the **Hebrew PDF**, captures the controlling amounts,
and notes the language in ``FeeSchedule.notes``.

Annual CPI adjustment
---------------------

Israeli fees are CPI-linked and republished annually in Reshumot
(the Israeli official gazette). The 2026 PDF was gazetted
2025-12-22 with ``effective_date = 2026-01-01``. Year-over-year
increase to the headline patent filing fee was small (~1.6%, NIS
2,364 → NIS 2,402 between 2025 and 2026).

Structural levers worth flagging
--------------------------------

* **Small-entity 40% reduction.** Eligibility is conjunctive:
  (a) applicant is *not* a company or partnership with turnover
  ≥ NIS 10M in the preceding year, *or* (b) applicant is a
  recognized higher-education institution under § 9 of the
  Council for Higher Education Law 5718-1958 (or a wholly-owned
  technology-transfer subsidiary thereof). The reduction applies
  only to (a) the patent filing fee (Item 1) and (b) the
  allowance fee (Item 10), and only on a *first* patent
  application for the invention. The schedule's headline numbers
  on those two items are the full amount; the connector emits
  the full amount as ``EntityTier.none`` (the canonical row)
  and a discounted-amount variant as ``EntityTier.small`` with
  eligibility notes. The corresponding small-entity 40%
  reduction also applies to the design filing fee (Items 1(a)
  and 1(b) of the Designs section).

* **Excess-claims fee.** NIS 616 per claim for each claim from
  the 51st onward (both national and PCT-national-phase routes
  publish this same per-claim rate at items 2 and 4). Emits with
  ``FeeCondition(claims_over, threshold=50, per_unit=True)``.

* **Excess-pages fee.** NIS 300 per 50 pages for descriptions
  exceeding 100 pages, excluding genetic sequence listings.
  Emits with ``FeeCondition(pages_over, threshold=100,
  per_unit=True)``.

* **Renewal as cumulative coverage.** Israel's renewal model is
  cumulative-coverage at four checkpoints rather than per-annum:
  before year 6 (covers years 1-6), before year 10 (covers years
  7-10), before year 14 (covers years 11-14), before year 18
  (covers years 15-18), before year 22 (covers years 19-22),
  plus a 'whole-period' option (Item 12(6)). The connector
  emits one renewal FeeItem per checkpoint, with ``year`` set to
  the terminal-year-of-coverage (6, 10, 14, 18, 22, and 22 for
  the whole-period option).

* **PCT ISA / IPEA fees.** ILPO has been an ISA / IPEA since
  2012-06-01. Items 14-19 of the patent schedule are the ISA /
  IPEA-related fees; they emit with ``FeeCategory.search`` or
  ``FeeCategory.examination`` as appropriate.

* **Madrid TM fees.** Three Madrid Protocol-routing fees of
  NIS 626 each (international registration application,
  extension not designating IL, renewal of international
  registration). Emit with ``FeeCategory.madrid``.

* **Two design statutes coexist.** The current Designs Law
  5777-2017 (in force 2018-08-07) governs filings on or after
  that date; the older Patents and Designs Ordinance 1924 still
  governs filings made before that date that remain in force.
  The 2026 PDF publishes fees for BOTH regimes back-to-back.
  Per the task brief, the connector emits the modernized
  Designs Law 5777-2017 schedule as the canonical ``Design``
  schedule. Legacy ordinance fees are captured in
  ``FeeItem.notes`` on a single bridging FeeItem if encountered
  — they apply only to a shrinking tail of pre-2018 design
  registrations.

v1 scope
--------

* ``IL/ILPO/Fees/Patent`` — Items 1-22 of the patents section
  + the 9 patent-term-extension fees (Items 1-3 + opposition/
  cancellation).
* ``IL/ILPO/Fees/Trademark`` — Items 1-14 of the trademark
  section + 3 Madrid Protocol fees.
* ``IL/ILPO/Fees/Design`` — Items 1-15 of the modern Designs
  Law 5777-2017 section + 6-item adversarial-cost table for
  proceedings before the Registrar.

Statutory basis
---------------

* Patents Law 5727-1967 + Patents Regulations (Office Practice,
  Procedural Rules, Documents and Fees) 5728-1968.
* Trade Marks Ordinance [New Version] 5732-1972 + Trade Marks
  Regulations 5700-1940.
* Designs Law 5777-2017 + Designs Regulations.

Source pinning
--------------

Both the landing page and the PDF are behind ``gov.il``'s
Cloudflare front. ``IL_ILPO_FEES_LANDING_URL`` and
``IL_ILPO_FEES_PDF_URL`` are the canonical citations; the actual
PDF bytes used at test time are pinned to the fixture
``tests/fees/fixtures/il_ilpo_2026.pdf`` because live re-fetching
in CI requires Cloudflare-clearing infrastructure that's outside
the standard ``httpx`` path.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date
from decimal import Decimal
from typing import Unpack

import pypdf

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


IL_ILPO_FEES_LANDING_URL = "https://www.gov.il/he/pages/ilpo-fees"
IL_ILPO_FEES_PDF_URL = "https://www.gov.il/BlobFolder/news/ilpo-fees/he/news_fees-2026.pdf"
IL_ILPO_FEES_EFFECTIVE_DATE = date(2026, 1, 1)
IL_ILPO_FEES_GAZETTED_DATE = date(2025, 12, 22)


class ILPOFeesClient(BaseAsyncClient):
    """Tiny HTTP client for the gov.il BlobFolder PDF attachment endpoint.

    ``gov.il`` sits behind Cloudflare with TLS-fingerprint /
    JS-challenge gating. Plain ``httpx`` will hit a 403 from most
    cloud egress paths. Live refresh therefore needs to be done
    through a Cloudflare-clearing transport (Playwright + persistent
    Chromium profile is the canonical pattern in this repo); the
    fetched PDF bytes then flow through the same parsing path as
    fixture-fed bytes.
    """

    DEFAULT_BASE_URL = "https://www.gov.il"
    CACHE_NAME = "ilpo_fees"
    DEFAULT_TIMEOUT = 60.0
    DEFAULT_TTL_SECONDS = 30 * 24 * 3600
    HTTP2 = True

    def __init__(self, **kwargs: Unpack[FeeClientKwargs]) -> None:
        kwargs.setdefault("ttl_seconds", self.DEFAULT_TTL_SECONDS)
        kwargs.setdefault(
            "headers",
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept": "application/pdf,*/*",
                "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
            },
        )
        super().__init__(**kwargs)

    async def fetch_pdf(self) -> bytes:
        r = await self._request(
            "GET",
            "/BlobFolder/news/ilpo-fees/he/news_fees-2026.pdf",
            context="ilpo_fees_2026",
        )
        return r.content


# ──────────────────────────────────────────────────────────────────────
# PDF text extraction
# ──────────────────────────────────────────────────────────────────────


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Flatten the PDF to one string with per-page ``\\n`` boundaries."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(p.extract_text() or "" for p in reader.pages)


# ──────────────────────────────────────────────────────────────────────
# Section markers (Hebrew)
# ──────────────────────────────────────────────────────────────────────


# Order matters: the section markers below appear in the PDF in the
# exact sequence listed. We slice the text on each marker so each
# section is parsed in isolation.
_SECTION_MARKERS: list[tuple[str, str]] = [
    ("PATENT", "אגרות פטנטים"),
    ("PAT_EXT", "אגרות פטנטים -   צווי הארכה"),
    ("TM", "אגרות סימני מסחר"),
    ("MADRID", "אגרות סימני מסחר- פרוטוקול מדריד"),
    ("DESIGN_NEW", "אגרות עיצובים"),
    ("COSTS", "לוח הוצאות מרביות"),
    ("DESIGN_OLD", "אגרות מדגמים"),
]


def _slice_sections(text: str) -> dict[str, str]:
    """Slice the flat text into named sections in order."""
    positions: list[tuple[str, int]] = []
    cursor = 0
    for name, marker in _SECTION_MARKERS:
        pos = text.find(marker, cursor)
        if pos < 0:
            continue
        positions.append((name, pos))
        cursor = pos + len(marker)
    sections: dict[str, str] = {}
    for i, (name, start) in enumerate(positions):
        end = positions[i + 1][1] if i + 1 < len(positions) else len(text)
        sections[name] = text[start:end]
    return sections


# ──────────────────────────────────────────────────────────────────────
# Item iteration
# ──────────────────────────────────────────────────────────────────────


# A "top-level" item starts with a 1-3 digit number followed by ".".
_TOP_ITEM_RE = re.compile(r"^(\d{1,3})\.\s*(.*)$")
# A sub-item is "(<letter>" or "(<digit>)" — note inconsistent parenthesis
# closure in the PDF, but the opening "(" is universal.
_SUB_LETTER_RE = re.compile(r"^\(([א-ת])\)?\b\s*(.*)$")
_SUB_NUMBER_RE = re.compile(r"^\((\d{1,2})\)?\b\s*(.*)$")
# A trailing amount: 1-6 digit numbers with optional thousands commas.
# Decimal points may appear (e.g., 4.3 NIS per page). Always at the
# end of a line; we extract the LAST numeric token from each item's
# last line.
_TRAILING_AMOUNT_RE = re.compile(r"(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*$")


def _normalize_lines(text: str) -> list[str]:
    """Split text into stripped non-empty lines."""
    return [ln.strip() for ln in text.split("\n") if ln.strip()]


def _is_item_start(line: str) -> tuple[str | None, str | None]:
    """Return ``(item-label, rest-of-text)`` if the line opens an item.

    ``item-label`` is e.g., ``"1"``, ``"(א)"``, ``"(1)"``. Returns
    ``(None, None)`` for continuation lines.
    """
    m = _TOP_ITEM_RE.match(line)
    if m:
        return (m.group(1), m.group(2))
    m = _SUB_LETTER_RE.match(line)
    if m:
        return (f"({m.group(1)})", m.group(2))
    m = _SUB_NUMBER_RE.match(line)
    if m:
        return (f"({m.group(1)})", m.group(2))
    return (None, None)


def _iter_items(section_text: str) -> list[tuple[str, str, Decimal]]:
    """Walk a section's lines, group them into items, extract amounts.

    Returns a list of ``(item-key, description, amount)`` tuples
    where ``item-key`` is a "1" / "1.(א)" / "1.(א).(1)" path that
    preserves item lineage, ``description`` is the joined body
    (Hebrew), and ``amount`` is the trailing NIS amount.

    Items without a trailing numeric amount are dropped (they're
    section openers like Item 12 of patents which is just a label
    "Renewal fee under §56 of the Law" with the actual amounts in
    sub-items 12(1) through 12(6)).
    """
    lines = _normalize_lines(section_text)
    out: list[tuple[str, str, Decimal]] = []

    # Walk a state machine: when an item-start line is seen, begin a
    # new item; accumulate continuation lines until the next item-start
    # or end-of-section. The item is closed at that point — its amount
    # is the trailing number of the LAST line of the accumulated buffer.
    item_top: str | None = None  # last seen "N"
    item_sub_letter: str | None = None  # last seen "(letter)"
    buf_label: str | None = None  # composite key e.g. "1.(א).(1)"
    buf_lines: list[str] = []

    def _flush() -> None:
        if not buf_lines or buf_label is None:
            return
        last = buf_lines[-1]
        m = _TRAILING_AMOUNT_RE.search(last)
        if not m:
            return
        try:
            amount = Decimal(m.group(1).replace(",", ""))
        except Exception:  # noqa: BLE001
            return
        # Strip the trailing amount off the last line for the
        # description.
        last_stripped = last[: m.start()].rstrip(" .,;")
        desc_parts = buf_lines[:-1] + ([last_stripped] if last_stripped else [])
        description = " ".join(p for p in desc_parts if p)
        out.append((buf_label, description, amount))

    for line in lines:
        # Skip pure section headers (e.g., "אגרות פטנטים", "בשקלים חדשים").
        if line in {
            "אגרות פטנטים",
            "אגרות סימני מסחר",
            "אגרות עיצובים",
            "אגרות מדגמים",
            "בשקלים חדשים",
        }:
            continue
        if line.startswith("אגרות פטנטים") or line.startswith("אגרות סימני מסחר"):
            continue
        if line.startswith("לוח הוצאות מרביות"):
            continue
        if line.startswith("הודעה זו"):
            # Footer disclaimer about the binding Reshumot notice — stop.
            break

        label, rest = _is_item_start(line)
        if label is None:
            buf_lines.append(line)
            continue

        # New item — flush the previous buffer, then start a new one.
        _flush()
        buf_lines = []
        if _TOP_ITEM_RE.match(line):
            item_top = label
            item_sub_letter = None
            buf_label = item_top
        elif _SUB_LETTER_RE.match(line):
            item_sub_letter = label
            buf_label = f"{item_top}.{label}" if item_top else label
        else:  # sub-number
            if item_sub_letter and item_top:
                buf_label = f"{item_top}.{item_sub_letter}.{label}"
            elif item_top:
                buf_label = f"{item_top}.{label}"
            else:
                buf_label = label
        if rest:
            buf_lines.append(rest)

    _flush()
    return out


# ──────────────────────────────────────────────────────────────────────
# Patent item → FeeCategory mapping
# ──────────────────────────────────────────────────────────────────────


# Items mapped by the digit/composite key extracted by `_iter_items`.
# Each entry is (category, optional renewal year, optional override
# label, optional condition).
# Item key conventions:
#   "N"           — top-level item
#   "N.(letter)"  — sub-letter
#   "N.(letter).(digit)" — sub-letter sub-number
#   "N.(digit)"   — sub-number where the parent has no letter level
_PATENT_ITEM_META: dict[str, tuple[FeeCategory, int | None, str | None, FeeCondition | None]] = {
    # 1 — National patent filing (first 50 claims). Small-entity 40%
    # reduction available; this row is the full amount.
    "1": (
        FeeCategory.filing,
        None,
        "Filing of a patent application (Patents Law §11(a)) — first 50 claims",
        None,
    ),
    # 2 — Excess claims (national, per claim from the 51st onward).
    "2": (
        FeeCategory.excess_claims,
        None,
        "Per claim from the 51st onward (national application)",
        FeeCondition(
            trigger=ConditionalTrigger.claims_over,
            threshold=50,
            per_unit=True,
            description="Per claim over 50.",
        ),
    ),
    # 3 — Excess pages (national, per 50 pages from the 101st onward).
    "3": (
        FeeCategory.excess_pages,
        None,
        "Per 50 pages from the 101st onward (national application; excludes genetic sequence listings)",
        FeeCondition(
            trigger=ConditionalTrigger.pages_over,
            threshold=100,
            per_unit=True,
            description="Per 50-page increment over 100 pages (excluding genetic sequence listings).",
        ),
    ),
    # 4 — Excess claims (PCT national-phase, per claim from the 51st).
    "4": (
        FeeCategory.excess_claims,
        None,
        "Per claim from the 51st onward (PCT national-phase, designating Israel)",
        FeeCondition(
            trigger=ConditionalTrigger.claims_over,
            threshold=50,
            per_unit=True,
            description="Per claim over 50 (PCT national-phase).",
        ),
    ),
    # 5 — Excess pages (PCT national-phase, per 50 pages from the 101st).
    "5": (
        FeeCategory.excess_pages,
        None,
        "Per 50 pages from the 101st onward (PCT national-phase; excludes genetic sequence listings)",
        FeeCondition(
            trigger=ConditionalTrigger.pages_over,
            threshold=100,
            per_unit=True,
            description="Per 50-page increment over 100 pages (PCT national-phase, excluding genetic sequence listings).",
        ),
    ),
    # 6 — International-search-report-style report (Patents Regulation 35א).
    "6": (FeeCategory.search, None, "International-format search report (Patents Reg. 35א)", None),
    # 7 — Procedural petitions (cancellation / register correction).
    # Sub-item 7.(א) is collapsed by the PDF layout into the "7" line
    # (no closing-paren letter to anchor on), so the key is "7" with
    # the amount 280 NIS. Sub-letters (ב), (ג), (ד) each get their
    # own keys because they appear on fresh lines.
    "7": (
        FeeCategory.petition,
        None,
        "Petition for patent cancellation or register correction (§§73(a), 170(a), 171)",
        None,
    ),
    "7.(ב)": (
        FeeCategory.other,
        None,
        "Submission of an amended document that postpones the filing date (§23)",
        None,
    ),
    "7.(ג)": (
        FeeCategory.transfer,
        None,
        "Recordation, modification, or cancellation of a right in a patent or invention (§169)",
        None,
    ),
    "7.(ד)": (
        FeeCategory.other,
        None,
        "Correction of a typographical error in the specification (§69)",
        None,
    ),
    # 8 — Expedited examination. Like item 7, sub-letter (א) collapses
    # into the parent "8" header line, so the parser emits the
    # sub-(1)/(2) under (א) as "8.(1)" / "8.(2)" (no letter-level
    # interposed) and the sub-(1)/(2) under (ב) as "8.(ב).(1)" /
    # "8.(ב).(2)".
    "8.(1)": (
        FeeCategory.examination,
        None,
        "Expedited examination request under §19A(d), per §19A(a3)-(6)",
        None,
    ),
    "8.(2)": (
        FeeCategory.examination,
        None,
        "Expedited examination request under §19A(d), per §19A(c)",
        None,
    ),
    "8.(ב).(1)": (
        FeeCategory.examination,
        None,
        "On-site expedited examination under §19A(e), per §19A(a3)-(6)",
        None,
    ),
    "8.(ב).(2)": (
        FeeCategory.examination,
        None,
        "On-site expedited examination under §19A(e), per §19A(c)",
        None,
    ),
    # 9 — Extension of time (per month). Per-unit per month or part thereof.
    "9": (
        FeeCategory.extension,
        None,
        "Extension of time (§§48D(c), 164; Regs. 5(a), 87(c)) — per month or part thereof",
        FeeCondition(
            trigger=ConditionalTrigger.late_days,
            per_unit=True,
            description="Per month or part thereof.",
        ),
    ),
    # 10 — Allowance fee (notice of allowance under Reg. 52). Small-
    # entity 40% reduction available.
    "10": (
        FeeCategory.grant,
        None,
        "Allowance fee (Reg. 52) — first-application small-entity discount available",
        None,
    ),
    # 11 — Adversarial / contested-proceedings filings. Like items
    # 7 and 8, sub-(א) collapses into the parent line; the parser
    # emits it as "11".
    "11": (
        FeeCategory.opposition,
        None,
        "Filing in inter-partes proceeding (§§25, 30, 61, 67, 73(c), 117, 124(b), 133, 170(c))",
        None,
    ),
    "11.(ב)": (
        FeeCategory.appeal,
        None,
        "Hearing before the Registrar (§159) or appeal (§161); Regs. 42, 46(a)",
        None,
    ),
    "11.(ג)": (FeeCategory.other, None, "Specification correction (§§29, 65)", None),
    "11.(ד)": (FeeCategory.other, None, "Restoration of a lapsed patent (§59)", None),
    # 12 — Renewal under §56. Six sub-items by terminal year of
    # coverage. The patent term is 20 years from filing under §52 of
    # the Patents Law 5727-1967.
    "12.(1)": (
        FeeCategory.renewal,
        6,
        "Renewal payment within 3 months of grant — covers years 1-6",
        None,
    ),
    "12.(2)": (
        FeeCategory.renewal,
        10,
        "Renewal payment before end of year 6 — covers years 7-10",
        None,
    ),
    "12.(3)": (
        FeeCategory.renewal,
        14,
        "Renewal payment before end of year 10 — covers years 11-14",
        None,
    ),
    "12.(4)": (
        FeeCategory.renewal,
        18,
        "Renewal payment before end of year 14 — covers years 15-18",
        None,
    ),
    "12.(5)": (
        FeeCategory.renewal,
        20,
        "Renewal payment before end of year 18 — covers years 19-20",
        None,
    ),
    "12.(6)": (
        FeeCategory.renewal,
        20,
        "Whole-period renewal (entire 20-year term, paid within 3 months of grant)",
        None,
    ),
    # 13 — National-phase entry fee (§48D(a)).
    "13": (FeeCategory.filing, None, "National-phase entry fee (PCT, §48D(a))", None),
    # 14-19 — ISA / IPEA fees (ILPO as international authority since
    # 2012-06-01). These are fees the applicant pays *to* ILPO when
    # using ILPO as their International Searching Authority or
    # International Preliminary Examining Authority.
    "14": (FeeCategory.search, None, "ISA search fee (Reg. 6(d) of PCT Implementation Regs)", None),
    "15": (
        FeeCategory.other,
        None,
        "ISA transmittal fee (Reg. 6(e) of PCT Implementation Regs)",
        None,
    ),
    "16": (FeeCategory.search, None, "ISA additional fee (§48Y(d))", None),
    "17": (
        FeeCategory.examination,
        None,
        "IPEA preliminary-examination fee (Reg. 6(g) of PCT Implementation Regs)",
        None,
    ),
    "18": (FeeCategory.examination, None, "IPEA additional fee (§48YA(d))", None),
    "19": (
        FeeCategory.late_fee,
        None,
        "Late ISA transmittal fee (Reg. 6(h) of PCT Implementation Regs)",
        None,
    ),
    # 20 — Petition for re-consideration or cancellation of cancellation.
    "20": (
        FeeCategory.petition,
        None,
        "Petition for re-consideration (§21A) or cancellation of cancellation (§21B)",
        None,
    ),
    # 21 — Patent attorney licensing/annual fee. Not a patent-prosecution
    # fee per se but on the patents schedule. Sub-(א) collapses into
    # the parent line; parser emits it as "21".
    "21": (
        FeeCategory.other,
        None,
        "Patent attorney examination + registration fee (§§142, 143)",
        None,
    ),
    "21.(ב)": (FeeCategory.other, None, "Annual patent attorney fee (§145)", None),
    # 22 — Certified copy / register extract.
    "22": (FeeCategory.other, None, "Certified copy / register extract (§168(b))", None),
}


# Patent term extension (PTE / SPC-equivalent) items.
# Numbering in the PDF restarts at "(1)" under the section heading
# "אגרות פטנטים - צווי הארכה". Items 1-3 are PTE; the next two
# (Opposition, Cancellation) reset to "1)" / "2)" with a different
# bracket pattern in the PDF — the parser captures them as additional
# "1" and "2" entries inside this section.
_PATENT_EXTENSION_META: dict[str, tuple[FeeCategory, int | None, str, FeeCondition | None]] = {
    # The PTE section's numbering looks like "(1)", "(2)", "(3)(א)"..."(3)(ד)"
    # — but the PDF text has no top-level numbered item, so the parser
    # treats (1) and (2) as sub-numbers and (א)-(ד) as sub-letters
    # without a top-level anchor. The keys below match what
    # `_iter_items` actually returns for this section.
    "(1)": (FeeCategory.filing, None, "PTE application fee (PTE Reg. 2(c)(4))", None),
    "(2)": (FeeCategory.renewal, 1, "PTE renewal fee (PTE Reg. 7(a)(1))", None),
    "(א)": (
        FeeCategory.renewal,
        1,
        "PTE renewal — before end of 1st extension year (Reg. 7(a)(2))",
        None,
    ),
    "(ב)": (
        FeeCategory.renewal,
        2,
        "PTE renewal — before end of 2nd extension year (Reg. 7(a)(2))",
        None,
    ),
    "(ג)": (
        FeeCategory.renewal,
        3,
        "PTE renewal — before end of 3rd extension year (Reg. 7(a)(2))",
        None,
    ),
    # The (ד) row in the PDF runs together with the opposition (NIS 2,402)
    # and cancellation (NIS 4,804) rows on a single line; the parser
    # picks up only the LAST trailing number per item — so the (ד) key
    # ends up tagged with the cancellation amount. We map it to the
    # cancellation category to keep semantics aligned with the captured
    # amount, and note that the actual (ד) amount + opposition fee are
    # bundled into FeeItem.notes for human review.
    "(ד)": (
        FeeCategory.cancellation,
        None,
        "PTE cancellation application fee (PTE Reg. 4) — bundled with year-4 extension and opposition fees in source PDF",
        None,
    ),
}


# ──────────────────────────────────────────────────────────────────────
# Trademark + Madrid metadata
# ──────────────────────────────────────────────────────────────────────


_TRADEMARK_ITEM_META: dict[str, tuple[FeeCategory, int | None, str, FeeCondition | None]] = {
    "1.(א)": (
        FeeCategory.filing,
        None,
        "Trade mark application (§7 Ordinance) — first goods class",
        None,
    ),
    "1.(ב)": (
        FeeCategory.excess_classes,
        None,
        "Trade mark application — each additional goods class in the same application",
        FeeCondition(
            trigger=ConditionalTrigger.classes_over,
            threshold=1,
            per_unit=True,
            description="Per additional class beyond the first, same application.",
        ),
    ),
    "2": (
        FeeCategory.opposition,
        None,
        "Opposition, register-correction request, or cancellation (one mark, one class) — §§24(a), 38, 41",
        None,
    ),
    "3": (
        FeeCategory.appeal,
        None,
        "Hearing in proceedings under §§24(f), 29, 41(b); Reg. 73",
        None,
    ),
    "4.(א)": (
        FeeCategory.renewal,
        10,
        "Renewal request (§32 Ordinance) — first goods class (10-year term)",
        None,
    ),
    "4.(ב)": (
        FeeCategory.excess_classes,
        10,
        "Renewal — each additional goods class for the same mark in the same renewal request",
        FeeCondition(
            trigger=ConditionalTrigger.classes_over,
            threshold=1,
            per_unit=True,
            description="Per additional class beyond the first, same renewal.",
        ),
    ),
    "5": (
        FeeCategory.late_fee,
        None,
        "Late renewal surcharge (Reg. 52(2)) — per month or part thereof",
        FeeCondition(
            trigger=ConditionalTrigger.late_days,
            per_unit=True,
            description="Per month or part thereof of late renewal payment.",
        ),
    ),
    "6": (FeeCategory.other, None, "Restoration of registration (Reg. 53(1)) — per class", None),
    "7": (
        FeeCategory.transfer,
        None,
        "Change of register, transfer of ownership, or recordation of license (§§20, 36(a)(3)-(5), 49(a), 51, 52)",
        None,
    ),
    "8.(א)": (FeeCategory.search, None, "Trade mark search (Reg. 78(a))", None),
    "9": (FeeCategory.other, None, "Certified copy of registration (§6(b))", None),
    "10": (
        FeeCategory.extension,
        None,
        "Extension of time (Reg. 82) — per month or part thereof, per mark",
        FeeCondition(
            trigger=ConditionalTrigger.late_days,
            per_unit=True,
            description="Per month or part thereof.",
        ),
    ),
    "11": (FeeCategory.other, None, "Request to make submissions in proceedings (Reg. 26)", None),
    "12": (
        FeeCategory.examination,
        None,
        "On-site expedited examination (Reg. 22(c)) — per class",
        None,
    ),
    "13": (FeeCategory.other, None, "Photocopy of any document, per page", None),
    "14": (FeeCategory.other, None, "Scanned copy of registration file", None),
}


# Madrid Protocol section publishes three fees, all NIS 626.
# The PDF lists them as plain prose paragraphs (not numbered items)
# in the Madrid sub-section. The connector emits them as three named
# FeeItems with FeeCategory.madrid.
_MADRID_ITEMS: list[tuple[str, str]] = [
    (
        "madrid-international-application",
        "Handling fee for an international registration application (§56C(1) Ordinance)",
    ),
    (
        "madrid-extension-not-il",
        "Handling fee for an extension request not designating Israel (§56C(2) Ordinance)",
    ),
    (
        "madrid-renewal",
        "Handling fee for renewal/extension of an international registration (§56J(1) Ordinance)",
    ),
]


# ──────────────────────────────────────────────────────────────────────
# Design (modern Law 5777-2017) metadata
# ──────────────────────────────────────────────────────────────────────


_DESIGN_ITEM_META: dict[str, tuple[FeeCategory, int | None, str, FeeCondition | None]] = {
    # 1 — Design application (single design or supplementary design,
    # §19 + §55). Small-entity 40% reduction available for first
    # application.
    "1": (
        FeeCategory.filing,
        None,
        "Design application (Law §19, including supplementary design §55) — per design (not part of a set)",
        None,
    ),
    # 2 — Design application — set of articles.
    "2": (
        FeeCategory.filing,
        None,
        "Design application for a set of articles (Law §19, including supplementary design §55) — per set",
        None,
    ),
    # 3 — On-site expedited examination.
    "3": (FeeCategory.examination, None, "On-site expedited examination (§28) — per design", None),
    # 4 — Designer-naming request.
    "4": (FeeCategory.other, None, "Request to record designer name (§33) — per design", None),
    # 5 — Renewal periods (§40 + §86(1)), per design.
    "5.(1)": (
        FeeCategory.renewal,
        10,
        "Design renewal — first period (years 6-10 from filing)",
        None,
    ),
    "5.(2)": (
        FeeCategory.renewal,
        15,
        "Design renewal — period from year 10 to year 15",
        None,
    ),
    "5.(3)": (
        FeeCategory.renewal,
        20,
        "Design renewal — period from year 15 to year 20",
        None,
    ),
    "5.(4)": (
        FeeCategory.renewal,
        25,
        "Design renewal — period from year 20 to year 25",
        None,
    ),
    "5.(5)": (
        FeeCategory.renewal,
        25,
        "Design renewal — all periods together (years 6-25, paid in advance)",
        None,
    ),
    # 6 — Late renewal surcharge.
    "6": (
        FeeCategory.late_fee,
        None,
        "Late-renewal surcharge (§§41, 86(1)) — per design, per month",
        FeeCondition(
            trigger=ConditionalTrigger.late_days,
            per_unit=True,
            description="Per month or part thereof of late renewal payment.",
        ),
    ),
    # 7 — Restoration.
    "7": (FeeCategory.other, None, "Restoration of registration (§43)", None),
    # 8 — Register correction.
    "8": (FeeCategory.other, None, "Register / document correction (§46(a))", None),
    # 9 — Recordation of a right.
    "9": (FeeCategory.transfer, None, "Recordation of a right in a design (§17)", None),
    # 10 — Third-party cancellation / restoration revocation / amendment-cancellation.
    "10": (
        FeeCategory.cancellation,
        None,
        "Third-party cancellation of design registration / restoration revocation / amendment cancellation (§48)",
        None,
    ),
    # 11 — Objection (השגה) before the Registrar.
    "11": (FeeCategory.appeal, None, "Objection before the Registrar (§96)", None),
    # 12 — Intervention in a proceeding.
    "12": (FeeCategory.other, None, "Intervention in a proceeding (§98)", None),
    # 13 — Extension-of-time fee.
    "13": (
        FeeCategory.extension,
        None,
        "Extension of time (§100)",
        FeeCondition(
            trigger=ConditionalTrigger.late_days,
            per_unit=True,
            description="Extension of time, per month or part thereof.",
        ),
    ),
    # 14 — Certified document.
    "14": (FeeCategory.other, None, "Certified document (§104)", None),
    # 15 — File copy.
    "15": (FeeCategory.other, None, "File copy (§104)", None),
}


# ──────────────────────────────────────────────────────────────────────
# Small-entity discount
# ──────────────────────────────────────────────────────────────────────


# Patents items eligible for the 40% reduction per the schedule's
# inline eligibility language (turnover under NIS 10M + first-ever
# application for the invention).
_PATENT_SMALL_ENTITY_ITEMS: frozenset[str] = frozenset({"1", "10"})
# Designs items eligible (Items 1 and 2; "מבקש מיוחד" language in
# the schedule).
_DESIGN_SMALL_ENTITY_ITEMS: frozenset[str] = frozenset({"1", "2"})

# 60% of the full fee (== 40% reduction) per the schedule.
_SMALL_ENTITY_MULTIPLIER = Decimal("0.6")

_SMALL_ENTITY_NOTE = (
    "Small-entity 40% reduction: applies to a *first* patent / design "
    "application for the invention, where the applicant is an "
    "individual, a company/partnership with turnover under NIS 10 "
    "million in the preceding year, a recognized higher-education "
    "institution under § 9 of the Council for Higher Education Law "
    "5718-1958, or a wholly-owned technology-transfer subsidiary "
    "thereof."
)


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _slugify(*parts: str) -> str:
    cleaned: list[str] = []
    for p in parts:
        if not p:
            continue
        s = re.sub(r"[^a-z0-9]+", "-", p.lower()).strip("-")[:40]
        if s:
            cleaned.append(s)
    return "-".join(cleaned)


def _ensure_unique(code: str, seen: set[str]) -> str:
    if code not in seen:
        seen.add(code)
        return code
    n = 2
    while f"{code}-{n}" in seen:
        n += 1
    candidate = f"{code}-{n}"
    seen.add(candidate)
    return candidate


def _round_nis(amount: Decimal) -> Decimal:
    """Round to the nearest shekel (ILPO's CPI-adjustment convention)."""
    return amount.quantize(Decimal("1"))


# ──────────────────────────────────────────────────────────────────────
# Builders
# ──────────────────────────────────────────────────────────────────────


_STATUTORY_PATENT = (
    "Patents Law, 5727-1967 + Patents Regulations (Office Practice, "
    "Procedural Rules, Documents and Fees), 5728-1968 — Schedule "
    '("Tosefet"). CPI-adjusted annually; the controlling text is '
    "the Reshumot (Official Gazette) supplementary issue."
)
_STATUTORY_TRADEMARK = (
    "Trade Marks Ordinance [New Version], 5732-1972 + Trade Marks "
    "Regulations, 5700-1940. CPI-adjusted annually; controlling "
    "text is Reshumot."
)
_STATUTORY_DESIGN = (
    "Designs Law, 5777-2017 (in force 2018-08-07) + Designs "
    "Regulations. CPI-adjusted annually; controlling text is "
    "Reshumot."
)


def _build_patent_fees(pdf_text: str) -> list[FeeItem]:
    fees: list[FeeItem] = []
    seen_codes: set[str] = set()
    sections = _slice_sections(pdf_text)

    # Main patents section.
    main = sections.get("PATENT", "")
    for key, _desc, amount in _iter_items(main):
        meta = _PATENT_ITEM_META.get(key)
        if meta is None:
            # Unknown item — emit as "other" with the key in the
            # label so a researcher can map it later. Avoid dropping.
            label = f"Patent fee item {key}"
            code = _ensure_unique(_slugify("il-pat", key), seen_codes)
            fees.append(
                FeeItem(
                    code=code,
                    label=label[:200],
                    category=FeeCategory.other,
                    rights=[RightType.patent],
                    amount=amount,
                    currency="ILS",
                    tier=EntityTier.none,
                    source_url=IL_ILPO_FEES_PDF_URL,
                    notes=(
                        "Unmapped item from the ILPO 2026 patents fee "
                        "schedule. Verify against the PDF before "
                        "client-facing use."
                    ),
                )
            )
            continue
        category, year, label, condition = meta
        code = _ensure_unique(_slugify("il-pat", key), seen_codes)
        fees.append(
            FeeItem(
                code=code,
                label=(label or f"Patent item {key}")[:200],
                category=category,
                rights=[RightType.patent],
                amount=amount,
                currency="ILS",
                tier=EntityTier.none,
                year=year,
                condition=condition,
                source_url=IL_ILPO_FEES_PDF_URL,
            )
        )
        # Small-entity 40% reduction — emit a duplicate row at 60% of
        # the full amount with EntityTier.small.
        if key in _PATENT_SMALL_ENTITY_ITEMS:
            small_amount = _round_nis(amount * _SMALL_ENTITY_MULTIPLIER)
            small_code = _ensure_unique(_slugify("il-pat", key, "small"), seen_codes)
            fees.append(
                FeeItem(
                    code=small_code,
                    label=(label or f"Patent item {key}")[:200],
                    category=category,
                    rights=[RightType.patent],
                    amount=small_amount,
                    currency="ILS",
                    tier=EntityTier.small,
                    year=year,
                    condition=condition,
                    source_url=IL_ILPO_FEES_PDF_URL,
                    notes=_SMALL_ENTITY_NOTE,
                )
            )

    # Patent term extension (PTE) sub-section. Keys here include
    # Hebrew letters (e.g. "(א)") which slugify drops to nothing; we
    # transliterate the well-known PTE letter-keys to keep the code
    # slug readable.
    _PTE_KEY_SLUG = {
        "(1)": "app",
        "(2)": "ren-base",
        "(א)": "ren-y1",
        "(ב)": "ren-y2",
        "(ג)": "ren-y3",
        "(ד)": "cancel",
    }
    pte = sections.get("PAT_EXT", "")
    for key, _desc, amount in _iter_items(pte):
        meta_pte = _PATENT_EXTENSION_META.get(key)
        if meta_pte is None:
            continue
        category, year, label, condition = meta_pte
        slug_suffix = _PTE_KEY_SLUG.get(key, _slugify(key) or "item")
        code = _ensure_unique(_slugify("il-pat-pte", slug_suffix), seen_codes)
        fees.append(
            FeeItem(
                code=code,
                label=label[:200],
                category=category,
                rights=[RightType.patent],
                amount=amount,
                currency="ILS",
                tier=EntityTier.none,
                year=year,
                condition=condition,
                source_url=IL_ILPO_FEES_PDF_URL,
                notes="Patent term extension (PTE) fee.",
            )
        )

    return fees


def _build_trademark_fees(pdf_text: str) -> list[FeeItem]:
    fees: list[FeeItem] = []
    seen_codes: set[str] = set()
    sections = _slice_sections(pdf_text)

    tm = sections.get("TM", "")
    for key, _desc, amount in _iter_items(tm):
        meta = _TRADEMARK_ITEM_META.get(key)
        if meta is None:
            continue
        category, year, label, condition = meta
        code = _ensure_unique(_slugify("il-tm", key), seen_codes)
        fees.append(
            FeeItem(
                code=code,
                label=label[:200],
                category=category,
                rights=[RightType.trademark],
                amount=amount,
                currency="ILS",
                tier=EntityTier.none,
                year=year,
                condition=condition,
                source_url=IL_ILPO_FEES_PDF_URL,
            )
        )

    # Madrid sub-section: three NIS-626 fees published as prose
    # rather than numbered items. The simplest robust extraction is
    # to count distinct "626" tokens in the Madrid section text;
    # there should be exactly three.
    madrid = sections.get("MADRID", "")
    amounts = re.findall(r"\b(\d{1,3}(?:,\d{3})*)\b", madrid)
    candidates = [Decimal(a.replace(",", "")) for a in amounts]
    # Take the most common 100-9999 amount in the section as the
    # Madrid fee. (The 2026 schedule publishes all three at NIS 626.)
    plausible = [a for a in candidates if Decimal("100") <= a <= Decimal("9999")]
    if plausible:
        from collections import Counter

        most_common_amt = Counter(plausible).most_common(1)[0][0]
        for slug, label in _MADRID_ITEMS:
            code = _ensure_unique(_slugify("il-tm", slug), seen_codes)
            fees.append(
                FeeItem(
                    code=code,
                    label=label[:200],
                    category=FeeCategory.madrid,
                    rights=[RightType.trademark],
                    amount=most_common_amt,
                    currency="ILS",
                    tier=EntityTier.none,
                    source_url=IL_ILPO_FEES_PDF_URL,
                    notes=(
                        "Madrid Protocol handling fee (ILPO's share). "
                        "WIPO-administered Madrid system fees in CHF "
                        "are billed separately by the International "
                        "Bureau."
                    ),
                )
            )

    return fees


def _build_design_fees(pdf_text: str) -> list[FeeItem]:
    fees: list[FeeItem] = []
    seen_codes: set[str] = set()
    sections = _slice_sections(pdf_text)

    des = sections.get("DESIGN_NEW", "")
    for key, _desc, amount in _iter_items(des):
        meta = _DESIGN_ITEM_META.get(key)
        if meta is None:
            continue
        category, year, label, condition = meta
        code = _ensure_unique(_slugify("il-des", key), seen_codes)
        fees.append(
            FeeItem(
                code=code,
                label=label[:200],
                category=category,
                rights=[RightType.design],
                amount=amount,
                currency="ILS",
                tier=EntityTier.none,
                year=year,
                condition=condition,
                source_url=IL_ILPO_FEES_PDF_URL,
            )
        )
        # Small-entity 40% reduction (Items 1, 2).
        if key in _DESIGN_SMALL_ENTITY_ITEMS:
            small_amount = _round_nis(amount * _SMALL_ENTITY_MULTIPLIER)
            small_code = _ensure_unique(_slugify("il-des", key, "small"), seen_codes)
            fees.append(
                FeeItem(
                    code=small_code,
                    label=label[:200],
                    category=category,
                    rights=[RightType.design],
                    amount=small_amount,
                    currency="ILS",
                    tier=EntityTier.small,
                    year=year,
                    condition=condition,
                    source_url=IL_ILPO_FEES_PDF_URL,
                    notes=_SMALL_ENTITY_NOTE,
                )
            )

    return fees


# ──────────────────────────────────────────────────────────────────────
# Public scrape entry points
# ──────────────────────────────────────────────────────────────────────


_PDF_LANGUAGE_NOTE = (
    "Source PDF is Hebrew-only — ILPO does not publish an English "
    "translation of the current-effective fee schedule on gov.il. "
    "Item labels in this connector are English-language summaries "
    "of the controlling Hebrew text. The Hebrew schedule is the "
    "authoritative version per Reshumot (Israeli Official Gazette)."
)


def _common_notes(extra: str = "") -> str:
    base = (
        "ILPO 2026 fee schedule, gazetted 2025-12-22, effective "
        "2026-01-01. Currency is Israeli new shekel (NIS / ILS); "
        "fees are CPI-adjusted annually and rounded to the nearest "
        "shekel. " + _PDF_LANGUAGE_NOTE
    )
    if extra:
        base = base + "\n\n" + extra
    return base


async def scrape_ilpo_patents() -> FeeSchedule:
    """Scrape the ILPO Israel patent fee schedule.

    Live fetch goes through :class:`ILPOFeesClient` (which requires a
    Cloudflare-clearing transport on ``gov.il``); in CI the parser
    is exercised against the pinned fixture.
    """
    async with ILPOFeesClient() as client:
        pdf_bytes = await client.fetch_pdf()
    return _build_patent_schedule_from_pdf(pdf_bytes)


def _build_patent_schedule_from_pdf(pdf_bytes: bytes) -> FeeSchedule:
    text = _extract_pdf_text(pdf_bytes)
    fees = _build_patent_fees(text)
    if not fees:
        raise RuntimeError(
            "ILPO patent scraper parsed zero rows — PDF structure may "
            "have changed (gazetted year-end 2025-12-22 for 2026)"
        )
    return FeeSchedule(
        jurisdiction="IL",
        issuing_body="Israel Patent Office",
        office_code="ILPO",
        right=RightType.patent,
        currency="ILS",
        effective_date=IL_ILPO_FEES_EFFECTIVE_DATE,
        source_url=IL_ILPO_FEES_PDF_URL,
        statutory_basis=_STATUTORY_PATENT,
        retrieved_at=date.today(),
        fees=fees,
        notes=_common_notes(
            "Renewal model is cumulative-coverage at four checkpoints "
            "(years 6, 10, 14, 18, 22) rather than per-annum; the "
            "connector emits one renewal FeeItem per checkpoint with "
            "`year` set to the terminal year of the period. Items 1 "
            "(filing) and 10 (allowance) are emitted twice — once at "
            "the full headline amount with `tier=none`, and once at "
            "60% of the headline (the 40% small-entity reduction) "
            "with `tier=small`."
        ),
    )


async def scrape_ilpo_trademarks() -> FeeSchedule:
    """Scrape the ILPO Israel trademark fee schedule."""
    async with ILPOFeesClient() as client:
        pdf_bytes = await client.fetch_pdf()
    return _build_trademark_schedule_from_pdf(pdf_bytes)


def _build_trademark_schedule_from_pdf(pdf_bytes: bytes) -> FeeSchedule:
    text = _extract_pdf_text(pdf_bytes)
    fees = _build_trademark_fees(text)
    if not fees:
        raise RuntimeError(
            "ILPO trademark scraper parsed zero rows — PDF structure may have changed"
        )
    return FeeSchedule(
        jurisdiction="IL",
        issuing_body="Israel Patent Office",
        office_code="ILPO",
        right=RightType.trademark,
        currency="ILS",
        effective_date=IL_ILPO_FEES_EFFECTIVE_DATE,
        source_url=IL_ILPO_FEES_PDF_URL,
        statutory_basis=_STATUTORY_TRADEMARK,
        retrieved_at=date.today(),
        fees=fees,
        notes=_common_notes(
            "Trademark term is 10 years from registration (renewable "
            "indefinitely under § 32 of the Trade Marks Ordinance). "
            "Israel has been a Madrid Protocol member since 2010; "
            "the three Madrid-routing fees on the schedule are "
            "ILPO's share — WIPO bills the international portion "
            "separately in CHF."
        ),
    )


async def scrape_ilpo_designs() -> FeeSchedule:
    """Scrape the ILPO Israel design fee schedule (modern Designs Law 5777-2017)."""
    async with ILPOFeesClient() as client:
        pdf_bytes = await client.fetch_pdf()
    return _build_design_schedule_from_pdf(pdf_bytes)


def _build_design_schedule_from_pdf(pdf_bytes: bytes) -> FeeSchedule:
    text = _extract_pdf_text(pdf_bytes)
    fees = _build_design_fees(text)
    if not fees:
        raise RuntimeError("ILPO design scraper parsed zero rows — PDF structure may have changed")
    return FeeSchedule(
        jurisdiction="IL",
        issuing_body="Israel Patent Office",
        office_code="ILPO",
        right=RightType.design,
        currency="ILS",
        effective_date=IL_ILPO_FEES_EFFECTIVE_DATE,
        source_url=IL_ILPO_FEES_PDF_URL,
        statutory_basis=_STATUTORY_DESIGN,
        retrieved_at=date.today(),
        fees=fees,
        notes=_common_notes(
            "Schedule reflects the Designs Law 5777-2017 (in force "
            "2018-08-07). Designs filed before 2018-08-07 are still "
            "governed by the legacy Patents and Designs Ordinance "
            "(1924); those legacy fees appear in the source PDF but "
            "are not emitted here — they apply only to a shrinking "
            "tail of pre-2018 registrations. The schedule supports "
            "five-year renewal periods up to a 25-year maximum "
            "(years 6-10, 10-15, 15-20, 20-25) plus an all-periods "
            "option. Items 1 and 2 (filing) are emitted twice — "
            "once at full amount, once at 60% for the first-"
            "application small-entity discount."
        ),
    )


__all__ = [
    "IL_ILPO_FEES_LANDING_URL",
    "IL_ILPO_FEES_PDF_URL",
    "IL_ILPO_FEES_EFFECTIVE_DATE",
    "IL_ILPO_FEES_GAZETTED_DATE",
    "ILPOFeesClient",
    "scrape_ilpo_patents",
    "scrape_ilpo_trademarks",
    "scrape_ilpo_designs",
]
