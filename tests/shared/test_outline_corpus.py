"""Tests for the shared outline-corpus layer and the epo.org crawler."""

from __future__ import annotations

import asyncio
import importlib
import re
import sqlite3
import warnings
from pathlib import Path

import httpx2
import pytest

from mcp_data_core.corpus_db import OutlineCorpusDB
from patent_client_agents import fts_query as legacy_fts_query
from patent_client_agents.shared.corpus import epo_legal
from patent_client_agents.shared.corpus.fts_query import translate_fts_query
from patent_client_agents.shared.corpus.outline import (
    OUTLINE_DDL,
    OutlineCorpusClient,
    OutlineSearchHit,
    OutlineSearchResponse,
    OutlineSection,
    OutlineVersion,
    init_outline_corpus,
    insert_outline_section,
    outline_meta_keys,
)
from patent_client_agents.shared.corpus.outline import api as outline_api
from patent_client_agents.shared.errors import SectionNotFoundError
from tests.corpus_build_support import read_corpus, serve, today

OUTLINE_PACKAGES = [
    "mpep",
    "tmep",
    "epc",
    "epo_guidelines",
    "epo_pct_guidelines",
    "epo_up_guidelines",
    "epo_case_law",
    "ukipo_mopp",
]


# --- schema and write helpers ------------------------------------------------


@pytest.mark.parametrize("pkg", OUTLINE_PACKAGES)
def test_every_outline_package_uses_the_shared_ddl(pkg: str) -> None:
    schema = importlib.import_module(f"patent_client_agents.{pkg}.corpus.schema")
    assert schema.DDL == OUTLINE_DDL
    assert schema.SCHEMA_VERSION == 1


def test_outline_meta_keys_names_the_source() -> None:
    keys = outline_meta_keys("EPC")
    assert keys["source_version"] == "EPC version label as reported by eEPC"
    assert set(keys) == {"schema_version", "snapshot_date", "source_version", "section_count"}


def _write_corpus(path: Path, rows: list[tuple[str, str | None, str, str | None, str]]) -> None:
    conn = sqlite3.connect(path)
    try:
        init_outline_corpus(conn, [("snapshot_date", "2025-01-02"), ("edition_year", "2024")])
        for href, number, title, chapter, text in rows:
            insert_outline_section(
                conn,
                href=href,
                section_number=number,
                title=title,
                breadcrumb=None,
                chapter=chapter,
                html=f"<p>{text}</p>",
                text=text,
            )
        conn.commit()
    finally:
        conn.close()


def test_insert_outline_section_replaces_on_href(tmp_path: Path) -> None:
    path = tmp_path / "c.db"
    _write_corpus(path, [("a", "1", "old", None, "old"), ("a", "1", "new", None, "new")])
    rows, meta = read_corpus(path, columns="href, title, text")
    assert [tuple(r) for r in rows] == [("a", "new", "new")]
    assert meta == {"snapshot_date": "2025-01-02", "edition_year": "2024"}


# --- client ------------------------------------------------------------------


class _DB(OutlineCorpusDB):
    LABEL = "TEST"
    ENV_VAR = "TEST_OUTLINE_CORPUS_PATH"
    DEFAULT_FILENAME = "test_outline.db"
    BUILD_COMMAND = "build-test-outline"


class _Hit(OutlineSearchHit):
    pass


class _Response(OutlineSearchResponse):
    hits: list[_Hit]


class _NumberClient(OutlineCorpusClient[_Response, OutlineSection, OutlineVersion]):
    CORPUS_DB = _DB
    HIT_MODEL = _Hit
    RESPONSE_MODEL = _Response
    SECTION_MODEL = OutlineSection
    VERSION_MODEL = OutlineVersion
    DEFAULT_BASE_URL = "https://example.test/"
    CACHE_NAME = "test"
    NOT_FOUND_LABEL = "TEST"
    SECTION_NUMBER_PATTERN = re.compile(r"^\d+(\.\d+)?$")

    def _normalize_href(self, value: str) -> str:
        return value.strip().removesuffix(".html")

    def _result_url(self, href: str, edition: str | None) -> str:
        return f"{self.base_url}/{href}?e={edition}"


class _SlugClient(epo_legal.EpoLegalClient[_Response, OutlineSection, OutlineVersion]):
    CORPUS_DB = _DB
    HIT_MODEL = _Hit
    RESPONSE_MODEL = _Response
    SECTION_MODEL = OutlineSection
    VERSION_MODEL = OutlineVersion
    DEFAULT_BASE_URL = "https://www.epo.org"
    CACHE_NAME = "test"
    NOT_FOUND_LABEL = "Test Book"
    BOOK = "test-book"
    DEFAULT_VERSION = "1999"
    EDITION_META_KEY = "edition_year"
    CHAPTER_LABEL = "{}"

    def _citation_to_slug(self, section: str) -> str | None:
        m = re.fullmatch(r"Part (\d+)", section)
        return f"p{m.group(1)}" if m else None

    def _section_number_for_slug(self, slug: str) -> str | None:
        return f"Number {slug}"


