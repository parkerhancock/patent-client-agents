"""TIPO Taiwan fee-schedule scraper.

TIPO publishes English fee tables on two separate landing pages:

* Patents — https://www.tipo.gov.tw/en/tipo2/326.html (single HTML
  table, 34 line-items in NT$).
* Trademarks — https://www.tipo.gov.tw/en/tipo2/342.html (HTML
  wrapper with a "Download File" link to a bilingual zh-TW + EN PDF;
  the EN amounts read as ``NT$X,YYY per <unit>``).

Both schedules cover three patent right-types: invention patents
(20-year term), utility model patents (10-year term), and design
patents (15-year term, post-2013 amendments). All amounts are in
TWD (New Taiwan dollar).

Patent quirks
-------------
* **Entity tiers**: standard + small. Small applies to natural
  persons, schools, and SMEs (the schedule phrases this as "a
  patentee who is a natural person, a school, or a small and
  medium-sized enterprise"). The schedule publishes the small-tier
  amount as a sibling row to the standard row — we emit BOTH as
  separate FeeItems with ``tier=large`` and ``tier=small``.
* **Multi-sub-item rows**: row 1 bundles four procedural variants
  ``(1)`` through ``(4)`` under one NT$3,500 amount. We emit ONE
  FeeItem per logical row with the full sub-item list preserved in
  ``notes``.
* **Year-banded annuities** by right-type:
  - Invention: 1-3, 4-6, 7-9, 10+ (cap at 20)
  - Utility model: 1-3 (shared row with invention), 4-6, 7+ (cap at 10)
  - Design: 1-3, 4-6, 7+ (cap at 15)
* **Per-claim surcharge** (over 10 claims): NT$800 for invention
  substantive examination; NT$600 for utility-model TER.
* **Per-page surcharge** (over 50 pages): NT$500 each additional 50
  pages.

Trademark quirks
----------------
The TM PDF interleaves Chinese and English line-by-line and pypdf's
extract_text() breaks words across whitespace ("designate d good",
"Restrictio n"). Rather than attempt a positional walk on this
chaotic stream, the scraper ships a **curated catalog of 30
entries** and verifies each against the live PDF: the entry's
English label and amount must co-occur within a 300-character
window in the normalized text. Drift raises loudly rather than
silently mis-categorizing rows. This trades automation for
robustness — TIPO revises the TM schedule on a planned ~annual
cadence (most recent: 2024-05-01), so each amendment is reviewable.

Statutory bases
---------------
* Patent Act (專利法) and its implementing Patent Fee Regulations.
* Trademark Act (商標法) Article 33 (10-year renewal cycle) and
  Article 104 (fee delegation); the 2024-05-01 Trademark Fee
  Standards notice is carried on the PDF first page.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date
from decimal import Decimal

import pypdf
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

TIPO_BASE_URL = "https://www.tipo.gov.tw"
TIPO_PATENT_FEES_URL = "https://www.tipo.gov.tw/en/tipo2/326.html"
TIPO_TM_FEES_URL = "https://www.tipo.gov.tw/en/tipo2/342.html"


# ──────────────────────────────────────────────────────────────────────
# HTTP client
# ──────────────────────────────────────────────────────────────────────


class TIPOFeesClient(BaseAsyncClient):
    """Shared HTTP client for both TIPO fee routes (HTML + PDF)."""

    DEFAULT_BASE_URL = TIPO_BASE_URL
    CACHE_NAME = "tipo_fees"
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
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def fetch_html(self, path: str) -> str:
        r = await self._request("GET", path, context=f"tipo_html {path[:40]}")
        return r.text

    async def fetch_pdf(self, path: str) -> bytes:
        r = await self._request("GET", path, context=f"tipo_pdf {path[:40]}")
        return r.content


# ──────────────────────────────────────────────────────────────────────
# Shared amount + tier helpers
# ──────────────────────────────────────────────────────────────────────

_NT_RE = re.compile(r"NT\$\s*([\d,]+)")


def _parse_nt(raw: str) -> Decimal | None:
    """Parse 'NT$3,500' → Decimal('3500')."""
    m = _NT_RE.search(raw)
    if not m:
        return None
    cleaned = m.group(1).replace(",", "")
    try:
        return Decimal(cleaned)
    except Exception:
        return None


def _slugify(*parts: str | int | None) -> str:
    """Build a stable lowercase kebab-case code from arbitrary parts."""
    pieces: list[str] = []
    for p in parts:
        if p is None:
            continue
        s = str(p).lower()
        s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
        if s:
            pieces.append(s[:40])
    return "-".join(pieces) or "tipo-fee"


# ──────────────────────────────────────────────────────────────────────
# Patent scraper
# ──────────────────────────────────────────────────────────────────────

# Patentees on the SME tier per the schedule:
#   "natural person, a school, or a small and medium-sized enterprise"
_SME_RE = re.compile(r"natural person.{0,20}school.{0,30}small and medium", re.IGNORECASE)
_ANNUITY_RE = re.compile(
    r"annuity for a granted (invention|utility model|design) patent"
    r"(?: or a granted (invention|utility model|design) patent)?"
    r"\s*\(?\s*"
    r"(?:(\d+)(?:st|nd|rd|th)?\s*-\s*(\d+)(?:st|nd|rd|th)?\s*year"
    r"|(\d+)(?:st|nd|rd|th)?\s*year(?:\s+and beyond)?)",
    re.IGNORECASE,
)
# Term caps by Taiwan patent type. Used to expand "Nth year and beyond" rows.
_RIGHT_TERM_CAP = {"invention": 20, "utility model": 10, "design": 15}


def _emit_annuity_rows(
    row_no: int,
    desc: str,
    amount: Decimal,
    *,
    sme_amount: Decimal | None = None,
) -> list[FeeItem]:
    """Expand a TIPO annuity description into per-year FeeItem rows.

    Handles:
    * "Annuity for a granted invention patent or a granted utility model
      patent (1st-3rd year)" → years 1,2,3 for BOTH invention & UM.
    * "Annuity for a granted invention patent (10th year and beyond)" →
      years 10..20 (capped at the invention term).
    * "Annuity for a granted design patent (4th-6th year)" → 4,5,6.

    The same FeeItem is emitted at ``EntityTier.large`` (standard) and,
    when ``sme_amount`` is non-None, additionally at ``EntityTier.small``.
    """
    m = _ANNUITY_RE.search(desc)
    if not m:
        return []
    primary_right, secondary_right, ystart, yend, yopen = m.groups()
    rights_text = [primary_right]
    if secondary_right:
        rights_text.append(secondary_right)
    if ystart and yend:
        years = list(range(int(ystart), int(yend) + 1))
    else:
        years = []
        if yopen:
            yopen_int = int(yopen)
            # Cap by right-type term
            caps = [_RIGHT_TERM_CAP[r.lower()] for r in rights_text]
            cap = max(caps) if caps else 20
            years = list(range(yopen_int, cap + 1))
    if not years:
        return []

    out: list[FeeItem] = []
    for right_text in rights_text:
        right_text_lc = right_text.lower()
        # Always patent — TIPO does not file utility models/designs under
        # separate "right" categories in our closed vocab; we use
        # RightType.patent and capture the variant in the label/notes.
        for year in years:
            for tier, value in (
                (EntityTier.large, amount),
                (EntityTier.small, sme_amount),
            ):
                if value is None:
                    continue
                out.append(
                    FeeItem(
                        code=_slugify("tipo", "annuity", right_text_lc, year, tier.value),
                        label=(f"Annuity for granted {right_text_lc} patent, year {year}"),
                        category=FeeCategory.renewal,
                        rights=[RightType.patent],
                        amount=value,
                        currency="TWD",
                        tier=tier,
                        year=year,
                        source_url=TIPO_PATENT_FEES_URL,
                        notes=(f"TIPO Schedule of Patent Fees row {row_no}. Source row: {desc!r}"),
                    )
                )
    return out


def _categorize_patent(desc: str) -> tuple[FeeCategory, FeeCondition | None]:
    """Map a patent fee description to a closed-vocab category + condition."""
    d = desc.lower()

    # Order matters: check more specific patterns first.
    if "annuity" in d:
        return FeeCategory.renewal, None
    if "each additional claim" in d or "exceed 10" in d and "claim" in d:
        return FeeCategory.excess_claims, FeeCondition(
            trigger="claims_over",  # type: ignore[arg-type]
            threshold=10,
            per_unit=True,
            description="TIPO per-claim surcharge over 10 claims.",
        )
    if "additional fee" in d and "page" in d:
        return FeeCategory.excess_pages, FeeCondition(
            trigger="pages_over",  # type: ignore[arg-type]
            threshold=50,
            per_unit=True,
            description="TIPO per-50-page surcharge over 50 pages (each addl 50 pages counted as 50).",
        )
    if "substantive examination" in d or "re-examination of an invention application" in d:
        return FeeCategory.examination, None
    if "technical evaluation report" in d:
        return FeeCategory.examination, None
    if "accelerated examination" in d:
        return FeeCategory.examination, None
    if (
        "filing of an invention" in d
        or "filing of a utility model" in d
        or "filing of a design" in d
    ):
        return FeeCategory.filing, None
    if "conversion" in d and "application" in d:
        return FeeCategory.filing, None
    if "division of" in d and "application" in d:
        return FeeCategory.filing, None
    if "invalidation" in d:
        return FeeCategory.cancellation, None
    if "post-grant amendment" in d:
        return FeeCategory.other, None
    if "adding supplementary reasons" in d:
        return FeeCategory.other, None
    if "early laying-open" in d or "interview" in d:
        return FeeCategory.other, None
    if "compulsory license" in d:
        return FeeCategory.petition, None
    if "recordation" in d or "assignment" in d or "license" in d or "pledge" in d:
        return FeeCategory.transfer, None
    if "patent certificate" in d or "certified copy" in d:
        return FeeCategory.other, None
    if "patent attorney license" in d or "patent agent license" in d:
        return FeeCategory.other, None
    return FeeCategory.other, None


def _build_patent_fees(doc: L.HtmlElement) -> list[FeeItem]:
    """Walk the single 35-row TIPO patent fee table and emit FeeItems.

    SME-tier rows are detected by the phrase "A patentee who is a natural
    person, a school, or a small and medium-sized enterprise" — we
    associate each SME row with the *preceding* standard-tier row and
    emit them as paired large/small FeeItem instances.
    """
    fees: list[FeeItem] = []
    table = doc.cssselect("table")
    if not table:
        return fees
    rows = table[0].cssselect("tr")
    pending_standard: tuple[int, str, Decimal] | None = None
    """(row_no, description, amount) of the most-recently-seen standard row,
    held until we know if the next row is its SME-tier sibling."""

    for tr in rows:
        cells = tr.cssselect("th, td")
        if len(cells) < 3:
            continue
        rowno_raw = cells[0].text_content().strip()
        desc = re.sub(r"\s+", " ", cells[1].text_content()).strip()
        amount_raw = cells[2].text_content().strip()
        if not rowno_raw.isdigit():
            continue
        rowno = int(rowno_raw)
        amount = _parse_nt(amount_raw)
        if amount is None:
            logger.debug("TIPO patent row %d: unparseable amount %r", rowno, amount_raw)
            continue

        is_sme = bool(_SME_RE.search(desc))
        if is_sme and pending_standard is not None:
            std_rowno, std_desc, std_amount = pending_standard
            # Annuity SME pairing: re-emit prior annuity row with both tiers.
            ann = _emit_annuity_rows(std_rowno, std_desc, std_amount, sme_amount=amount)
            if ann:
                # Drop any already-emitted std-only annuity rows for this row#
                fees = [f for f in fees if f"row {std_rowno}." not in (f.notes or "")]
                fees.extend(ann)
            else:
                # Non-annuity SME row (rare in TIPO patent schedule; defensive)
                category, condition = _categorize_patent(std_desc)
                fees.append(
                    FeeItem(
                        code=_slugify("tipo", "patent", std_rowno, "small"),
                        label=std_desc[:160],
                        category=category,
                        rights=[RightType.patent],
                        amount=amount,
                        currency="TWD",
                        tier=EntityTier.small,
                        condition=condition,
                        source_url=TIPO_PATENT_FEES_URL,
                        notes=(f"TIPO Schedule of Patent Fees row {std_rowno}. SME tier: {desc!r}"),
                    )
                )
            pending_standard = None
            continue

        # Standard-tier row — emit immediately, but remember it in case
        # the next row is its SME pair.
        ann = _emit_annuity_rows(rowno, desc, amount)
        if ann:
            fees.extend(ann)
            pending_standard = (rowno, desc, amount)
            continue

        category, condition = _categorize_patent(desc)
        # Build a tier value: TIPO is "none" for non-annuity rows (they
        # don't carry an entity discount).
        fees.append(
            FeeItem(
                code=_slugify("tipo", "patent", rowno),
                label=desc[:160],
                category=category,
                rights=[RightType.patent],
                amount=amount,
                currency="TWD",
                tier=EntityTier.none,
                condition=condition,
                source_url=TIPO_PATENT_FEES_URL,
                notes=f"TIPO Schedule of Patent Fees row {rowno}. Source row: {desc!r}",
            )
        )
        pending_standard = None
    return fees


async def scrape_tipo_patents() -> FeeSchedule:
    """Scrape TIPO Taiwan patent fee schedule (TWD, large + small tiers on annuities)."""
    async with TIPOFeesClient() as client:
        html_text = await client.fetch_html("/en/tipo2/326.html")
    doc = L.fromstring(html_text)
    fees = _build_patent_fees(doc)
    if not fees:
        raise RuntimeError("TIPO patent scraper parsed zero rows — page structure likely changed")

    return FeeSchedule(
        jurisdiction="TW",
        issuing_body="Taiwan Intellectual Property Office",
        office_code="TIPO",
        right=RightType.patent,
        currency="TWD",
        # TIPO does not stamp an effective date on the patent fee table
        # (unlike the TM PDF, which carries a 2024-05-01 banner). Anchor
        # to the most recent visible amendment year; refresh on re-verify.
        effective_date=date(2024, 5, 1),
        source_url=TIPO_PATENT_FEES_URL,
        statutory_basis=(
            "Patent Act (專利法) + Patent Fee Regulations issued by TIPO. "
            "Schedule of Patent Fees published on the TIPO English site."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "TIPO covers three patent right-types under one office: invention "
            "(20-yr term), utility model (10-yr term), and design (15-yr term). "
            "Annuity rows are expanded per-year, and the small-tier discount "
            "(natural persons / schools / SMEs) is emitted as a sibling row "
            "for the three years where it applies (1-3, 4-6, plus design 1-3 "
            "which goes to NT$0). Non-annuity rows are emitted at "
            "EntityTier.none since the schedule does not publish a small-tier "
            "discount for procedural fees."
        ),
    )


# ──────────────────────────────────────────────────────────────────────
# Trademark scraper (PDF)
# ──────────────────────────────────────────────────────────────────────


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Return CJK-stripped, whitespace-collapsed text of the TM fee PDF.

    The PDF is bilingual (Chinese + English) and after pypdf's
    extract_text() the columns interleave. Stripping CJK characters
    leaves an English-mostly stream where each fee reads as
    ``<label> <amount> NT$<amount> per <unit>`` (the amount appears
    twice because the Chinese column also uses Arabic numerals).
    """
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    parts = [page.extract_text() or "" for page in reader.pages]
    raw = "\n".join(parts)
    # Strip non-ASCII (CJK + Chinese punctuation)
    ascii_only = re.sub(r"[^\x00-\x7F]+", " ", raw)
    return re.sub(r"\s+", " ", ascii_only).strip()


