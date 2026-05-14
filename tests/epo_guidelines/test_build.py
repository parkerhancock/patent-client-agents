"""Tests for the EPO Guidelines build helpers."""

from __future__ import annotations

from patent_client_agents.epo_guidelines.corpus.build import (
    _enumerate_section_paths,
    _extract_main_content,
    _part_from_slug,
    _section_number_from_slug,
    _slug_from_path,
)


class TestSectionNumberFromSlug:
    def test_part_only(self) -> None:
        assert _section_number_from_slug("a") == "A"
        assert _section_number_from_slug("h") == "H"

    def test_part_chapter(self) -> None:
        assert _section_number_from_slug("g_ii") == "G-II"
        assert _section_number_from_slug("a_iv") == "A-IV"

    def test_part_chapter_section(self) -> None:
        assert _section_number_from_slug("g_ii_3") == "G-II, 3"

    def test_part_chapter_section_subsection(self) -> None:
        assert _section_number_from_slug("g_ii_3_1") == "G-II, 3.1"
        assert _section_number_from_slug("f_iv_4_5_2") == "F-IV, 4.5.2"


class TestPartFromSlug:
    def test_extracts_part(self) -> None:
        assert _part_from_slug("g_ii_3_1") == "G"
        assert _part_from_slug("a") == "A"


class TestSlugFromPath:
    def test_strips_path_and_extension(self) -> None:
        assert _slug_from_path("/en/legal/guidelines-epc/2024/g_ii_3_1.html") == "g_ii_3_1"
        assert _slug_from_path("g_ii.html") == "g_ii"

    def test_returns_none_for_non_slug(self) -> None:
        assert _slug_from_path("/some/other/page.html") is None
        assert _slug_from_path("index.html") is None


class TestEnumerateSectionPaths:
    def test_extracts_relative_and_absolute_links(self) -> None:
        html = """
        <a href="/en/legal/guidelines-epc/2024/a_i.html">A-I</a>
        <a href="g_ii_3_1.html">3.1</a>
        <a href="g_ii_3.html">3</a>
        <a href="https://www.epo.org/en/legal/guidelines-epc/2024/h.html">H</a>
        <a href="/some/non-guideline/page.html">no</a>
        """
        paths = _enumerate_section_paths(html)
        assert paths == {"a_i.html", "g_ii_3_1.html", "g_ii_3.html", "h.html"}


class TestExtractMainContent:
    def test_uses_h1_as_title(self) -> None:
        html = """
        <html><body>
          <main>
            <h1>3.1 Discoveries</h1>
            <p>Discoveries as such are not inventions.</p>
          </main>
        </body></html>
        """
        frag, text, title = _extract_main_content(html)
        assert title == "3.1 Discoveries"
        assert "Discoveries as such" in text
        assert "<main>" in frag