ROWS = [
    ("s1", "1", "First", "A", "alpha common"),
    ("s2", "2", "Second", "A", "beta common"),
    ("s3", "Number p3", "Third", None, "gamma common"),
]


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    path = tmp_path / "outline.db"
    _write_corpus(path, ROWS)
    return path


async def test_number_client_looks_up_section_numbers_then_hrefs(corpus: Path) -> None:
    async with _NumberClient(corpus_path=corpus) as client:
        assert client.base_url == "https://example.test"
        assert (await client.get_section("2")).href == "s2"
        assert (await client.get_section("s1.html")).title == "First"
        with pytest.raises(SectionNotFoundError, match="Could not find TEST section '9'"):
            await client.get_section("9")
        with pytest.raises(SectionNotFoundError, match="Could not find TEST href 'zz'"):
            await client.get_section("zz")
        assert await client.resolve_section_href("1") == "s1"
        assert await client.resolve_section_href("9") is None


async def test_search_pages_with_one_extra_row(corpus: Path) -> None:
    async with _NumberClient(corpus_path=corpus) as client:
        first = await client.search("common", syntax="and", sort="outline", per_page=2)
        assert [h.href for h in first.hits] == ["s1", "s2"]
        assert first.has_more is True
        assert isinstance(first, _Response)
        assert first.hits[0].title == "1 - First"
        assert first.hits[0].path == ["Chapter A", "1"]
        assert first.hits[0].result_url == "https://example.test/s1?e=None"
        second = await client.search("common", syntax="and", sort="outline", per_page=2, page=2)
        assert [h.href for h in second.hits] == ["s3"]
        assert second.has_more is False
        by_offset = await client.search("common", syntax="and", sort="outline", offset=1)
        assert [h.href for h in by_offset.hits] == ["s2", "s3"]
        empty = await client.search("   ")
        assert empty.hits == [] and empty.has_more is False


async def test_list_versions_uses_snapshot(corpus: Path) -> None:
    async with _NumberClient(corpus_path=corpus) as client:
        [version] = await client.list_versions()
    assert version.label == "current (snapshot 2025-01-02)"
    assert version.value == "current" and version.current


async def test_missing_corpus_raises_on_first_call(tmp_path: Path) -> None:
    client = _NumberClient(corpus_path=tmp_path / "missing.db")
    with pytest.raises(RuntimeError, match="TEST corpus not found"):
        await client.search("x")


async def test_epo_client_tries_citation_slug_then_section_number_then_href(
    corpus: Path,
) -> None:
    async with _SlugClient(corpus_path=corpus) as client:
        # "Part 3" → slug "p3" (no such href) → section_number "Number p3".
        assert (await client.get_section("Part 3")).href == "s3"
        assert (
            await client.get_section("https://www.epo.org/en/legal/test-book/2024/S2.html")
        ).href == "s2"
        with pytest.raises(SectionNotFoundError, match="Could not find Test Book section 'x'"):
            await client.get_section("x")
        result = await client.search("alpha")
        assert result.hits[0].result_url == "https://www.epo.org/en/legal/test-book/2024/s1.html"
        assert result.hits[0].path == ["A", "1"]
        [version] = await client.list_versions()
        assert version.label == "2024 edition (snapshot 2025-01-02)"


def test_normalize_epo_href() -> None:
    assert epo_legal.normalize_epo_href(" /en/legal/epc/2020/A54.html ", "epc") == "a54"
    assert epo_legal.normalize_epo_href("legal/case-law/2022/clr_i", "case-law") == "clr_i"
    assert epo_legal.normalize_epo_href("a54", "guidelines-epc") == "a54"


def test_guidelines_citations() -> None:
    assert epo_legal.guidelines_citation_to_slug("G-II, 3.1") == "g_ii_3_1"
    assert epo_legal.guidelines_citation_to_slug("a") == "a"
    assert epo_legal.guidelines_citation_to_slug("Z-1") is None
    assert epo_legal.guidelines_section_number("f_iv_4_5") == "F-IV, 4.5"


# --- api helpers -------------------------------------------------------------


class _SearchInput(outline_api.OutlineSearchInput):
    pass


class _SectionInput(outline_api.OutlineSectionInput):
    """Input for a test section."""


async def _search_via_wrapper(params: _SearchInput, client: _NumberClient) -> _Response:
    # Stands in for a package's ``api.search``.
    return await outline_api.search(_NumberClient, params, client=client)


