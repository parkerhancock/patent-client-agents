"""Tests for Google Patents figures parser."""

from __future__ import annotations

from lxml import html

from ip_tools.google_patents.parsers.figures import (
    _absolute_url,
    _extract_bounds,
    _extract_callouts,
    _extract_image_id,
    _infer_page_number,
    _parse_int,
    extract_figures,
)


class TestAbsoluteUrl:
    """Tests for _absolute_url function."""

    def test_returns_none_for_none(self) -> None:
        assert _absolute_url(None) is None

    def test_returns_none_for_empty(self) -> None:
        assert _absolute_url("") is None
        assert _absolute_url("   ") is None

    def test_adds_https_to_double_slash(self) -> None:
        result = _absolute_url("//example.com/path")
        assert result == "https://example.com/path"

    def test_adds_domain_to_single_slash(self) -> None:
        result = _absolute_url("/patent/US10123456B2")
        assert result == "https://patents.google.com/patent/US10123456B2"

    def test_returns_absolute_unchanged(self) -> None:
        result = _absolute_url("https://example.com/image.png")
        assert result == "https://example.com/image.png"


class TestParseInt:
    """Tests for _parse_int function."""

    def test_returns_none_for_none(self) -> None:
        assert _parse_int(None) is None

    def test_returns_none_for_empty(self) -> None:
        assert _parse_int("") is None
        assert _parse_int("   ") is None

    def test_parses_integer(self) -> None:
        assert _parse_int("42") == 42

    def test_parses_with_whitespace(self) -> None:
        assert _parse_int("  123  ") == 123

    def test_returns_none_for_invalid(self) -> None:
        assert _parse_int("abc") is None
        assert _parse_int("12.5") is None


class TestExtractImageId:
    """Tests for _extract_image_id function."""

    def test_returns_none_for_none(self) -> None:
        assert _extract_image_id(None) is None

    def test_returns_none_for_empty(self) -> None:
        assert _extract_image_id("") is None

    def test_extracts_from_url(self) -> None:
        url = "https://example.com/path/to/US10123456-D00001"
        result = _extract_image_id(url)
        assert result == "US10123456-D00001"

    def test_handles_trailing_slash(self) -> None:
        url = "https://example.com/path/to/image123/"
        result = _extract_image_id(url)
        assert result == "image123"


class TestExtractBounds:
    """Tests for _extract_bounds function."""

    def test_returns_empty_bounds_for_no_span(self) -> None:
        elem = html.fromstring("<li></li>")
        result = _extract_bounds(elem)
        assert result == {"left": None, "top": None, "right": None, "bottom": None}

    def test_extracts_bounds_values(self) -> None:
        elem = html.fromstring("""
            <li>
                <span itemprop="bounds">
                    <meta itemprop="left" content="10">
                    <meta itemprop="top" content="20">
                    <meta itemprop="right" content="100">
                    <meta itemprop="bottom" content="150">
                </span>
            </li>
        """)
        result = _extract_bounds(elem)
        assert result == {"left": 10, "top": 20, "right": 100, "bottom": 150}

    def test_handles_partial_bounds(self) -> None:
        elem = html.fromstring("""
            <li>
                <span itemprop="bounds">
                    <meta itemprop="left" content="10">
                    <meta itemprop="bottom" content="150">
                </span>
            </li>
        """)
        result = _extract_bounds(elem)
        assert result["left"] == 10
        assert result["top"] is None
        assert result["right"] is None
        assert result["bottom"] == 150


class TestInferPageNumber:
    """Tests for _infer_page_number function."""

    def test_uses_figure_page_meta(self) -> None:
        elem = html.fromstring("""
            <li>
                <meta itemprop="figurePage" content="5">
            </li>
        """)
        result = _infer_page_number(elem, None)
        assert result == 5

    def test_extracts_from_url_identifier(self) -> None:
        elem = html.fromstring("<li></li>")
        result = _infer_page_number(elem, "https://example.com/US12345-D00003")
        assert result == 3

    def test_handles_leading_zeros_in_url(self) -> None:
        elem = html.fromstring("<li></li>")
        result = _infer_page_number(elem, "https://example.com/US12345-D00010")
        assert result == 10

    def test_returns_none_when_not_found(self) -> None:
        elem = html.fromstring("<li></li>")
        result = _infer_page_number(elem, None)
        assert result is None


