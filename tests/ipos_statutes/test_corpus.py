"""Tests for the IPOS Singapore statutes corpus.

Builds a tiny in-memory corpus from inline fixtures rather than hitting
``sso.agc.gov.sg`` or parsing real HTML. The schema + FTS5 wiring is
what we want pinned; statute fetch / parse / extract is a separate
concern covered by the build CLI tests.
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from patent_client_agents.ipos_statutes import IposStatutesClient
from patent_client_agents.ipos_statutes.client import (
    _resolve_statute,
    _translate_fts_query,
    parse_citation,
)
from patent_client_agents.ipos_statutes.corpus import CorpusUnavailable
from patent_client_agents.ipos_statutes.corpus.schema import DDL, SCHEMA_VERSION

FIXTURES = [
    {
        "statute": "patents",
        "short_name": "Patents Act",
        "statute_title": "Patents Act 1994 (2020 Revised Edition)",
        "section_label": "13",
        "title": "Patentable inventions",
        "breadcrumb": "Patents Act › Section 13",
        "source_url": "https://example.com/Act/PA1994#pr13",
        "source_version": "2020 Revised Edition",
        "text": (
            "13. Patentable inventions. An invention shall be patentable if "
            "it is new, involves an inventive step, and is capable of "
            "industrial application. The inventive-step test in Singapore "
            "tracks the EPC formulation closely."
        ),
    },
    {
        "statute": "patents",
        "short_name": "Patents Act",
        "statute_title": "Patents Act 1994 (2020 Revised Edition)",
        "section_label": "14",
        "title": "Novelty",
        "breadcrumb": "Patents Act › Section 14",
        "source_url": "https://example.com/Act/PA1994#pr14",
        "source_version": "2020 Revised Edition",
        "text": (
            "14. Novelty. An invention shall be taken to be new if it does "
            "not form part of the state of the art."
        ),
    },
    {
        "statute": "tm",
        "short_name": "Trade Marks Act",
        "statute_title": "Trade Marks Act 1998 (2020 Revised Edition)",
        "section_label": "27",
        "title": "Rights conferred by registered trade mark",
        "breadcrumb": "Trade Marks Act › Section 27",
        "source_url": "https://example.com/Act/TMA1998#pr27",
        "source_version": "2020 Revised Edition",
        "text": (
            "27.—(1) The proprietor of a registered trade mark has exclusive "
            "rights in the trade mark which are infringed by use of the "
            "trade mark in Singapore without his consent."
        ),
    },
    {
        "statute": "designs",
        "short_name": "Registered Designs Act",
        "statute_title": "Registered Designs Act 2000 (2020 Revised Edition)",
        "section_label": "5",
        "title": "Registrable designs",
        "breadcrumb": "Registered Designs Act › Section 5",
        "source_url": "https://example.com/Act/RDA2000#pr5",
        "source_version": "2020 Revised Edition",
        "text": ("5. A design is registrable if it is new and has individual character."),
    },
    {
        "statute": "copyright",
        "short_name": "Copyright Act",
        "statute_title": "Copyright Act 2021",
        "section_label": "9",
        "title": "Subject-matter eligible for copyright",
        "breadcrumb": "Copyright Act › Section 9",
        "source_url": "https://example.com/Act/CA2021#pr9",
        "source_version": "2021",
        "text": (
            "9. Copyright subsists in original literary, dramatic, musical, "
            "and artistic works fixed in a material form."
        ),
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
                    (statute, short_name, statute_title, section_label,
                     title, breadcrumb, source_url, source_version, text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["statute"],
                    row["short_name"],
                    row["statute_title"],
                    row["section_label"],
                    row["title"],
                    row["breadcrumb"],
                    row["source_url"],
                    row["source_version"],
                    row["text"],
                ),
            )
        for key, value in [
            ("schema_version", str(SCHEMA_VERSION)),
            ("snapshot_date", "2026-05-16"),
            ("source_version", "2020 Revised Edition"),
            ("section_count", str(len(FIXTURES))),
            ("statute_count", "4"),
        ]:
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                (key, value),
            )
        conn.execute("INSERT INTO sections_fts(sections_fts) VALUES ('optimize')")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def corpus_path(tmp_path: Path) -> Path:
    db = tmp_path / "ipos_statutes.db"
    _seed_corpus(db)
    return db


def _run(coro):
    return asyncio.run(coro)


def test_translate_fts_query_quotes_punctuation():
    assert _translate_fts_query("inventive", "and") == "inventive"
    assert _translate_fts_query("inventive-step", "and") == '"inventive-step"'
    assert _translate_fts_query("Section 13", "and") == "Section 13"
    assert _translate_fts_query("Section 13", "exact") == '"Section 13"'
    assert _translate_fts_query("a b", "or") == "a OR b"
    assert _translate_fts_query("", "and") == ""


def test_resolve_statute_aliases():
    assert _resolve_statute("Patents Act") == "patents"
    assert _resolve_statute("PA1994") == "patents"
    assert _resolve_statute("TMA1998") == "tm"
    assert _resolve_statute("Trade Marks Act 1998") == "tm"
    assert _resolve_statute("RDA") == "designs"
    assert _resolve_statute("CA2021") == "copyright"
    assert _resolve_statute(None) is None
    # Unknown keys pass through lowercased
    assert _resolve_statute("Made Up Act") == "made up act"


def test_parse_citation_section_first():
    assert parse_citation("Section 13 Patents Act") == ("patents", "13")
    assert parse_citation("s. 14 Patents Act") == ("patents", "14")
    assert parse_citation("s 27 Trade Marks Act") == ("tm", "27")


def test_parse_citation_statute_first():
    assert parse_citation("Patents Act s. 13") == ("patents", "13")
    assert parse_citation("Patents Act section 14") == ("patents", "14")


def test_parse_citation_bare_label():
    assert parse_citation("13 Patents Act") == ("patents", "13")
    assert parse_citation("Patents Act 13") == ("patents", "13")


def test_parse_citation_with_subsections():
    parsed = parse_citation("s 27(1) Trade Marks Act")
    assert parsed == ("tm", "27(1)")


def test_parse_citation_returns_none_when_no_match():
    assert parse_citation("not a citation") is None
    assert parse_citation("") is None


def test_list_statutes(corpus_path: Path):
    async def go():
        async with IposStatutesClient(corpus_path=corpus_path) as c:
            return await c.list_statutes()

    statutes = _run(go())
    keys = {s.statute for s in statutes}
    assert keys == {"patents", "tm", "designs", "copyright"}
    # short_names are citation-ready
    short_names = {s.short_name for s in statutes}
    assert "Patents Act" in short_names
    assert "Trade Marks Act" in short_names


def test_get_section_by_canonical_key(corpus_path: Path):
    async def go():
        async with IposStatutesClient(corpus_path=corpus_path) as c:
            return await c.get_section(statute="patents", section_label="13")

    section = _run(go())
    assert section is not None
    assert section.short_name == "Patents Act"
    assert section.section_label == "13"
    assert "Patentable inventions" in section.title  # type: ignore[arg-type]
    assert "inventive step" in section.text.lower()


def test_get_section_by_alias(corpus_path: Path):
    async def go():
        async with IposStatutesClient(corpus_path=corpus_path) as c:
            return await c.get_section(statute="Patents Act", section_label="13")

    section = _run(go())
    assert section is not None
    assert section.statute == "patents"


def test_get_section_missing_returns_none(corpus_path: Path):
    async def go():
        async with IposStatutesClient(corpus_path=corpus_path) as c:
            return await c.get_section(statute="patents", section_label="99999")

    assert _run(go()) is None


def test_get_by_citation_round_trip(corpus_path: Path):
    async def go():
        async with IposStatutesClient(corpus_path=corpus_path) as c:
            return await c.get_by_citation("Section 13 Patents Act")

    section = _run(go())
    assert section is not None
    assert section.section_label == "13"
    assert section.statute == "patents"


def test_get_by_citation_with_subsection(corpus_path: Path):
    async def go():
        async with IposStatutesClient(corpus_path=corpus_path) as c:
            return await c.get_by_citation("s 27(1) Trade Marks Act")

    # The seeded fixture stores '27' (not '27(1)'), so this returns None,
    # but the citation parser must still resolve the statute key.
    assert _run(go()) is None


def test_get_by_citation_unparseable_returns_none(corpus_path: Path):
    async def go():
        async with IposStatutesClient(corpus_path=corpus_path) as c:
            return await c.get_by_citation("not a citation")

    assert _run(go()) is None


def test_search_scoped_by_statute(corpus_path: Path):
    async def go():
        async with IposStatutesClient(corpus_path=corpus_path) as c:
            return await c.search("inventive step", statute="patents")

    response = _run(go())
    assert response.hits
    assert all(h.statute == "patents" for h in response.hits)
    assert "<mark>" in response.hits[0].snippet


def test_search_unscoped_finds_across_statutes(corpus_path: Path):
    async def go():
        async with IposStatutesClient(corpus_path=corpus_path) as c:
            return await c.search("design")

    response = _run(go())
    # 'design' should hit the Registered Designs Act text.
    assert any(h.statute == "designs" for h in response.hits)


def test_search_returns_empty_when_query_is_blank(corpus_path: Path):
    async def go():
        async with IposStatutesClient(corpus_path=corpus_path) as c:
            return await c.search("")

    response = _run(go())
    assert response.hits == []
    assert response.has_more is False


def test_search_pagination(corpus_path: Path):
    async def go():
        async with IposStatutesClient(corpus_path=corpus_path) as c:
            return await c.search("the", per_page=1)

    response = _run(go())
    assert len(response.hits) == 1
    # 'the' appears in every fixture row, so has_more is true on first page
    assert response.has_more is True


def test_missing_corpus_raises_with_install_hint(tmp_path: Path):
    missing = tmp_path / "absent.db"

    async def go():
        async with IposStatutesClient(corpus_path=missing) as c:
            await c.list_statutes()

    with pytest.raises(CorpusUnavailable, match="build-ipos-statutes-corpus"):
        _run(go())


def test_meta_round_trip(corpus_path: Path):
    async def go():
        async with IposStatutesClient(corpus_path=corpus_path) as c:
            return await c.meta()

    meta = _run(go())
    assert meta.schema_version == SCHEMA_VERSION
    assert meta.section_count == len(FIXTURES)
    assert meta.statute_count == 4
    assert meta.snapshot_date == "2026-05-16"
    assert meta.source_version == "2020 Revised Edition"
