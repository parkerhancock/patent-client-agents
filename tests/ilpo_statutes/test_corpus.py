"""Tests for the ILPO Israel statutes corpus.

Builds a tiny in-memory corpus from inline fixtures rather than hitting
WIPO Lex or unpacking real PDFs. The schema + FTS5 wiring + client
query surface is what we want pinned; PDF text extraction and section
parsing are covered by ``test_build.py``.
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from patent_client_agents.ilpo_statutes import IlpoStatutesClient
from patent_client_agents.ilpo_statutes.client import (
    STATUTE_ALIASES,
    _resolve_statute,
    _translate_fts_query,
    parse_citation,
)
from patent_client_agents.ilpo_statutes.corpus import CorpusUnavailable
from patent_client_agents.ilpo_statutes.corpus.schema import DDL, SCHEMA_VERSION

FIXTURES = [
    {
        "statute": "patents",
        "section_number": "3",
        "section_label": "Section 3 Patents Law",
        "title": "Patentable invention",
        "text": (
            "Patentable invention An invention, whether a product or a "
            "process in any field of technology, which is new, useful, "
            "industrially applicable and involves an inventive step, "
            "is patentable."
        ),
        "source_url": "https://www.wipo.int/wipolex/en/legislation/details/15167",
    },
    {
        "statute": "trademarks",
        "section_number": "1",
        "section_label": "Section 1 Trade Marks Ordinance",
        "title": "Definitions",
        "text": (
            'Definitions "mark" means letters, numerals, words, '
            "figures or other signs or any combination thereof, "
            "whether two-dimensional or three-dimensional."
        ),
        "source_url": "https://www.wipo.int/wipolex/en/legislation/details/8200",
    },
    {
        "statute": "designs",
        "section_number": "2",
        "section_label": "Section 2 Designs Law",
        "title": "Definitions",
        "text": (
            "Definitions In this Law: 'design' means the appearance "
            "of a product or part thereof, consisting of one or more "
            "visual features of the product."
        ),
        "source_url": "https://www.wipo.int/wipolex/en/legislation/details/19434",
    },
    {
        "statute": "copyright",
        "section_number": "1",
        "section_label": "Section 1 Copyright Act",
        "title": "Definitions",
        "text": (
            "Definitions In this Act: 'work' means an original literary, "
            "artistic, dramatic or musical work, including a computer "
            "program; 'author' means the creator of a work."
        ),
        "source_url": "https://www.wipo.int/wipolex/en/legislation/details/11509",
    },
    {
        "statute": "commercial_torts",
        "section_number": "6",
        "section_label": "Article 6 Commercial Torts Law",
        "title": "Trade secret — misappropriation",
        "text": (
            "Trade secret misappropriation A person shall not "
            "misappropriate the trade secret of another. "
            "Misappropriation of a trade secret is the taking of a "
            "trade secret without consent of its owner."
        ),
        "source_url": "https://www.wipo.int/wipolex/en/legislation/details/2375",
    },
    {
        "statute": "commercial_torts",
        "section_number": "13",
        "section_label": "Article 13 Commercial Torts Law",
        "title": "Statutory damages",
        "text": (
            "Statutory damages In an action under this Law the Court "
            "may award the plaintiff damages without proof of damage "
            "in an amount not exceeding NIS 100,000 per violation."
        ),
        "source_url": "https://www.wipo.int/wipolex/en/legislation/details/2375",
    },
]


def _seed_corpus(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(DDL)
        for row in FIXTURES:
            conn.execute(
                """
                INSERT INTO sections
                    (statute, section_number, section_label, title,
                     text, source_url)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row["statute"],
                    row["section_number"],
                    row["section_label"],
                    row["title"],
                    row["text"],
                    row["source_url"],
                ),
            )
        conn.executemany(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            [
                ("schema_version", str(SCHEMA_VERSION)),
                ("snapshot_date", "2026-05-16"),
                ("source_version", "WIPO Lex authoritative EN"),
                ("section_count", str(len(FIXTURES))),
            ],
        )
        conn.execute("INSERT INTO sections_fts(sections_fts) VALUES ('optimize')")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def corpus_path(tmp_path: Path) -> Path:
    db = tmp_path / "ilpo_statutes.db"
    _seed_corpus(db)
    return db


