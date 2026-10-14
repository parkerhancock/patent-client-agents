"""Differential test: each PatentNumber legacy emitter == the pre-existing normalizer.

The ``_legacy_*`` functions below are frozen, verbatim copies of the
normalizers as they stood before ``patent_client_agents.identifiers``
existed (PCA 45cb1e0). Each emitter is checked against both the frozen copy
and the live function it now backs, so the test fails if an emitter drifts
or if a shim is wired to the wrong emitter.

Changing a frozen copy is changing behavior. Do it only together with a
deliberate fix and a note in CHANGELOG.md.
"""

from __future__ import annotations

import itertools
import re
from typing import Any, cast

import pytest

from patent_client_agents.epo_ops.client import EpoOpsClient
from patent_client_agents.google_patents.client import _normalize_patent_number
from patent_client_agents.identifiers import PatentNumber
from patent_client_agents.mcp.tools.epo_ops import _normalize_epo_number
from patent_client_agents.unified import _is_us_number
from patent_client_agents.uspto_odp.clients.applications import _clean_patent_identifier
from patent_client_agents.uspto_odp.clients.base import UsptoOdpBaseClient
from patent_client_agents.uspto_publications.utils import normalize_publication_number

# ---------------------------------------------------------------------------
# Frozen legacy implementations (verbatim)
# ---------------------------------------------------------------------------

_PUB_NUMBER_CLEAN_RE = re.compile(r"[^A-Z0-9]")
_KIND_CODE_RE = re.compile(r"[A-Z]\d$")
_BARE_KIND_LETTER_RE = re.compile(r"(?<=\d)[A-Z]$")
_DOCDB_PGPUB_RE = re.compile(r"^(20\d{2})(\d{6})$")
_US_PGPUB_PRINTED_RE = re.compile(r"^US(20\d{2})0(\d{6})([A-Z]\d?)?$")
_BARE_US_NUMBER_RE = re.compile(r"^[\d,]+$")


def _legacy_normalize_publication_number(value: str | None) -> str:
    if not value:
        return ""
    cleaned = _PUB_NUMBER_CLEAN_RE.sub("", value.upper())
    if cleaned.startswith("US"):
        cleaned = cleaned[2:]
    stripped = _KIND_CODE_RE.sub("", cleaned)
    if stripped == cleaned:
        stripped = _BARE_KIND_LETTER_RE.sub("", cleaned)
    cleaned = stripped
    docdb = _DOCDB_PGPUB_RE.match(cleaned)
    if docdb:
        cleaned = f"{docdb.group(1)}0{docdb.group(2)}"
    return cleaned


def _legacy_clean_patent_identifier(identifier: str) -> str:
    cleaned = "".join(ch for ch in identifier.upper() if ch.isalnum())
    if cleaned.startswith("US"):
        cleaned = cleaned[2:]
    cleaned = re.sub(r"[A-Z]\d$", "", cleaned)
    return cleaned


def _legacy_normalize_application_number(application_number: str) -> str:
    normalized = application_number.strip().replace("/", "").replace(",", "").replace(" ", "")
    return normalized


def _legacy_normalize_epo_number(number: str) -> str:
    return number.strip().replace(" ", "").upper()


def _legacy_ops_number(number: str, *, doc_type: str, fmt: str) -> str:
    normalized = _legacy_normalize_epo_number(number)
    if doc_type == "publication" and fmt in ("docdb", "epodoc"):
        match = _US_PGPUB_PRINTED_RE.match(normalized)
        if match:
            year, serial, kind = match.groups()
            normalized = f"US{year}{serial}{kind or ''}"
    return normalized


