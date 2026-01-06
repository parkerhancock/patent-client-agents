"""Tests for USPTO Assignments client utilities."""

from ip_tools.uspto_assignments.client import _clean_patent_number


class TestCleanPatentNumber:
    """Tests for _clean_patent_number function."""

    def test_plain_number(self):
        """Test plain patent number."""
        assert _clean_patent_number("8830957") == "8830957"

    def test_with_us_prefix(self):
        """Test patent number with US prefix."""
        assert _clean_patent_number("US8830957") == "8830957"

    def test_with_us_prefix_lowercase(self):
        """Test patent number with lowercase US prefix."""
        assert _clean_patent_number("us8830957") == "8830957"

    def test_with_commas(self):
        """Test patent number with commas."""
        assert _clean_patent_number("8,830,957") == "8830957"

    def test_with_dashes(self):
        """Test patent number with dashes."""
        assert _clean_patent_number("US-8830957-B2") == "8830957B2"

    def test_with_spaces(self):
        """Test patent number with spaces."""
        assert _clean_patent_number("US 8830957") == "8830957"

    def test_application_number(self):
        """Test application number format."""
        assert _clean_patent_number("16/123,456") == "16123456"

    def test_with_slashes(self):
        """Test number with slashes."""
        assert _clean_patent_number("17/123/456") == "17123456"
