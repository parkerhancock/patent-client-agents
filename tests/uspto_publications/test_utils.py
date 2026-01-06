"""Tests for USPTO Publications utility functions."""

from ip_tools.uspto_publications.utils import (
    ClaimsParser,
    html_to_text,
    normalize_publication_number,
)


class TestHtmlToText:
    """Tests for html_to_text function."""

    def test_none_input(self):
        """Test None returns None."""
        assert html_to_text(None) is None

    def test_empty_string(self):
        """Test empty string returns None."""
        assert html_to_text("") is None

    def test_plain_text(self):
        """Test plain text passthrough."""
        assert html_to_text("Hello world") == "Hello world"

    def test_html_tags_stripped(self):
        """Test HTML tags are stripped."""
        result = html_to_text("<p>Hello <b>world</b></p>")
        assert result == "Hello world"

    def test_br_tags_to_newlines(self):
        """Test <br> tags are converted to newlines."""
        result = html_to_text("Line 1<br>Line 2")
        assert "Line 1" in result
        assert "Line 2" in result

    def test_br_self_closing(self):
        """Test self-closing <br/> tags."""
        result = html_to_text("Line 1<br/>Line 2")
        assert "Line 1" in result
        assert "Line 2" in result


class TestNormalizePublicationNumber:
    """Tests for normalize_publication_number function."""

    def test_none_input(self):
        """Test None returns empty string."""
        assert normalize_publication_number(None) == ""

    def test_empty_string(self):
        """Test empty string returns empty string."""
        assert normalize_publication_number("") == ""

    def test_plain_number(self):
        """Test plain number passthrough."""
        assert normalize_publication_number("8830957") == "8830957"

    def test_us_prefix_removed(self):
        """Test US prefix is removed."""
        assert normalize_publication_number("US8830957") == "8830957"

    def test_lowercase_us_prefix(self):
        """Test lowercase us prefix is removed."""
        assert normalize_publication_number("us8830957") == "8830957"

    def test_commas_removed(self):
        """Test commas are removed."""
        assert normalize_publication_number("8,830,957") == "8830957"

    def test_dashes_removed(self):
        """Test dashes are removed."""
        assert normalize_publication_number("US-8830957-B2") == "8830957B2"

    def test_spaces_removed(self):
        """Test spaces are removed."""
        assert normalize_publication_number("US 8830957 B2") == "8830957B2"

    def test_uppercase_output(self):
        """Test output is uppercase."""
        assert normalize_publication_number("us8830957b2") == "8830957B2"


class TestClaimsParser:
    """Tests for ClaimsParser class."""

    def test_none_input(self):
        """Test None returns empty list."""
        parser = ClaimsParser()
        assert parser.parse(None) == []

    def test_empty_string(self):
        """Test empty string returns empty list."""
        parser = ClaimsParser()
        assert parser.parse("") == []

    def test_single_claim(self):
        """Test parsing a single claim."""
        parser = ClaimsParser()
        text = "1. A method for doing something."
        result = parser.parse(text)

        assert len(result) == 1
        assert result[0]["number"] == 1
        assert "doing something" in result[0]["limitations"][0]

    def test_multiple_claims(self):
        """Test parsing multiple claims."""
        parser = ClaimsParser()
        text = """
        1. A method comprising step A.
        2. The method of claim 1, further comprising step B.
        """
        result = parser.parse(text)

        assert len(result) == 2
        assert result[0]["number"] == 1
        assert result[1]["number"] == 2

    def test_dependent_claim_detection(self):
        """Test that dependent claims are detected."""
        parser = ClaimsParser()
        text = """
        1. A method comprising step A.
        2. The method of claim 1, further comprising step B.
        """
        result = parser.parse(text)

        # Claim 2 depends on claim 1
        assert result[1]["depends_on"] == [1]
        # Claim 1 has claim 2 as dependent
        assert 2 in result[0]["dependent_claims"]

    def test_independent_claim(self):
        """Test that independent claims have no dependencies."""
        parser = ClaimsParser()
        text = "1. A method comprising step A."
        result = parser.parse(text)

        assert result[0]["depends_on"] == []
        assert result[0]["dependent_claims"] == []