def _legacy_google_normalize_patent_number(patent_number: str) -> str:
    normalized = patent_number.upper().strip()

    if normalized and normalized[0].isdigit():
        normalized = f"US{normalized}"

    if re.match(r"^US\d{4}\d{6}A1$", normalized) and len(normalized) == 14:
        normalized = f"{normalized[:6]}0{normalized[6:]}"

    if re.match(r"^WO\d{2}[0-9]+[A-Z][0-9]*$", normalized) and len(normalized) <= 12:
        year_part = normalized[2:4]
        century = "19" if int(year_part) >= 80 else "20"
        suffix = normalized[4:]
        normalized = (
            f"WO{century}{year_part}0{suffix}"
            if len(suffix) >= 5
            else f"WO{century}{normalized[2:]}"
        )

    return normalized


def _legacy_is_us_number(patent_number: str) -> bool:
    cleaned = patent_number.strip().upper()
    return cleaned.startswith("US") or bool(_BARE_US_NUMBER_RE.match(cleaned))


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------

#: Rows from the research disagreement table plus every format family.
_SEEDS: list[str] = [
    # Research table rows
    "US2023012345A1",
    "RE46070E",
    "USRE46070E",
    "USRE46070E1",
    "10123456",
    "D1142829S",
    "USD1142829S",
    # US utility grants
    "US10123456",
    "US10123456B2",
    "US10123456B1",
    "US 10,123,456 B2",
    "US-10,123,456-B2",
    "US 10 123 456",
    "10,123,456",
    "10,123,456 B2",
    "US7654321B2",
    "US5668033A",
    "5668033",
    "5,668,033",
    "US05668033",
    "US 5668033 A",
    "U.S. Pat. No. 10,123,456",
    "U.S. 10,123,456",
    "US11999999B2",
    "11999999",
    "US12345678",
    "US123",
    "1",
    "US4",
    "US10123456E",
    "US10123456C1",
    "US10123456B9",
    "US1012345B",
    # US pre-grant publications, printed and docdb
    "US20230012345A1",
    "US20230012345",
    "US 2023/0012345 A1",
    "US 2023-0012345 A1",
    "2023/0012345",
    "20230012345",
    "20230012345A1",
    "US2016309324A1",
    "US2016309324",
    "2016309324",
    "US20160309324A1",
    "US20050262543A1",
    "US2005262543A1",
    "US20050262543A9",
    "US20050262543A2",
    "US20050262543",
    "US20050262543B",
    "US1999012345A1",
    "US19990123456A1",
    "US2099123456A1",
    "US20991234567A1",
    "US2023123456A2",
    "US 2023012345 A1",
    # Reissue / design / plant / SIR / defensive / X / AI
    "RE46070",
    "USRE46070",
    "US RE46,070 E",
    "RE 46,070",
    "Re. 46,070",
    "RE046070",
    "USRE046070E",
    "RE12345E1",
    "D1142829",
    "USD1142829",
    "US D1,142,829 S",
    "D 1,142,829",
    "D1142829S1",
    "Des. 1,142,829",
    "D0512345",
    "PP12345",
    "USPP12345",
    "USPP12345P2",
    "PP12345P3",
    "PP 12,345",
    "PP012345",
    "H1",
    "H0001",
    "USH0001",
    "USH001234H",
    "H1234",
    "H 1,234",
    "T1",
    "T100001",
    "UST100001",
    "UST100001I4",
    "SIR1234",
    "USSIR1234",
    "X12345",
    "USX12345",
    "AI00001",
    "USAI00001",
    # EP
    "EP1234567",
    "EP1234567A1",
    "EP1234567B1",
    "EP 1 234 567 B1",
    "EP 1234567 A1",
    "ep1234567a1",
    "EP3000000A2",
    "EP-1234567-B1",
    "EP1234567.8",
    "EP04001234",
    "EP 04 001 234.5",
    # WO short / long
    "WO2012012345",
    "WO2012012345A1",
    "WO 2012/012345 A1",
    "WO2012/012345",
    "WO/2012/012345",
    "WO12/12345",
    "WO1212345A1",
    "WO0112345A1",
    "WO9912345A1",
    "WO8012345A1",
    "WO7912345A1",
    "WO991234A1",
    "WO99123A1",
    "WO12123A",
    "WO121234A2",
    "WO1234567890A1",
    "WO2020123456A1",
    "WO 20/123456",
    "WO20123456A1",
    "wo2012012345a1",
    "WO00/12345",
    "WO0012345A1",
    "WO8512345B1",
    # PCT applications
    "PCT/US2012/012345",
    "PCT/US12/34567",
    "PCTUS2012012345",
    "PCT/EP2020/054321",
    "pct/us2012/012345",
    "PCT/JP2019/001234",
    "PCT/IB2021/051234",
    # US application serials
    "16/123,456",
    "16/123456",
    "16123456",
    "16 123 456",
    "16,123,456",
    "US 16/123,456",
    "US16/123456",
    "US16123456",
    "08/123,456",
    "08123456",
    "29/123,456",
    "29123456",
    "60/123,456",
    "62/123456",
    "63123456",
    "35/123,456",
    "17-123456",
    "17.123.456",
    "Application No. 16/123,456",
    "Ser. No. 16/123,456",
    "16/123,456 ",
    " 16/123,456",
    "US 2016/123,456",
    # JP / KR / CN / others
    "JP2020123456A",
    "JP 2020-123456 A",
    "JP2020-123456",
    "JP6123456B2",
    "JPH10123456A",
    "JPS61123456A",
    "jp2020123456a",
    "KR1020200012345A",
    "KR 10-2020-0012345",
    "KR102345678B1",
    "KR20200012345A",
    "CN112345678A",
    "CN 112345678 A",
    "CN1234567C",
    "CN201920123456U",
    "CN 2019 1 0123456.7",
    "DE102020123456A1",
    "DE 10 2020 123 456 A1",
    "GB2012345A",
    "FR3012345A1",
    "CA3012345A1",
    "AU2020123456A1",
    "TW202012345A",
    "IN202011012345",
    "BR102020012345A2",
    "ES2123456T3",
    # Lowercase / mixed
    "us10123456b2",
    "Us10123456B2",
    "usre46070e",
    "usd1142829s",
    "us2023012345a1",
    "us20230012345a1",
    "d1142829s",
    "re46070e",
    "pp12345p2",
    # Garbage / edge
    "",
    " ",
    "   ",
    "\t",
    "\n",
    "US",
    "us",
    "USA",
    "USELESS",
    "U S",
    "A1",
    "B2",
    "S",
    "E",
    "0",
    "00000000",
    ",",
    ",,,",
    "1,",
    ",1",
    "/",
    "//",
    "-",
    "hello",
    "patent",
    "not a number",
    "???",
    "123abc",
    "abc123",
    "A1B2",
    "WO",
    "WOWO",
    "WO12",
    "WO1A",
    "WO12A",
    "WO123A",
    "WO1234A",
    "WO80A",
    "EP",
    "PCT",
    "PCT/",
    "RE",
    "D",
    "PP",
    "H",
    "10123456\n",
    "US10123456\n",
    "US2023012345A1\n",
    "10 123 456",
    "US 10123456",
    " 10123456 ",
    "１０１２３４５６",
    "US１０１２３４５６",
    "٢٠٢٣",
    "US٢٠٢٣٠١٢٣٤٥A1",
    "WO١٢١٢٣٤٥A1",
    "١٢٣",
    "straße1",
    "USé1234",
    "²123",
    "US²123",
    "ﬁ123",
    "10123456​",
    "10/123,456",
    "10/123/456",
    "1/2",
    "US10123456B2 US10123457B2",
    "US10123456B2,US10123457B2",
    "US 10,123,456 B2; US 10,123,457 B1",
    "https://patents.google.com/patent/US10123456B2/en",
    "US10123456B2/en",
]


