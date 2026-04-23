"""Tests for MPEP HTML transformers."""

from __future__ import annotations

from patent_client_agents.mpep.transformers import (
    _build_path,
    parse_search_response,
    parse_section_html,
    parse_versions,
)


class TestParseSearchResponse:
    """Tests for parse_search_response function."""

    def test_parses_search_results(self) -> None:
        payload = {
            "list": """
                <ul>
                    <li><span>Chapter 700</span>
                        <ul>
                            <li><a href="#/result/0700?q=patent">§701 Patent Examination</a></li>
                        </ul>
                    </li>
                </ul>
            """
        }
        result = parse_search_response(payload, "https://mpep.uspto.gov", page=1, per_page=10)
        assert len(result.hits) == 1
        assert result.hits[0].title == "§701 Patent Examination"
        assert result.hits[0].href == "0700"
        assert result.page == 1
        assert result.per_page == 10

    def test_handles_empty_results(self) -> None:
        payload = {"list": "<div></div>"}
        result = parse_search_response(payload, "https://mpep.uspto.gov", page=1, per_page=10)
        assert len(result.hits) == 0
        assert result.has_more is False

    def test_handles_missing_list(self) -> None:
        payload = {}
        result = parse_search_response(payload, "https://mpep.uspto.gov", page=1, per_page=10)
        assert len(result.hits) == 0

    def test_has_more_when_full_page(self) -> None:
        # Create 10 links to trigger has_more
        links = "".join(
            f'<li><a href="#/result/070{i}?q=test">Section {i}</a></li>' for i in range(10)
        )
        payload = {"list": f"<ul>{links}</ul>"}
        result = parse_search_response(payload, "https://mpep.uspto.gov", page=1, per_page=10)
        assert result.has_more is True

    def test_builds_result_url(self) -> None:
        payload = {"list": '<ul><li><a href="#/result/0700?q=test">Section</a></li></ul>'}
        result = parse_search_response(payload, "https://mpep.uspto.gov", page=1, per_page=10)
        assert "RDMS/MPEP" in result.hits[0].result_url


class TestParseSectionHtml:
    """Tests for parse_section_html function."""

    def test_extracts_title(self) -> None:
        html = """
            <html>
                <body>
                    <h1>§702 Patent Examination Process</h1>
                    <p>Content here</p>
                </body>
            </html>
        """
        result = parse_section_html(html, version="current", href="0702")
        assert result.title == "§702 Patent Examination Process"

    def test_extracts_text_content(self) -> None:
        html = """
            <html>
                <body>
                    <h1>Title</h1>
                    <p>Paragraph one.</p>
                    <p>Paragraph two.</p>
                </body>
            </html>
        """
        result = parse_section_html(html, version="current", href="0702")
        assert "Paragraph one" in result.text
        assert "Paragraph two" in result.text

    def test_removes_scripts_and_styles(self) -> None:
        html = """
            <html>
                <head>
                    <script>console.log('secret');</script>
                    <style>.hidden { display: none; }</style>
                </head>
                <body>
                    <p>Visible content</p>
                </body>
            </html>
        """
        result = parse_section_html(html, version="current", href="test")
        assert "secret" not in result.text
        assert "hidden" not in result.text
        assert "Visible content" in result.text

    def test_preserves_href_and_version(self) -> None:
        html = "<html><body><h1>Title</h1></body></html>"
        result = parse_section_html(html, version="R-09.2019", href="0700/0701")
        assert result.version == "R-09.2019"
        assert result.href == "0700/0701"

    def test_handles_missing_title(self) -> None:
        html = "<html><body><p>No heading here</p></body></html>"
        result = parse_section_html(html, version="current", href="test")
        assert result.title is None


class TestParseVersions:
    """Tests for parse_versions function."""

    def test_parses_version_select(self) -> None:
        html = """
            <html>
                <body>
                    <select id="edition-select">
                        <option value="/current" selected>Current Edition</option>
                        <option value="/R-09.2019">R-09.2019</option>
                        <option value="/R-11.2013">R-11.2013</option>
                    </select>
                </body>
            </html>
        """
        result = parse_versions(html)
        assert len(result) == 3
        assert result[0].label == "Current Edition"
        assert result[0].value == "current"
        assert result[0].current is True
        assert result[1].label == "R-09.2019"
        assert result[1].value == "R-09.2019"
        assert result[1].current is False

    def test_handles_missing_select(self) -> None:
        html = "<html><body><p>No select here</p></body></html>"
        result = parse_versions(html)
        assert result == []

    def test_strips_leading_slash(self) -> None:
        html = """
            <select id="edition-select">
                <option value="/R-09.2019">September 2019</option>
            </select>
        """
        result = parse_versions(html)
        assert result[0].value == "R-09.2019"


class TestBuildPath:
    """Tests for _build_path helper."""

    def test_builds_path_from_ancestors(self) -> None:
        from lxml import html as lxml_html

        tree = lxml_html.fromstring("""
            <ul>
                <li><span>Chapter 700</span>
                    <ul>
                        <li><span>Section 701</span>
                            <a href="#test">Link</a>
                        </li>
                    </ul>
                </li>
            </ul>
        """)
        anchor = tree.cssselect("a")[0]
        path = _build_path(anchor)
        # Path should include ancestor spans
        assert len(path) >= 1
