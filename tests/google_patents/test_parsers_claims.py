"""Tests for Google Patents claims parser."""

from __future__ import annotations

from lxml import html

from ip_tools.google_patents.parsers.claims import (
    _direct_text_before_nested,
    _extract_limitations,
    _has_class,
    _leaf_claim_texts,
    _normalize_spaces,
    _split_long_limitations,
    _strip_leading_number,
    _to_root,
    extract_claims,
)


class TestNormalizeSpaces:
    """Tests for _normalize_spaces function."""

    def test_collapses_multiple_spaces(self) -> None:
        result = _normalize_spaces("hello    world")
        assert result == "hello world"

    def test_collapses_tabs_and_newlines(self) -> None:
        result = _normalize_spaces("hello\t\nworld")
        assert result == "hello world"

    def test_strips_leading_trailing(self) -> None:
        result = _normalize_spaces("   hello world   ")
        assert result == "hello world"

    def test_handles_empty_string(self) -> None:
        result = _normalize_spaces("")
        assert result == ""


class TestStripLeadingNumber:
    """Tests for _strip_leading_number function."""

    def test_strips_number_with_period(self) -> None:
        result = _strip_leading_number("1. A method comprising:")
        assert result == "A method comprising:"

    def test_strips_number_with_spaces(self) -> None:
        result = _strip_leading_number("25.   A system wherein:")
        assert result == "A system wherein:"

    def test_handles_no_number(self) -> None:
        result = _strip_leading_number("A method comprising:")
        assert result == "A method comprising:"

    def test_fixes_comma_spacing(self) -> None:
        result = _strip_leading_number("1. step one , step two")
        assert result == "step one, step two"

    def test_fixes_semicolon_spacing(self) -> None:
        result = _strip_leading_number("1. step one ; step two")
        assert result == "step one; step two"


class TestSplitLongLimitations:
    """Tests for _split_long_limitations function."""

    def test_returns_empty_for_empty(self) -> None:
        result = _split_long_limitations("")
        assert result == []

    def test_returns_single_for_short_text(self) -> None:
        result = _split_long_limitations("A short limitation text")
        assert result == ["A short limitation text"]

    def test_splits_on_wherein(self) -> None:
        # Make text long enough (>50 words) to trigger splitting
        long_text = " ".join(["word"] * 60) + ", wherein the system further comprises a processor"
        result = _split_long_limitations(long_text)
        assert len(result) == 2
        assert result[1].startswith("wherein")

    def test_keeps_short_text_with_wherein(self) -> None:
        # Short text should not be split
        result = _split_long_limitations("A method, wherein the step is performed")
        assert result == ["A method, wherein the step is performed"]


class TestHasClass:
    """Tests for _has_class function."""

    def test_finds_single_class(self) -> None:
        elem = html.fromstring('<div class="claim-text">text</div>')
        assert _has_class(elem, "claim-text") is True

    def test_finds_class_in_multiple(self) -> None:
        elem = html.fromstring('<div class="foo claim-text bar">text</div>')
        assert _has_class(elem, "claim-text") is True

    def test_returns_false_for_missing(self) -> None:
        elem = html.fromstring('<div class="other-class">text</div>')
        assert _has_class(elem, "claim-text") is False

    def test_handles_no_class(self) -> None:
        elem = html.fromstring("<div>text</div>")
        assert _has_class(elem, "claim-text") is False


class TestDirectTextBeforeNested:
    """Tests for _direct_text_before_nested function."""

    def test_extracts_direct_text(self) -> None:
        elem = html.fromstring('<div class="claim-text">Direct text</div>')
        result = _direct_text_before_nested(elem)
        assert result == "Direct text"

    def test_stops_at_nested_claim_text(self) -> None:
        elem = html.fromstring(
            """<div class="claim-text">Preamble text
            <div class="claim-text">Nested text</div>
            </div>"""
        )
        result = _direct_text_before_nested(elem)
        assert "Preamble text" in result
        assert "Nested text" not in result

    def test_includes_inline_elements(self) -> None:
        elem = html.fromstring('<div class="claim-text">Text with <b>bold</b> content</div>')
        result = _direct_text_before_nested(elem)
        assert "bold" in result