def _variants(seed: str) -> list[str]:
    return [seed, seed.lower(), f"  {seed}  ", seed.replace(" ", ""), seed.replace(" ", "\t")]


CORPUS: list[str] = list(dict.fromkeys(itertools.chain.from_iterable(_variants(s) for s in _SEEDS)))


def test_corpus_is_large_enough():
    assert len(CORPUS) >= 300


# ---------------------------------------------------------------------------
# Differential assertions
# ---------------------------------------------------------------------------


def _check(name: str, emitted: object, frozen: object, live: object, raw: str) -> None:
    assert emitted == frozen, f"{name}: emitter {emitted!r} != frozen legacy {frozen!r} for {raw!r}"
    assert live == frozen, f"{name}: live function {live!r} != frozen legacy {frozen!r} for {raw!r}"
    assert type(emitted) is type(frozen)


@pytest.mark.parametrize("raw", CORPUS)
def test_emitters_match_legacy(raw: str) -> None:
    pn = PatentNumber.parse(raw)
    assert pn.raw == raw

    _check(
        "ppubs_pn",
        pn.ppubs_pn(),
        _legacy_normalize_publication_number(raw),
        normalize_publication_number(raw),
        raw,
    )
    _check(
        "odp_patent_query",
        pn.odp_patent_query(),
        _legacy_clean_patent_identifier(raw),
        _clean_patent_identifier(raw),
        raw,
    )
    _check(
        "odp_application",
        pn.odp_application(),
        _legacy_normalize_application_number(raw),
        UsptoOdpBaseClient._normalize_application_number(cast(Any, None), raw),
        raw,
    )
    _check(
        "epo_original",
        pn.epo_original(),
        _legacy_normalize_epo_number(raw),
        _normalize_epo_number(raw),
        raw,
    )
    _check(
        "epo_original (client)",
        pn.epo_original(),
        _legacy_normalize_epo_number(raw),
        EpoOpsClient._normalize_number(raw),
        raw,
    )
    _check(
        "google_slug",
        pn.google_slug(),
        _legacy_google_normalize_patent_number(raw),
        _normalize_patent_number(raw),
        raw,
    )
    _check("is_us", pn.is_us(), _legacy_is_us_number(raw), _is_us_number(raw), raw)