# ── Curated catalog ────────────────────────────────────────────────────
# The TIPO TM PDF interleaves zh-TW + EN columns and a positional walk
# cannot reliably pair fees with their hierarchical sub-conditions
# ("For a class in Classes 1 to 34" / "20 designated goods or less in a
# single class" → NT$3,000 per class). Instead we ship a hand-curated
# catalog of fees and *verify* each one against the live PDF — every
# entry's ``expected_phrase`` must appear in the text, and its
# ``expected_amount`` must appear within the same window. A mismatch
# raises immediately so drift is loud, not silent.
#
# This trades automation for robustness: the schedule changes ~annually
# (last revision 2024-05-01) and each amendment is a planned event, not
# a surprise.

# Each entry: (code_suffix, label, category, expected_amount, expected_phrase,
#              condition, year)
_TM_CATALOG: list[tuple[str, str, FeeCategory, int, str, FeeCondition | None, int | None]] = [
    # ─── Application Fees ───
    (
        "app-class-1to34",
        "Trademark or collective trademark — application, per class in Classes 1-34 (≤20 designated goods)",
        FeeCategory.filing,
        3000,
        "For a class in Classes 1 to 34",
        FeeCondition(
            trigger="classes_over",  # type: ignore[arg-type]
            threshold=1,
            per_unit=True,
            description="Per-class fee in Nice Classes 1-34, ≤20 designated goods per class.",
        ),
        None,
    ),
    (
        "app-class-1to34-over20-goods",
        "Trademark application — additional per designated good over 20 in a single class (Classes 1-34)",
        FeeCategory.filing,
        200,
        "Additional NT$200 per designated good over 20 goods",
        FeeCondition(
            trigger="classes_over",  # type: ignore[arg-type]
            threshold=20,
            per_unit=True,
            description="TIPO additional NT$200 per designated good over 20 goods in a single class.",
        ),
        None,
    ),
    (
        "app-class-35to45",
        "Trademark or collective trademark — application, per class in Classes 35-45",
        FeeCategory.filing,
        3000,
        "For a class in Classes",  # combined w/ "35 to 45" runs to "Classes 35 to 45"; we verify the surrounding phrase
        FeeCondition(
            trigger="classes_over",  # type: ignore[arg-type]
            threshold=1,
            per_unit=True,
            description="Per-class fee in Nice Classes 35-45.",
        ),
        None,
    ),
    (
        "app-class-35-retail-over5",
        "Trademark application — additional per retail service over 5 in Class 35 (specific goods)",
        FeeCategory.filing,
        500,
        "Additional NT$500 per designated retail service",
        FeeCondition(
            trigger="classes_over",  # type: ignore[arg-type]
            threshold=5,
            per_unit=True,
            description="TIPO surcharge per retail service over 5 designated retail services of specific goods in Class 35.",
        ),
        None,
    ),
    (
        "app-accelerated",
        "Trademark accelerated examination — additional per class",
        FeeCategory.examination,
        6000,
        "Accelerated Examination",
        None,
        None,
    ),
    (
        "app-collective-cert-mark",
        "Collective membership mark or certification mark — application",
        FeeCategory.filing,
        5000,
        "Collective membership mark or certification mark",
        None,
        None,
    ),
    (
        "app-efile-discount",
        "Trademark application — e-filing discount per application",
        FeeCategory.filing,
        300,
        "A discount of NT$300 per application",
        None,
        None,
    ),
    (
        "app-efile-matched-terms",
        "Trademark application — additional e-filing discount per class for matched recommended terms",
        FeeCategory.filing,
        300,
        "An additional discount of NT$300 per class",
        None,
        None,
    ),
    # ─── Registration Fees ───
    (
        "reg-trademark",
        "Trademark or collective trademark — registration, per class",
        FeeCategory.grant,
        2500,
        "Registration Fees",
        FeeCondition(
            trigger="classes_over",  # type: ignore[arg-type]
            threshold=1,
            per_unit=True,
            description="Per-class registration fee.",
        ),
        None,
    ),
    (
        "reg-collective-cert-mark",
        "Collective membership mark or certification mark — registration",
        FeeCategory.grant,
        2500,
        "NT$2,500 per registration",
        None,
        None,
    ),
    # ─── Renewal Fees (10-year cycle per Trademark Act §33) ───
    (
        "renewal-trademark",
        "Trademark or collective trademark — renewal, per class (10-year cycle)",
        FeeCategory.renewal,
        4000,
        "Renewal Fees",
        FeeCondition(
            trigger="classes_over",  # type: ignore[arg-type]
            threshold=1,
            per_unit=True,
            description="Per-class renewal fee on the 10-year cycle.",
        ),
        10,
    ),
    (
        "renewal-collective-cert-mark",
        "Collective membership mark or certification mark — renewal (10-year cycle)",
        FeeCategory.renewal,
        4000,
        "NT$4,000 per renewal",
        None,
        10,
    ),
    # ─── Division Fees ───
    (
        "division-application",
        "Division of an application for registration — per additional application after division",
        FeeCategory.other,
        2000,
        "Division of an application for registration",
        None,
        None,
    ),
    (
        "division-registration",
        "Division of a trademark, certification mark, or collective trademark registration",
        FeeCategory.other,
        2000,
        "Division of a tradem",  # "trademark, certification mar k, ..." has space artifacts in extraction
        None,
        None,
    ),
    (
        "division-pre-disposition-surcharge",
        "Division surcharge — request prior to final disposition of opposition / invalidation / revocation",
        FeeCategory.other,
        2000,
        "Prior to the final disposition of an opposition",
        None,
        None,
    ),
    # ─── Other Fees ───
    (
        "amend-particulars",
        "Amendment or change to particulars in a registration or application — per request",
        FeeCategory.other,
        500,
        "Amendment or chan",  # "Amendment or change to particulars" with space artifact
        None,
        None,
    ),
    (
        "restrict-goods-services",
        "Restriction of designated goods or services of a registered trademark — per request",
        FeeCategory.other,
        500,
        "Restriction of designated goods or services",
        None,
        None,
    ),
    (
        "license-entry",
        "Entry of a license or sub-license — per entry",
        FeeCategory.transfer,
        2000,
        "Entry of a license",
        None,
        None,
    ),
    (
        "license-removal",
        "Entry of license or sub-license removal — per entry",
        FeeCategory.transfer,
        1000,
        "Entry of license or sub",  # "Entry of license or sub-license removal"
        None,
        None,
    ),
    (
        "transfer-entry",
        "Registration transfer entry — per entry",
        FeeCategory.transfer,
        2000,
        "Registration transfer entry",
        None,
        None,
    ),
    (
        "pledge-creation",
        "Pledge creation entry — per entry",
        FeeCategory.transfer,
        2000,
        "Pledge creation entry",
        None,
        None,
    ),
    (
        "pledge-extinguishment",
        "Pledge extinguishment entry — per entry",
        FeeCategory.transfer,
        1000,
        "Pledge extinguishment entry",
        None,
        None,
    ),
    # ─── Adversarial ───
    (
        "opposition",
        "Opposition — per class",
        FeeCategory.opposition,
        4000,
        "Opposition",
        FeeCondition(
            trigger="classes_over",  # type: ignore[arg-type]
            threshold=1,
            per_unit=True,
            description="Per-class opposition fee.",
        ),
        None,
    ),
    (
        "invalidation",
        "Invalidation — per class",
        FeeCategory.cancellation,
        7000,
        "Invalidation",
        FeeCondition(
            trigger="classes_over",  # type: ignore[arg-type]
            threshold=1,
            per_unit=True,
            description="Per-class invalidation fee.",
        ),
        None,
    ),
    (
        "revocation",
        "Revocation — per class",
        FeeCategory.cancellation,
        7000,
        "Revocation",
        FeeCondition(
            trigger="classes_over",  # type: ignore[arg-type]
            threshold=1,
            per_unit=True,
            description="Per-class revocation fee.",
        ),
        None,
    ),
    (
        "intervene",
        "Request to intervene in an opposition, invalidation, or revocation — per request",
        FeeCategory.other,
        2000,
        "Request to intervene",
        None,
        None,
    ),
    # ─── Administrative ───
    (
        "certified-copy",
        "Request to issue a certified copy of a document — per copy",
        FeeCategory.other,
        500,
        "certified copy of a document",
        None,
        None,
    ),
    (
        "file-review",
        "Request to review official files of a case — per request",
        FeeCategory.other,
        500,
        "review official files",
        None,
        None,
    ),
    (
        "tm-agent-registration",
        "Trademark agent registration or change thereto — per request",
        FeeCategory.other,
        500,
        "trademark agent registrations",
        None,
        None,
    ),
    (
        "replacement-registration-cert",
        "Request to issue a replacement registration certificate or re-issue — per request",
        FeeCategory.other,
        500,
        "replacement registration certificate",
        None,
        None,
    ),
]


