"""Tests for USPTO publications utils module."""

from __future__ import annotations

from patent_client_agents.uspto_publications.utils import (
    ClaimsParser,
    html_to_text,
    normalize_publication_number,
)


class TestHtmlToText:
    """Tests for html_to_text function."""

    def test_converts_simple_html(self) -> None:
        html = "<p>Simple paragraph</p>"
        result = html_to_text(html)
        assert result == "Simple paragraph"

    def test_converts_br_tags_to_newlines(self) -> None:
        html = "Line one<br>Line two"
        result = html_to_text(html)
        assert result is not None
        assert "Line one" in result
        assert "Line two" in result

    def test_converts_br_self_closing(self) -> None:
        html = "Line one<br/>Line two"
        result = html_to_text(html)
        assert result is not None
        assert "Line one" in result
        assert "Line two" in result

    def test_converts_br_with_space(self) -> None:
        html = "Line one<br />Line two"
        result = html_to_text(html)
        assert result is not None
        assert "Line one" in result
        assert "Line two" in result

    def test_strips_nested_tags(self) -> None:
        html = "<div><p><b>Bold</b> and <i>italic</i></p></div>"
        result = html_to_text(html)
        assert result == "Bold and italic"

    def test_returns_none_for_none(self) -> None:
        result = html_to_text(None)
        assert result is None

    def test_returns_none_for_empty_string(self) -> None:
        result = html_to_text("")
        assert result is None


class TestNormalizePublicationNumber:
    """Tests for normalize_publication_number function."""

    def test_normalizes_basic_number(self) -> None:
        result = normalize_publication_number("US10123456")
        assert result == "10123456"

    def test_strips_us_prefix_and_kind_code(self) -> None:
        result = normalize_publication_number("US7654321B2")
        assert result == "7654321"

    def test_removes_special_characters_and_kind_code(self) -> None:
        result = normalize_publication_number("US-10,123,456-B2")
        assert result == "10123456"

    def test_uppercases_and_strips_kind_code(self) -> None:
        result = normalize_publication_number("us10123456b2")
        assert result == "10123456"

    def test_strips_a1_kind_code(self) -> None:
        result = normalize_publication_number("US20230012345A1")
        assert result == "20230012345"

    def test_bare_number_unchanged(self) -> None:
        result = normalize_publication_number("10123456")
        assert result == "10123456"

    def test_handles_none(self) -> None:
        result = normalize_publication_number(None)
        assert result == ""

    def test_handles_empty_string(self) -> None:
        result = normalize_publication_number("")
        assert result == ""

    def test_strips_kind_code_from_non_us(self) -> None:
        result = normalize_publication_number("EP1234567A1")
        assert result == "EP1234567"

    def test_removes_spaces(self) -> None:
        result = normalize_publication_number("US 10 123 456")
        assert result == "10123456"


class TestClaimsParser:
    """Tests for ClaimsParser class."""

    def test_parses_single_claim(self) -> None:
        parser = ClaimsParser()
        claims_text = "1. A method comprising: a step."
        result = parser.parse(claims_text)
        assert len(result) == 1
        assert result[0]["number"] == 1

    def test_parses_multiple_claims(self) -> None:
        parser = ClaimsParser()
        claims_text = "1. A first claim.\n2. A second claim."
        result = parser.parse(claims_text)
        assert len(result) == 2
        assert result[0]["number"] == 1
        assert result[1]["number"] == 2

    def test_parses_dependent_claim(self) -> None:
        parser = ClaimsParser()
        claims_text = "1. A method.\n2. The method of claim 1, further comprising a step."
        result = parser.parse(claims_text)
        assert len(result) == 2
        assert result[1]["depends_on"] == [1]
        assert 2 in result[0]["dependent_claims"]

    def test_parses_multiple_dependencies(self) -> None:
        parser = ClaimsParser()
        claims_text = "1. A first claim.\n2. A second claim.\n3. The method of claims 1 or 2."
        result = parser.parse(claims_text)
        assert len(result) == 3
        assert result[2]["depends_on"] == [1, 2]

    def test_returns_empty_for_none(self) -> None:
        parser = ClaimsParser()
        result = parser.parse(None)
        assert result == []

    def test_returns_empty_for_empty_string(self) -> None:
        parser = ClaimsParser()
        result = parser.parse("")
        assert result == []

    def test_extracts_limitations(self) -> None:
        parser = ClaimsParser()
        claims_text = "1. A method comprising: step one; and step two."
        result = parser.parse(claims_text)
        assert len(result) == 1
        assert len(result[0]["limitations"]) > 0

    def test_handles_claim_intro_text(self) -> None:
        parser = ClaimsParser()
        claims_text = "What is claimed is: 1. A method."
        result = parser.parse(claims_text)
        assert len(result) == 1
        assert result[0]["number"] == 1

    def test_handles_claim_range(self) -> None:
        parser = ClaimsParser()
        claims_text = "1-3. (Canceled)"
        result = parser.parse(claims_text)
        assert len(result) == 3
        assert result[0]["number"] == 1
        assert result[1]["number"] == 2
        assert result[2]["number"] == 3

    def test_depends_on_all_foregoing(self) -> None:
        parser = ClaimsParser()
        claims_text = "1. First claim.\n2. Second claim.\n3. As in any of the foregoing claims."
        result = parser.parse(claims_text)
        assert len(result) == 3
        assert result[2]["depends_on"] == [1, 2]

    def test_initializes_dependent_claims_list(self) -> None:
        parser = ClaimsParser()
        claims_text = "1. A method."
        result = parser.parse(claims_text)
        assert result[0]["dependent_claims"] == []
