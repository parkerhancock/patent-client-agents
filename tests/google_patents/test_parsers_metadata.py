"""Tests for Google Patents metadata parser."""

from __future__ import annotations

import re

from lxml import html

from ip_tools.google_patents.parsers.metadata import (
    _dd_text,
    _event_entries,
    _extract_abstract,
    _extract_title,
    _find_dt,
    _first_attr,
    _first_text,
    _text,
)


class TestText:
    """Tests for _text function."""

    def test_returns_text_content(self) -> None:
        elem = html.fromstring("<div>Hello World</div>")
        assert _text(elem) == "Hello World"

    def test_strips_whitespace(self) -> None:
        elem = html.fromstring("<div>   Hello   </div>")
        assert _text(elem) == "Hello"

    def test_returns_empty_for_none(self) -> None:
        assert _text(None) == ""

    def test_handles_nested_text(self) -> None:
        elem = html.fromstring("<div>Hello <b>World</b></div>")
        assert _text(elem) == "Hello World"


class TestFirstText:
    """Tests for _first_text function."""

    def test_returns_first_match(self) -> None:
        elem = html.fromstring("<div><span>First</span><span>Second</span></div>")
        assert _first_text(elem, "//span") == "First"

    def test_returns_empty_for_no_match(self) -> None:
        elem = html.fromstring("<div>text</div>")
        assert _first_text(elem, "//span") == ""

    def test_handles_string_result(self) -> None:
        elem = html.fromstring("<div><span title='value'>text</span></div>")
        assert _first_text(elem, "//span/@title") == "value"

    def test_strips_string_result(self) -> None:
        elem = html.fromstring("<div><span title='  value  '>text</span></div>")
        assert _first_text(elem, "//span/@title") == "value"


class TestFirstAttr:
    """Tests for _first_attr function."""

    def test_returns_attribute_value(self) -> None:
        elem = html.fromstring("<div><a href='http://example.com'>link</a></div>")
        assert _first_attr(elem, "//a", "href") == "http://example.com"

    def test_returns_none_for_no_match(self) -> None:
        elem = html.fromstring("<div>text</div>")
        assert _first_attr(elem, "//a", "href") is None

    def test_returns_none_for_missing_attribute(self) -> None:
        elem = html.fromstring("<div><a>link</a></div>")
        assert _first_attr(elem, "//a", "href") is None

    def test_returns_none_for_empty_attribute(self) -> None:
        elem = html.fromstring("<div><a href=''>link</a></div>")
        assert _first_attr(elem, "//a", "href") is None

    def test_strips_whitespace(self) -> None:
        elem = html.fromstring("<div><a href='  http://example.com  '>link</a></div>")
        assert _first_attr(elem, "//a", "href") == "http://example.com"


class TestFindDt:
    """Tests for _find_dt function."""

    def test_finds_matching_dt(self) -> None:
        elem = html.fromstring("""
            <dl>
                <dt>Priority</dt><dd>2020-01-01</dd>
                <dt>Filed</dt><dd>2021-01-01</dd>
            </dl>
        """)
        pattern = re.compile(r"Priority")
        result = _find_dt(elem, pattern)
        assert result is not None
        assert _text(result) == "Priority"

    def test_returns_none_for_no_match(self) -> None:
        elem = html.fromstring("<dl><dt>Other</dt><dd>value</dd></dl>")
        pattern = re.compile(r"Priority")
        assert _find_dt(elem, pattern) is None

    def test_handles_case_insensitive(self) -> None:
        elem = html.fromstring("<dl><dt>PRIORITY DATE</dt><dd>value</dd></dl>")
        pattern = re.compile(r"priority", re.IGNORECASE)
        result = _find_dt(elem, pattern)
        assert result is not None


class TestDdText:
    """Tests for _dd_text function."""

    def test_returns_dd_text(self) -> None:
        elem = html.fromstring("""
            <dl>
                <dt id="test">Label</dt><dd>Value</dd>
            </dl>
        """)
        dt = elem.xpath("//dt[@id='test']")[0]
        assert _dd_text(dt) == "Value"

    def test_returns_empty_for_none(self) -> None:
        assert _dd_text(None) == ""

    def test_skips_non_dd_siblings(self) -> None:
        elem = html.fromstring("""
            <dl>
                <dt id="test">Label</dt>
                <span>skip</span>
                <dd>Value</dd>
            </dl>
        """)
        dt = elem.xpath("//dt[@id='test']")[0]
        assert _dd_text(dt) == "Value"


class TestEventEntries:
    """Tests for _event_entries function."""

    def test_returns_dd_elements(self) -> None:
        elem = html.fromstring("""
            <html>
            <section itemprop="events">
                <dl>
                    <dt>Event 1</dt><dd>Date 1</dd>
                    <dt>Event 2</dt><dd>Date 2</dd>
                </dl>
            </section>
            </html>
        """)
        result = _event_entries(elem)
        assert len(result) == 2

    def test_returns_empty_for_no_events(self) -> None:
        elem = html.fromstring("<html><body>no events</body></html>")
        assert _event_entries(elem) == []


class TestExtractTitle:
    """Tests for _extract_title function."""

    def test_extracts_from_meta(self) -> None:
        elem = html.fromstring("""
            <html>
            <head>
                <meta name="DC.title" content="Patent Title Here">
            </head>
            </html>
        """)
        assert _extract_title(elem) == "Patent Title Here"

    def test_falls_back_to_title_tag(self) -> None:
        elem = html.fromstring("""
            <html>
            <head><title>US12345 - Actual Patent Title - Google Patents</title></head>
            </html>
        """)
        result = _extract_title(elem)
        assert result == "Actual Patent Title"

    def test_returns_default_for_missing(self) -> None:
        elem = html.fromstring("<html><head></head></html>")
        assert _extract_title(elem) == "Title not found"


class TestExtractAbstract:
    """Tests for _extract_abstract function."""

    def test_extracts_from_meta(self) -> None:
        elem = html.fromstring("""
            <html>
            <head>
                <meta name="description" content="This is the abstract text.">
            </head>
            </html>
        """)
        assert _extract_abstract(elem) == "This is the abstract text."

    def test_falls_back_to_section(self) -> None:
        elem = html.fromstring("""
            <html>
            <body>
                <section class="abstract">Abstract content here</section>
            </body>
            </html>
        """)
        assert _extract_abstract(elem) == "Abstract content here"

    def test_returns_empty_for_missing(self) -> None:
        elem = html.fromstring("<html><body>no abstract</body></html>")
        assert _extract_abstract(elem) == ""