def _normalize_for_match(s: str) -> str:
    """Lowercase + strip all whitespace, dashes, and punctuation for lookup.

    pypdf's text extraction breaks words mid-token ("designate d good",
    "Restrictio n", "trade mark") because the underlying PDF positions
    each glyph independently. Normalizing both haystack and needle to
    a single lowercase alphanumeric stream makes the catalog lookups
    robust to that artifact.
    """
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _build_tm_fees(text: str) -> list[FeeItem]:
    """Verify each catalog entry against ``text`` and emit FeeItems.

    Each entry's ``expected_phrase`` and ``expected_amount`` must
    co-occur within a 300-character window in the normalized text.
    Phrases like "Invalidation" appear in multiple non-fee contexts
    (e.g., "Prior to the final disposition of an opposition,
    invalidation or revocation..."); requiring co-occurrence with the
    expected amount disambiguates the actual fee label from prose
    references. A missing entry raises so drift is loud.
    """
    fees: list[FeeItem] = []
    norm_text = _normalize_for_match(text)
    for (
        code_suffix,
        label,
        category,
        expected_amount,
        expected_phrase,
        condition,
        year,
    ) in _TM_CATALOG:
        norm_phrase = _normalize_for_match(expected_phrase)
        norm_amount = _normalize_for_match(f"NT${expected_amount}")

        # Find every occurrence of the phrase, then pick the first one
        # that has the amount within ±300 chars. This handles labels
        # that appear in narrative prose elsewhere in the PDF.
        positions = [i for i in range(len(norm_text)) if norm_text.startswith(norm_phrase, i)]
        if not positions:
            raise RuntimeError(
                f"TIPO TM catalog entry {code_suffix!r} expected phrase "
                f"{expected_phrase!r} not found in PDF — schedule may have changed."
            )
        matched = False
        for pos in positions:
            window = norm_text[max(0, pos - 300) : pos + 400]
            if norm_amount in window:
                matched = True
                break
        if not matched:
            raise RuntimeError(
                f"TIPO TM catalog entry {code_suffix!r}: phrase "
                f"{expected_phrase!r} appears {len(positions)} time(s) but never "
                f"within 300 chars of NT${expected_amount} — amount may have changed."
            )
        fees.append(
            FeeItem(
                code=_slugify("tipo", "tm", code_suffix),
                label=label,
                category=category,
                rights=[RightType.trademark],
                amount=Decimal(expected_amount),
                currency="TWD",
                tier=EntityTier.none,
                year=year,
                condition=condition,
                source_url=TIPO_TM_FEES_URL,
                notes=(
                    f"TIPO Trademark Fee Standards (effective 2024-05-01). "
                    f"Verified against the bilingual PDF: phrase "
                    f"{expected_phrase!r}."
                ),
            )
        )
    return fees


