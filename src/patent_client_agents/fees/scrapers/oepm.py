"""OEPM Spain fee-schedule scraper.

OEPM (Oficina Española de Patentes y Marcas) publishes a single
consolidated PDF — *"Tasas y Precios Públicos de la OEPM"* —
covering every fee surface (patents, utility models, SPCs, designs,
trademarks, trade names, semiconductor topographies, PCT national
phase, EP-validation, and *precios públicos*):

  https://www.oepm.es/export/sites/portal/comun/documentos_relacionados/PDF/TASAS_y_PRECIOS_PUBLICOS.pdf

Layout
------
The PDF stamps "Actualizado a fecha: 1 de abril de 2026" on page 1
(the file is re-published once per year after the *Ley de
Presupuestos Generales del Estado* takes effect on 1 January).

Each fee row in the dual-channel sections follows the shape::

    <description>  <PAPER_CODE>  <PAPER_AMOUNT>  <ELEC_CODE>  <ELEC_AMOUNT>

The second character of the code marks the filing channel:

* ``T`` — *trámite o pago no electrónicos* (paper) — full tariff
* ``E`` — *trámite y pago electrónicos* (electronic) — ~15% reduction

The first character (and sometimes the first two) marks the
applicant-tier × subject-matter bucket:

* ``IT/IE`` — Patents / utility models, **full rate**
* ``YT/YE`` — Patents / utility models, **PYMES / individual
  entrepreneur** (50% reduction on filing, search, exam)
* ``UT/UE`` — Patents / utility models, **public universities** (50%)
* ``MT/ME`` — Marcas / trade names (signos distintivos)
* ``DT/DE`` — Diseños industriales (industrial designs)
* ``ET`` — Publicación de traducción de patente europea (EP-validation
  in Spain) — paper-only on that section
* ``PT/PE`` — Prórroga de CCP (SPC extension)
* ``CM/CI`` — Tasas comunes (procedural — restablecimiento, recurso,
  modificaciones, oposiciones, …) shared across rights
* ``I3xx/I5xx`` — Tasas comunes for the *full-rate* patent table
  (same as CM/CI but indexed inside the patent section)
* ``I7xx/I8xx`` — Tasas comunes for the *universities* patent table
* ``BB`` — Agentes de la Propiedad Industrial registration fees
* ``CP`` — Certificados Complementarios de Protección (SPC) annuities

Annuities, multi-design renewal tables, and PCT international fees
ship as separate column structures and are out of v1 scope (see
"v1 GAPS" in the schedule notes).

Amount format
-------------
Spanish thousands/decimal convention: ``7.329,17`` means 7329.17
(``.`` thousands separator, ``,`` decimal mark). Same as
``inpi_br._parse_br_amount``.

The ``(*)`` marker that appears next to some electronic codes (e.g.
``ME17 (*) 82,84``) flags rows payable by credit/debit card per the
on-page footnote — NOT an SME-eligibility marker as one earlier
draft of the research note suggested. The connector does not lift it
into provenance because it is a payment-method affordance, not a
legal tariff dimension.

v1 scope
--------
* ``ES/OEPM/Fees/Patent`` — IT/IE (full-rate) + YT/YE (PYMES) +
  UT/UE (universities) + ET (EP-validation) + PT/PE (SPC prórroga) +
  I3/I5/I7/I8 (procedural) + CP (SPC annuities, year=N expanded)
* ``ES/OEPM/Fees/Trademark`` — MT/ME + CM/CI shared procedural
* ``ES/OEPM/Fees/Design`` — DT/DE + CM/CI shared procedural

v1 GAPS
* Patent annuities IP/2P/5P/IR/2R/5R/YP/Y2/Y5/UP/U2/U5 on page 6 ship
  as a multi-column year-band table (3-20 yr × 4 recargo bands ×
  4 applicant tiers) — needs a bespoke parser; not captured.
* Design renewal table on page 13 is also multi-column
  (DT41/DT42/DT43 × 4 quinquennial periods × 3 recargo bands) — not
  captured; periodic renewal fees DQR0/DQR1/DQR2 (single column) ARE
  captured.
* PCT international fees on pages 8-9 are single-column with prose
  amounts (e.g., "1.428,00" without a Clave code) — not captured.
* Precios públicos on pages 16-17 use a different code shape
  (``1.01``/``2.02``/…) and are out of v1 scope.

Statutory basis
---------------
* Ley 24/2015, de 24 de julio, de Patentes — Annex (patent / UM / SPC)
  · Art. 186 (PYMES / individual-entrepreneur / public-university 50%
  reduction)
* Ley 17/2001, de 7 de diciembre, de Marcas — Annex (TM fees)
* Ley 20/2003, de 7 de julio, de Protección Jurídica del Diseño
  Industrial (design fees)
* Year-over-year amounts adjusted by the annual *Ley de Presupuestos
  Generales del Estado*.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date
from decimal import Decimal
from typing import Unpack

import pypdf

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

OEPM_FEES_PDF_URL = (
    "https://www.oepm.es/export/sites/portal/comun/documentos_relacionados/"
    "PDF/TASAS_y_PRECIOS_PUBLICOS.pdf"
)
OEPM_FEES_LANDING_URL = "https://www.oepm.es/en/tasas-y-precios-publicos/"

# Per the page-1 stamp on the current PDF. Update when the connector
# is re-pointed at a new revision.
OEPM_EFFECTIVE_DATE = date(2026, 4, 1)


class OEPMFeesClient(BaseAsyncClient):
    """HTTP client for the OEPM consolidated fees PDF."""

    DEFAULT_BASE_URL = "https://www.oepm.es"
    CACHE_NAME = "oepm_fees"
    DEFAULT_TIMEOUT = 60.0
    DEFAULT_TTL_SECONDS = 7 * 24 * 3600
    HTTP2 = True

    def __init__(self, **kwargs: Unpack[FeeClientKwargs]) -> None:
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
                "Accept-Language": "es;q=0.9,en;q=0.8",
            },
        )
        super().__init__(**kwargs)

    async def fetch_pdf(self) -> bytes:
        r = await self._request(
            "GET",
            "/export/sites/portal/comun/documentos_relacionados/PDF/TASAS_y_PRECIOS_PUBLICOS.pdf",
            context="oepm_fees_pdf",
        )
        return r.content


# ──────────────────────────────────────────────────────────────────────
# PDF text + amount helpers
# ──────────────────────────────────────────────────────────────────────


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Whitespace-collapsed text of the consolidated TASAS PDF."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    parts = [page.extract_text() or "" for page in reader.pages]
    raw = "\n".join(parts)
    return re.sub(r"\s+", " ", raw).strip()


def _parse_es_amount(raw: str) -> Decimal | None:
    """Parse Spanish-format decimal '7.329,17' → Decimal('7329.17')."""
    if not raw:
        return None
    cleaned = raw.strip().replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except Exception:
        return None


# Code shapes seen in the PDF (page references in module docstring):
#   IT01 IE01 MT17 ME17 DT25 DE26 ET01 BB01 CM01 CI01 TC01 CP01
#   PT16 PE16 I301 I501 YT01 YE01 UT01 UE01
#   IP03 2P03 5P03 IR03 2R03 5R03 YP03 Y203 Y503 UP03 U203 U503
#   D235 D535 D625 D650 DQR0 DQR1 DQR2 CPR0 CPR1 CPR5
#   MX15 XM10 DX36 XD24 CX09 XC09 (multi-letter "PAGO MÁXIMO" codes)
_CODE_RE = re.compile(
    r"""
    (?<![A-Z0-9])
    (
        [A-Z]{2}\d{2,3}                  # IT01, ME17, BB01, ET01, CP01
      | [A-Z]\d[A-Z]\d{2}                # 5P03, 2R03 ← actually digit-letter-digit
      | \d[A-Z]\d{2,3}                   # 2P03, 5P03, 2R03, 5R03, 5R20
      | [A-Z]\d{3}                       # I301, I501, I701, I801, D235, D535, D625, D650
      | [A-Z]\d[A-Z]\d                   # not currently used
      | [A-Z]{3}\d                       # DQR0, DQR1, DQR2, CPR0, CPR1, CPR5
    )
    (?![A-Z0-9])
    """,
    re.VERBOSE,
)

# Spanish amount; rejects bare integers (the schedule always uses ,NN cents).
_AMOUNT_RE = re.compile(r"(?<![\w])(\d{1,3}(?:\.\d{3})*,\d{2})(?!\w)")

# A code immediately (possibly with an optional ``(*)``) followed by an
# amount. This catches the dual-channel row body without trying to
# match a description; the description is recovered from the preceding
# text window.
_CODE_AMOUNT_RE = re.compile(
    rf"{_CODE_RE.pattern}\s*(?:\(\*\))?\s+{_AMOUNT_RE.pattern}",
    re.VERBOSE,
)


# ──────────────────────────────────────────────────────────────────────
# Row extraction
# ──────────────────────────────────────────────────────────────────────


def _clean_description_window(window: str) -> str:
    """Strip column-header rubrics, interleaved bare amounts, and (*) markers."""
    # Strip "TRÁMITE Y PAGO ELECTRÓNICOS / NO ELECTRÓNICOS" rubrics.
    window = re.sub(
        r"TR[ÁA]MITE[^.]{0,40}?ELECTR[ÓO]NICOS?",
        " ",
        window,
        flags=re.IGNORECASE,
    )
    # Strip table header rows.
    window = re.sub(
        r"CONCEPTO\s+(?:Clave|CLAVE)\.?\s+(?:Importe|IMPORTE)\.?(?:\s+(?:Clave|CLAVE)\.?\s+(?:Importe|IMPORTE)\.?)?",
        " ",
        window,
    )
    window = re.sub(r"\(\*\)", " ", window)
    # pypdf often interleaves a row's amount cells *before* the row's code
    # cells, producing runs like "150,45 127,88 97,48 82,84 " just before
    # a code. Remove any leading/embedded amount-only streak (1-6 bare
    # amounts) so the description doesn't carry it.
    window = re.sub(r"(?:\s*\d{1,3}(?:\.\d{3})*,\d{2}\s*){1,6}", " ", window)
    # Section banners like "SIGNOS DISTINTIVOS." or "PATENTES Y MODELOS
    # DE UTILIDAD" that bleed into descriptions of the first row.
    window = re.sub(
        r"(?:SIGNOS DISTINTIVOS|PATENTES Y MODELOS DE UTILIDAD|"
        r"TASAS COMUNES|UNIVERSIDADES P[ÚU]BLICAS|"
        r"PRECIOS P[ÚU]BLICOS|TOPOGRAFIAS DE PRODUCTOS SEMICONDUCTORES|"
        r"DISE[ÑN]OS INDUSTRIALES|PATENTES EUROPEAS\.?\s*PUBLICACI[ÓO]N DE LA "
        r"TRADUCCI[ÓO]N EN ESPA[ÑN]A|CERTIFICADOS COMPLEMENTARIOS DE PROTECCI[ÓO]N"
        r"[^.]*?)\.?",
        " ",
        window,
        flags=re.IGNORECASE,
    )
    window = re.sub(r"Actualizado a fecha:[^.]+", " ", window)
    return re.sub(r"\s+", " ", window).strip(" -.,:;()*")


def _extract_pairs(text: str) -> list[tuple[str, Decimal, str]]:
    """Walk the collapsed PDF text and return (code, amount, desc) tuples.

    Description is the cleaned text between the previous match's end (or
    150 chars back, whichever is closer) and the current code's start.
    """
    rows: list[tuple[str, Decimal, str]] = []
    last_end = 0
    for m in _CODE_AMOUNT_RE.finditer(text):
        code = m.group(1)
        amount = _parse_es_amount(m.group(2))
        if amount is None:
            continue
        # Take at most 250 chars back, but never cross the previous
        # match boundary (so a description doesn't bleed into the
        # neighboring row's text).
        window_start = max(last_end, m.start() - 250)
        desc = _clean_description_window(text[window_start : m.start()])
        rows.append((code, amount, desc))
        last_end = m.end()
    return rows


def _dedupe_by_code(
    rows: list[tuple[str, Decimal, str]],
) -> list[tuple[str, Decimal, str]]:
    """Dedupe by code, preferring the entry with the most-informative description.

    The PDF intentionally repeats common procedural rows (I301-I309,
    CM01-CM09) inside every right-type section so each is
    self-contained. Pick the occurrence with the longest meaningful
    description so the catalog fallback has something to work with.
    """
    seen: dict[str, tuple[str, Decimal, str]] = {}
    for code, amount, desc in rows:
        cur = seen.get(code)
        if cur is None:
            seen[code] = (code, amount, desc)
            continue
        # Prefer the entry with a longer description that isn't just the
        # bare code (which happens when pypdf interleaves cells).
        cur_desc_len = len(cur[2]) if cur[2] and cur[2] != code else 0
        new_desc_len = len(desc) if desc and desc != code else 0
        if new_desc_len > cur_desc_len:
            seen[code] = (code, amount, desc)
    return list(seen.values())


# ──────────────────────────────────────────────────────────────────────
# Curated label + category catalog
# ──────────────────────────────────────────────────────────────────────
#
# Codes here come from the OEPM TASAS PDF cross-referenced against the
# ``research/national/es-oepm.md`` §4 synopsis. For codes not in the
# catalog we fall back to the regex-extracted description (best-effort)
# and ``FeeCategory.other``.
#
# Schema: ``code → (English label, FeeCategory)``. The label is the
# canonical English description; the Spanish text from the PDF goes
# into ``notes``.

_OEPM_CODE_CATALOG: dict[str, tuple[str, FeeCategory]] = {
    # ─── Marcas / signos distintivos (page 1) ──────────────────────
    "MT17": ("Trademark application — 1st class (paper)", FeeCategory.filing),
    "ME17": ("Trademark application — 1st class (electronic)", FeeCategory.filing),
    "MT18": ("Trademark application — 2nd+ class each (paper)", FeeCategory.excess_classes),
    "ME18": (
        "Trademark application — 2nd+ class each (electronic)",
        FeeCategory.excess_classes,
    ),
    "MT03": ("Trademark — international registration request (paper)", FeeCategory.filing),
    "ME06": (
        "Trademark — international registration request (electronic)",
        FeeCategory.filing,
    ),
    "MT05": ("Trademark — divisional application (paper)", FeeCategory.other),
    "ME03": ("Trademark — divisional application (electronic)", FeeCategory.other),
    "MT07": ("Trademark — priority claim (paper)", FeeCategory.other),
    "ME08": ("Trademark — priority claim (electronic)", FeeCategory.other),
    "MT08": ("Trademark — assignment / licence recordation (paper)", FeeCategory.transfer),
    "ME09": (
        "Trademark — assignment / licence recordation (electronic)",
        FeeCategory.transfer,
    ),
    "MT15": ("Trademark — class not paid with the application (paper)", FeeCategory.late_fee),
    "ME10": (
        "Trademark — class not paid with the application (electronic)",
        FeeCategory.late_fee,
    ),
    "MX15": ("Trademark — PAGO MÁXIMO cap (paper)", FeeCategory.other),
    "XM10": ("Trademark — PAGO MÁXIMO cap (electronic)", FeeCategory.other),
    "MT20": ("Trademark — certifications (paper)", FeeCategory.other),
    "ME11": ("Trademark — certifications (electronic)", FeeCategory.other),
    "MT25": (
        "Trademark — nullity or cancellation petition (paper)",
        FeeCategory.cancellation,
    ),
    "ME25": (
        "Trademark — nullity or cancellation petition (electronic)",
        FeeCategory.cancellation,
    ),
    "ME01": ("Trademark — opposition (electronic)", FeeCategory.opposition),
    "ME02": ("Trademark — opposition / per-claim (electronic)", FeeCategory.opposition),
    # ─── Tasas comunes (page 2) ────────────────────────────────────
    "CM01": ("Restoration of rights (paper)", FeeCategory.petition),
    "CI01": ("Restoration of rights (electronic)", FeeCategory.petition),
    "CM02": ("Appeal / request for review (paper)", FeeCategory.appeal),
    "CI02": ("Appeal / request for review (electronic)", FeeCategory.appeal),
    "CM03": ("Inspection of file / case (paper)", FeeCategory.other),
    "CM04": ("Copy of file documents (paper)", FeeCategory.other),
    "CM05": (
        "BOPI announcement — contentious-administrative appeal (paper)",
        FeeCategory.publication,
    ),
    "CI05": (
        "BOPI announcement — contentious-administrative appeal (electronic)",
        FeeCategory.publication,
    ),
    "CM06": (
        "BOPI announcement — ruling on contentious-administrative appeal (paper)",
        FeeCategory.publication,
    ),
    "CI06": (
        "BOPI announcement — ruling on contentious-administrative appeal (electronic)",
        FeeCategory.publication,
    ),
    "CM07": ("Modifications (paper)", FeeCategory.transfer),
    "CI07": ("Modifications (electronic)", FeeCategory.transfer),
    "CM08": ("Oppositions (paper)", FeeCategory.opposition),
    "CI08": ("Oppositions (electronic)", FeeCategory.opposition),
    "CM09": ("Change of name of holder (paper)", FeeCategory.transfer),
    "CI09": ("Change of name of holder (electronic)", FeeCategory.transfer),
    "CX09": ("Common — PAGO MÁXIMO cap (paper)", FeeCategory.other),
    "XC09": ("Common — PAGO MÁXIMO cap (electronic)", FeeCategory.other),
    # ─── Patentes y modelos de utilidad — full rate (page 3) ──────
    "IT01": ("Patent or utility model application filing (paper)", FeeCategory.filing),
    "IE01": ("Patent or utility model application filing (electronic)", FeeCategory.filing),
    "IT02": ("Change of protection modality (paper)", FeeCategory.other),
    "IE02": ("Change of protection modality (electronic)", FeeCategory.other),
    "IT03": ("Urgent resolution of a file (paper)", FeeCategory.extension),
    "IE03": ("Urgent resolution of a file (electronic)", FeeCategory.extension),
    "IT04": ("Search report (IET) request (paper)", FeeCategory.search),
    "IE04": ("Search report (IET) request (electronic)", FeeCategory.search),
    "IT05": ("Prior examination — pre-2017 cases (paper)", FeeCategory.examination),
    "IE05": ("Prior examination — pre-2017 cases (electronic)", FeeCategory.examination),
    "IT06": ("Priority claim — patents / UM (paper)", FeeCategory.other),
    "IE06": ("Priority claim — patents / UM (electronic)", FeeCategory.other),
    "IT08": ("Response to suspension for formal defects (paper)", FeeCategory.other),
    "IE08": ("Response to suspension for formal defects (electronic)", FeeCategory.other),
    "IT11": ("Licence of right offer (paper)", FeeCategory.transfer),
    "IE11": ("Licence of right offer (electronic)", FeeCategory.transfer),
    "IT13": ("Certification of registered data (paper)", FeeCategory.other),
    "IE13": ("Certification of registered data (electronic)", FeeCategory.other),
    "IT14": ("Semiconductor topography — registration application (paper)", FeeCategory.filing),
    "IE14": (
        "Semiconductor topography — registration application (electronic)",
        FeeCategory.filing,
    ),
    "IT15": ("Semiconductor topography — material deposit (paper)", FeeCategory.other),
    "IE15": (
        "Semiconductor topography — material deposit (electronic)",
        FeeCategory.other,
    ),
    "IT16": ("SPC — filing (paper)", FeeCategory.filing),
    "IE16": ("SPC — filing (electronic)", FeeCategory.filing),
    "IT20": ("Recordation of assignments / modifications (paper)", FeeCategory.transfer),
    "IE20": ("Recordation of assignments / modifications (electronic)", FeeCategory.transfer),
    "IT22": ("Substantive examination request (paper)", FeeCategory.examination),
    "IE22": ("Substantive examination request (electronic)", FeeCategory.examination),
    "IT23": ("Revocation or limitation request (paper)", FeeCategory.cancellation),
    "IE23": ("Revocation or limitation request (electronic)", FeeCategory.cancellation),
    "IT24": ("Expert report request (art. 120.7) (paper)", FeeCategory.other),
    "PT16": ("SPC — extension request (paper)", FeeCategory.extension),
    "PE16": ("SPC — extension request (electronic)", FeeCategory.extension),
    # ─── EP-validation in Spain (page 7) ───────────────────────────
    "ET01": (
        "EP-ES — claims publication (provisional protection) (paper)",
        FeeCategory.translation,
    ),
    "ET02": (
        "EP-ES — claims publication (provisional protection) (electronic)",
        FeeCategory.translation,
    ),
    "ET03": (
        "EP-ES — fascicle publication (definitive protection) — extra page (paper)",
        FeeCategory.translation,
    ),
    "ET04": (
        "EP-ES — fascicle publication (definitive protection) — extra page (electronic)",
        FeeCategory.translation,
    ),
    # ─── Designs (page 13) ─────────────────────────────────────────
    "DT25": ("Design — divisional (paper)", FeeCategory.other),
    "DE26": ("Design — divisional (electronic)", FeeCategory.other),
    "DT27": ("Design — priority or exhibition claim (paper)", FeeCategory.other),
    "DE27": ("Design — priority or exhibition claim (electronic)", FeeCategory.other),
    "DT36": ("Design — assignment / licence recordation (paper)", FeeCategory.transfer),
    "DE24": ("Design — assignment / licence recordation (electronic)", FeeCategory.transfer),
    "DX36": ("Design — PAGO REGISTRO MÁXIMO cap (paper)", FeeCategory.other),
    "XD24": ("Design — PAGO REGISTRO MÁXIMO cap (electronic)", FeeCategory.other),
    "DT38": ("Design — certifications (paper)", FeeCategory.other),
    "DE25": ("Design — certifications (electronic)", FeeCategory.other),
    # ─── Agentes (page 15) ─────────────────────────────────────────
    "BB01": ("Agent — Special Register inscription request", FeeCategory.other),
    "BB02": ("Agent — employee authorization", FeeCategory.other),
}


def _spc_annuity_label(code: str) -> str | None:
    """Synthesize a label for SPC annuity codes (CP01..CP55) not in the catalog."""
    year = _spc_year_for_code(code)
    if year is None:
        return None
    recargo = _spc_recargo_label(code)
    return f"SPC annuity — year {year} ({recargo})"


# ──────────────────────────────────────────────────────────────────────
# Code → (right bucket, tier, channel) classification
# ──────────────────────────────────────────────────────────────────────


# Per-prefix bucket — see module docstring for the section→prefix map.
# ``channel`` is "paper" when the code ends in a T-shaped letter (T/M/P
# on the 2nd char), "electronic" when it ends in E, "n/a" for codes
# that the PDF lists as single-channel (BB, CP, DQR, CPR, …).
def _classify_code(code: str) -> tuple[str, EntityTier, str]:
    """Map a fee code to ``(right_bucket, tier, channel)``.

    ``right_bucket`` is one of ``"patent" / "trademark" / "design" /
    "common"``. Common fees apply across multiple rights — callers
    decide whether to include them in a given schedule.
    """
    # Two-letter prefix coverers the bulk of the schedule.
    head2 = code[:2]
    # Patents / UM full-rate, dual-channel.
    if head2 == "IT":
        return ("patent", EntityTier.large, "paper")
    if head2 == "IE":
        return ("patent", EntityTier.large, "electronic")
    # Patents / UM PYMES (50% reduction on filing/search/exam under
    # Ley 24/2015 art. 186).
    if head2 == "YT":
        return ("patent", EntityTier.small, "paper")
    if head2 == "YE":
        return ("patent", EntityTier.small, "electronic")
    # Patents / UM public universities (also 50% reduction). We map to
    # small as well; the distinction lives in notes.
    if head2 == "UT":
        return ("patent", EntityTier.small, "paper")
    if head2 == "UE":
        return ("patent", EntityTier.small, "electronic")
    # EP-validation in Spain (translation publication).
    if head2 == "ET":
        # ET01 / ET03 are paper; ET02 / ET04 are electronic per the
        # page-7 column headings.
        ch = "electronic" if code in {"ET02", "ET04"} else "paper"
        return ("patent", EntityTier.large, ch)
    # SPC prórroga.
    if head2 == "PT":
        return ("patent", EntityTier.large, "paper")
    if head2 == "PE":
        return ("patent", EntityTier.large, "electronic")
    # SPC annuities + transitional codes (single-channel).
    if head2 == "CP":
        return ("patent", EntityTier.large, "n/a")
    # Procedural common — full-rate patent section.
    if code.startswith("I3"):
        return ("common", EntityTier.large, "paper")
    if code.startswith("I5"):
        return ("common", EntityTier.large, "electronic")
    # Procedural common — universities patent section.
    if code.startswith("I7"):
        return ("common", EntityTier.small, "paper")
    if code.startswith("I8"):
        return ("common", EntityTier.small, "electronic")
    # Tasas comunes that ship under their own page.
    if head2 == "CM":
        return ("common", EntityTier.large, "paper")
    if head2 == "CI":
        return ("common", EntityTier.large, "electronic")
    # Trademarks / signos distintivos.
    if head2 == "MT" or head2 == "MX":
        return ("trademark", EntityTier.large, "paper")
    if head2 == "ME" or head2 == "XM":
        return ("trademark", EntityTier.large, "electronic")
    # Designs.
    if head2 == "DT" or head2 == "DX":
        return ("design", EntityTier.large, "paper")
    if head2 == "DE" or head2 == "XD":
        return ("design", EntityTier.large, "electronic")
    # "PAGO MÁXIMO" caps on common procedural.
    if head2 == "CX":
        return ("common", EntityTier.large, "paper")
    if head2 == "XC":
        return ("common", EntityTier.large, "electronic")
    # Agentes de la Propiedad Industrial — TM / common channel.
    if head2 == "BB":
        return ("common", EntityTier.large, "n/a")
    # "Complemento de tasas" — libre (amount=0); we drop them via the
    # amount filter so they never reach _classify_code. Fall through.
    return ("common", EntityTier.large, "n/a")


# ──────────────────────────────────────────────────────────────────────
# Categorization (Spanish keyword → FeeCategory)
# ──────────────────────────────────────────────────────────────────────


def _categorize(code: str, desc: str) -> FeeCategory:
    d = desc.lower()
    # Annuities use IP/2P/5P/IR/2R/5R + reduced YP/Y2/Y5/UP/U2/U5
    # prefixes — out of v1 scope; we still tag with a category in case
    # later expansion brings them in.
    if code[:2] in {"IP", "2P", "5P", "IR", "2R", "5R", "YP", "UP"} or code[:2] in {
        "Y2",
        "Y5",
        "U2",
        "U5",
    }:
        return FeeCategory.renewal
    # SPC annuities (CP00, CP01..CP55) — see _build_spc_renewals which
    # also tags year. CPR* are prórroga annuities.
    if code.startswith("CP") or code.startswith("CPR"):
        return FeeCategory.renewal
    # Design quinquennial renewal codes.
    if code.startswith("DQR"):
        return FeeCategory.renewal
    if "renovaci" in d or "anualidad" in d or "mantenimiento" in d:
        return FeeCategory.renewal
    if "informe sobre el estado de la t" in d or "iet" in d:
        return FeeCategory.search
    if "examen sustantivo" in d or "examen previo" in d:
        return FeeCategory.examination
    if "concesi" in d:
        return FeeCategory.grant
    if "publicaci" in d or "anuncio bopi" in d:
        return FeeCategory.publication
    if "oposici" in d or "oposiciones" in d:
        return FeeCategory.opposition
    if "nulidad" in d or "caducidad" in d:
        return FeeCategory.cancellation
    if "recurso" in d or "revisi" in d:
        return FeeCategory.appeal
    if "restablecimiento" in d:
        return FeeCategory.petition
    if "modificaci" in d or "cambio de nombre" in d or "transmisi" in d or "cesi" in d:
        return FeeCategory.transfer
    if "licencia" in d:
        return FeeCategory.transfer
    if "prioridad" in d:
        return FeeCategory.other
    if "traducci" in d or "patente europea" in d:
        return FeeCategory.translation
    if "página adicional" in d or "pagina adicional" in d or "página que exceda" in d:
        return FeeCategory.excess_pages
    if "resolución urgente" in d or "resolucion urgente" in d:
        return FeeCategory.extension
    if "certificaci" in d or "copia" in d or "consulta" in d or "vista" in d:
        return FeeCategory.other
    if "demanda de dep" in d or "solicitud de marca" in d or "solicitud de registro" in d:
        return FeeCategory.filing
    if "solicitud" in d:
        return FeeCategory.filing
    if "complemento de tasas" in d:
        return FeeCategory.other
    return FeeCategory.other


# ──────────────────────────────────────────────────────────────────────
# SPC annuity year expansion
# ──────────────────────────────────────────────────────────────────────

# Page 10: SPC annuities are tabulated as
#   IGUAL O INFERIOR A 1 AÑO  CP01  CP21  CP51  (full / 25% / 50% recargo)
#   IGUAL O INFERIOR A 2 AÑOS CP02  CP22  CP52
#   ...
#   IGUAL O INFERIOR A 5 AÑOS CP05  CP25  CP55
# A separate "PRORROGA" track ships as CPR0/CPR1/CPR2/CPR5.

_SPC_ANNUITY_YEAR_RE = re.compile(r"^CP(\d{2})$")


def _spc_year_for_code(code: str) -> int | None:
    """Return the SPC year a CP-annuity code corresponds to.

    CP01..CP05 = year 1-5 (full rate). CP21..CP25 = same years, 25%
    recargo. CP51..CP55 = same years, 50% recargo. CP00 is
    transitional (pre-1.4.17 grant fee) and returns ``None``.
    """
    m = _SPC_ANNUITY_YEAR_RE.match(code)
    if not m:
        return None
    n = int(m.group(1))
    if n == 0:
        return None
    if 1 <= n <= 5:
        return n
    if 21 <= n <= 25:
        return n - 20
    if 51 <= n <= 55:
        return n - 50
    return None


def _spc_recargo_label(code: str) -> str:
    """Return a short label describing the SPC annuity recargo tier."""
    m = _SPC_ANNUITY_YEAR_RE.match(code)
    if not m:
        return ""
    n = int(m.group(1))
    if 1 <= n <= 5:
        return "without surcharge"
    if 21 <= n <= 25:
        return "25% surcharge"
    if 51 <= n <= 55:
        return "50% surcharge"
    return ""


# ──────────────────────────────────────────────────────────────────────
# FeeItem emit helper
# ──────────────────────────────────────────────────────────────────────


def _build_fee_item(
    *,
    code: str,
    desc: str,
    label: str,
    right: RightType,
    tier: EntityTier,
    channel: str,
    amount: Decimal,
    category: FeeCategory,
    year: int | None,
    extra_notes: str = "",
) -> FeeItem:
    condition: FeeCondition | None = None
    if channel == "paper":
        condition = FeeCondition(
            trigger="paper_filing",
            description="OEPM paper-filing (trámite no electrónico) variant.",
        )
    note_bits = [
        f"OEPM fee code {code}",
        f"channel: {channel}",
    ]
    if tier == EntityTier.small:
        note_bits.append(
            "PYMES / individual-entrepreneur / public-university 50% reduction "
            "under Ley 24/2015 art. 186"
        )
    if code.startswith("ET"):
        note_bits.append("validation_track: EP-ES (European patent translation publication)")
    if code.startswith("CP") or code.startswith("PT") or code.startswith("PE"):
        note_bits.append("subject: SPC (Certificado Complementario de Protección)")
    if desc and desc != code and desc != label:
        note_bits.append(f"PDF text: {desc[:160]}")
    if extra_notes:
        note_bits.append(extra_notes)
    notes = "; ".join(note_bits)
    return FeeItem(
        code=f"oepm-{code}",
        label=label[:200] if label else code,
        category=category,
        rights=[right],
        amount=amount,
        currency="EUR",
        tier=tier,
        year=year,
        condition=condition,
        source_url=OEPM_FEES_PDF_URL,
        notes=notes,
    )


# ──────────────────────────────────────────────────────────────────────
# Per-right schedule builders
# ──────────────────────────────────────────────────────────────────────


# Map a tier-variant code to its full-rate equivalent in _OEPM_CODE_CATALOG.
# YT/YE (PYMES) and UT/UE (universities) share the same fee structure
# as IT/IE — only the amount differs. I7/I8 (universities procedural)
# share the same structure as I3/I5. So the catalog lookup can be keyed
# off the full-rate equivalent.
def _catalog_key(code: str) -> str:
    """Normalize a code to its catalog key (full-rate equivalent if applicable)."""
    if len(code) >= 4:
        # YT01 → IT01, YE01 → IE01, UT01 → IT01, UE01 → IE01
        if code[0] in {"Y", "U"} and code[1] in {"T", "E"}:
            return "I" + code[1:]
        # I701 → I301, I801 → I501 (universities procedural ↔ full-rate)
        if code[0] == "I" and code[1] in {"7", "8"}:
            if code[1] == "7":
                return "I3" + code[2:]
            if code[1] == "8":
                return "I5" + code[2:]
    return code


def _label_and_category(code: str, desc: str) -> tuple[str, FeeCategory]:
    """Look up canonical label + category, falling back to description-mined category."""
    key = _catalog_key(code)
    entry = _OEPM_CODE_CATALOG.get(key) or _OEPM_CODE_CATALOG.get(code)
    if entry is not None:
        label, category = entry
        return label, category
    # SPC annuity codes (CP01..CP55) — synthesize a clean label.
    spc_label = _spc_annuity_label(code)
    if spc_label is not None:
        return spc_label, FeeCategory.renewal
    # Fall back to the regex-extracted description (if usable) + heuristic.
    label = desc if (desc and desc != code and len(desc) >= 4) else f"OEPM fee code {code}"
    return label[:200], _categorize(code, desc)


def _build_fees_for_right(
    text: str,
    right: RightType,
    *,
    accept_buckets: set[str],
) -> list[FeeItem]:
    """Emit FeeItems whose code maps into one of ``accept_buckets``.

    ``accept_buckets`` is a subset of ``{"patent", "trademark", "design",
    "common"}`` — the schedule's right pulls in its own bucket plus
    ``"common"`` for shared procedural codes.
    """
    pairs = _dedupe_by_code(_extract_pairs(text))
    fees: list[FeeItem] = []
    seen_emitted: set[str] = set()
    for code, amount, desc in pairs:
        bucket, tier, channel = _classify_code(code)
        if bucket not in accept_buckets:
            continue
        # Skip annuity codes — out of v1 scope (multi-column table on page 6).
        if code[:2] in {"IP", "2P", "5P", "IR", "2R", "5R", "YP", "Y2", "Y5", "UP", "U2", "U5"}:
            continue
        # Skip multi-design renewal codes (page 13 multi-col table).
        if code[:1] == "D" and code[1] in {"2", "5", "6"}:
            continue
        # Skip "I100" type sums (e.g., "5P03+I100") — these are concatenated
        # combos that should not be FeeItems on their own.
        if code == "I100" or code == "IP00":
            continue
        # Codes I101..I199 / I199 are part of the annuity table.
        if code.startswith("I1") and len(code) == 4 and code[2:].isdigit():
            continue
        label, category = _label_and_category(code, desc)
        year: int | None = None
        extra_notes = ""
        # SPC annuities — derive year from the code.
        if code.startswith("CP") and not code.startswith("CPR"):
            year = _spc_year_for_code(code)
            recargo = _spc_recargo_label(code)
            if recargo:
                extra_notes = f"SPC annuity {recargo}"
            if year is None:
                category = FeeCategory.other
        # If category needs a year but we don't have one, fall back to
        # 'other' to keep the schedule valid.
        if category in {FeeCategory.renewal, FeeCategory.maintenance} and year is None:
            category = FeeCategory.other
        # Build a stable internal code that distinguishes tier variants.
        emit_code = f"oepm-{code}"
        if emit_code in seen_emitted:
            continue
        seen_emitted.add(emit_code)
        fee = _build_fee_item(
            code=code,
            desc=desc,
            label=label,
            right=right,
            tier=tier,
            channel=channel,
            amount=amount,
            category=category,
            year=year,
            extra_notes=extra_notes,
        )
        fees.append(fee)
    return fees


# ──────────────────────────────────────────────────────────────────────
# Public scrapers
# ──────────────────────────────────────────────────────────────────────


_COMMON_NOTES = (
    "Scraped from OEPM's consolidated TASAS y PRECIOS PÚBLICOS PDF "
    "(670 KB / 17 pages, stamped 'Actualizado a fecha: 1 de abril de 2026'). "
    "Each fee row in the dual-channel sections emits one FeeItem; the "
    "2nd character of the code marks the filing channel (T = paper, "
    "E = electronic) and is also flagged on paper rows via "
    "FeeCondition(trigger=paper_filing). Applicant tier maps as "
    "follows: IT/IE/MT/ME/DT/DE/CM/CI/ET/CP/I3/I5 → EntityTier.large; "
    "YT/YE/UT/UE/I7/I8 → EntityTier.small (PYMES + public-university "
    "50% reduction under Ley 24/2015 art. 186). v1 GAPS: patent "
    "annuities (page 6 IP/2P/5P × IR/2R/5R × YP/Y2/Y5 × UP/U2/U5), "
    "design renewal table (page 13 DT41/D241/D541), PCT international "
    "fees (pages 8-9), and precios públicos (pages 16-17) ship as "
    "separate column structures and are not captured."
)


async def scrape_oepm_patents() -> FeeSchedule:
    """Scrape OEPM Spain patent + UM fee schedule (EUR, large + small tiers)."""
    async with OEPMFeesClient() as client:
        pdf_bytes = await client.fetch_pdf()
    text = _extract_pdf_text(pdf_bytes)
    fees = _build_fees_for_right(
        text,
        RightType.patent,
        accept_buckets={"patent", "common"},
    )
    if not fees:
        raise RuntimeError("OEPM patent scraper parsed zero rows — PDF structure may have changed")
    return FeeSchedule(
        jurisdiction="ES",
        issuing_body="Oficina Española de Patentes y Marcas (OEPM)",
        office_code="OEPM",
        right=RightType.patent,
        currency="EUR",
        effective_date=OEPM_EFFECTIVE_DATE,
        source_url=OEPM_FEES_PDF_URL,
        statutory_basis=(
            "Ley 24/2015 de Patentes (Annex) — art. 186 PYMES / "
            "entrepreneur / public-university 50% reduction; "
            "year-over-year amounts adjusted by the annual Ley de "
            "Presupuestos Generales del Estado."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=_COMMON_NOTES,
    )


async def scrape_oepm_trademarks() -> FeeSchedule:
    """Scrape OEPM Spain trademark / signos distintivos fee schedule (EUR)."""
    async with OEPMFeesClient() as client:
        pdf_bytes = await client.fetch_pdf()
    text = _extract_pdf_text(pdf_bytes)
    fees = _build_fees_for_right(
        text,
        RightType.trademark,
        accept_buckets={"trademark", "common"},
    )
    if not fees:
        raise RuntimeError(
            "OEPM trademark scraper parsed zero rows — PDF structure may have changed"
        )
    return FeeSchedule(
        jurisdiction="ES",
        issuing_body="Oficina Española de Patentes y Marcas (OEPM)",
        office_code="OEPM",
        right=RightType.trademark,
        currency="EUR",
        effective_date=OEPM_EFFECTIVE_DATE,
        source_url=OEPM_FEES_PDF_URL,
        statutory_basis=(
            "Ley 17/2001 de Marcas (Annex); year-over-year amounts "
            "adjusted by the annual Ley de Presupuestos Generales del Estado."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            f"{_COMMON_NOTES} "
            "Trademarks: per-class structure — first class on the MT17/ME17 "
            "row, each subsequent class on MT18/ME18 at the reduced "
            "sub-rate. PAGO MÁXIMO (MX15/XM10) caps the total payable on "
            "high-multi-class filings."
        ),
    )


async def scrape_oepm_designs() -> FeeSchedule:
    """Scrape OEPM Spain industrial-design fee schedule (EUR)."""
    async with OEPMFeesClient() as client:
        pdf_bytes = await client.fetch_pdf()
    text = _extract_pdf_text(pdf_bytes)
    fees = _build_fees_for_right(
        text,
        RightType.design,
        accept_buckets={"design", "common"},
    )
    if not fees:
        raise RuntimeError("OEPM design scraper parsed zero rows — PDF structure may have changed")
    return FeeSchedule(
        jurisdiction="ES",
        issuing_body="Oficina Española de Patentes y Marcas (OEPM)",
        office_code="OEPM",
        right=RightType.design,
        currency="EUR",
        effective_date=OEPM_EFFECTIVE_DATE,
        source_url=OEPM_FEES_PDF_URL,
        statutory_basis=(
            "Ley 20/2003 de Protección Jurídica del Diseño Industrial; "
            "year-over-year amounts adjusted by the annual Ley de "
            "Presupuestos Generales del Estado."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            f"{_COMMON_NOTES} "
            "Designs: multi-design discounts (de 11 a 20, 21 a 30, …) "
            "ship as bare amounts on the page-13 table — the code keys "
            "DT40/DE40 / DT41/DE41 / DT42/DE42 are listed at the bottom "
            "of the page and don't pair tightly enough with the amount "
            "cells for regex extraction. PAGO REGISTRO MÁXIMO "
            "(DX36/XD24) caps the total payable on large multi-design "
            "filings."
        ),
    )


__all__ = [
    "OEPM_FEES_PDF_URL",
    "OEPM_FEES_LANDING_URL",
    "OEPM_EFFECTIVE_DATE",
    "OEPMFeesClient",
    "scrape_oepm_patents",
    "scrape_oepm_trademarks",
    "scrape_oepm_designs",
]
