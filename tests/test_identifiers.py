"""Structured parsing tests for PatentNumber."""

from __future__ import annotations

import dataclasses

import pytest

from patent_client_agents.identifiers import PatentNumber

CASES = [
    # raw, hint, (country, series, number, kind, ambiguous)
    ("US10123456B2", None, ("US", "utility", "10123456", "B2", False)),
    ("US 10,123,456 B2", None, ("US", "utility", "10123456", "B2", False)),
    ("us10123456b2", None, ("US", "utility", "10123456", "B2", False)),
    ("US05668033", None, ("US", "utility", "5668033", None, False)),
    ("5,668,033", None, ("US", "utility", "5668033", None, False)),
    ("10123456", None, ("US", "utility", "10123456", None, True)),
    ("10123456", "patent", ("US", "utility", "10123456", None, False)),
    ("10123456", "application", ("US", "application", "10123456", None, False)),
    ("US20230012345A1", None, ("US", "pgpub", "20230012345", "A1", False)),
    ("US 2023/0012345 A1", None, ("US", "pgpub", "20230012345", "A1", False)),
    ("US2023012345A1", None, ("US", "pgpub", "20230012345", "A1", False)),
    ("RE46070E", None, ("US", "RE", "46070", "E", False)),
    ("USRE46070E1", None, ("US", "RE", "46070", "E1", False)),
    ("D1142829S", None, ("US", "D", "1142829", "S", False)),
    ("USPP12345P2", None, ("US", "PP", "12345", "P2", False)),
    ("H0001", None, ("US", "H", "1", None, False)),
    ("UST100001", None, ("US", "T", "100001", None, False)),
    ("16/123,456", None, ("US", "application", "16123456", None, False)),
    ("US 16/123,456", None, ("US", "application", "16123456", None, False)),
    ("EP 1 234 567 B1", None, ("EP", None, "1234567", "B1", False)),
    ("WO 2012/012345 A1", None, ("WO", None, "2012012345", "A1", False)),
    ("WO12/12345", None, ("WO", None, "2012012345", None, False)),
    ("WO9912345A1", None, ("WO", None, "1999012345", "A1", False)),
    ("PCT/US2012/012345", None, ("WO", "application", "US2012012345", None, False)),
    ("PCT/US12/34567", None, ("WO", "application", "US2012034567", None, False)),
    ("JP 2020-123456 A", None, ("JP", None, "2020123456", "A", False)),
    ("KR1020200012345A", None, ("KR", None, "1020200012345", "A", False)),
    ("CN112345678A", None, ("CN", None, "112345678", "A", False)),
    ("DE102020123456A1", None, ("DE", None, "102020123456", "A1", False)),
    ("hello", None, (None, None, "HELLO", None, True)),
    ("", None, (None, None, "", None, True)),
    ("US", None, (None, None, "US", None, True)),
]


@pytest.mark.parametrize(("raw", "hint", "expected"), CASES)
def test_parse(raw, hint, expected):
    pn = PatentNumber.parse(raw, hint=hint)
    assert (pn.country, pn.series, pn.number, pn.kind, pn.ambiguous) == expected
    assert pn.raw == raw


def test_none_parses_to_empty():
    pn = PatentNumber.parse(None)
    assert pn.raw == "" and pn.ambiguous


def test_frozen():
    pn = PatentNumber.parse("US10123456B2")
    with pytest.raises(dataclasses.FrozenInstanceError):
        pn.number = "1"  # type: ignore[misc]


def test_research_table_disagreements_are_preserved():
    """The emitters keep today's cross-connector disagreements (fixes come later)."""
    pgpub = PatentNumber.parse("US2023012345A1")
    assert pgpub.ppubs_pn() == "20230012345"
    assert pgpub.odp_patent_query() == "2023012345"
    reissue = PatentNumber.parse("RE46070E")
    assert reissue.ppubs_pn() == "RE46070"
    assert reissue.odp_patent_query() == "RE46070E"
    assert PatentNumber.parse("D1142829S").odp_patent_query() == "D1142829S"