class TestLeafClaimTexts:
    """Tests for _leaf_claim_texts function."""

    def test_extracts_leaf_nodes(self) -> None:
        elem = html.fromstring(
            """<div>
            <div class="claim-text">
                <div class="claim-text">Leaf 1</div>
                <div class="claim-text">Leaf 2</div>
            </div>
            </div>"""
        )
        result = list(_leaf_claim_texts(elem))
        assert "Leaf 1" in result
        assert "Leaf 2" in result

    def test_skips_empty_nodes(self) -> None:
        elem = html.fromstring(
            """<div>
            <div class="claim-text">   </div>
            <div class="claim-text">Content</div>
            </div>"""
        )
        result = list(_leaf_claim_texts(elem))
        assert len(result) == 1
        assert "Content" in result[0]


class TestExtractLimitations:
    """Tests for _extract_limitations function."""

    def test_extracts_from_simple_claim(self) -> None:
        elem = html.fromstring(
            """<div class="claim">
            <div class="claim-text">A method comprising: step one.</div>
            </div>"""
        )
        result = _extract_limitations(elem)
        assert len(result) >= 1
        assert "step one" in result[0].lower() or "method" in result[0].lower()

    def test_extracts_nested_limitations(self) -> None:
        elem = html.fromstring(
            """<div class="claim">
            <div class="claim-text">A method comprising:
                <div class="claim-text">performing step one;</div>
                <div class="claim-text">performing step two.</div>
            </div>
            </div>"""
        )
        result = _extract_limitations(elem)
        assert len(result) >= 2

    def test_handles_no_claim_text(self) -> None:
        elem = html.fromstring("<div>Plain text content</div>")
        result = _extract_limitations(elem)
        assert "Plain text content" in result[0]


class TestToRoot:
    """Tests for _to_root function."""

    def test_returns_element_unchanged(self) -> None:
        elem = html.fromstring("<div>test</div>")
        result = _to_root(elem)
        assert result is elem

    def test_parses_string_to_element(self) -> None:
        result = _to_root("<div>test</div>")
        assert result.tag == "div"
        assert result.text == "test"


class TestExtractClaims:
    """Tests for extract_claims function."""

    def test_extracts_single_claim(self) -> None:
        html_content = """
        <html><body>
        <div class="claims">
            <div class="claim" num="1">
                <div class="claim-text">1. A method comprising: a step.</div>
            </div>
        </div>
        </body></html>
        """
        claims, limitations, _ = extract_claims(html_content)
        assert len(claims) == 1
        assert claims[0]["number"] == "1"
        assert "method" in (claims[0]["text"] or "").lower()

    def test_extracts_multiple_claims(self) -> None:
        html_content = """
        <html><body>
        <div class="claims">
            <div class="claim" num="1">
                <div class="claim-text">1. A first method.</div>
            </div>
            <div class="claim child" num="2">
                <div class="claim-text">2. The method of
                    <claim-ref idref="CLM-1">claim 1</claim-ref>.</div>
            </div>
        </div>
        </body></html>
        """
        claims, limitations, _ = extract_claims(html_content)
        assert len(claims) == 2
        assert claims[0]["type"] == "independent"
        assert claims[1]["type"] == "dependent"
        assert claims[1]["depends_on"] == "1"

    def test_returns_empty_for_no_claims(self) -> None:
        html_content = """
        <html><body>
        <div>No claims section here</div>
        </body></html>
        """
        claims, limitations, original_limitations = extract_claims(html_content)
        assert claims == []
        assert limitations == {}
        assert original_limitations == {}

    def test_skips_claims_without_number(self) -> None:
        html_content = """
        <html><body>
        <div class="claims">
            <div class="claim">
                <div class="claim-text">Unnumbered claim</div>
            </div>
            <div class="claim" num="1">
                <div class="claim-text">1. Numbered claim.</div>
            </div>
        </div>
        </body></html>
        """
        claims, limitations, _ = extract_claims(html_content)
        assert len(claims) == 1
        assert claims[0]["number"] == "1"

    def test_extracts_limitations_per_claim(self) -> None:
        html_content = """
        <html><body>
        <div class="claims">
            <div class="claim" num="1">
                <div class="claim-text">1. A method comprising:
                    <div class="claim-text">step one;</div>
                    <div class="claim-text">step two.</div>
                </div>
            </div>
        </div>
        </body></html>
        """
        claims, limitations, _ = extract_claims(html_content)
        assert "1" in limitations
        assert len(limitations["1"]) >= 1

    def test_handles_html_element_input(self) -> None:
        elem = html.fromstring(
            """<html><body>
            <div class="claims">
                <div class="claim" num="1">
                    <div class="claim-text">1. A test claim.</div>
                </div>
            </div>
            </body></html>"""
        )
        claims, limitations, _ = extract_claims(elem)
        assert len(claims) == 1
