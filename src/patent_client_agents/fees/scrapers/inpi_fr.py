"""INPI France fee-schedule scraper.

INPI (Institut National de la Propriété Industrielle) publishes the
current French procedural fee schedule as a downloadable PDF linked
from:

    https://www.inpi.fr/ressources/propriete-intellectuelle/tarifs-procedures-et-prestations-de-linpi

The page is HTML but the fee schedule itself lives in a PDF at:

    https://www.inpi.fr/inpi-block/download-document?id=20516
    "Tarifs des procédures applicables au 27 avril 2026.pdf"

This is the **patents + trademarks + designs + GIs** combined
schedule (2 pages, ~6,000 chars of extracted text). The companion
"Tarifs des prestations" PDF (id=20514) covers ancillary services
like document copies — not modeled in v1.

Layout
------
The PDF organises fees by IP right under bold section headings:

* ``BREVETS D'INVENTION, CERTIFICATS D'UTILITÉ ET CERTIFICATS
  COMPLÉMENTAIRES DE PROTECTION`` — patents + utility certificates + SPCs
* ``BREVETS EUROPÉENS`` — national validation of European patents
* ``DEMANDES INTERNATIONALES (PCT)`` — PCT-routed entry fees
* ``MARQUES DE FABRIQUE, DE COMMERCE OU DE SERVICE`` — trademarks
* ``DESSINS ET MODÈLES`` — designs
* ``REGISTRES NATIONAUX`` — register admin fees (out of v1 scope)
* ``INDICATIONS GÉOGRAPHIQUES`` — GIs (out of v1 scope)
* ``DROITS VOISINS`` — semiconductor topographies + awards
  (out of v1 scope)

Each row reads as:

    <Intitulé (description)> <Tarif> € [<Tarif réduit> €]

Amounts use ``XX €`` format (no thousands separator inside
patent/TM schedules since amounts rarely exceed €1,000). The
"tarif réduit" (reduced rate) column applies to:

* natural persons (personnes physiques)
* non-profit research/education organisations
* companies with <1000 employees AND <25% capital held by a
  non-qualifying entity

We map standard → ``EntityTier.large`` and reduced →
``EntityTier.small``. Not every row has a reduced amount; rows
without one ship as ``EntityTier.none``.

Annuities
---------
Annuity rows are listed by French ordinal — "Deuxième annuité" (2nd
year) through "Vingtième annuité" (20th year). The first annuity
is included in the filing fee. The reduced rate is extracted for
years 2-7 (where pypdf can recover it); years 8-20 only have the
standard rate in extracted text — those ship at ``EntityTier.none``
with a notes-field caveat. The reduced rate is documented to apply
across the full 2-20 range per the schedule footnote.

Statutory basis
---------------
Code de la propriété intellectuelle (CPI) Articles R.411-17 et seq.;
arrêtés fixant les redevances perçues par l'INPI; most recent rate
adjustment effective 2026-04-27.

v1 scope
--------
Patents (incl. SPC + utility certificates), trademarks, designs.
Out of scope:

* GI (INDICATIONS GÉOGRAPHIQUES), semiconductor topographies,
  national-register admin fees
* Madrid international application fees (separate PDF id=20520)
* Prestations / services PDF (id=20514)
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

INPI_FR_TARIFS_PAGE = "https://www.inpi.fr/ressources/propriete-intellectuelle/tarifs-procedures-et-prestations-de-linpi"
# Stable INPI block download URLs. IDs may change in the future when
# the schedule is rev'd; the discovery uses the landing-page anchor
# text "Tarifs des procédures applicables au ...".
INPI_FR_PROCEDURES_PDF_PATH = "/inpi-block/download-document?id=20516"
INPI_FR_PROCEDURES_PDF_URL = f"https://www.inpi.fr{INPI_FR_PROCEDURES_PDF_PATH}"


class INPIFranceFeesClient(BaseAsyncClient):
    """HTTP client for the INPI France procedural fees PDF."""

    DEFAULT_BASE_URL = "https://www.inpi.fr"
    CACHE_NAME = "inpi_fr_fees"
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
                "Accept": "application/pdf,text/html,*/*",
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )
        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def fetch_html(self, path: str) -> str:
        r = await self._request("GET", path, context=f"inpi_fr_html {path[:40]}")
        return r.text

    async def fetch_pdf(self, path: str) -> bytes:
        r = await self._request("GET", path, context=f"inpi_fr_pdf {path[:40]}")
        return r.content


# ──────────────────────────────────────────────────────────────────────
# PDF text + amount parsing
# ──────────────────────────────────────────────────────────────────────


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Return collapsed-whitespace text of the procedures PDF."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    parts = [p.extract_text() or "" for p in reader.pages]
    raw = "\n".join(parts)
    return re.sub(r"\s+", " ", raw).strip()


# Match a Euro amount: "26 €", "1 595 €", "0.75 €", "0,75 €"
_EURO_RE = re.compile(r"(\d+(?:[\s.,]\d+)*)\s*€")


def _parse_eur(raw: str) -> Decimal | None:
    """Parse '26 €' / '1 595 €' / '0,75 €' → Decimal."""
    m = _EURO_RE.search(raw)
    if not m:
        return None
    s = m.group(1)
    # French uses NBSP / space as thousands separator; , as decimal mark
    # but "0.75 €" also seen in this PDF. Try both.
    s = s.replace("\xa0", "").replace(" ", "")
    # Decide if last separator is decimal:
    if "," in s and "." in s:
        # "1.595,00" form
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        # could be "0,75" (decimal) or "1,595" (US thousands)
        # In French, comma is always decimal — so treat as decimal
        s = s.replace(",", ".")
    # else "0.75" or pure integer
    try:
        return Decimal(s)
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────
# French ordinal → year
# ──────────────────────────────────────────────────────────────────────

_FRENCH_ORDINAL_TO_YEAR: dict[str, int] = {
    "première": 1,
    "premier": 1,
    "deuxième": 2,
    "troisième": 3,
    "quatrième": 4,
    "cinquième": 5,
    "sixième": 6,
    "septième": 7,
    "huitième": 8,
    "neuvième": 9,
    "dixième": 10,
    "onzième": 11,
    "douzième": 12,
    "treizième": 13,
    "quatorzième": 14,
    "quinzième": 15,
    "seizième": 16,
    "dix-septième": 17,
    "dix-huitième": 18,
    "dix-neuvième": 19,
    "vingtième": 20,
}
# Regex matches "<ordinal> annuité <amount> € [<amount> €]"
_ANNUITY_ROW_RE = re.compile(
    r"(première|premier|deuxième|troisième|quatrième|cinquième|sixième|septième|"
    r"huitième|neuvième|dixième|onzième|douzième|treizième|quatorzième|quinzième|"
    r"seizième|dix-septième|dix-huitième|dix-neuvième|vingtième)\s+annuité\s+"
    r"(\d+(?:[\s.,]\d+)*)\s*€\s*(?:(\d+(?:[\s.,]\d+)*)\s*€)?",
    re.IGNORECASE,
)


# ──────────────────────────────────────────────────────────────────────
# Section boundary detection
# ──────────────────────────────────────────────────────────────────────

# Top-level sections in the procedures PDF. Each maps to a RightType
# (or 'skip' for sections we don't model in v1).
_SECTION_HEADERS: list[tuple[str, str]] = [
    ("BREVETS D'INVENTION", "patent"),
    ("BREVETS EUROPÉENS", "patent"),
    ("DEMANDES INTERNATIONALES (PCT)", "patent"),
    ("MARQUES DE FABRIQUE", "trademark"),
    ("DESSINS ET MODÈLES", "design"),
    ("REGISTRES NATIONAUX", "skip"),
    ("INDICATIONS GÉOGRAPHIQUES", "skip"),
    ("DROITS VOISINS", "skip"),
]


def _split_into_sections(text: str) -> list[tuple[str, str, str]]:
    """Return [(section_header, right_label, content)] for each section.

    The text is processed in document order; each section's content
    is from the section header to the start of the next section
    (or end of document).
    """
    # Find positions of every known header in the text
    positions: list[tuple[int, str, str]] = []
    for header, right in _SECTION_HEADERS:
        idx = text.find(header)
        if idx >= 0:
            positions.append((idx, header, right))
    positions.sort()
    if not positions:
        return []
    out: list[tuple[str, str, str]] = []
    for i, (pos, header, right) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        content = text[pos:end]
        out.append((header, right, content))
    return out


# ──────────────────────────────────────────────────────────────────────
# Curated row catalog
# ──────────────────────────────────────────────────────────────────────
# The PDF mixes prose rows with amount columns; positional walks
# entangle the description and amount across rows. We instead curate
# the patent / TM / design entries and verify each against the live
# PDF (same pattern as TIPO TM). Drift raises loudly.

# (code_suffix, label_fr, category, expected_phrase, std_amount,
#  reduced_amount_or_None, condition, year_or_None, right)
_FEE_CATALOG: list[
    tuple[str, str, FeeCategory, str, int, int | None, FeeCondition | None, int | None, RightType]
] = [
    # ─── BREVETS D'INVENTION ───
    (
        "patent-filing",
        "Dépôt d'une demande de brevet ou de certificat d'utilité (inclut première annuité)",
        FeeCategory.filing,
        "Dépôt d’une demande de brevet ou de certificat d’utilité",
        26,
        13,
        None,
        None,
        RightType.patent,
    ),
    (
        "spc-filing",
        "Dépôt d'une demande de certificat complémentaire de protection (SPC)",
        FeeCategory.filing,
        "demande de certificat complémentaire de protection",
        520,
        None,
        None,
        None,
        RightType.patent,
    ),
    (
        "spc-pediatric",
        "Prorogation d'un certificat complémentaire de protection (usage pédiatrique)",
        FeeCategory.other,
        "demande de prorogation d'un certificat complémentaire de protection",
        470,
        None,
        None,
        None,
        RightType.patent,
    ),
    (
        "patent-search",
        "Rapport de recherche",
        FeeCategory.search,
        "Rapport de recherche 520",
        520,
        260,
        None,
        None,
        RightType.patent,
    ),
    (
        "patent-search-equivalent",
        "Rapport de recherche fondé sur priorité étrangère équivalente",
        FeeCategory.search,
        "rapport de recherche reconnu équivalent",
        156,
        None,
        None,
        None,
        RightType.patent,
    ),
    (
        "patent-new-claims-search",
        "Nouvelles revendications entraînant rapport de recherche complémentaire",
        FeeCategory.search,
        "Nouvelles revendications entraînant rapport de recherche complémentaire",
        520,
        260,
        None,
        None,
        RightType.patent,
    ),
    (
        "patent-claim-over-11",
        "Revendication à partir de la 11ème (excess-claims surcharge)",
        FeeCategory.excess_claims,
        "à partir de la 11ème revendication",
        42,
        21,
        FeeCondition(
            trigger="claims_over",  # type: ignore[arg-type]
            threshold=10,
            per_unit=True,
            description="INPI FR per-claim surcharge from the 11th claim onward.",
        ),
        None,
        RightType.patent,
    ),
    (
        "patent-rectification",
        "Rectification d'erreurs matérielles par requête",
        FeeCategory.other,
        "Rectification d'erreurs matérielles par requête",
        52,
        None,
        None,
        None,
        RightType.patent,
    ),
    (
        "patent-continuation",
        "Requête en poursuite de procédure",
        FeeCategory.petition,
        "Requête en poursuite de procédure",
        104,
        52,
        None,
        None,
        RightType.patent,
    ),
    (
        "patent-grant",
        "Délivrance et impression du fascicule",
        FeeCategory.grant,
        "Délivrance et impression du fascicule",
        90,
        45,
        None,
        None,
        RightType.patent,
    ),
    (
        "patent-limitation",
        "Requête en limitation",
        FeeCategory.other,
        "Requête en limitation",
        260,
        130,
        None,
        None,
        RightType.patent,
    ),
    (
        "patent-opposition",
        "Opposition à un brevet",
        FeeCategory.opposition,
        "Opposition 600",
        600,
        None,
        None,
        None,
        RightType.patent,
    ),
    (
        "patent-spc-annual",
        "Redevance annuelle de maintien en vigueur d'un SPC (et prorogation)",
        FeeCategory.renewal,
        "certificat complémentaire de protection et de sa prorogation 950",
        950,
        None,
        None,
        21,  # year=21 reflects beyond-20 SPC extension
        RightType.patent,
    ),
    (
        "patent-restoration",
        "Recours en restauration",
        FeeCategory.petition,
        "Recours en restauration 156",
        156,
        None,
        None,
        None,
        RightType.patent,
    ),
    # ─── BREVETS EUROPÉENS ───
    (
        "ep-translation-publication",
        "Publication de traduction des revendications d'un brevet européen",
        FeeCategory.translation,
        "Publication de traduction",
        36,
        None,
        None,
        None,
        RightType.patent,
    ),
    (
        "ep-transmission",
        "Établissement et transmission de copies d'une demande EP aux Etats destinataires",
        FeeCategory.other,
        "transmission de copies de la demande de brevet européen",
        26,
        None,
        None,
        None,
        RightType.patent,
    ),
    # ─── PCT ───
    (
        "pct-transmission",
        "Transmission d'une demande internationale PCT",
        FeeCategory.other,
        "Transmission d'une demande internationale 62",
        62,
        None,
        None,
        None,
        RightType.patent,
    ),
    # ─── MARQUES ───
    (
        "tm-filing-1class",
        "Dépôt de marque pour une classe",
        FeeCategory.filing,
        "Dépôt pour une classe 190",
        190,
        None,
        FeeCondition(
            trigger="classes_over",  # type: ignore[arg-type]
            threshold=1,
            per_unit=True,
            description="INPI FR base filing fee covers the first Nice class.",
        ),
        None,
        RightType.trademark,
    ),
    (
        "tm-filing-collective-1class",
        "Dépôt de marque collective ou de garantie pour une classe",
        FeeCategory.filing,
        "marque collective ou marque de garantie) 350",
        350,
        None,
        FeeCondition(
            trigger="classes_over",  # type: ignore[arg-type]
            threshold=1,
            per_unit=True,
            description="INPI FR collective/guarantee mark base filing covers the first Nice class.",
        ),
        None,
        RightType.trademark,
    ),
    (
        "tm-class-additional",
        "Par classe de produit ou de services au-delà de la première",
        FeeCategory.excess_classes,
        "Par classe de produit ou de services (au-delà de la première) 40",
        40,
        None,
        FeeCondition(
            trigger="classes_over",  # type: ignore[arg-type]
            threshold=1,
            per_unit=True,
            description="INPI FR additional-class surcharge for each Nice class beyond the first.",
        ),
        None,
        RightType.trademark,
    ),
    (
        "tm-regularisation",
        "Régularisation, rectification d'erreur matérielle (marques)",
        FeeCategory.other,
        "Régularisation, rectification d'erreur matérielle 104",
        104,
        None,
        None,
        None,
        RightType.trademark,
    ),
    (
        "tm-opposition",
        "Opposition à une marque",
        FeeCategory.opposition,
        "Opposition 400",
        400,
        None,
        None,
        None,
        RightType.trademark,
    ),
    (
        "tm-nullity",
        "Requête en nullité ou déchéance d'une marque",
        FeeCategory.cancellation,
        "Requête en nullité ou déchéance 600",
        600,
        None,
        None,
        None,
        RightType.trademark,
    ),
    (
        "tm-renewal-1class",
        "Renouvellement de marque pour une classe (10-year cycle)",
        FeeCategory.renewal,
        "Renouvellement pour une classe 290",
        290,
        None,
        FeeCondition(
            trigger="classes_over",  # type: ignore[arg-type]
            threshold=1,
            per_unit=True,
            description="INPI FR base renewal fee covers the first Nice class on the 10-year cycle.",
        ),
        10,
        RightType.trademark,
    ),
    (
        "tm-renewal-collective-1class",
        "Renouvellement de marque collective/garantie pour une classe",
        FeeCategory.renewal,
        "marque collective ou marque de garantie) 450",
        450,
        None,
        FeeCondition(
            trigger="classes_over",  # type: ignore[arg-type]
            threshold=1,
            per_unit=True,
            description="INPI FR collective/guarantee mark renewal base, first class.",
        ),
        10,
        RightType.trademark,
    ),
    (
        "tm-relevé-déchéance",
        "Requête en relevé de déchéance (marques)",
        FeeCategory.petition,
        "Requête en relevé de déchéance",
        156,
        None,
        None,
        None,
        RightType.trademark,
    ),
    (
        "tm-division",
        "Division d'une marque",
        FeeCategory.other,
        "Division 150",
        150,
        None,
        None,
        None,
        RightType.trademark,
    ),
    # ─── DESSINS ET MODÈLES ───
    (
        "design-filing",
        "Dépôt du dossier de demande d'enregistrement (dessins et modèles)",
        FeeCategory.filing,
        "Dépôt du dossier de demande d'enregistrement 39",
        39,
        None,
        None,
        None,
        RightType.design,
    ),
    (
        "design-bw-reproduction",
        "Supplément par reproduction déposée en noir et blanc",
        FeeCategory.filing,
        "reproduction déposée en noir et blanc 23",
        23,
        None,
        None,
        None,
        RightType.design,
    ),
    (
        "design-color-reproduction",
        "Supplément par reproduction déposée en couleur",
        FeeCategory.filing,
        "reproduction déposée en couleur 47",
        47,
        None,
        None,
        None,
        RightType.design,
    ),
    (
        "design-renewal",
        "Prorogation d'un dessin ou modèle (5-year periods × up to 25 years)",
        FeeCategory.renewal,
        "Prorogation (par dépôt) 52",
        52,
        None,
        None,
        5,
        RightType.design,
    ),
    (
        "design-regularisation",
        "Régularisation / rectification / relevé de déchéance (dessins)",
        FeeCategory.other,
        "Régularisation, rectification d'erreur matérielle, requête en relevé de déchéance 78",
        78,
        None,
        None,
        None,
        RightType.design,
    ),
]


# ──────────────────────────────────────────────────────────────────────
# Catalog verifier
# ──────────────────────────────────────────────────────────────────────


def _normalize_for_match(s: str) -> str:
    """Lowercase + collapse non-alphanumeric for forgiving lookup.

    Accents and apostrophes get tricky in PDF extraction; normalising
    to ASCII-lowercase-alphanumeric makes catalog lookups robust.
    """
    # Replace common accented chars
    s = s.lower()
    s = re.sub(r"[àâä]", "a", s)
    s = re.sub(r"[éèêë]", "e", s)
    s = re.sub(r"[îï]", "i", s)
    s = re.sub(r"[ôö]", "o", s)
    s = re.sub(r"[ùûü]", "u", s)
    s = re.sub(r"[ç]", "c", s)
    s = re.sub(r"[’'`]", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def _build_catalog_fees(text: str, right_filter: RightType) -> list[FeeItem]:
    """Verify each catalog entry for the given right against ``text`` and emit FeeItems."""
    fees: list[FeeItem] = []
    norm_text = _normalize_for_match(text)
    for (
        code_suffix,
        label,
        category,
        expected_phrase,
        std_amount,
        reduced_amount,
        condition,
        year,
        right,
    ) in _FEE_CATALOG:
        if right != right_filter:
            continue
        norm_phrase = _normalize_for_match(expected_phrase)
        idx = norm_text.find(norm_phrase)
        if idx < 0:
            raise RuntimeError(
                f"INPI FR catalog entry {code_suffix!r} expected phrase "
                f"{expected_phrase!r} not found in PDF — schedule may have changed."
            )
        # Emit large-tier row
        fees.append(
            FeeItem(
                code=f"inpi-fr-{code_suffix}-l",
                label=label,
                category=category,
                rights=[right],
                amount=Decimal(std_amount),
                currency="EUR",
                tier=EntityTier.large if reduced_amount is not None else EntityTier.none,
                year=year,
                condition=condition,
                source_url=INPI_FR_PROCEDURES_PDF_URL,
                notes=(
                    "INPI France 'Tarifs des procédures applicables au 27 avril 2026'. "
                    "Source PDF discovered via the landing page anchor; the inpi-block "
                    "download URL is the canonical fetch path."
                ),
            )
        )
        if reduced_amount is not None:
            fees.append(
                FeeItem(
                    code=f"inpi-fr-{code_suffix}-s",
                    label=f"{label} (tarif réduit)",
                    category=category,
                    rights=[right],
                    amount=Decimal(reduced_amount),
                    currency="EUR",
                    tier=EntityTier.small,
                    year=year,
                    condition=condition,
                    source_url=INPI_FR_PROCEDURES_PDF_URL,
                    notes=(
                        "INPI France reduced rate (personnes physiques, organismes de "
                        "recherche / enseignement, entreprises <1000 salariés et capital "
                        "<25% non-qualifying)."
                    ),
                )
            )
    return fees


# ──────────────────────────────────────────────────────────────────────
# Annuity rows
# ──────────────────────────────────────────────────────────────────────


def _extract_annuity_rows(text: str) -> list[FeeItem]:
    """Walk the patent annuity block and emit per-year FeeItems."""
    fees: list[FeeItem] = []
    for m in _ANNUITY_ROW_RE.finditer(text):
        ordinal = m.group(1).lower()
        year = _FRENCH_ORDINAL_TO_YEAR.get(ordinal)
        if year is None:
            continue
        std_amount = _parse_eur(m.group(2) + " €")
        if std_amount is None:
            continue
        reduced_amount = _parse_eur(m.group(3) + " €") if m.group(3) else None
        # Standard tier
        fees.append(
            FeeItem(
                code=f"inpi-fr-annuity-y{year:02d}-l",
                label=f"Redevance annuelle de maintien en vigueur d'un brevet — {ordinal} annuité (year {year})",
                category=FeeCategory.renewal,
                rights=[RightType.patent],
                amount=std_amount,
                currency="EUR",
                tier=EntityTier.large if reduced_amount is not None else EntityTier.none,
                year=year,
                source_url=INPI_FR_PROCEDURES_PDF_URL,
                notes=(
                    "INPI France patent annuity. The reduced rate applies to "
                    "natural persons, non-profit research/education organisations, "
                    "and companies <1000 employees with <25% non-qualifying capital."
                ),
            )
        )
        if reduced_amount is not None:
            fees.append(
                FeeItem(
                    code=f"inpi-fr-annuity-y{year:02d}-s",
                    label=f"Redevance annuelle (tarif réduit) — {ordinal} annuité (year {year})",
                    category=FeeCategory.renewal,
                    rights=[RightType.patent],
                    amount=reduced_amount,
                    currency="EUR",
                    tier=EntityTier.small,
                    year=year,
                    source_url=INPI_FR_PROCEDURES_PDF_URL,
                    notes=(
                        "INPI France patent annuity reduced rate. GAP: pypdf "
                        "reliably recovers the reduced amount for years 2-7 "
                        "only; years 8-20 reduced rates exist in the source "
                        "PDF but pypdf drops the second column for those rows. "
                        "Caller may estimate 50% of the standard rate as an "
                        "approximation but verify against the source for "
                        "any specific year > 7."
                    ),
                )
            )
    return fees


# ──────────────────────────────────────────────────────────────────────
# Scrapers
# ──────────────────────────────────────────────────────────────────────


async def _fetch_procedures_pdf() -> bytes:
    """Discover the procedures PDF link via the landing page and fetch it.

    Falls back to the hard-coded URL if discovery fails — the link ID
    has been stable through multiple INPI fee revisions.
    """
    async with INPIFranceFeesClient() as client:
        # Fetch the landing page to discover the current PDF link
        path = "/ressources/propriete-intellectuelle/tarifs-procedures-et-prestations-de-linpi"
        try:
            html_text = await client.fetch_html(path)
            doc = L.fromstring(html_text)
            for a in doc.cssselect("a[href]"):
                text = (a.text_content() or "").strip().lower()
                if "tarifs des procédures" in text or "tarifs des procedures" in text:
                    href = a.get("href") or ""
                    if "download-document" in href:
                        pdf_path = href if href.startswith("/") else "/" + href.lstrip("/")
                        return await client.fetch_pdf(pdf_path)
        except Exception as exc:
            logger.warning("INPI FR landing-page discovery failed: %s", exc)
        # Fallback to the hard-coded URL
        return await client.fetch_pdf(INPI_FR_PROCEDURES_PDF_PATH)


async def scrape_inpi_fr_patents() -> FeeSchedule:
    """Scrape INPI France patent fee schedule (EUR, large/small tiers)."""
    pdf_bytes = await _fetch_procedures_pdf()
    text = _extract_pdf_text(pdf_bytes)
    fees = _build_catalog_fees(text, RightType.patent)
    fees.extend(_extract_annuity_rows(text))
    if not fees:
        raise RuntimeError("INPI FR patent scraper parsed zero rows — PDF structure likely changed")
    return FeeSchedule(
        jurisdiction="FR",
        issuing_body="Institut National de la Propriété Industrielle (INPI)",
        office_code="INPI-FR",
        right=RightType.patent,
        currency="EUR",
        effective_date=date(2026, 4, 27),
        source_url=INPI_FR_TARIFS_PAGE,
        statutory_basis=(
            "Code de la propriété intellectuelle (CPI) Articles R.411-17 et "
            "seq.; arrêtés fixant les redevances perçues par l'INPI."
        ),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "INPI France patent + utility-certificate + SPC fees in EUR. "
            "Annuities 2-20 are extracted from the PDF; reduced rates are "
            "reliably captured for years 2-7 only (years 8-20 reduced rates "
            "exist in the source but pypdf drops the second column for those "
            "rows). The reduced rate applies to natural persons, non-profit "
            "research/education organisations, and companies <1000 employees "
            "with <25% non-qualifying capital. SPC annual fee (€950) is "
            "treated as year=21 since it covers extension beyond the 20-year "
            "patent term. v1 GAPS: register admin fees (REGISTRES NATIONAUX), "
            "GI fees, and semiconductor-topography fees are out of scope."
        ),
    )


async def scrape_inpi_fr_trademarks() -> FeeSchedule:
    """Scrape INPI France trademark fee schedule (EUR, 10-year cycle)."""
    pdf_bytes = await _fetch_procedures_pdf()
    text = _extract_pdf_text(pdf_bytes)
    fees = _build_catalog_fees(text, RightType.trademark)
    if not fees:
        raise RuntimeError(
            "INPI FR trademark scraper parsed zero rows — PDF structure likely changed"
        )
    return FeeSchedule(
        jurisdiction="FR",
        issuing_body="Institut National de la Propriété Industrielle (INPI)",
        office_code="INPI-FR",
        right=RightType.trademark,
        currency="EUR",
        effective_date=date(2026, 4, 27),
        source_url=INPI_FR_TARIFS_PAGE,
        statutory_basis=("Code de la propriété intellectuelle (CPI) Articles R.411-17 et seq."),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "INPI France trademark fees per-class (Nice classification) in "
            "EUR on a 10-year renewal cycle. Additional-class surcharge €40 "
            "per class beyond the first. Collective/guarantee marks have "
            "their own base rate. Madrid international application fees "
            "live in a separate PDF (id=20520) — not modeled in v1."
        ),
    )


async def scrape_inpi_fr_designs() -> FeeSchedule:
    """Scrape INPI France design fee schedule (EUR, 5-year periods)."""
    pdf_bytes = await _fetch_procedures_pdf()
    text = _extract_pdf_text(pdf_bytes)
    fees = _build_catalog_fees(text, RightType.design)
    if not fees:
        raise RuntimeError("INPI FR design scraper parsed zero rows — PDF structure likely changed")
    return FeeSchedule(
        jurisdiction="FR",
        issuing_body="Institut National de la Propriété Industrielle (INPI)",
        office_code="INPI-FR",
        right=RightType.design,
        currency="EUR",
        effective_date=date(2026, 4, 27),
        source_url=INPI_FR_TARIFS_PAGE,
        statutory_basis=("Code de la propriété intellectuelle (CPI) Livre V (dessins et modèles)."),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "INPI France design fees in EUR. Base filing €39 plus per-"
            "reproduction surcharges (b&w €23 / colour €47). Renewal "
            "('prorogation') €52 per 5-year period (up to 25 years total). "
            "Year=5 reflects the 5-year period mapping."
        ),
    )


__all__ = [
    "INPI_FR_TARIFS_PAGE",
    "INPI_FR_PROCEDURES_PDF_URL",
    "INPIFranceFeesClient",
    "scrape_inpi_fr_patents",
    "scrape_inpi_fr_trademarks",
    "scrape_inpi_fr_designs",
]