def _run(coro):
    return asyncio.run(coro)


# ──────────────────────────────────────────────────────────────────────
# Query translation + alias resolution
# ──────────────────────────────────────────────────────────────────────


def test_translate_fts_query_quotes_hyphenated_terms() -> None:
    assert _translate_fts_query("trade", "and") == "trade"
    assert _translate_fts_query("trade-secret", "and") == '"trade-secret"'
    assert _translate_fts_query("trade secret", "and") == "trade secret"
    assert _translate_fts_query("trade secret", "exact") == '"trade secret"'
    assert _translate_fts_query("trade secret", "or") == "trade OR secret"
    assert _translate_fts_query("", "and") == ""


def test_resolve_statute_aliases() -> None:
    assert _resolve_statute("Patents Law") == "patents"
    assert _resolve_statute("trade marks") == "trademarks"
    assert _resolve_statute("trade secret") == "commercial_torts"
    assert _resolve_statute("trade secrets") == "commercial_torts"
    assert _resolve_statute("commercial torts") == "commercial_torts"
    assert _resolve_statute(None) is None
    # Unknown name passes through lowercase (lets downstream fail loudly)
    assert _resolve_statute("Unknown") == "unknown"


def test_statute_alias_coverage_includes_commercial_torts() -> None:
    """Sanity-check that the trade-secret alias points at the right key."""
    assert STATUTE_ALIASES["trade secret"] == "commercial_torts"
    assert STATUTE_ALIASES["trade secrets"] == "commercial_torts"


# ──────────────────────────────────────────────────────────────────────
# Citation parsing
# ──────────────────────────────────────────────────────────────────────


def test_parse_citation_forward_form() -> None:
    assert parse_citation("Section 3 Patents Law") == ("patents", "3")
    assert parse_citation("Section 1 Trade Marks Ordinance") == ("trademarks", "1")
    assert parse_citation("Article 6 Commercial Torts Law") == ("commercial_torts", "6")
    assert parse_citation("§3 Patents Law") == ("patents", "3")


def test_parse_citation_reverse_form() -> None:
    assert parse_citation("Patents Law §3") == ("patents", "3")
    assert parse_citation("Patents Law Section 3") == ("patents", "3")
    assert parse_citation("Commercial Torts Law Article 6") == ("commercial_torts", "6")


def test_parse_citation_case_insensitive() -> None:
    assert parse_citation("section 3 patents law") == ("patents", "3")


def test_parse_citation_unrecognized_returns_none() -> None:
    assert parse_citation("") is None
    assert parse_citation("Article 6 No Such Statute") is None


# ──────────────────────────────────────────────────────────────────────
# Client read-paths
# ──────────────────────────────────────────────────────────────────────


def test_list_statutes(corpus_path: Path) -> None:
    async def go():
        async with IlpoStatutesClient(corpus_path=corpus_path) as c:
            return await c.list_statutes()

    statutes = _run(go())
    keys = {s.statute for s in statutes}
    assert keys == {
        "patents",
        "trademarks",
        "designs",
        "copyright",
        "commercial_torts",
    }
    # Commercial Torts Law has two fixture sections (Articles 6 and 13).
    ct = next(s for s in statutes if s.statute == "commercial_torts")
    assert ct.section_count == 2


def test_get_section_by_pair(corpus_path: Path) -> None:
    async def go():
        async with IlpoStatutesClient(corpus_path=corpus_path) as c:
            return await c.get_section(statute="patents", section_number="3")

    section = _run(go())
    assert section is not None
    assert section.section_label == "Section 3 Patents Law"
    assert "Patentable" in section.text


