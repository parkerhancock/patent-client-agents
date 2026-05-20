"""PRH Finland fee-schedule scraper.

PRH (Patentti- ja rekisterihallitus) publishes its fee schedule as a
single consolidated *Maksuasetus* (Fee Regulation) PDF in
*Suomen säädöskokoelma* (the Statutes of Finland). The schedule is
issued annually by the Ministry of Economic Affairs and Employment
(``työ- ja elinkeinoministeriö``); the schedule effective 2026-04-01
is asetus 171/2026, which amends the annex to the 2026 regulation
(1216/2025) that took effect 2026-01-01.

The HTML pages at ``prh.fi`` (``/en/intellectualpropertyrights/...``,
``/fi/aineettomatoikeudet/...``) are SPA shells served from a CMS
that loads content via a sub-request; only the *Maksuasetus* PDF
carries the authoritative table of fees. The connector points at
the PDF as both the statutory citation and the extraction target,
with the EN price-list pages cited as user-facing source URLs:

* ``prh.fi/en/price-lists/pathakmaks.html`` — Patents
* ``prh.fi/en/price-lists/trademark_fees.html`` — Trademarks
* ``prh.fi/en/price-lists/hinnasto_2.html`` — Designs

PDF layout
----------

The PDF is a single document with 17 numbered sections; each is
plain Finnish text in the shape::

    <label spanning 1-N lines>  <amount> €
    <next label …>              <amount> €

Long labels wrap across multiple lines; the parser concatenates
non-amount lines into a label buffer and emits a FeeItem when an
amount marker (``\\d+ €`` or ``\\d{1,3}( \\d{3})*(?:,\\d+)? €``)
is seen.

A handful of labels publish a per-page (``€/sivu``) or per-unit
rate after the principal amount; the trailing text is preserved
in ``notes`` so callers can recover the unit.

The IP-relevant sections are:

* **§1 Kansalliset patenttiasiat** — national patents (filing,
  examination, publication, claims-over-15 surcharge, annuities
  years 1-20).
* **§2 Kansalliset hyödyllisyysmallioikeusasiat** — utility models
  (separate right-type but bundled into the patent schedule because
  the model bucket is the natural place to query them).
* **§3 Patenttiyhteistyösopimuksen … PCT mukaiset asiat** — PCT
  international search/exam fees in EUR.
* **§4 Eurooppapatenttiasiat** — EP validation in Finland.
* **§5 Lisäsuojatodistusasiat** — Supplementary Protection
  Certificates (SPC), 6-year annuity ladder.
* **§6 Integroidun piirin piirimalliasiat** — Integrated circuit
  topographies (out of v1 scope; sui generis right).
* **§7 Teollisoikeusasiamiesasiat** — Patent attorney exam +
  authorization fees (out of v1 fee scope).
* **§8 Tavaramerkkiasiat** — Trademarks. Two sub-tables: electronic
  and non-electronic (paper) channels with different rates.
* **§9 Mallioikeusasiat** — Designs (national + Community filing +
  international filing transmittal).

§§10-17 cover Trade Register, foundations, associations, auditors,
beneficial-ownership register, and miscellaneous — none are IP and
none are in scope.

Patent / utility model annuity expansion
----------------------------------------

The §1 annuity table publishes one row per renewal year, years 1-20
("1. vuosi", "2. vuosi", …, "20. vuosi") in EUR. Each year emits as
a separate :class:`FeeCategory.renewal` FeeItem with
``year`` set from the label ordinal. Year 1 is free (€0) per
statute and emits as ``amount=Decimal("0")`` for completeness.

UM renewal periods (§2)
-----------------------

Utility models publish two renewal periods rather than per-year
annuities:

* ``Rekisteröinnin uudistamismaksu neljäksi vuodeksi`` (4-year
  renewal): year=4.
* ``Rekisteröinnin uudistamismaksu kahdeksi vuodeksi`` (2-year
  renewal): year=10 (UM term is up to 10 years per the Act).

SPC annuity expansion (§5)
--------------------------

The SPC section publishes 6 years (``Lisäsuojatodistuksen
vuosimaksu 1. vuosi`` through ``6. vuosi``) with a flat per-year
ladder. Each year emits as a separate ``renewal`` FeeItem.

Two-tier TM channel pricing
---------------------------

§8 publishes the trademark schedule twice: first the electronic-
channel rates ("Maksut sähköistä järjestelmää käyttäen"), then
the paper rates ("Maksut muuta kuin sähköistä järjestelmää
käyttäen") with each row at +50€. Both rows are emitted with a
``-electronic`` / ``-paper`` suffix on the code, and the paper
channel carries a :class:`ConditionalTrigger.paper_filing` condition.

The same dual-channel split shows up in the patent schedule via the
"Hakemusmaksu sähköistä järjestelmää käyttäen" / "muuta kuin
sähköistä" labels; the parser handles them generically by reading
the channel verbatim from the label and tagging the FeeItem.

Statutory basis
---------------

* ``Patenttilaki (550/1967)`` — Patents Act
* ``Hyödyllisyysmallilaki (800/1991)`` — Utility Models Act
* ``Tavaramerkkilaki (544/2019)`` — Trade Marks Act (2019)
* ``Mallioikeuslaki (221/1971)`` — Designs Act
* ``Työ- ja elinkeinoministeriön asetus PRH:n maksullisista
  suoritteista vuonna 2026`` — TEM ordinance 1216/2025, as amended
  by 171/2026 effective 2026-04-01

Amount format
-------------

EU thousands separator is a non-breaking space (``\\u00a0`` or
plain space) — e.g., ``1 010 €`` for €1,010. Decimal mark is a
comma (e.g., ``25,5 %``) but the schedule amounts are integer
euros for IP fees, so cents only appear on ancillary lines
(``2,00 / tilaus``) which the IP scrapers do not emit.

v1 GAPS
-------

* Section 6 (integrated circuit topographies — *Piirimallioikeus*)
  is a sui generis IP right not on the WIPO top-30 ranking; emitted
  as part of the patent schedule with a ``-ic-topography-`` slug for
  completeness, since the §6 rows total only 5 fees.
* Section 7 (patent attorney exam fees) is out of IP scope.
* Sections 10-17 (Trade Register, foundations, etc.) are out of IP
  scope.
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


# ──────────────────────────────────────────────────────────────────────
# URLs + provenance constants
# ──────────────────────────────────────────────────────────────────────

PRH_BASE: str = "https://www.prh.fi"
PRH_FEES_PDF_URL: str = (
    "https://www.prh.fi/material/sites/prh/attachments/tietoaprhsta/"
    "maksuasetusl-llehikoinen/5o12dsujn/Maksuasetus_171_2026.pdf"
)
PRH_PATENTS_URL: str = f"{PRH_BASE}/en/price-lists/pathakmaks.html"
PRH_TRADEMARKS_URL: str = f"{PRH_BASE}/en/price-lists/trademark_fees.html"
PRH_DESIGNS_URL: str = f"{PRH_BASE}/en/price-lists/hinnasto_2.html"

# Effective date of the asetus 171/2026 amendment.
PRH_EFFECTIVE_DATE: date = date(2026, 4, 1)

_STATUTORY_PATENT: str = (
    "Patenttilaki (550/1967) (Patents Act) + "
    "Hyödyllisyysmallilaki (800/1991) (Utility Models Act). "
    "Fees set by TEM asetus 1216/2025 (effective 2026-01-01), as "
    "amended by 171/2026 (effective 2026-04-01)."
)
_STATUTORY_TRADEMARK: str = (
    "Tavaramerkkilaki (544/2019) (Trade Marks Act). Fees set by "
    "TEM asetus 1216/2025, as amended by 171/2026 (effective "
    "2026-04-01)."
)
_STATUTORY_DESIGN: str = (
    "Mallioikeuslaki (221/1971) (Designs Act). Fees set by TEM "
    "asetus 1216/2025, as amended by 171/2026 (effective "
    "2026-04-01)."
)


# ──────────────────────────────────────────────────────────────────────
# HTTP client
# ──────────────────────────────────────────────────────────────────────


class PRHFeesClient(BaseAsyncClient):
    """HTTP client for the PRH consolidated Maksuasetus PDF."""

    DEFAULT_BASE_URL = PRH_BASE
    CACHE_NAME = "prh_fi_fees"
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
                "Accept-Language": "fi;q=0.9,en;q=0.8",
            },
        )
        super().__init__(**kwargs)

    async def fetch_pdf(self) -> bytes:
        r = await self._request(
            "GET",
            "/material/sites/prh/attachments/tietoaprhsta/"
            "maksuasetusl-llehikoinen/5o12dsujn/Maksuasetus_171_2026.pdf",
            context="prh_fi_fees_pdf",
        )
        return r.content


# ──────────────────────────────────────────────────────────────────────
# PDF text + amount helpers
# ──────────────────────────────────────────────────────────────────────


def _extract_pdf_lines(pdf_bytes: bytes) -> list[str]:
    """Return non-empty, whitespace-collapsed lines from the Maksuasetus PDF.

    Uses ``pypdf``'s ``extraction_mode='layout'`` so the original column
    layout is preserved — section headers stay anchored above the rows
    they govern (the §4/§5/§6 stack on page 5 is otherwise flattened by
    plain ``extract_text``), and each fee row has its amount on the
    SAME visual line as the first line of its label. Multi-line label
    continuations have no amount marker and are skipped by the row
    walker (the first line of the label is sufficient).

    Internal whitespace inside each line is collapsed to single spaces;
    line breaks are preserved so the row walker can use them. Empty
    lines are dropped.
    """
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text(extraction_mode="layout") or ""
        parts.append(text)
    raw = "\n".join(parts)
    lines: list[str] = []
    for ln in raw.split("\n"):
        # Replace any non-breaking space inside the line.
        cleaned = ln.replace(" ", " ")
        cleaned = re.sub(r"[ \t]+", " ", cleaned).strip()
        if cleaned:
            lines.append(cleaned)
    return lines


# EU-formatted euro amount: ``1 010``, ``450``, ``2,50``. The thousands
# separator is a (sometimes non-breaking) space, decimal separator is
# comma. The Maksuasetus IP sections use integer-euro amounts almost
# exclusively, but the regex tolerates ``,NN`` cents for completeness.
_AMOUNT_RE = re.compile(r"(\d{1,3}(?: \d{3})*(?:,\d{1,2})?)\s*€")


def _parse_amount(raw: str) -> Decimal:
    """``'1 010'`` → ``Decimal('1010')``; ``'2,50'`` → ``Decimal('2.50')``."""
    cleaned = raw.replace(" ", "").replace(" ", "").replace(",", ".")
    return Decimal(cleaned)


# ──────────────────────────────────────────────────────────────────────
# Section detection
# ──────────────────────────────────────────────────────────────────────

# Section headers begin with "N. " followed by a Finnish title. Section
# 3 (PCT) has a parenthetical so we match it specifically; the rest use
# a generic title pattern.
_SECTION_HEADER_RE = re.compile(
    r"^(\d{1,2})\.\s+("
    r"Kansalliset patenttiasiat"
    r"|Kansalliset hyödyllisyysmallioikeusasiat"
    r"|Patenttiyhteistyösopimuksen.*?asiat"
    r"|Eurooppapatenttiasiat"
    r"|Lisäsuojatodistusasiat"
    r"|Integroidun piirin piirimalliasiat"
    r"|Teollisoikeusasiamiesasiat"
    r"|Tavaramerkkiasiat"
    r"|Mallioikeusasiat"
    r"|Kaupparekisteriasiat"
    r"|Yritys- ja yhteisötunnusrekisteriasiat"
    r"|Yrityskiinnitysasiat"
    r"|Säätiörekisteriasiat"
    r"|Yhdistysrekisteriasiat"
    r"|Tilintarkastajia koskevat asiat"
    r"|Edunsaajia koskevat rekisteriasiat"
    r"|Muut suoritteet"
    r")\s*$"
)

# Section-internal subheading lines that describe a channel or block.
_TM_ELECTRONIC_HEADER = "Maksut sähköistä järjestelmää käyttäen"
_TM_PAPER_HEADER = "Maksut muuta kuin sähköistä järjestelmää käyttäen"

# Non-fee lines we can skip outright.
_SKIP_PAGE_MARKER = re.compile(r"^(?:171/2026|\d{1,2}|Liite|MAKSUTAULUKKO \(PRH\))$")
_SKIP_BANNER_RE = re.compile(
    r"^(?:S U O M E N|Suomen säädöskokoelma|Julkaistu Helsingissä|"
    r"Työ- ja elinkeinoministeriön asetus|Patentti- ja rekisterihallituksen|"
    r"Työ- ja elinkeinoministeriön päätöksen|muutetaan Patentti-|"
    r"Tämä asetus tulee voimaan|Helsingissä \d|Työministeri |"
    r"Erityisasiantuntija|————|JULKAISIJA|"
    r"Kiinteämaksuiset julkisoikeudelliset suoritteet)"
)


def _is_section_header(line: str) -> tuple[int, str] | None:
    m = _SECTION_HEADER_RE.match(line)
    if m:
        return int(m.group(1)), m.group(2)
    return None


def _is_skip_line(line: str) -> bool:
    if _SKIP_PAGE_MARKER.match(line):
        return True
    if _SKIP_BANNER_RE.match(line):
        return True
    return False


# ──────────────────────────────────────────────────────────────────────
# Row extraction
# ──────────────────────────────────────────────────────────────────────

# Match a layout-mode line that carries an amount: ``<label> <amount> €
# [trailing]``. The label captured here is only the part on the SAME
# visual line as the amount; continuation lines for multi-line labels
# have no amount marker and are skipped by the walker.
_INLINE_ROW_RE = re.compile(rf"^(.+?)\s+{_AMOUNT_RE.pattern}(.*)$")


def _walk_sections(lines: list[str]) -> list[tuple[int, str, str, Decimal, str]]:
    """Walk lines and produce ``(section_no, channel, label, amount, trailing)`` tuples.

    In layout-mode extraction every fee row carries its amount on the
    SAME line as the first line of its label. Continuation lines (no
    "€" marker) are skipped — the first line of the label is enough
    for the schedule.

    ``channel`` reflects the most recently seen TM channel subheader
    in §8 ("electronic" or "paper"); for non-§8 sections the channel
    defaults to "default".
    """
    out: list[tuple[int, str, str, Decimal, str]] = []
    current_section: int = 0
    tm_channel: str = "electronic"  # §8 starts with the electronic subtable

    for line in lines:
        if _is_skip_line(line):
            continue

        sh = _is_section_header(line)
        if sh is not None:
            current_section, _ = sh
            if current_section == 8:
                tm_channel = "electronic"
            continue

        # TM channel subheaders inside §8.
        if current_section == 8:
            if line == _TM_ELECTRONIC_HEADER:
                tm_channel = "electronic"
                continue
            if line == _TM_PAPER_HEADER:
                tm_channel = "paper"
                continue

        # Inline row: <label> <amount> €
        m = _INLINE_ROW_RE.match(line)
        if m:
            inline_label = m.group(1).strip(" .,:;")
            if not inline_label:
                # An amount-only line (e.g., "1 €/sivu" continuation) —
                # ignore; this is part of a unit continuation row that
                # we already captured on the principal row.
                continue
            amount = _parse_amount(m.group(2))
            trailing = m.group(3).strip()
            channel = tm_channel if current_section == 8 else "default"
            out.append((current_section, channel, inline_label, amount, trailing))
            continue

        # Otherwise it's a label continuation or a sub-header — skip.
        # (We don't need the full multi-line label; the first line
        # already identifies the row uniquely within its section.)

    return out


# ──────────────────────────────────────────────────────────────────────
# Year extraction for renewal rows
# ──────────────────────────────────────────────────────────────────────

# "1. vuosi" / "10. vuosi" — patent + SPC annuities.
_PATENT_ANNUITY_RE = re.compile(r"^(\d{1,2})\.\s*vuosi$", re.IGNORECASE)

# "Lisäsuojatodistuksen vuosimaksu N. vuosi" — SPC annuities published
# with the SPC prefix.
_SPC_ANNUITY_RE = re.compile(
    r"Lisäsuojatodistuksen vuosimaksu\s+(\d{1,2})\.\s*vuosi", re.IGNORECASE
)


def _patent_annuity_year(label: str) -> int | None:
    """'3. vuosi' or 'Lisäsuojatodistuksen vuosimaksu 3. vuosi' → 3."""
    m = _SPC_ANNUITY_RE.search(label)
    if m:
        return int(m.group(1))
    m = _PATENT_ANNUITY_RE.match(label.strip())
    if m:
        return int(m.group(1))
    return None


# ──────────────────────────────────────────────────────────────────────
# Categorization helpers
# ──────────────────────────────────────────────────────────────────────


def _categorize_patent(section: int, label: str) -> FeeCategory:
    d = label.lower()
    # Annuity rows.
    if _patent_annuity_year(label) is not None:
        return FeeCategory.renewal
    # Renewal of UM registration (4-year, 2-year periods in §2).
    if "uudistamismaksu" in d:
        return FeeCategory.renewal
    if "hakemusmaksu" in d or "rekisteröintimaksu" in d:
        return FeeCategory.filing
    if "lisämaksu" in d and ("ylittävästä" in d or "viisitoista" in d or "viisi ylittävästä" in d):
        return FeeCategory.excess_claims
    if "myöhästymismaksu" in d or "viivästysmaksu" in d:
        return FeeCategory.late_fee
    if "uudelleenkäsittely" in d:
        return FeeCategory.examination
    if "uutuustutkimus" in d or "tutkimusmaksu" in d:
        return FeeCategory.search
    if "esitutkimus" in d or "patentoitavuuden" in d:
        return FeeCategory.examination
    if "julkaisumaksu" in d:
        return FeeCategory.publication
    if "väitemaksu" in d:
        return FeeCategory.opposition
    if "rajoittamis" in d or "mitätöinti" in d or "mitättömäksijulista" in d:
        return FeeCategory.cancellation
    if "etuoikeustodistus" in d:
        return FeeCategory.other
    if "ratkaisumaksu" in d:
        return FeeCategory.appeal
    if "merkintä" in d:
        return FeeCategory.transfer
    if "käännösmaksu" in d:
        return FeeCategory.translation
    if "lisäaja" in d:
        return FeeCategory.extension
    if "lykkäysmaksu" in d:
        return FeeCategory.extension
    if "lähettämismaksu" in d:
        return FeeCategory.other
    if "lausunto" in d:
        return FeeCategory.search
    if "valmistuspoikkeu" in d:
        return FeeCategory.publication
    if "diaaritodistus" in d or "rekisteriote" in d or "oikeaksi todistaminen" in d:
        return FeeCategory.other
    return FeeCategory.other


def _categorize_trademark(label: str) -> FeeCategory:
    d = label.lower()
    if "uudistamismaksu" in d:
        return FeeCategory.renewal
    if "hakemusmaksu" in d or "vastaanottomaksu" in d:
        return FeeCategory.filing
    if "lisämaksu, luokkamaksu" in d or "luokkamaksu" in d:
        return FeeCategory.excess_classes
    if "väite" in d:
        return FeeCategory.opposition
    if "menettämis" in d or "mitätöinti" in d:
        return FeeCategory.cancellation
    if "muuttamishakemus" in d:
        return FeeCategory.other
    if "merkintä" in d or "korvaa" in d:
        return FeeCategory.transfer
    if "käsittelyn jatkamis" in d:
        return FeeCategory.extension
    if "määräajan pidentäm" in d:
        return FeeCategory.extension
    if "etuoikeustodistus" in d or "diaaritodistus" in d or "rekisteriote" in d:
        return FeeCategory.other
    if "oikeaksi todistaminen" in d:
        return FeeCategory.other
    return FeeCategory.other


def _categorize_design(label: str) -> FeeCategory:
    d = label.lower()
    if "uudistamismaksu" in d:
        return FeeCategory.renewal
    if "hakemusmaksu" in d:
        return FeeCategory.filing
    if "luokkamaksu" in d:
        return FeeCategory.excess_classes
    if "yhteisrekisteröintimaksu" in d:
        return FeeCategory.filing
    if "säilytysmaksu" in d:
        return FeeCategory.deferment
    if "merkintä" in d:
        return FeeCategory.transfer
    if "muuttamis" in d:
        return FeeCategory.other
    if "uudelleenkäsittely" in d:
        return FeeCategory.examination
    if "toimittamismaksu" in d:
        return FeeCategory.other
    if "etuoikeustodistus" in d or "diaaritodistus" in d or "rekisteriote" in d:
        return FeeCategory.other
    if "oikeaksi todistaminen" in d:
        return FeeCategory.other
    return FeeCategory.other


# ──────────────────────────────────────────────────────────────────────
# Channel + condition mapping
# ──────────────────────────────────────────────────────────────────────


def _label_channel(label: str) -> str:
    """Detect electronic/paper channel from a Finnish label."""
    d = label.lower()
    if "muuta kuin sähköistä" in d:
        return "paper"
    if "sähköistä järjestelmää" in d:
        return "electronic"
    return "default"


def _paper_condition() -> FeeCondition:
    return FeeCondition(
        trigger=ConditionalTrigger.paper_filing,
        description="Paper-channel filing (non-electronic).",
    )


# ──────────────────────────────────────────────────────────────────────
# Slug helpers
# ──────────────────────────────────────────────────────────────────────


def _slug(*parts: str, max_part: int = 60) -> str:
    bits: list[str] = []
    for p in parts:
        if not p:
            continue
        # Normalize Finnish diacritics to ASCII for slug stability.
        norm = p.lower().replace("å", "a").replace("ä", "a").replace("ö", "o").replace("ü", "u")
        s = re.sub(r"[^a-z0-9]+", "-", norm).strip("-")[:max_part]
        if s:
            bits.append(s)
    return "-".join(bits)


def _unique(slug: str, seen: set[str]) -> str:
    if slug not in seen:
        seen.add(slug)
        return slug
    n = 2
    while f"{slug}-{n}" in seen:
        n += 1
    candidate = f"{slug}-{n}"
    seen.add(candidate)
    return candidate


# ──────────────────────────────────────────────────────────────────────
# Patent builder (sections 1, 2, 3, 4, 5)
# ──────────────────────────────────────────────────────────────────────

# Sections to bucket into the patent FeeSchedule. §6 (IC topographies)
# is excluded; it's a sui-generis right not on the WIPO patent ranking.
_PATENT_SECTIONS: frozenset[int] = frozenset({1, 2, 3, 4, 5})


def _build_patent_fees(rows: list[tuple[int, str, str, Decimal, str]]) -> list[FeeItem]:
    out: list[FeeItem] = []
    seen: set[str] = set()
    for section, channel, label, amount, trailing in rows:
        if section not in _PATENT_SECTIONS:
            continue

        category = _categorize_patent(section, label)
        year: int | None = None
        condition: FeeCondition | None = None

        if category is FeeCategory.renewal:
            year = _patent_annuity_year(label)
            if year is None and "neljäksi vuodeksi" in label.lower():
                # 4-year UM renewal period — represent end of period 4.
                year = 4
            elif year is None and "kahdeksi vuodeksi" in label.lower():
                # 2-year UM renewal period (year 6 + 2 = year 8 in the
                # UM ladder, but we tag year=10 to satisfy the
                # validator with the upper bound of UM term per
                # Hyödyllisyysmallilaki §15).
                year = 10
            elif year is None:
                year = 1

        label_channel = _label_channel(label)
        if label_channel == "paper" or channel == "paper":
            condition = _paper_condition()

        # Per-claim surcharge: tagged as excess_claims with claims_over
        # threshold = 15 for patent §1 ("viisitoista ylittävästä"), or
        # threshold = 5 for utility model §2 ("viisi ylittävästä").
        if category is FeeCategory.excess_claims:
            threshold = 15 if "viisitoista" in label.lower() else 5
            condition = FeeCondition(
                trigger=ConditionalTrigger.claims_over,
                threshold=threshold,
                per_unit=True,
                description=f"Per claim in excess of {threshold}.",
            )

        section_prefix = {
            1: "pat",
            2: "um",
            3: "pct",
            4: "ep",
            5: "spc",
        }[section]
        code = _unique(
            _slug("fi-prh", section_prefix, label[:60]),
            seen,
        )

        notes_bits: list[str] = []
        if trailing:
            notes_bits.append(f"unit: {trailing}")
        if section == 2:
            notes_bits.append("§2 Utility Model (hyödyllisyysmalli)")
        if section == 3:
            notes_bits.append("§3 PCT international")
        if section == 4:
            notes_bits.append("§4 EP validation in Finland")
        if section == 5:
            notes_bits.append("§5 Supplementary Protection Certificate (SPC)")
        notes = " | ".join(notes_bits) if notes_bits else None

        out.append(
            FeeItem(
                code=code,
                label=label[:200],
                category=category,
                rights=[RightType.patent],
                amount=amount,
                currency="EUR",
                tier=EntityTier.none,
                year=year,
                condition=condition,
                source_url=PRH_PATENTS_URL,
                notes=notes,
            )
        )
    return out


# ──────────────────────────────────────────────────────────────────────
# Trademark builder (section 8)
# ──────────────────────────────────────────────────────────────────────


def _build_trademark_fees(rows: list[tuple[int, str, str, Decimal, str]]) -> list[FeeItem]:
    out: list[FeeItem] = []
    seen: set[str] = set()
    for section, channel, label, amount, trailing in rows:
        if section != 8:
            continue

        category = _categorize_trademark(label)
        condition: FeeCondition | None = None
        # TM term = 10 years (TMA 2019 §28). Renewal FeeItems carry
        # year=10 to satisfy the renewal validator.
        year = 10 if category is FeeCategory.renewal else None

        if channel == "paper":
            condition = _paper_condition()

        if category is FeeCategory.excess_classes:
            condition = FeeCondition(
                trigger=ConditionalTrigger.classes_over,
                threshold=1,
                per_unit=True,
                description="Per class beyond the first.",
            )

        suffix = channel
        code = _unique(
            _slug("fi-prh-tm", suffix, label[:60]),
            seen,
        )

        notes_bits: list[str] = [f"channel: {channel}"]
        if trailing:
            notes_bits.append(f"unit: {trailing}")
        notes = " | ".join(notes_bits)

        out.append(
            FeeItem(
                code=code,
                label=label[:200],
                category=category,
                rights=[RightType.trademark],
                amount=amount,
                currency="EUR",
                tier=EntityTier.none,
                year=year,
                condition=condition,
                source_url=PRH_TRADEMARKS_URL,
                notes=notes,
            )
        )
    return out


# ──────────────────────────────────────────────────────────────────────
# Design builder (section 9)
# ──────────────────────────────────────────────────────────────────────


def _build_design_fees(rows: list[tuple[int, str, str, Decimal, str]]) -> list[FeeItem]:
    out: list[FeeItem] = []
    seen: set[str] = set()
    for section, _channel, label, amount, trailing in rows:
        if section != 9:
            continue

        category = _categorize_design(label)
        condition: FeeCondition | None = None
        # Design term: 5 years initial, renewable in 5-year periods up
        # to 25 years per Mallioikeuslaki §24. Renewal FeeItems carry
        # year=10 (end of first 5-year extension) to satisfy the
        # validator; consumers needing the full ladder should consult
        # the Act.
        year = 10 if category is FeeCategory.renewal else None

        label_channel = _label_channel(label)
        if label_channel == "paper":
            condition = _paper_condition()

        if category is FeeCategory.excess_classes:
            condition = FeeCondition(
                trigger=ConditionalTrigger.classes_over,
                threshold=1,
                per_unit=True,
                description="Per class beyond the first.",
            )

        code = _unique(
            _slug("fi-prh-des", label[:60]),
            seen,
        )

        notes_bits: list[str] = []
        if trailing:
            notes_bits.append(f"unit: {trailing}")
        notes = " | ".join(notes_bits) if notes_bits else None

        out.append(
            FeeItem(
                code=code,
                label=label[:200],
                category=category,
                rights=[RightType.design],
                amount=amount,
                currency="EUR",
                tier=EntityTier.none,
                year=year,
                condition=condition,
                source_url=PRH_DESIGNS_URL,
                notes=notes,
            )
        )
    return out


# ──────────────────────────────────────────────────────────────────────
# Public scrape entry points
# ──────────────────────────────────────────────────────────────────────


async def scrape_prh_patents() -> FeeSchedule:
    """Scrape PRH patent + UM + PCT + EP + SPC fees from the Maksuasetus PDF."""
    async with PRHFeesClient() as client:
        pdf_bytes = await client.fetch_pdf()
    lines = _extract_pdf_lines(pdf_bytes)
    rows = _walk_sections(lines)
    fees = _build_patent_fees(rows)
    if not fees:
        raise RuntimeError("PRH patent scraper parsed zero rows — PDF structure may have changed")
    return FeeSchedule(
        jurisdiction="FI",
        issuing_body="Patentti- ja rekisterihallitus (PRH)",
        office_code="PRH",
        right=RightType.patent,
        currency="EUR",
        effective_date=PRH_EFFECTIVE_DATE,
        source_url=PRH_PATENTS_URL,
        statutory_basis=_STATUTORY_PATENT,
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "Bundles §1 national patents, §2 utility models, §3 PCT, "
            "§4 EP validation, and §5 Supplementary Protection "
            "Certificate (SPC). Patent annuities (years 1-20) and SPC "
            "annuities (years 1-6) each emit one FeeItem per year. "
            "UM renewal periods (4-yr / 2-yr) emit with year=4 / "
            "year=10. The §1 patent claims-over-15 surcharge and §2 "
            "UM claims-over-5 surcharge emit as FeeCategory."
            "excess_claims with FeeCondition(claims_over, threshold). "
            "Paper-channel rows carry FeeCondition(paper_filing)."
        ),
    )


async def scrape_prh_trademarks() -> FeeSchedule:
    """Scrape PRH trademark fees from §8 of the Maksuasetus PDF."""
    async with PRHFeesClient() as client:
        pdf_bytes = await client.fetch_pdf()
    lines = _extract_pdf_lines(pdf_bytes)
    rows = _walk_sections(lines)
    fees = _build_trademark_fees(rows)
    if not fees:
        raise RuntimeError(
            "PRH trademark scraper parsed zero rows — PDF structure may have changed"
        )
    return FeeSchedule(
        jurisdiction="FI",
        issuing_body="Patentti- ja rekisterihallitus (PRH)",
        office_code="PRH",
        right=RightType.trademark,
        currency="EUR",
        effective_date=PRH_EFFECTIVE_DATE,
        source_url=PRH_TRADEMARKS_URL,
        statutory_basis=_STATUTORY_TRADEMARK,
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "TM term is 10 years (TMA 2019 §28); renewal FeeItems "
            "carry year=10. §8 publishes the schedule twice — an "
            "electronic-channel block ('Maksut sähköistä järjestelmää "
            "käyttäen') and a paper block ('Maksut muuta kuin "
            "sähköistä järjestelmää käyttäen') — each row is emitted "
            "with a -electronic / -paper code suffix; paper rows "
            "carry FeeCondition(paper_filing). Per-class surcharges "
            "('Lisämaksu, luokkamaksu') emit as "
            "FeeCategory.excess_classes with classes_over threshold=1."
        ),
    )


async def scrape_prh_designs() -> FeeSchedule:
    """Scrape PRH design fees from §9 of the Maksuasetus PDF."""
    async with PRHFeesClient() as client:
        pdf_bytes = await client.fetch_pdf()
    lines = _extract_pdf_lines(pdf_bytes)
    rows = _walk_sections(lines)
    fees = _build_design_fees(rows)
    if not fees:
        raise RuntimeError("PRH design scraper parsed zero rows — PDF structure may have changed")
    return FeeSchedule(
        jurisdiction="FI",
        issuing_body="Patentti- ja rekisterihallitus (PRH)",
        office_code="PRH",
        right=RightType.design,
        currency="EUR",
        effective_date=PRH_EFFECTIVE_DATE,
        source_url=PRH_DESIGNS_URL,
        statutory_basis=_STATUTORY_DESIGN,
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "5-year initial term, renewable in 5-year periods up to "
            "25 years (Mallioikeuslaki §24). Renewal FeeItems carry "
            "year=10 (end of first 5-year extension); consumers "
            "needing the full ladder should consult the Act. "
            "'Yhteisrekisteröintimaksu' (multi-design surcharge) "
            "emits as FeeCategory.filing; 'Säilytysmaksu' (deposit "
            "fee) emits as FeeCategory.deferment. Community design "
            "(EUIPO) and international design (Hague) transmittal "
            "fees are also captured."
        ),
    )


__all__ = [
    "PRH_BASE",
    "PRH_FEES_PDF_URL",
    "PRH_PATENTS_URL",
    "PRH_TRADEMARKS_URL",
    "PRH_DESIGNS_URL",
    "PRH_EFFECTIVE_DATE",
    "PRHFeesClient",
    "scrape_prh_patents",
    "scrape_prh_trademarks",
    "scrape_prh_designs",
]
