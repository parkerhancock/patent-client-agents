"""The shared FTS5 query translator, run against a real FTS5 table."""

from __future__ import annotations

import sqlite3

import pytest

from patent_client_agents.fts_query import translate_fts_query

ROWS = [
    "Article 54(2) EPC defines the state of the art",
    "TMEP 1207.01(a) likelihood of confusion",
    "Article L. 611-10 du code de la propriété intellectuelle",
    "Guidelines G-II, 3.6 on programs for computers",
    "A section about NOT and NEAR used as plain words",
]


@pytest.fixture
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE VIRTUAL TABLE t USING fts5(body)")
    conn.executemany("INSERT INTO t(body) VALUES (?)", [(r,) for r in ROWS])
    return conn


def _hits(conn: sqlite3.Connection, query: str, syntax: str) -> list[str]:
    match = translate_fts_query(query, syntax)
    return [r[0] for r in conn.execute("SELECT body FROM t WHERE t MATCH ?", (match,))]


@pytest.mark.parametrize("syntax", ["and", "or", "adj"])
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("54(2) EPC", ROWS[0]),
        ("1207.01(a) likelihood", ROWS[1]),
        ("L. 611-10", ROWS[2]),
        ("G-II, 3.6", ROWS[3]),
        ('"Article 54(2)', ROWS[0]),
    ],
)
def test_citation_punctuation_matches_instead_of_raising(
    db: sqlite3.Connection, query: str, expected: str, syntax: str
) -> None:
    assert expected in _hits(db, query, syntax)


def test_operator_words_are_matched_as_text(db: sqlite3.Connection) -> None:
    assert _hits(db, "NOT NEAR", "and") == [ROWS[4]]
    assert _hits(db, "AND", "and") == [ROWS[4]]


def test_and_requires_every_term_and_or_accepts_any(db: sqlite3.Connection) -> None:
    assert _hits(db, "Article confusion", "and") == []
    assert set(_hits(db, "Article confusion", "or")) == {ROWS[0], ROWS[1], ROWS[2]}


def test_blank_query_translates_to_empty() -> None:
    assert translate_fts_query("   ", "and") == ""