def test_get_section_by_citation_forward_form(corpus_path: Path) -> None:
    async def go():
        async with IlpoStatutesClient(corpus_path=corpus_path) as c:
            return await c.get_section_by_citation("Article 6 Commercial Torts Law")

    section = _run(go())
    assert section is not None
    assert section.statute == "commercial_torts"
    assert "Trade secret" in section.text


def test_get_section_by_citation_alias(corpus_path: Path) -> None:
    """The 'trade secret' alias should route to the Commercial Torts Law."""

    async def go():
        async with IlpoStatutesClient(corpus_path=corpus_path) as c:
            # Alias path via parse_citation → "trade secret" → commercial_torts
            return await c.get_section_by_citation("Article 6 Trade Secret")

    section = _run(go())
    assert section is not None
    assert section.statute == "commercial_torts"


def test_get_section_by_citation_unparseable_returns_none(corpus_path: Path) -> None:
    async def go():
        async with IlpoStatutesClient(corpus_path=corpus_path) as c:
            return await c.get_section_by_citation("nonsense")

    assert _run(go()) is None


def test_get_section_unknown_statute_returns_none(corpus_path: Path) -> None:
    async def go():
        async with IlpoStatutesClient(corpus_path=corpus_path) as c:
            return await c.get_section(statute="patents", section_number="9999")

    assert _run(go()) is None


def test_search_trade_secret_in_commercial_torts(corpus_path: Path) -> None:
    async def go():
        async with IlpoStatutesClient(corpus_path=corpus_path) as c:
            return await c.search("trade secret", statute="commercial_torts")

    response = _run(go())
    assert response.hits
    assert all(h.statute == "commercial_torts" for h in response.hits)
    assert "<mark>" in response.hits[0].snippet


def test_search_unscoped_returns_all(corpus_path: Path) -> None:
    async def go():
        async with IlpoStatutesClient(corpus_path=corpus_path) as c:
            return await c.search("Definitions")

    response = _run(go())
    statutes = {h.statute for h in response.hits}
    # Several statutes have a "Definitions" section in the fixtures.
    assert "trademarks" in statutes
    assert "designs" in statutes


def test_search_pagination_has_more(corpus_path: Path) -> None:
    async def go():
        async with IlpoStatutesClient(corpus_path=corpus_path) as c:
            return await c.search("Definitions", per_page=1)

    response = _run(go())
    assert len(response.hits) == 1
    assert response.has_more is True


def test_search_empty_query_returns_empty(corpus_path: Path) -> None:
    async def go():
        async with IlpoStatutesClient(corpus_path=corpus_path) as c:
            return await c.search("")

    response = _run(go())
    assert response.hits == []
    assert response.has_more is False


def test_search_outline_sort(corpus_path: Path) -> None:
    async def go():
        async with IlpoStatutesClient(corpus_path=corpus_path) as c:
            return await c.search("Definitions", sort="outline", per_page=10)

    response = _run(go())
    # Outline sort orders by statute then section_number; "copyright" sorts
    # before "designs" alphabetically and both have a "Definitions" section.
    statutes_in_order = [h.statute for h in response.hits]
    assert statutes_in_order == sorted(statutes_in_order)


def test_meta_round_trip(corpus_path: Path) -> None:
    async def go():
        async with IlpoStatutesClient(corpus_path=corpus_path) as c:
            return await c.meta()

    meta = _run(go())
    assert meta.schema_version == SCHEMA_VERSION
    assert meta.section_count == len(FIXTURES)
    assert meta.snapshot_date == "2026-05-16"
    assert meta.source_version == "WIPO Lex authoritative EN"


def test_missing_corpus_raises_with_install_hint(tmp_path: Path) -> None:
    missing = tmp_path / "absent.db"

    async def go():
        async with IlpoStatutesClient(corpus_path=missing) as c:
            await c.list_statutes()

    with pytest.raises(CorpusUnavailable, match="build-ilpo-statutes-corpus"):
        _run(go())
