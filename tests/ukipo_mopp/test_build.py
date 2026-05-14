"""Tests for the MoPP build helpers (slug parsing, content extraction)."""

from __future__ import annotations

from patent_client_agents.ukipo_mopp.corpus.build import (
    _enumerate_section_paths,
    _extract_main_content,
    _slug_to_section_number,
    _slug_to_title,
)


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