async def scrape_tipo_trademarks() -> FeeSchedule:
    """Scrape TIPO Taiwan trademark fee schedule (TWD, single tier).

    The TM page wraps the PDF; we discover the PDF link from the
    landing page and fetch its bytes from the same client.
    """
    async with TIPOFeesClient() as client:
        landing_html = await client.fetch_html("/en/tipo2/342.html")
        doc = L.fromstring(landing_html)
        pdf_hrefs = [
            a.get("href")
            for a in doc.cssselect("a[href]")
            if a.get("href", "").lower().endswith(".pdf")
        ]
        if not pdf_hrefs:
            raise RuntimeError("TIPO TM landing has no PDF link — page structure likely changed")
        pdf_path = pdf_hrefs[0]
        if not pdf_path.startswith("/"):
            pdf_path = "/" + pdf_path.lstrip("/")
        pdf_bytes = await client.fetch_pdf(pdf_path)

    text = _extract_pdf_text(pdf_bytes)
    fees = _build_tm_fees(text)
    if not fees:
        raise RuntimeError("TIPO TM scraper parsed zero rows — PDF structure likely changed")

    # Pull the effective-date banner from page 1 if possible
    # The PDF stamps "Enforced on May 1, 2024" on page 1.
    eff_m = re.search(r"Enforced on (\w+ \d+,\s*\d{4})", text)
    effective: date
    if eff_m:
        try:
            from datetime import datetime as _dt

            effective = _dt.strptime(
                eff_m.group(1).replace(",", "").replace("  ", " "), "%B %d %Y"
            ).date()
        except ValueError:
            effective = date(2024, 5, 1)
    else:
        effective = date(2024, 5, 1)

    return FeeSchedule(
        jurisdiction="TW",
        issuing_body="Taiwan Intellectual Property Office",
        office_code="TIPO",
        right=RightType.trademark,
        currency="TWD",
        effective_date=effective,
        source_url=TIPO_TM_FEES_URL,
        statutory_basis=(
            "Trademark Act (商標法) and the Trademark Fee Standards published "
            "by TIPO under Article 104. Current schedule effective 2024-05-01."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "TIPO trademark fees are quoted per-class for application, "
            "registration, renewal, opposition, invalidation, and revocation. "
            "Multi-good surcharge applies over 20 designated goods in a single "
            "class (NT$200/good); Class 35 retail services surcharge applies "
            "over 5 designated services (NT$500/service). Source is a bilingual "
            "(zh-TW + EN) PDF; this scraper extracts the English side after "
            "stripping CJK characters and walking labelled NT$ amounts."
        ),
    )


__all__ = [
    "TIPO_BASE_URL",
    "TIPO_PATENT_FEES_URL",
    "TIPO_TM_FEES_URL",
    "TIPOFeesClient",
    "scrape_tipo_patents",
    "scrape_tipo_trademarks",
]