@pytest.mark.parametrize("raw", CORPUS)
@pytest.mark.parametrize(
    ("doc_type", "fmt"),
    [
        ("publication", "docdb"),
        ("publication", "epodoc"),
        ("publication", "original"),
        ("application", "docdb"),
        ("application", "epodoc"),
        ("priority", "docdb"),
    ],
)
def test_ops_number_matches_legacy(raw: str, doc_type: str, fmt: str) -> None:
    frozen = _legacy_ops_number(raw, doc_type=doc_type, fmt=fmt)
    live = EpoOpsClient._ops_number(raw, doc_type=doc_type, fmt=fmt)
    pn = PatentNumber.parse(raw)
    emitted = (
        pn.epo_docdb()
        if doc_type == "publication" and fmt in ("docdb", "epodoc")
        else pn.epo_original()
    )
    _check(f"_ops_number[{doc_type},{fmt}]", emitted, frozen, live, raw)


def test_ppubs_none_input() -> None:
    assert normalize_publication_number(None) == _legacy_normalize_publication_number(None) == ""
    assert PatentNumber.parse(None).ppubs_pn() == ""


@pytest.mark.parametrize("hint", [None, "patent", "publication", "application"])
def test_hint_does_not_change_legacy_emitters(hint: Any) -> None:
    for raw in CORPUS:
        base = PatentNumber.parse(raw)
        hinted = PatentNumber.parse(raw, hint=hint)
        assert (
            hinted.ppubs_pn(),
            hinted.odp_patent_query(),
            hinted.odp_application(),
            hinted.epo_original(),
            hinted.epo_docdb(),
            hinted.google_slug(),
            hinted.is_us(),
        ) == (
            base.ppubs_pn(),
            base.odp_patent_query(),
            base.odp_application(),
            base.epo_original(),
            base.epo_docdb(),
            base.google_slug(),
            base.is_us(),
        )


def test_parse_never_raises_on_corpus() -> None:
    for raw in CORPUS:
        for hint in (None, "patent", "publication", "application"):
            PatentNumber.parse(raw, hint=cast(Any, hint))
