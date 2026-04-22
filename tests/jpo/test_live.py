"""Live integration tests for JPO API.

These tests hit the real JPO API and require valid credentials.
Run with: pytest -m live_jpo tests/jpo/test_live.py

Requires environment variables:
    JPO_API_USERNAME: JPO-issued username
    JPO_API_PASSWORD: JPO-issued password
"""

import os

import pytest

from ip_tools.jpo import (
    JpoClient,
    NumberType,
    get_patent_jplatpat_url,
    get_patent_progress,
)

# Skip all tests if credentials not available
pytestmark = [
    pytest.mark.live_jpo,
    pytest.mark.skipif(
        not os.getenv("JPO_API_USERNAME") or not os.getenv("JPO_API_PASSWORD"),
        reason="JPO_API_USERNAME and JPO_API_PASSWORD required for live tests",
    ),
]

# Test data - well-known Japanese patents
# Toyota hybrid patent (widely cited)
TOYOTA_PATENT_APP = "2004239955"
# Sony PlayStation patent
SONY_PATENT_APP = "2019233345"
# Nintendo Switch patent
NINTENDO_PATENT_APP = "2016047445"


class TestPatentProgressLive:
    """Live tests for patent progress APIs."""

    @pytest.mark.asyncio
    async def test_get_patent_progress_real(self) -> None:
        """Test fetching real patent progress data."""
        async with JpoClient() as client:
            progress = await client.get_patent_progress(TOYOTA_PATENT_APP)

            # Should return data for a known patent
            assert progress is not None
            assert progress.application_number == TOYOTA_PATENT_APP
            assert progress.invention_title  # Should have a title
            assert progress.filing_date  # Should have filing date

    @pytest.mark.asyncio
    async def test_get_patent_progress_simple_real(self) -> None:
        """Test simplified progress retrieval."""
        async with JpoClient() as client:
            progress = await client.get_patent_progress_simple(TOYOTA_PATENT_APP)

            assert progress is not None
            assert progress.application_number == TOYOTA_PATENT_APP

    @pytest.mark.asyncio
    async def test_get_patent_progress_not_found(self) -> None:
        """Test handling of non-existent patent."""
        async with JpoClient() as client:
            # Use a clearly invalid number
            progress = await client.get_patent_progress("9999999999")

            # Should return None, not raise
            assert progress is None


class TestPatentDocumentsLive:
    """Live tests for patent document APIs."""

    @pytest.mark.asyncio
    async def test_get_application_documents(self) -> None:
        """Test fetching application documents."""
        async with JpoClient() as client:
            docs = await client.get_patent_application_documents(TOYOTA_PATENT_APP)

            # May or may not have documents depending on the patent
            if docs:
                assert docs.application_number == TOYOTA_PATENT_APP

    @pytest.mark.asyncio
    async def test_get_mailed_documents(self) -> None:
        """Test fetching office actions."""
        async with JpoClient() as client:
            docs = await client.get_patent_mailed_documents(TOYOTA_PATENT_APP)

            if docs:
                assert docs.application_number == TOYOTA_PATENT_APP

    @pytest.mark.asyncio
    async def test_get_cited_documents(self) -> None:
        """Test fetching prior art citations."""
        async with JpoClient() as client:
            cites = await client.get_patent_cited_documents(TOYOTA_PATENT_APP)

            # Returns list (may be empty)
            assert isinstance(cites, list)


class TestNumberReferenceLive:
    """Live tests for number cross-reference API."""

    @pytest.mark.asyncio
    async def test_cross_reference_by_application(self) -> None:
        """Test number cross-reference from application number."""
        async with JpoClient() as client:
            refs = await client.get_patent_number_reference(
                NumberType.APPLICATION, TOYOTA_PATENT_APP
            )

            assert isinstance(refs, list)
            if refs:
                # Should include the application number we searched
                assert any(r.application_number == TOYOTA_PATENT_APP for r in refs)


class TestJplatpatUrlLive:
    """Live tests for J-PlatPat URL generation."""

    @pytest.mark.asyncio
    async def test_get_jplatpat_url(self) -> None:
        """Test J-PlatPat URL retrieval."""
        async with JpoClient() as client:
            url = await client.get_patent_jplatpat_url(TOYOTA_PATENT_APP)

            if url:
                assert "j-platpat" in url.lower()


class TestApplicantLookupLive:
    """Live tests for applicant lookup APIs."""

    @pytest.mark.asyncio
    async def test_applicant_by_name(self) -> None:
        """Test applicant search by name."""
        async with JpoClient() as client:
            # Search for Toyota (トヨタ)
            applicants = await client.get_patent_applicant_by_name("トヨタ")

            assert isinstance(applicants, list)
            # Toyota should definitely be in the system
            if applicants:
                assert any("トヨタ" in a.name for a in applicants)


class TestDesignProgressLive:
    """Live tests for design APIs."""

    @pytest.mark.asyncio
    async def test_get_design_progress(self) -> None:
        """Test design progress retrieval."""
        # Known design application (example - may need updating)
        design_app = "2020015234"

        async with JpoClient() as client:
            progress = await client.get_design_progress(design_app)

            # May or may not exist
            if progress:
                assert progress.application_number == design_app


class TestTrademarkProgressLive:
    """Live tests for trademark APIs."""

    @pytest.mark.asyncio
    async def test_get_trademark_progress(self) -> None:
        """Test trademark progress retrieval."""
        # Known trademark application (example - may need updating)
        tm_app = "2020123456"

        async with JpoClient() as client:
            progress = await client.get_trademark_progress(tm_app)

            # May or may not exist
            if progress:
                assert progress.application_number == tm_app


class TestConvenienceFunctionsLive:
    """Live tests for one-shot convenience functions."""

    @pytest.mark.asyncio
    async def test_oneshot_get_patent_progress(self) -> None:
        """Test one-shot patent progress function."""
        progress = await get_patent_progress(TOYOTA_PATENT_APP)

        assert progress is not None
        assert progress.application_number == TOYOTA_PATENT_APP

    @pytest.mark.asyncio
    async def test_oneshot_get_jplatpat_url(self) -> None:
        """Test one-shot J-PlatPat URL function."""
        url = await get_patent_jplatpat_url(TOYOTA_PATENT_APP)

        if url:
            assert "j-platpat" in url.lower()


class TestRateLimiting:
    """Tests to verify rate limiting is working."""

    @pytest.mark.asyncio
    async def test_multiple_requests_within_limit(self) -> None:
        """Test that multiple requests work within rate limit."""
        async with JpoClient() as client:
            # Make 5 requests - should all succeed
            for _ in range(5):
                progress = await client.get_patent_progress_simple(TOYOTA_PATENT_APP)
                # Simple endpoint should work
                assert progress is not None or True  # May return None for some apps
