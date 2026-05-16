"""Tests for the IPOS Singapore manuals corpus."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from patent_client_agents.ipos_manuals import IposManualsClient
from patent_client_agents.ipos_manuals.client import (
    _resolve_manual,
    _translate_fts_query,
    parse_citation,
)
from patent_client_agents.ipos_manuals.corpus import CorpusUnavailable
from patent_client_agents.ipos_manuals.corpus.schema import DDL, SCHEMA_VERSION

FIXTURES = [
    {
        "manual": "peg",
        "short_name": "PEG",
        "manual_title": "IPOS Patent Examination Guidelines",
        "section_label": "1.5.3",
        "title": "Inventive Step",
        "breadcrumb": "PEG › 1.5.3",
        "source_url": "https://example.com/peg.pdf#1.5.3",
        "source_version": None,
        "text": (
            "1.5.3 Inventive Step. An invention shall be taken to involve "
            "an inventive step if it is not obvious to a person skilled in "
            "the art having regard to the state of the art."
        ),
    },
    {
        "manual": "peg",
        "short_name": "PEG",
        "manual_title": "IPOS Patent Examination Guidelines",
        "section_label": "1.6",
        "title": "Industrial Applicability",
        "breadcrumb": "PEG › 1.6",
        "source_url": "https://example.com/peg.pdf#1.6",
        "source_version": None,
        "text": (
            "1.6 Industrial Applicability. An invention is taken to be "
            "capable of industrial application if it can be made or used "
            "in any kind of industry."
        ),
    },
    {
        "manual": "tm",
        "short_name": "TM Work Manual",
        "manual_title": "IPOS Trade Marks Work Manual",
        "section_label": "3.4",
        "title": "Distinctiveness",
        "breadcrumb": "TM Work Manual › 3.4",
        "source_url": "https://example.com/tm-work-manual.pdf#3.4",
        "source_version": None,
        "text": (
            "3.4 Distinctiveness. A trade mark must be distinctive of the "
            "goods or services of one undertaking from those of others."
        ),
    },
    {
        "manual": "designs",
        "short_name": "Designs Work Manual",
        "manual_title": "IPOS Industrial Designs Work Manual",
        "section_label": "2.1",
        "title": "Novelty Requirement",
        "breadcrumb": "Designs Work Manual › 2.1",
        "source_url": "https://example.com/designs-work-manual.pdf#2.1",
        "source_version": None,
        "text": (
            "2.1 Novelty Requirement. A design is new if no identical "
            "design has been made available to the public before the "
            "relevant date."
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
                    (manual, short_name, manual_title, section_label,
                     title, breadcrumb, source_url, source_version, text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["manual"],
                    row["short_name"],
                    row["manual_title"],
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
            ("section_count", str(len(FIXTURES))),
            ("manual_count", "3"),
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
    db = tmp_path / "ipos_manuals.db"
    _seed_corpus(db)
    return db


def _run(coro):
    return asyncio.run(coro)


def test_translate_fts_query_quotes_punctuation():
    assert _translate_fts_query("novelty", "and") == "novelty"
    assert _translate_fts_query("inventive-step", "and") == '"inventive-step"'
    assert _translate_fts_query("1.5.3", "and") == '"1.5.3"'
    assert _translate_fts_query("1.5.3", "exact") == '"1.5.3"'
    assert _translate_fts_query("", "and") == ""


def test_resolve_manual_aliases():
    assert _resolve_manual("PEG") == "peg"
    assert _resolve_manual("Patent Examination Guidelines") == "peg"
    assert _resolve_manual("Trade Marks Work Manual") == "tm"
    assert _resolve_manual("TM Work Manual") == "tm"
    assert _resolve_manual("Industrial Designs Work Manual") == "designs"
    assert _resolve_manual(None) is None


def test_parse_citation_prefix_forms():
    assert parse_citation("IPOS PEG 1.5.3") == ("peg", "1.5.3")
    assert parse_citation("PEG 1.5.3") == ("peg", "1.5.3")
    assert parse_citation("IPOS TM Work Manual 3.4") == ("tm", "3.4")
    assert parse_citation("TM Work Manual 3.4") == ("tm", "3.4")
    assert parse_citation("Designs Work Manual 2.1") == ("designs", "2.1")


def test_parse_citation_label_first():
    assert parse_citation("1.5.3 PEG") == ("peg", "1.5.3")
    assert parse_citation("3.4 TM Work Manual") == ("tm", "3.4")


def test_parse_citation_returns_none_when_no_match():
    assert parse_citation("not a citation") is None
    assert parse_citation("") is None


def test_list_manuals(corpus_path: Path):
    async def go():
        async with IposManualsClient(corpus_path=corpus_path) as c:
            return await c.list_manuals()

    manuals = _run(go())
    assert {m.manual for m in manuals} == {"peg", "tm", "designs"}


def test_get_section_by_canonical_key(corpus_path: Path):
    async def go():
        async with IposManualsClient(corpus_path=corpus_path) as c:
            return await c.get_section(manual="peg", section_label="1.5.3")

    section = _run(go())
    assert section is not None
    assert section.short_name == "PEG"
    assert section.section_label == "1.5.3"
    assert "Inventive Step" in section.title  # type: ignore[arg-type]
    assert "obvious" in section.text


def test_get_section_by_alias(corpus_path: Path):
    async def go():
        async with IposManualsClient(corpus_path=corpus_path) as c:
            return await c.get_section(
                manual="Patent Examination Guidelines",
                section_label="1.5.3",
            )

    section = _run(go())
    assert section is not None
    assert section.manual == "peg"


def test_get_section_missing_returns_none(corpus_path: Path):
    async def go():
        async with IposManualsClient(corpus_path=corpus_path) as c:
            return await c.get_section(manual="peg", section_label="99")

    assert _run(go()) is None


def test_get_by_citation_round_trip(corpus_path: Path):
    async def go():
        async with IposManualsClient(corpus_path=corpus_path) as c:
            return await c.get_by_citation("IPOS PEG 1.5.3")

    section = _run(go())
    assert section is not None
    assert section.section_label == "1.5.3"
    assert section.manual == "peg"


def test_get_by_citation_unparseable_returns_none(corpus_path: Path):
    async def go():
        async with IposManualsClient(corpus_path=corpus_path) as c:
            return await c.get_by_citation("not a citation")

    assert _run(go()) is None


def test_search_scoped_by_manual(corpus_path: Path):
    async def go():
        async with IposManualsClient(corpus_path=corpus_path) as c:
            return await c.search("inventive", manual="peg")

    response = _run(go())
    assert response.hits
    assert all(h.manual == "peg" for h in response.hits)
    assert "<mark>" in response.hits[0].snippet


def test_search_unscoped(corpus_path: Path):
    async def go():
        async with IposManualsClient(corpus_path=corpus_path) as c:
            return await c.search("distinctive")

    response = _run(go())
    assert any(h.manual == "tm" for h in response.hits)


def test_search_blank_query_returns_empty(corpus_path: Path):
    async def go():
        async with IposManualsClient(corpus_path=corpus_path) as c:
            return await c.search("")

    response = _run(go())
    assert response.hits == []
    assert response.has_more is False


def test_search_pagination(corpus_path: Path):
    async def go():
        async with IposManualsClient(corpus_path=corpus_path) as c:
            return await c.search("the", per_page=1)

    response = _run(go())
    assert len(response.hits) == 1
    assert response.has_more is True


def test_missing_corpus_raises_with_install_hint(tmp_path: Path):
    missing = tmp_path / "absent.db"

    async def go():
        async with IposManualsClient(corpus_path=missing) as c:
            await c.list_manuals()

    with pytest.raises(CorpusUnavailable, match="build-ipos-manuals-corpus"):
        _run(go())


def test_meta_round_trip(corpus_path: Path):
    async def go():
        async with IposManualsClient(corpus_path=corpus_path) as c:
            return await c.meta()

    meta = _run(go())
    assert meta.schema_version == SCHEMA_VERSION
    assert meta.section_count == len(FIXTURES)
    assert meta.manual_count == 3
    assert meta.snapshot_date == "2026-05-16"
