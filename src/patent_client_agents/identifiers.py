"""One parsed representation of a patent document number.

:class:`PatentNumber` has two halves.

The structured fields (``country``, ``series``, ``number``, ``kind``,
``ambiguous``) come from :meth:`PatentNumber.parse` and describe what the
input most likely names. They are the target model for new code.

The ``*_pn`` / ``odp_*`` / ``epo_*`` / ``google_slug`` / ``is_us`` methods
are *legacy emitters*. Each reproduces, byte for byte, a normalizer that
existed before this module, quirks included, and each works from ``raw``
rather than from the structured fields so the old behavior survives inputs
the parser does not understand. The old functions now delegate here, and
``tests/test_identifiers_differential.py`` pins every emitter to a frozen
copy of the original code. Fix a quirk by changing an emitter and its
golden on purpose, never by accident.

This module must stay stdlib-only so any connector can import it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Hint = Literal["patent", "publication", "application"]

#: US grant series with a letter prefix. Longest first so ``SIR`` beats ``S``.
_US_SERIES = ("SIR", "RE", "PP", "AI", "D", "H", "T", "X")

_CLEAN_RE = re.compile(r"[^A-Z0-9/]")
_PREFIXED_RE = re.compile(r"^(?P<cc>[A-Z]{2})(?P<body>[A-Z]{0,3}\d[\d/]*)(?P<kind>[A-Z]\d?)?$")
_BARE_RE = re.compile(r"^(?P<body>[A-Z]{0,3}\d[\d/]*)(?P<kind>[A-Z]\d?)?$")
_PCT_RE = re.compile(r"^PCT/?(?P<ro>[A-Z]{2})(?P<year>\d{2}|\d{4})/?(?P<serial>\d+)$")
_US_APP_SLASH_RE = re.compile(r"^(?P<series>\d{2})/(?P<serial>\d{6})$")

# Legacy-emitter patterns, copied verbatim from the original modules.
_PPUBS_CLEAN_RE = re.compile(r"[^A-Z0-9]")
_PPUBS_KIND_CODE_RE = re.compile(r"[A-Z]\d$")
_PPUBS_BARE_KIND_LETTER_RE = re.compile(r"(?<=\d)[A-Z]$")
_PPUBS_DOCDB_PGPUB_RE = re.compile(r"^(20\d{2})(\d{6})$")
_ODP_KIND_CODE_RE = re.compile(r"[A-Z]\d$")
_EPO_US_PGPUB_PRINTED_RE = re.compile(r"^US(20\d{2})0(\d{6})([A-Z]\d?)?$")
_GOOGLE_US_PGPUB_RE = re.compile(r"^US\d{4}\d{6}A1$")
_GOOGLE_WO_SHORT_RE = re.compile(r"^WO\d{2}[0-9]+[A-Z][0-9]*$")
_BARE_US_NUMBER_RE = re.compile(r"^[\d,]+$")


@dataclass(frozen=True)
class PatentNumber:
    """A patent, publication, or application number.

    Attributes:
        country: Two-letter office code (``"US"``, ``"EP"``, ``"WO"``), or
            ``None`` when the input carries none and no default applied.
        series: Which numbering series ``number`` belongs to. For US grants
            the letter series (``"RE"``, ``"D"``, ``"PP"``, ``"H"``, ``"T"``,
            ``"SIR"``, ``"AI"``, ``"X"``) or ``"utility"``; ``"pgpub"`` for US
            pre-grant publications; ``"application"`` for application serials
            (US and PCT); ``None`` for other offices or unparsed input.
        number: The number without country, series letters, kind code, or
            separators. US pre-grant publications use the printed 11-digit
            form (``20230012345``).
        kind: Kind code (``"B2"``, ``"A1"``, ``"E"``), or ``None``.
        raw: The input exactly as given.
        ambiguous: True when the parse had to guess, e.g. a bare 8-digit
            number with no hint, or input the parser does not recognize.
    """

    country: str | None
    series: str | None
    number: str
    kind: str | None
    raw: str
    ambiguous: bool = False

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @classmethod
    def parse(cls, s: str | None, hint: Hint | None = None) -> PatentNumber:
        """Parse ``s``. Never raises; unrecognized input is ``ambiguous``."""
        raw = s if s is not None else ""
        text = _CLEAN_RE.sub("", raw.upper())

        pct = _PCT_RE.match(text)
        if pct:
            year = pct["year"] if len(pct["year"]) == 4 else _wo_century(pct["year"])
            serial = pct["serial"].zfill(6)
            return cls("WO", "application", f"{pct['ro']}{year}{serial}", None, raw)

        slash_app = _US_APP_SLASH_RE.match(text.removeprefix("US"))
        if slash_app:
            return cls("US", "application", slash_app["series"] + slash_app["serial"], None, raw)

        m = _PREFIXED_RE.match(text)
        country: str | None
        if m and m["cc"] not in ("RE", "PP"):  # US series letters, not offices
            country, body, kind = m["cc"], m["body"], m["kind"]
        else:
            m = _BARE_RE.match(text)
            if not m:
                return cls(None, None, re.sub(r"[^A-Z0-9]", "", text), None, raw, True)
            country, body, kind = None, m["body"], m["kind"]

        body = body.replace("/", "")
        if country in (None, "US"):
            return cls._parse_us(country, body, kind, raw, hint)
        if country == "WO":
            return cls._parse_wo(body, kind, raw)
        return cls(country, None, body, kind, raw)

    @classmethod
    def _parse_us(
        cls, country: str | None, body: str, kind: str | None, raw: str, hint: Hint | None
    ) -> PatentNumber:
        for series in _US_SERIES:
            if body.startswith(series) and body[len(series) :].isdigit():
                return cls("US", series, body[len(series) :].lstrip("0") or "0", kind, raw)
        if not body.isdigit():
            return cls(country, None, body, kind, raw, True)
        if len(body) == 10 and body.startswith("20"):
            # EPO docdb pre-grant form: year + 6-digit serial.
            return cls("US", "pgpub", f"{body[:4]}0{body[4:]}", kind, raw)
        if len(body) == 11 and body.startswith("20"):
            return cls("US", "pgpub", body, kind, raw)
        if hint == "application":
            return cls("US", "application", body, kind, raw)
        if hint in ("patent", "publication") or country == "US" or kind:
            return cls("US", "utility", body.lstrip("0") or "0", kind, raw)
        # Bare digits, no country, no kind, no hint: an 8-digit string is
        # both a valid utility patent and a valid application serial.
        return cls("US", "utility", body.lstrip("0") or "0", kind, raw, len(body) == 8)

    @classmethod
    def _parse_wo(cls, body: str, kind: str | None, raw: str) -> PatentNumber:
        if not body.isdigit() or len(body) < 3:
            return cls("WO", None, body, kind, raw, True)
        if len(body) >= 10:
            return cls("WO", None, body, kind, raw)
        # Short form: 2-digit year + serial.
        year, serial = _wo_century(body[:2]), body[2:]
        return cls("WO", None, f"{year}{serial.zfill(6)}", kind, raw, len(serial) < 5)

    # ------------------------------------------------------------------
    # Legacy emitters (byte-for-byte; operate on ``raw``)
    # ------------------------------------------------------------------

    def ppubs_pn(self) -> str:
        """Former ``uspto_publications.utils.normalize_publication_number``."""
        if not self.raw:
            return ""
        cleaned = _PPUBS_CLEAN_RE.sub("", self.raw.upper())
        if cleaned.startswith("US"):
            cleaned = cleaned[2:]
        stripped = _PPUBS_KIND_CODE_RE.sub("", cleaned)
        if stripped == cleaned:
            stripped = _PPUBS_BARE_KIND_LETTER_RE.sub("", cleaned)
        cleaned = stripped
        docdb = _PPUBS_DOCDB_PGPUB_RE.match(cleaned)
        if docdb:
            cleaned = f"{docdb.group(1)}0{docdb.group(2)}"
        return cleaned

    def odp_patent_query(self) -> str:
        """Former ``uspto_odp.clients.applications._clean_patent_identifier``."""
        cleaned = "".join(ch for ch in self.raw.upper() if ch.isalnum())
        if cleaned.startswith("US"):
            cleaned = cleaned[2:]
        return _ODP_KIND_CODE_RE.sub("", cleaned)

    def odp_application(self) -> str:
        """Former ``UsptoOdpBaseClient._normalize_application_number``."""
        return self.raw.strip().replace("/", "").replace(",", "").replace(" ", "")

    def epo_original(self) -> str:
        """Former ``mcp.tools.epo_ops._normalize_epo_number`` and
        ``EpoOpsClient._normalize_number``."""
        return self.raw.strip().replace(" ", "").upper()

    def epo_docdb(self) -> str:
        """Former ``EpoOpsClient._ops_number(n, doc_type="publication", fmt="docdb")``.

        Also the ``epodoc`` result; other doc types use :meth:`epo_original`.
        """
        normalized = self.epo_original()
        match = _EPO_US_PGPUB_PRINTED_RE.match(normalized)
        if match:
            year, serial, kind = match.groups()
            normalized = f"US{year}{serial}{kind or ''}"
        return normalized

    def google_slug(self) -> str:
        """Former ``google_patents.client._normalize_patent_number``."""
        normalized = self.raw.upper().strip()
        if normalized and normalized[0].isdigit():
            normalized = f"US{normalized}"
        if _GOOGLE_US_PGPUB_RE.match(normalized) and len(normalized) == 14:
            normalized = f"{normalized[:6]}0{normalized[6:]}"
        if _GOOGLE_WO_SHORT_RE.match(normalized) and len(normalized) <= 12:
            year_part = normalized[2:4]
            century = "19" if int(year_part) >= 80 else "20"
            suffix = normalized[4:]
            normalized = (
                f"WO{century}{year_part}0{suffix}"
                if len(suffix) >= 5
                else f"WO{century}{normalized[2:]}"
            )
        return normalized

    def is_us(self) -> bool:
        """Former ``unified._is_us_number``."""
        cleaned = self.raw.strip().upper()
        return cleaned.startswith("US") or bool(_BARE_US_NUMBER_RE.match(cleaned))


def _wo_century(yy: str) -> str:
    return ("19" if int(yy) >= 80 else "20") + yy


__all__ = ["PatentNumber"]