async def test_api_search_forwards_every_input_field(corpus: Path) -> None:
    seen: dict[str, object] = {}

    class Recording(_NumberClient):
        async def search(self, query: str, **kwargs: object) -> _Response:
            seen.update(query=query, **kwargs)
            return _Response(hits=[], page=1, per_page=10, has_more=False)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        await _search_via_wrapper(_SearchInput(query="q", page=3), Recording(corpus_path=corpus))
    assert seen["include_content"] is True
    assert seen["include_form_paragraphs"] is False
    assert seen["page"] == 3
    [warning] = caught
    assert warning.category is DeprecationWarning
    assert "async with _NumberClient()" in str(warning.message)
    # Attributed to whoever called the package-level wrapper.
    assert warning.filename == __file__


async def test_api_get_section_without_client_opens_its_own(
    monkeypatch: pytest.MonkeyPatch, corpus: Path
) -> None:
    monkeypatch.setenv("TEST_OUTLINE_CORPUS_PATH", str(corpus))
    section = await outline_api.get_section(_NumberClient, _SectionInput(href="s1"))
    assert section.title == "First"
    [version] = await outline_api.list_versions(_NumberClient)
    assert version.current


def test_section_input_accepts_href_alias() -> None:
    assert _SectionInput(href="x").section == "x"
    assert _SectionInput(section="y", href="x").section == "y"
    assert _SectionInput.model_json_schema()["description"] == "Input for a test section."


# --- epo.org crawls ----------------------------------------------------------


def _book_pages(request: httpx2.Request) -> str | None:
    path = request.url.path
    if path.endswith("/toc.html"):
        return '<a href="x1.html"></a><a href="x2.html"></a><a href="x3.html"></a>'
    if path.endswith("/x2"):
        return None  # 404: skipped
    name = path.rsplit("/", 1)[-1]
    return f"<html><main><nav>menu</nav><h1>Title {name}</h1><p>Body {name}</p></main></html>"


async def _discover(client: httpx2.AsyncClient, base_path: str) -> list[str]:
    toc = await epo_legal.fetch_text(client, f"{base_path}/toc.html")
    return sorted(set(re.findall(r'href="(x\d)\.html"', toc)))


def test_build_book_corpus_skips_failed_pages(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    requested = serve(monkeypatch, _book_pages)
    out = tmp_path / "book.db"
    pages = epo_legal.BookPages(
        section_number_for=lambda slug: slug.upper(),
        chapter_for=lambda slug: None,
        page_suffix="",
    )
    count = asyncio.run(
        epo_legal.build_book_corpus(
            out, book="demo", year_key="demo_year", year="2030", pages=pages,
            discover=_discover, pause=0,
        )
    )  # fmt: skip
    assert count == 2
    rows, meta = read_corpus(out, columns="href, section_number, title, chapter, text")
    assert [tuple(r) for r in rows] == [
        ("x1", "X1", "Title x1", None, "Title x1Body x1"),
        ("x3", "X3", "Title x3", None, "Title x3Body x3"),
    ]
    assert meta == {
        "schema_version": "1",
        "source": "https://www.epo.org/en/legal/demo/2030",
        "snapshot_date": today(),
        "demo_year": "2030",
    }
    assert requested[-1] == "https://www.epo.org/en/legal/demo/2030/x3"


def _guidelines_pages(request: httpx2.Request) -> str | None:
    path = request.url.path
    if path == "/en/legal/guidelines-pct/2024/index.html":
        return '<a href="/en/legal/guidelines-pct/2024/a.html">A</a>'
    pages = {
        "a.html": '<main><h1>Part A</h1><p>Intro</p><a href="a_ii.html">x</a></main>',
        "a_ii.html": '<main><div class="breadcrumb">crumbs</div><h1>Chapter II</h1>'
        "<p>Body</p></main>",
    }
    return pages.get(path.rsplit("/", 1)[-1])


def test_build_guidelines_corpus_crawls_the_named_book(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    serve(monkeypatch, _guidelines_pages)
    out = tmp_path / "pct.db"
    count = asyncio.run(
        epo_legal.build_guidelines_corpus(
            out, book="guidelines-pct", guidelines_year="2024", pause=0
        )
    )
    assert count == 2
    rows, meta = read_corpus(out, columns="href, section_number, chapter, title, text")
    assert [tuple(r) for r in rows] == [
        ("a", "A", "A", "Part A", "Part AIntrox"),
        ("a_ii", "A-II", "A", "Chapter II", "Chapter IIBody"),
    ]
    assert meta["guidelines_year"] == "2024"
    assert meta["source"] == "https://www.epo.org/en/legal/guidelines-pct/2024"


# --- fts_query move ----------------------------------------------------------


def test_fts_query_old_import_path_still_works() -> None:
    assert legacy_fts_query.translate_fts_query is translate_fts_query
    assert translate_fts_query("art. 54", "and") == '"art." "54"'
