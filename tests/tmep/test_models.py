"""Tests for TMEP models."""

from patent_client_agents.tmep.models import (
    TmepSearchHit,
    TmepSearchResponse,
    TmepSection,
    TmepVersion,
)


class TestTmepSearchHit:
    """Tests for TmepSearchHit model."""

    def test_basic_fields(self) -> None:
        """Test basic field parsing."""
        hit = TmepSearchHit(
            title="1207.01 - Likelihood of Confusion",
            href="TMEP-1200d1e8145.html",
            path=["1200", "1207", "1207.01"],
            result_url="https://tmep.uspto.gov/RDMS/TMEP/result/TMEP-1200d1e8145.html",
        )
        assert hit.title == "1207.01 - Likelihood of Confusion"
        assert hit.href == "TMEP-1200d1e8145.html"
        assert hit.path == ["1200", "1207", "1207.01"]

    def test_empty_path(self) -> None:
        """Test empty path defaults to empty list."""
        hit = TmepSearchHit(
            title="Test",
            href="test.html",
            result_url="https://example.com",
        )
        assert hit.path == []


class TestTmepSearchResponse:
    """Tests for TmepSearchResponse model."""

    def test_empty_response(self) -> None:
        """Test empty response."""
        response = TmepSearchResponse(hits=[], page=1, per_page=10, has_more=False)
        assert len(response.hits) == 0
        assert response.page == 1
        assert response.has_more is False

    def test_with_hits(self) -> None:
        """Test response with hits."""
        hits = [
            TmepSearchHit(
                title="Section 1",
                href="s1.html",
                result_url="https://example.com/s1",
            ),
            TmepSearchHit(
                title="Section 2",
                href="s2.html",
                result_url="https://example.com/s2",
            ),
        ]
        response = TmepSearchResponse(hits=hits, page=1, per_page=10, has_more=True)
        assert len(response.hits) == 2
        assert response.has_more is True


class TestTmepSection:
    """Tests for TmepSection model."""

    def test_basic_fields(self) -> None:
        """Test basic field parsing."""
        section = TmepSection(
            href="TMEP-1200d1e8145.html",
            html="<h1>Test</h1><p>Content</p>",
            text="Test\nContent",
            version="current",
            title="1207.01 - Test Section",
        )
        assert section.href == "TMEP-1200d1e8145.html"
        assert section.version == "current"
        assert section.title == "1207.01 - Test Section"

    def test_optional_title(self) -> None:
        """Test that title is optional."""
        section = TmepSection(
            href="test.html",
            html="<p>No title</p>",
            text="No title",
            version="current",
        )
        assert section.title is None


class TestTmepVersion:
    """Tests for TmepVersion model."""

    def test_basic_fields(self) -> None:
        """Test basic field parsing."""
        version = TmepVersion(label="November 2025", value="Nov2025", current=True)
        assert version.label == "November 2025"
        assert version.value == "Nov2025"
        assert version.current is True

    def test_current_defaults_false(self) -> None:
        """Test that current defaults to False."""
        version = TmepVersion(label="October 2024", value="Oct2024")
        assert version.current is False
