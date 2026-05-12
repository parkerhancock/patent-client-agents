"""Tests for TMEP transformers."""

from patent_client_agents.tmep.transformers import (
    parse_search_response,
    parse_section_html,
    parse_versions,
)


class TestParseSearchResponse:
    """Tests for parse_search_response."""

    def test_parses_hits_from_list(self) -> None:
        """Test parsing search hits from list HTML."""
        payload = {
            "list": """
<ul>
  <li><a href="#/result/TMEP-1200d1e8145.html?q=test">1207.01 - Section Title</a></li>
  <li><a href="#/result/TMEP-1200d1e8200.html?q=test">1207.02 - Another Section</a></li>
</ul>
            """,
            "content": "<p>Search results content</p>",
        }
        response = parse_search_response(
            payload, base_url="https://tmep.uspto.gov", page=1, per_page=10
        )
        assert len(response.hits) == 2
        assert response.hits[0].title == "1207.01 - Section Title"
        assert response.hits[0].href == "TMEP-1200d1e8145.html"
        assert response.hits[1].href == "TMEP-1200d1e8200.html"

    def test_empty_list_returns_no_hits(self) -> None:
        """Test that empty list returns no hits."""
        payload = {"list": "<ul></ul>", "content": ""}
        response = parse_search_response(
            payload, base_url="https://tmep.uspto.gov", page=1, per_page=10
        )
        assert len(response.hits) == 0
        assert response.has_more is False

    def test_has_more_when_full_page(self) -> None:
        """Test that has_more is True when page is full."""
        # Create payload with 10 hits
        links = "\n".join(
            f'<li><a href="#/result/TMEP-{i}.html?q=test">Section {i}</a></li>' for i in range(10)
        )
        payload = {"list": f"<ul>{links}</ul>", "content": ""}
        response = parse_search_response(
            payload, base_url="https://tmep.uspto.gov", page=1, per_page=10
        )
        assert response.has_more is True


class TestParseSectionHtml:
    """Tests for parse_section_html."""

    def test_extracts_content(self) -> None:
        """Test extracting content from section HTML."""
        html = """
            <html>
            <head><script>var x=1;</script></head>
            <body>
                <h1>1207.01 - Likelihood of Confusion</h1>
                <p>This section discusses likelihood of confusion.</p>
            </body>
            </html>
        """
        section = parse_section_html(html, version="current", href="TMEP-1200d1e8145.html")
        assert section.title == "1207.01 - Likelihood of Confusion"
        assert "likelihood of confusion" in section.text.lower()
        assert section.version == "current"
        assert section.href == "TMEP-1200d1e8145.html"

    def test_removes_script_tags(self) -> None:
        """Test that script tags are removed."""
        html = "<html><body><script>alert('bad');</script><p>Good content</p></body></html>"
        section = parse_section_html(html, version="current", href="test.html")
        assert "alert" not in section.html
        assert "Good content" in section.text


class TestParseVersions:
    """Tests for parse_versions."""

    def test_parses_version_dropdown(self) -> None:
        """Test parsing versions from select dropdown."""
        html = """
            <html>
            <body>
                <select id="edition-select">
                    <option value="/Nov2025" selected>November 2025</option>
                    <option value="/Oct2024">October 2024</option>
                    <option value="/May2024">May 2024</option>
                </select>
            </body>
            </html>
        """
        versions = parse_versions(html)
        assert len(versions) == 3
        assert versions[0].label == "November 2025"
        assert versions[0].value == "Nov2025"
        assert versions[0].current is True
        assert versions[1].current is False

    def test_empty_when_no_select(self) -> None:
        """Test returns empty list when no select found."""
        html = "<html><body><p>No dropdown here</p></body></html>"
        versions = parse_versions(html)
        assert len(versions) == 0
