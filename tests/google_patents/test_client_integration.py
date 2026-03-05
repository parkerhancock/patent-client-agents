"""VCR-recorded integration tests for GooglePatentsClient."""

from __future__ import annotations

import httpx
import pytest

from ip_tools.google_patents.client import (
    GooglePatentsClient,
    fetch_patent_from_google_patents,
)


class TestFetchPatent:
    @pytest.mark.vcr
    async def test_fetch_real_patent(self):
        patent = await fetch_patent_from_google_patents("US7654321B2", use_cache=False)
        assert patent.patent_number
        assert patent.title
        assert len(patent.claims) > 0

    @pytest.mark.vcr
    async def test_fetch_nonexistent_patent(self):
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_patent_from_google_patents("US0000001B2", use_cache=False)


class TestGooglePatentsClientIntegration:
    @pytest.mark.vcr
    async def test_get_patent_data(self):
        async with GooglePatentsClient(use_cache=False) as client:
            patent = await client.get_patent_data("US7654321B2")
            assert patent.title
            assert patent.patent_number

    @pytest.mark.vcr
    async def test_get_patent_details(self):
        async with GooglePatentsClient(use_cache=False) as client:
            details = await client.get_patent_details("US7654321B2")
            assert "patent_number" in details
            assert "title" in details

    @pytest.mark.vcr
    async def test_get_patent_claims(self):
        async with GooglePatentsClient(use_cache=False) as client:
            claims = await client.get_patent_claims("US7654321B2")
            assert len(claims) > 0
            assert "claim_text" in claims[0]

    @pytest.mark.vcr
    async def test_get_patent_pdf_url(self):
        async with GooglePatentsClient(use_cache=False) as client:
            pdf_url = await client.get_patent_pdf_url("US7654321B2")
            assert pdf_url is None or pdf_url.startswith("http")

    @pytest.mark.vcr
    async def test_search_patents(self):
        async with GooglePatentsClient(use_cache=False) as client:
            results = await client.search_patents(keywords=["robot"], page_size=5)
            assert len(results.results) > 0