class TestExtractCallouts:
    """Tests for _extract_callouts function."""

    def test_returns_empty_for_no_callouts(self) -> None:
        elem = html.fromstring("<li></li>")
        result = _extract_callouts(elem)
        assert result == []

    def test_extracts_callout_data(self) -> None:
        elem = html.fromstring("""
            <li>
                <li itemprop="callouts">
                    <meta itemprop="figurePage" content="1">
                    <meta itemprop="id" content="ref123">
                    <meta itemprop="label" content="processor">
                    <span itemprop="bounds">
                        <meta itemprop="left" content="50">
                        <meta itemprop="top" content="100">
                    </span>
                </li>
            </li>
        """)
        result = _extract_callouts(elem)
        assert len(result) == 1
        assert result[0]["figure_page"] == 1
        assert result[0]["reference_id"] == "ref123"
        assert result[0]["label"] == "processor"
        assert result[0]["bounds"]["left"] == 50

    def test_extracts_multiple_callouts(self) -> None:
        elem = html.fromstring("""
            <li>
                <li itemprop="callouts">
                    <meta itemprop="id" content="ref1">
                    <meta itemprop="label" content="component A">
                </li>
                <li itemprop="callouts">
                    <meta itemprop="id" content="ref2">
                    <meta itemprop="label" content="component B">
                </li>
            </li>
        """)
        result = _extract_callouts(elem)
        assert len(result) == 2
        assert result[0]["reference_id"] == "ref1"
        assert result[1]["reference_id"] == "ref2"


class TestExtractFigures:
    """Tests for extract_figures function."""

    def test_returns_empty_for_no_figures(self) -> None:
        elem = html.fromstring("<html><body>No figures here</body></html>")
        result = extract_figures(elem)
        assert result == []

    def test_extracts_figure_with_thumbnail(self) -> None:
        elem = html.fromstring("""
            <html><body>
            <li itemprop="images">
                <img itemprop="thumbnail" src="//example.com/thumb.jpg">
                <meta itemprop="full" content="//example.com/full.jpg">
                <meta itemprop="figurePage" content="1">
            </li>
            </body></html>
        """)
        result = extract_figures(elem)
        assert len(result) == 1
        assert result[0]["index"] == 0
        assert result[0]["page_number"] == 1
        assert result[0]["thumbnail_url"] == "https://example.com/thumb.jpg"
        assert result[0]["full_image_url"] == "https://example.com/full.jpg"

    def test_skips_figures_without_images(self) -> None:
        elem = html.fromstring("""
            <html><body>
            <li itemprop="images">
                <span>No image here</span>
            </li>
            <li itemprop="images">
                <img itemprop="thumbnail" src="//example.com/thumb.jpg">
            </li>
            </body></html>
        """)
        result = extract_figures(elem)
        assert len(result) == 1
        assert result[0]["index"] == 1

    def test_extracts_multiple_figures(self) -> None:
        elem = html.fromstring("""
            <html><body>
            <li itemprop="images">
                <img itemprop="thumbnail" src="//example.com/fig1.jpg">
                <meta itemprop="figurePage" content="1">
            </li>
            <li itemprop="images">
                <img itemprop="thumbnail" src="//example.com/fig2.jpg">
                <meta itemprop="figurePage" content="2">
            </li>
            </body></html>
        """)
        result = extract_figures(elem)
        assert len(result) == 2
        assert result[0]["page_number"] == 1
        assert result[1]["page_number"] == 2

    def test_uses_full_as_fallback_for_thumbnail(self) -> None:
        elem = html.fromstring("""
            <html><body>
            <li itemprop="images">
                <meta itemprop="full" content="//example.com/full.jpg">
            </li>
            </body></html>
        """)
        result = extract_figures(elem)
        assert len(result) == 1
        assert result[0]["full_image_url"] == "https://example.com/full.jpg"

    def test_extracts_callouts_with_figure(self) -> None:
        elem = html.fromstring("""
            <html><body>
            <li itemprop="images">
                <img itemprop="thumbnail" src="//example.com/fig.jpg">
                <ul>
                    <li itemprop="callouts">
                        <meta itemprop="id" content="10">
                        <meta itemprop="label" content="main component">
                    </li>
                </ul>
            </li>
            </body></html>
        """)
        result = extract_figures(elem)
        assert len(result) == 1
        assert len(result[0]["callouts"]) == 1
        assert result[0]["callouts"][0]["reference_id"] == "10"
        assert result[0]["callouts"][0]["label"] == "main component"

    def test_extracts_image_id(self) -> None:
        elem = html.fromstring("""
            <html><body>
            <li itemprop="images">
                <meta itemprop="full" content="//example.com/patents/US12345-D00001">
            </li>
            </body></html>
        """)
        result = extract_figures(elem)
        assert result[0]["image_id"] == "US12345-D00001"
