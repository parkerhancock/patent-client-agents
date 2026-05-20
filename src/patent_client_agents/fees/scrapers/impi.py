"""IMPI Mexico fee-schedule scraper.

IMPI's *Acuerdo* tariff (Mexican Institute of Industrial Property) is
published as a single consolidated PDF on the gob.mx CMS attachment
endpoint:

  https://www.gob.mx/cms/uploads/attachment/file/824879/Acuerdo.Tarifa.12.05.23.pdf

22-page consolidated *"ACUERDO POR EL QUE SE DA A CONOCER LA TARIFA POR
LOS SERVICIOS QUE PRESTA EL INSTITUTO MEXICANO DE LA PROPIEDAD
INDUSTRIAL"* (Publicación original DOF: 23-08-1995, Última reforma
publicada DOF: 12-05-2023). The PDF parses with ``pypdf`` even though
every other ``*.impi.gob.mx`` host is geo-blocked from US egress — the
Akamai-fronted gob.mx CMS attachment endpoint sits on different
infrastructure than the IMPI register hosts.

Article structure
-----------------

Articles use a hierarchical code pattern: a base number (1-37) plus an
optional lowercase letter (a-j) plus an optional ``bis`` / ``BIS`` /
``ter`` / ``quáter`` suffix. Examples: ``1 a``, ``1 a bis``, ``9 e``,
``9 e bis``, ``14 a``, ``16 ter``, ``27 a BIS``, ``34 ter``.

The article-to-right mapping is:

* **Patents** — Articles 1-5 (filing, annuities, compulsory licence,
  rehabilitation, conversion).
* **Utility models, designs, integrated circuits** — Article 9 sub-
  letters mixed: 9a-9d UM filing/PCT, 9e-9e bis IC, 9f-9g design.
  Article 10 (UM/IC annuities), 11 (design renewal), 12 (UM+design+IC
  rehabilitation), 13 (general prosecution review).
* **Trademarks, commercial slogans, trade names** — Article 14 sub-
  letters covering filing, opposition, renewal, declaration of use,
  notorious-mark and famous-mark proceedings.
* **Denominations of origin & GIs** — Article 15 sub-letters.
* **General concepts** (apply to all rights) — Articles 16-34 covering
  enforcement, technical information, certified copies, priority
  recognition, extension of time, recordation of transfers / licenses.
* **PCT national-phase fees** — Article 35 (USD/CHF references to the
  WIPO PCT tariff; deferred from v1).
* **Madrid international TM fees** — Article 36 (CHF + MXN portions).
* **Hague international design fees** — Article 37 (CHF + MXN portions).

v1 emits three schedules: ``MX/IMPI/Fees/Patent``,
``MX/IMPI/Fees/Trademark``, ``MX/IMPI/Fees/Design``. Utility-model and
integrated-circuit rows from Article 9 are bundled into the patent
schedule under FeeCategory.filing with a notes annotation identifying
the sub-right. This matches the JPO and IPIN precedent (one schedule
per RightType, not one per sub-track).

Disposición Cuarta — small-entity 50% reduction
-----------------------------------------------

The Fourth General Provision of the *Acuerdo* grants a 50% fee
reduction to individual-inventor natural persons, micro/small
industries, public + private higher-education institutions, and
public scientific/technological research institutes — applied to
the per-row tariffs in Articles 1a through 1f, 2 through 13, 19
through 23, and 26 BIS. The connector emits each eligible row TWICE:
once as ``EntityTier.large`` at the published amount, once as
``EntityTier.small`` at 50% of the published amount.

Trademark fees (Article 14) are NOT eligible for the Cuarta
reduction.

Disposición Décima Primera — indigenous waiver
----------------------------------------------

Added by the [March 15, 2024 modifying *Acuerdo* (DOF
codigo=5720420)](https://www.dof.gob.mx/nota_detalle.php?codigo=5720420&fecha=15/03/2024).
Waives fees entirely for indigenous and Afro-Mexican peoples and
communities filing collective marks or certification marks tied to
geographic indications under LFPPI Art. 184. Covers services in Arts.
14a-14d and 15a / 15b / 15d. Documented in schedule notes but NOT
emitted as a separate FeeItem track — the FeeItem model has no
``indigenous_collective`` tier in the closed vocabulary, so consumers
needing this should apply the waiver out-of-band.

Amount format
-------------

Mexican peso (MXN) convention with US-style separators: ``$X,XXX.XX``
— comma thousands separator, period decimal mark. Unlike the OEPM
Spanish convention (``X.XXX,XX``), MX rows parse with a standard
``[\\d,]+\\.\\d{2}`` regex.

v1 GAPS
-------

* Article 35 PCT international-phase fees publish their amounts as
  USD/CHF references to the WIPO PCT tariff rather than fixed MXN
  values — not in v1 scope (would require WIPO tariff coupling).
* Article 36 Madrid + Article 37 Hague fees mix CHF (paid to WIPO)
  and MXN (paid to IMPI) portions; only the MXN portions emit in
  v1 (under the relevant RightType).
* Section-header rows (Article 1, Article 9, Article 14a as section
  openers) are skipped — they describe the group, not a per-row fee.
* April 2026 LFPPI reform (in force 2026-04-04) — no post-reform
  tariff *Acuerdo* has been published in DOF as of 2026-05-19, so
  the 2023 + March-2024 consolidated state remains binding. Worth
  re-checking quarterly.

Statutory basis
---------------

* Ley Federal de Protección a la Propiedad Industrial (LFPPI),
  DOF 2020-07-01 (codigo=5596010), in force 2021-11-05.
* Annual tariff issued under LFPPI by the Junta de Gobierno of
  IMPI with authorization of the Secretaría de Hacienda y Crédito
  Público; published in DOF on an as-needed basis.
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
    EntityTier,
    FeeCategory,
    FeeClientKwargs,
    FeeItem,
    FeeSchedule,
    RightType,
)

logger = logging.getLogger(__name__)


IMPI_FEES_PDF_URL = (
    "https://www.gob.mx/cms/uploads/attachment/file/824879/"
    "Acuerdo.Tarifa.12.05.23.pdf"
)
IMPI_LAST_REFORM_DATE = date(2023, 5, 12)
IMPI_MARCH_2024_AMENDMENT_URL = (
    "https://www.dof.gob.mx/nota_detalle.php?"
    "codigo=5720420&fecha=15/03/2024"
)


class IMPIFeesClient(BaseAsyncClient):
    """Tiny HTTP client for the gob.mx CMS attachment endpoint."""

    DEFAULT_BASE_URL = "https://www.gob.mx"
    CACHE_NAME = "impi_fees"
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
                    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/pdf,*/*",
            },
        )
        super().__init__(**kwargs)

    async def fetch_pdf(self) -> bytes:
        r = await self._request(
            "GET",
            "/cms/uploads/attachment/file/824879/Acuerdo.Tarifa.12.05.23.pdf",
            context="impi_acuerdo",
        )
        return r.content


# ──────────────────────────────────────────────────────────────────────
# PDF text extraction
# ──────────────────────────────────────────────────────────────────────


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(p.extract_text() or "" for p in reader.pages)


# ──────────────────────────────────────────────────────────────────────
# Row parsing
# ──────────────────────────────────────────────────────────────────────

# Find every ``$N,NNN.NN`` amount marker in the flattened text.
_AMOUNT_RE = re.compile(r"\$\s*([\d,]+\.\d{2})")

# An article code is a 1-3 digit base number, optionally followed by a
# lowercase letter (a-j), optionally followed by a bis / BIS / ter /
# quáter suffix. ``\b`` boundaries keep us out of mid-amount or
# mid-phone-number digits.
_CODE_RE = re.compile(
    r"(?<![\d\.,])"
    r"(\d{1,3}(?:\s+(?:[a-j](?:\s+(?:bis|BIS))?|BIS|bis|ter|quáter|TER))?)"
    r"\s+"
    r"([A-ZÁÉÍÓÚÑ¡¿])"  # description starts with a Spanish-uppercase letter
)

# Footer / header artifacts that show up next to phone-number digits
# in the flattened text — skip rows whose description contains any of
# these.
_FOOTER_MARKERS = (
    "Periférico Sur",
    "gob.mx/impi",
    "Ciudad de México, Teléfono",
)

# A row whose description ends in a colon or refers to a sub-group is
# a section opener, not a tariff line.
_SECTION_OPENER_MARKERS = (
    "se pagarán las siguientes tarifas",
    "se pagarán las siguientes",
)


def _parse_rows(text: str) -> list[tuple[str, str, Decimal]]:
    """Find every ``(code, description, amount)`` row in the flattened PDF text.

    Walks left-to-right through ``$N,NNN.NN`` amount markers and
    associates each one with the LAST preceding article code (whose
    description starts with a Spanish-uppercase letter). This handles
    pypdf's habit of concatenating multi-row tables onto one
    continuous line.
    """
    rows: list[tuple[str, str, Decimal]] = []
    cursor = 0
    for amt_match in _AMOUNT_RE.finditer(text):
        last_code_match = None
        for cm in _CODE_RE.finditer(text, cursor, amt_match.start()):
            last_code_match = cm
        if last_code_match is None:
            continue
        raw_code = re.sub(r"\s+", " ", last_code_match.group(1).strip())
        desc_start = last_code_match.start(2)
        desc = text[desc_start:amt_match.start()].strip()
        desc = re.sub(r"\s+", " ", desc).rstrip(";").rstrip()

        # Filter out footer artifacts (page-number + phone fragments).
        if any(marker in desc for marker in _FOOTER_MARKERS):
            cursor = amt_match.end()
            continue
        # Filter out section-opener rows.
        if any(marker.lower() in desc.lower() for marker in _SECTION_OPENER_MARKERS):
            cursor = amt_match.end()
            continue

        amount_str = amt_match.group(1).replace(",", "")
        try:
            amount = Decimal(amount_str)
        except Exception:
            cursor = amt_match.end()
            continue

        rows.append((raw_code, desc[:300], amount))
        cursor = amt_match.end()

    return rows


# ──────────────────────────────────────────────────────────────────────
# Article-to-right routing + small-entity eligibility
# ──────────────────────────────────────────────────────────────────────


_CUARTA_ELIGIBLE_BASES: frozenset[int] = frozenset(
    list(range(2, 14)) + [19, 20, 21, 22, 23]
)
# Article 1 is partially eligible: 1a-1f are Cuarta-eligible, 1g/1h
# (Certificado Complementario) and 1i/1j (PASE + explotación) are not
# per the LFPPI reform.
_CUARTA_ELIGIBLE_1_LETTERS: frozenset[str] = frozenset(["a", "b", "c", "d", "e", "f"])


def _code_base_letter(code: str) -> tuple[int, str | None, bool]:
    """Parse ``'1 a bis'`` → ``(1, 'a', True)``; ``'2'`` → ``(2, None, False)``."""
    parts = code.lower().split()
    if not parts:
        return (0, None, False)
    try:
        base = int(parts[0])
    except ValueError:
        return (0, None, False)
    letter = None
    bis = False
    for p in parts[1:]:
        if p in ("bis", "ter", "quáter"):
            bis = True
        elif len(p) == 1 and p.isalpha():
            letter = p
    return (base, letter, bis)


def _is_cuarta_eligible(code: str) -> bool:
    """Disposición Cuarta — 50% small-entity reduction."""
    base, letter, _bis = _code_base_letter(code)
    if base == 1:
        return letter in _CUARTA_ELIGIBLE_1_LETTERS
    if base == 26:
        return _bis  # only 26 BIS qualifies
    return base in _CUARTA_ELIGIBLE_BASES


def _route_for_code(code: str) -> str:
    """Map an article code to ``'patent'`` / ``'trademark'`` / ``'design'`` / ``'gi'`` / ``'general'`` / ``'intl'``.

    ``'general'`` covers procedural rows (Arts. 16-18 enforcement,
    19-23 technical info, 27-34 copies / priority / recordation) that
    fan out to every right. The per-right builders include them.
    """
    base, letter, _ = _code_base_letter(code)
    if base in (35, 36, 37):
        return "intl"  # PCT / Madrid / Hague — skip in v1
    if base in (1, 2, 3, 4, 5):
        return "patent"
    if base == 9:
        if letter in ("a", "b", "c", "d"):
            return "patent"  # utility model — bundled into patent schedule
        if letter == "e":
            return "patent"  # integrated circuit — bundled into patent schedule
        if letter in ("f", "g"):
            return "design"
        return "patent"
    if base == 10:
        return "patent"  # UM/IC annuities → bundled
    if base == 11:
        return "design"  # design renewal
    if base == 12:
        if letter == "b":
            return "design"
        return "patent"  # UM/IC rehabilitation
    if base == 13:
        return "general"  # general prosecution review — applies to all
    if base == 14:
        return "trademark"
    if base == 15:
        return "gi"  # denominations of origin / GIs — separate from TM
    # General / procedural — applies to every right.
    return "general"


# ──────────────────────────────────────────────────────────────────────
# Categorization
# ──────────────────────────────────────────────────────────────────────


def _categorize_row(code: str, description: str) -> tuple[FeeCategory, int | None]:
    """Return ``(category, year)``. ``year`` is set for renewal/maintenance rows."""
    base, letter, _ = _code_base_letter(code)
    d = description.lower()

    # Annuities — Article 2 (patents), Article 10 (UM/IC).
    if base == 2:
        return (FeeCategory.maintenance, _annuity_year_for_2(letter))
    if base == 10:
        return (FeeCategory.maintenance, _annuity_year_for_10(letter))
    # Design renewal — Article 11.
    if base == 11:
        return (FeeCategory.renewal, 5)
    # TM renewal — Article 14c.
    if base == 14 and letter == "c":
        return (FeeCategory.renewal, 10)

    if "rehabilitac" in d:
        return (FeeCategory.other, None)
    if "extens" in d or "prórroga" in d:
        return (FeeCategory.extension, None)
    if "oposición" in d or "oposicion" in d:
        return (FeeCategory.opposition, None)
    if "nulidad" in d or "caducidad" in d or "cancelación" in d or "cancelacion" in d:
        return (FeeCategory.cancellation, None)
    if "infracción" in d or "infraccion" in d:
        return (FeeCategory.other, None)
    if "publicación anticipada" in d or "publicacion anticipada" in d:
        return (FeeCategory.publication, None)
    if "expedición del título" in d or "expedicion del titulo" in d:
        return (FeeCategory.grant, None)
    if "presentación de una solicitud" in d or "presentacion de una solicitud" in d:
        return (FeeCategory.filing, None)
    if "fase nacional" in d:
        return (FeeCategory.filing, None)
    if "examen" in d:
        return (FeeCategory.examination, None)
    if "búsqueda" in d or "busqueda" in d:
        return (FeeCategory.search, None)
    if "transmis" in d or "licencia" in d or "gravamen" in d or "franquicia" in d:
        return (FeeCategory.transfer, None)
    if "copia" in d or "compulsa" in d:
        return (FeeCategory.other, None)
    if "prioridad" in d:
        return (FeeCategory.other, None)
    if "estudio de una solicitud" in d:
        return (FeeCategory.examination, None)
    if "registro de marca" in d or "estudio de una solicitud nacional" in d:
        return (FeeCategory.filing, None)
    if "declaración de uso" in d or "declaracion de uso" in d:
        return (FeeCategory.declaration_of_use, None)

    return (FeeCategory.other, None)


def _annuity_year_for_2(letter: str | None) -> int:
    """Article 2 patent annuity year-band → single representative year."""
    if letter == "a":
        return 1  # years 1-5 (representative: 1)
    if letter == "b":
        return 6  # years 6-10
    if letter == "c":
        return 11  # years 11-20
    return 1


def _annuity_year_for_10(letter: str | None) -> int:
    """Article 10 UM/IC annuity year-band → single representative year."""
    if letter == "a":
        return 1  # years 1-3
    if letter == "b":
        return 4  # years 4-6
    if letter == "c":
        return 7  # years 7+
    return 1


# ──────────────────────────────────────────────────────────────────────
# Builders
# ──────────────────────────────────────────────────────────────────────


def _slug(code: str) -> str:
    return re.sub(r"\s+", "-", code.lower())


def _emit_fees_for_rights(
    rows: list[tuple[str, str, Decimal]],
    target_route: str,
    target_right: RightType,
) -> list[FeeItem]:
    """Build FeeItems for one right type from the parsed row list.

    Includes rows tagged with ``target_route`` plus ``'general'`` rows
    that fan out to every right.
    """
    fees: list[FeeItem] = []
    seen_codes: set[str] = set()
    for code, description, amount in rows:
        route = _route_for_code(code)
        if route == "intl":
            continue
        if route not in (target_route, "general"):
            continue
        category, year = _categorize_row(code, description)
        slug = f"impi-{_slug(code)}"
        if slug in seen_codes:
            continue
        seen_codes.add(slug)

        fees.append(FeeItem(
            code=slug,
            label=description[:200],
            category=category,
            rights=[target_right],
            amount=amount,
            currency="MXN",
            tier=EntityTier.large,
            year=year,
            condition=None,
            source_url=IMPI_FEES_PDF_URL,
            notes=f"Article {code}.",
        ))

        if target_right is not RightType.trademark and _is_cuarta_eligible(code):
            # Disposición Cuarta — 50% reduction for individual
            # inventors, micro/small industries, universities and
            # public research institutes. Trademarks are NOT eligible.
            half = (amount / Decimal("2")).quantize(Decimal("0.01"))
            small_slug = f"{slug}-small"
            if small_slug not in seen_codes:
                seen_codes.add(small_slug)
                fees.append(FeeItem(
                    code=small_slug,
                    label=description[:200],
                    category=category,
                    rights=[target_right],
                    amount=half,
                    currency="MXN",
                    tier=EntityTier.small,
                    year=year,
                    condition=None,
                    source_url=IMPI_FEES_PDF_URL,
                    notes=(
                        f"Article {code}; 50% reduction under "
                        "Disposición Cuarta (individual inventors, "
                        "micro/small industry, universities, public "
                        "research institutes)."
                    ),
                ))

    return fees


# ──────────────────────────────────────────────────────────────────────
# Public scrape entry points
# ──────────────────────────────────────────────────────────────────────


_STATUTORY = (
    "Ley Federal de Protección a la Propiedad Industrial (LFPPI), "
    "DOF 2020-07-01 (codigo=5596010), in force 2021-11-05. "
    f"Tariff Acuerdo: original DOF 1995-08-23, last reform DOF "
    f"{IMPI_LAST_REFORM_DATE.isoformat()}; March 2024 indigenous-"
    f"waiver amendment at {IMPI_MARCH_2024_AMENDMENT_URL}."
)


async def scrape_impi_patents() -> FeeSchedule:
    """Scrape IMPI patent (+ utility model + IC) fees from the Acuerdo PDF."""
    async with IMPIFeesClient() as client:
        pdf_bytes = await client.fetch_pdf()
    text = _extract_pdf_text(pdf_bytes)
    rows = _parse_rows(text)
    fees = _emit_fees_for_rights(rows, "patent", RightType.patent)
    if not fees:
        raise RuntimeError(
            "IMPI patent scraper parsed zero rows — PDF structure may have changed"
        )
    return FeeSchedule(
        jurisdiction="MX",
        issuing_body="Instituto Mexicano de la Propiedad Industrial (IMPI)",
        office_code="IMPI",
        right=RightType.patent,
        currency="MXN",
        effective_date=IMPI_LAST_REFORM_DATE,
        source_url=IMPI_FEES_PDF_URL,
        statutory_basis=_STATUTORY,
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "Bundles utility-model (Art. 9a-9d, 10a-10b, 12a) and "
            "integrated-circuit-layout (Art. 9e, 9e bis, parts of 10) "
            "rows under RightType.patent — the FeeItem closed vocab "
            "doesn't have a separate sub-track and LFPPI treats them "
            "together. Disposición Cuarta 50% reduction emits as a "
            "duplicate FeeItem with EntityTier.small on every "
            "eligible row (Arts. 1a-1f, 2-13, 19-23, 26 BIS). "
            "Article 35 PCT international-phase fees skipped — they "
            "publish USD/CHF references to the WIPO tariff rather "
            "than fixed MXN values."
        ),
    )


async def scrape_impi_trademarks() -> FeeSchedule:
    """Scrape IMPI trademark (Article 14) fees from the Acuerdo PDF."""
    async with IMPIFeesClient() as client:
        pdf_bytes = await client.fetch_pdf()
    text = _extract_pdf_text(pdf_bytes)
    rows = _parse_rows(text)
    fees = _emit_fees_for_rights(rows, "trademark", RightType.trademark)
    if not fees:
        raise RuntimeError(
            "IMPI trademark scraper parsed zero rows — PDF structure may have changed"
        )
    return FeeSchedule(
        jurisdiction="MX",
        issuing_body="Instituto Mexicano de la Propiedad Industrial (IMPI)",
        office_code="IMPI",
        right=RightType.trademark,
        currency="MXN",
        effective_date=IMPI_LAST_REFORM_DATE,
        source_url=IMPI_FEES_PDF_URL,
        statutory_basis=_STATUTORY,
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "Article 14 sub-letters cover filing (14a), opposition "
            "(14b), renewal (14c, year=10 per Mexican TM term), "
            "declaration of use (14d), and notorious/famous-mark "
            "proceedings (14e-14j). TM fees are NOT eligible for the "
            "Disposición Cuarta 50% reduction. March 2024 "
            "indigenous-collective-mark fee waiver applies to Arts. "
            "14a-14d for indigenous + Afro-Mexican communities filing "
            "collective or certification marks tied to GIs — "
            "documented here but not emitted as a separate FeeItem "
            "track (the closed FeeItem vocab has no indigenous tier)."
        ),
    )


async def scrape_impi_designs() -> FeeSchedule:
    """Scrape IMPI industrial-design (Art. 9f/9g, 11, 12b) fees from the Acuerdo PDF."""
    async with IMPIFeesClient() as client:
        pdf_bytes = await client.fetch_pdf()
    text = _extract_pdf_text(pdf_bytes)
    rows = _parse_rows(text)
    fees = _emit_fees_for_rights(rows, "design", RightType.design)
    if not fees:
        raise RuntimeError(
            "IMPI design scraper parsed zero rows — PDF structure may have changed"
        )
    return FeeSchedule(
        jurisdiction="MX",
        issuing_body="Instituto Mexicano de la Propiedad Industrial (IMPI)",
        office_code="IMPI",
        right=RightType.design,
        currency="MXN",
        effective_date=IMPI_LAST_REFORM_DATE,
        source_url=IMPI_FEES_PDF_URL,
        statutory_basis=_STATUTORY,
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "Article 9f (filing), 9g (grant + first 5 years), 11 "
            "(renewal, 5-year periods), 12b (rehabilitation). "
            "Renewal FeeItems carry year=5 (each renewal covers one "
            "5-year period; LFPPI design term is 25 years total = "
            "initial 5 + four 5-year renewals). Disposición Cuarta "
            "50% reduction emits as a duplicate EntityTier.small "
            "FeeItem on every eligible row."
        ),
    )


__all__ = [
    "IMPI_FEES_PDF_URL",
    "IMPI_LAST_REFORM_DATE",
    "IMPI_MARCH_2024_AMENDMENT_URL",
    "IMPIFeesClient",
    "scrape_impi_patents",
    "scrape_impi_trademarks",
    "scrape_impi_designs",
]
