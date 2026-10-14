"""Tests for the MoPP build helpers and an offline build smoke test."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from patent_client_agents.ukipo_mopp.corpus.build import (
    _enumerate_section_paths,
    _extract_main_content,
    _slug_to_section_number,
    _slug_to_title,
    build_corpus,
)
from tests.corpus_build_support import read_corpus, serve, today


class TestSlugToSectionNumber:
    def test_simple_section(self) -> None:
        assert _slug_to_section_number("section-1-patentability") == "1"

    def test_two_digit_section(self) -> None:
        assert _slug_to_section_number("section-14-the-application") == "14"

    def test_three_digit_section(self) -> None:
        assert _slug_to_section_number("section-100-burden-of-proof-in-certain-cases") == "100"

    def test_alphanumeric_section_with_leading_dash(self) -> None:
        # gov.uk's MoPP table of contents emits this exact form.
        assert _slug_to_section_number("-section-4a-methods-of-treatment-or-diagnosis") == "4A"

    def test_non_section_slug_returns_none(self) -> None:
        assert _slug_to_section_number("glossary-of-terms-and-abbreviations") is None
        assert _slug_to_section_number("table-of-cases") is None
        assert _slug_to_section_number("changes-to-the-manual-of-patent-practice") is None


class TestSlugToTitle:
    def test_section_slug(self) -> None:
        # Slug words below the section number stay lowercase — gov.uk
        # slugs are all lowercase to begin with; we only capitalize the
        # first character of the title for display.
        assert _slug_to_title("section-14-the-application") == "Section 14: the application"

    def test_alphanumeric_section_slug(self) -> None:
        assert (
            _slug_to_title("-section-4a-methods-of-treatment-or-diagnosis")
            == "Section 4A: methods of treatment or diagnosis"
        )

    def test_non_section_slug(self) -> None:
        assert _slug_to_title("glossary-of-terms") == "Glossary of terms"


class TestEnumerateSectionPaths:
    def test_extracts_unique_section_paths(self) -> None:
        html = """
        <ul>
          <li><a href="/guidance/manual-of-patent-practice-mopp/section-1-patentability">1</a></li>
          <li><a href="/guidance/manual-of-patent-practice-mopp/section-1-patentability">dup</a></li>
          <li><a href="/guidance/manual-of-patent-practice-mopp/section-14-the-application">14</a></li>
          <li><a href="/some/other/page">no</a></li>
          <li><a href="/guidance/manual-of-patent-practice-mopp">landing</a></li>
        </ul>
        """
        paths = _enumerate_section_paths(html)
        assert paths == [
            "/guidance/manual-of-patent-practice-mopp/section-1-patentability",
            "/guidance/manual-of-patent-practice-mopp/section-14-the-application",
        ]


class TestExtractMainContent:
    def test_picks_up_h2_as_title(self) -> None:
        html = """
        <html><body>
          <main>
            <h1>Manual of Patent Practice</h1>
            <h2>Section 1: Patentability</h2>
            <p>Body paragraph one.</p>
            <p>Body paragraph two.</p>
          </main>
        </body></html>
        """
        frag, text, title = _extract_main_content(html)
        assert title == "Section 1: Patentability"
        assert "Body paragraph one" in text
        assert "Body paragraph two" in text
        assert "<main>" in frag

    def test_returns_empty_when_no_main(self) -> None:
        frag, text, title = _extract_main_content("<html><body><div>orphan</div></body></html>")
        assert frag == ""
        assert text == ""
        assert title is None


_INDEX = "/guidance/manual-of-patent-practice-mopp"
_PAGES = {
    _INDEX: (
        f'<a href="{_INDEX}/section-1-patentability">s1</a>'
        f'<a href="{_INDEX}/-section-4a-methods-of-treatment">s4A</a>'
        f'<a href="{_INDEX}">self</a>'
    ),
    f"{_INDEX}/section-1-patentability": (
        "<main><h1>Manual of Patent Practice</h1><h2>Section 1: Patentability</h2>"
        "<p>Inventions.</p><form>search</form></main>"
    ),
    f"{_INDEX}/-section-4a-methods-of-treatment": "<main><p>Methods of treatment.</p></main>",
}


def _pages(request: httpx.Request) -> str | None:
    return _PAGES.get(request.url.path)


def test_build_corpus_end_to_end(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    serve(monkeypatch, _pages)
    out = tmp_path / "mopp.db"

    count = asyncio.run(build_corpus(out, pause=0))

    assert count == 2
    rows, meta = read_corpus(out, columns="href, section_number, title, text")
    assert [tuple(row)[:3] for row in rows] == [
        ("-section-4a-methods-of-treatment", "4A", "Section 4A: methods of treatment"),
        ("section-1-patentability", "1", "Section 1: Patentability"),
    ]
    assert "search" not in rows[1]["text"]
    assert meta["source"] == f"https://www.gov.uk{_INDEX}"
    assert meta["snapshot_date"] == today()
    assert "source_version" not in meta
