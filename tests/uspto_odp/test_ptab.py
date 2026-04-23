"""Integration tests for USPTO ODP PTAB clients.

Tests use VCR cassettes to record/replay HTTP interactions.
Run with --vcr-record=once to record cassettes for the first time.

Requires USPTO_ODP_API_KEY environment variable to be set.
"""

from __future__ import annotations

import os

import pytest

from patent_client_agents.uspto_odp import (
    PtabAppealsClient,
    PtabInterferencesClient,
    PtabTrialsClient,
)


@pytest.fixture
def api_key() -> str:
    """Get API key from environment, skip if not available."""
    key = os.environ.get("USPTO_ODP_API_KEY")
    if not key:
        pytest.skip("USPTO_ODP_API_KEY not set")
    return key


class TestPtabTrialsClient:
    """Integration tests for PTAB Trials client."""

    # =========================================================================
    # Trial Proceedings
    # =========================================================================

    @pytest.mark.asyncio
    async def test_search_proceedings(self, vcr_cassette, api_key) -> None:
        """Search for IPR proceedings."""
        async with PtabTrialsClient(api_key=api_key) as client:
            result = await client.search_proceedings(
                query="trialMetaData.trialTypeCode:IPR",
                limit=5,
            )

        assert result.count >= 0
        assert isinstance(result.patentTrialProceedingDataBag, list)
        if result.count > 0:
            proceeding = result.patentTrialProceedingDataBag[0]
            assert proceeding.trialNumber is not None

    @pytest.mark.asyncio
    async def test_search_proceedings_with_facets(self, vcr_cassette, api_key) -> None:
        """Search proceedings with facets."""
        async with PtabTrialsClient(api_key=api_key) as client:
            result = await client.search_proceedings(
                query="trialMetaData.trialTypeCode:IPR",
                facets=["trialMetaData.trialStatusCategory"],
                limit=5,
            )

        assert result.count >= 0
        # Facets should be returned when requested
        if result.facets:
            assert isinstance(result.facets, dict)

    @pytest.mark.asyncio
    async def test_get_proceeding(self, vcr_cassette, api_key) -> None:
        """Get a specific trial proceeding by number."""
        async with PtabTrialsClient(api_key=api_key) as client:
            result = await client.get_proceeding("IPR2025-01319")

        assert result.count >= 0
        if result.count > 0:
            proceeding = result.patentTrialProceedingDataBag[0]
            assert "IPR2025-01319" in (proceeding.trialNumber or "")

    @pytest.mark.asyncio
    async def test_download_proceedings(self, vcr_cassette, api_key) -> None:
        """Download proceedings search results."""
        async with PtabTrialsClient(api_key=api_key) as client:
            result = await client.download_proceedings(
                query="trialMetaData.trialTypeCode:IPR",
                limit=5,
                file_format="json",
            )

        assert result.count >= 0
        assert isinstance(result.patentTrialProceedingDataBag, list)

    # =========================================================================
    # Trial Decisions
    # =========================================================================

    @pytest.mark.asyncio
    async def test_search_decisions(self, vcr_cassette, api_key) -> None:
        """Search for trial decisions."""
        async with PtabTrialsClient(api_key=api_key) as client:
            result = await client.search_decisions(
                query="decisionData.decisionTypeCategory:Decision",
                limit=5,
            )

        assert result.count >= 0
        assert isinstance(result.patentTrialDocumentDataBag, list)

    @pytest.mark.asyncio
    async def test_get_decisions_by_trial(self, vcr_cassette, api_key) -> None:
        """Get all decisions for a specific trial."""
        async with PtabTrialsClient(api_key=api_key) as client:
            result = await client.get_decisions_by_trial("IPR2025-01319")

        assert result.count >= 0
        assert isinstance(result.patentTrialDocumentDataBag, list)

    # =========================================================================
    # Trial Documents
    # =========================================================================

    @pytest.mark.asyncio
    async def test_search_documents(self, vcr_cassette, api_key) -> None:
        """Search for trial documents."""
        async with PtabTrialsClient(api_key=api_key) as client:
            result = await client.search_documents(
                query="documentData.filingPartyCategory:Petitioner",
                limit=5,
            )

        assert result.count >= 0
        assert isinstance(result.patentTrialDocumentDataBag, list)

    @pytest.mark.asyncio
    async def test_get_documents_by_trial(self, vcr_cassette, api_key) -> None:
        """Get all documents for a specific trial."""
        async with PtabTrialsClient(api_key=api_key) as client:
            result = await client.get_documents_by_trial("IPR2025-01319")

        assert result.count >= 0
        assert isinstance(result.patentTrialDocumentDataBag, list)


class TestPtabAppealsClient:
    """Integration tests for PTAB Appeals client."""

    @pytest.mark.asyncio
    async def test_search(self, vcr_cassette, api_key) -> None:
        """Search for appeal decisions."""
        async with PtabAppealsClient(api_key=api_key) as client:
            result = await client.search(
                query="appellantData.technologyCenterNumber:2800",
                limit=5,
            )

        assert result.count >= 0
        assert isinstance(result.patentAppealDataBag, list)
        if result.count > 0:
            appeal = result.patentAppealDataBag[0]
            assert appeal.appealNumber is not None

    @pytest.mark.asyncio
    async def test_search_with_facets(self, vcr_cassette, api_key) -> None:
        """Search appeals with facets."""
        async with PtabAppealsClient(api_key=api_key) as client:
            result = await client.search(
                query="appellantData.technologyCenterNumber:2800",
                facets=["decisionData.decisionTypeCategory"],
                limit=5,
            )

        assert result.count >= 0
        if result.facets:
            assert isinstance(result.facets, dict)

    @pytest.mark.asyncio
    async def test_get_decisions_by_number(self, vcr_cassette, api_key) -> None:
        """Get decisions for a specific appeal number."""
        async with PtabAppealsClient(api_key=api_key) as client:
            result = await client.get_decisions_by_number("2026000120")

        assert result.count >= 0
        assert isinstance(result.patentAppealDataBag, list)

    @pytest.mark.asyncio
    async def test_download(self, vcr_cassette, api_key) -> None:
        """Download appeal decisions search results."""
        async with PtabAppealsClient(api_key=api_key) as client:
            result = await client.download(
                query="appellantData.technologyCenterNumber:2800",
                limit=5,
                file_format="json",
            )

        assert result.count >= 0
        assert isinstance(result.patentAppealDataBag, list)


class TestPtabInterferencesClient:
    """Integration tests for PTAB Interferences client.

    Note: Patent interferences were largely replaced by derivation proceedings
    in 2013 (AIA). The interference database may have limited recent records.
    """

    @pytest.mark.asyncio
    async def test_search(self, vcr_cassette, api_key) -> None:
        """Search for interference decisions."""
        async with PtabInterferencesClient(api_key=api_key) as client:
            result = await client.search(
                query="*",
                limit=5,
            )

        # May return 0 results if database is empty
        assert result.count >= 0
        assert isinstance(result.patentInterferenceDataBag, list)
        if result.count > 0:
            interference = result.patentInterferenceDataBag[0]
            assert interference.interferenceNumber is not None

    @pytest.mark.asyncio
    async def test_search_with_fields(self, vcr_cassette, api_key) -> None:
        """Search interferences requesting specific fields."""
        async with PtabInterferencesClient(api_key=api_key) as client:
            result = await client.search(
                query="*",
                fields=["interferenceNumber", "interferenceMetaData"],
                limit=5,
            )

        assert result.count >= 0
        assert isinstance(result.patentInterferenceDataBag, list)

    @pytest.mark.asyncio
    async def test_get_decisions_by_number(self, vcr_cassette, api_key) -> None:
        """Get decisions for a specific interference number."""
        async with PtabInterferencesClient(api_key=api_key) as client:
            result = await client.get_decisions_by_number("105801")

        assert result.count >= 0
        assert isinstance(result.patentInterferenceDataBag, list)

    @pytest.mark.asyncio
    async def test_download(self, vcr_cassette, api_key) -> None:
        """Download interference decisions search results."""
        async with PtabInterferencesClient(api_key=api_key) as client:
            result = await client.download(
                query="*",
                limit=5,
                file_format="json",
            )

        assert result.count >= 0
        assert isinstance(result.patentInterferenceDataBag, list)


class TestPtabModels:
    """Tests for PTAB response model parsing."""

    @pytest.mark.asyncio
    async def test_trial_proceeding_model_fields(self, vcr_cassette, api_key) -> None:
        """Verify trial proceeding model parses all expected fields."""
        async with PtabTrialsClient(api_key=api_key) as client:
            result = await client.search_proceedings(query="*", limit=1)

        if result.count > 0:
            proceeding = result.patentTrialProceedingDataBag[0]
            # Check key fields exist (may be None but should be parsed)
            assert hasattr(proceeding, "trialNumber")
            assert hasattr(proceeding, "trialMetaData")
            assert hasattr(proceeding, "patentOwnerData")
            assert hasattr(proceeding, "regularPetitionerData")

    @pytest.mark.asyncio
    async def test_appeal_model_fields(self, vcr_cassette, api_key) -> None:
        """Verify appeal model parses all expected fields."""
        async with PtabAppealsClient(api_key=api_key) as client:
            result = await client.search(query="*", limit=1)

        if result.count > 0:
            appeal = result.patentAppealDataBag[0]
            assert hasattr(appeal, "appealNumber")
            assert hasattr(appeal, "appealMetaData")
            assert hasattr(appeal, "appellantData")
            assert hasattr(appeal, "decisionData")

    @pytest.mark.asyncio
    async def test_interference_model_fields(self, vcr_cassette, api_key) -> None:
        """Verify interference model parses all expected fields."""
        async with PtabInterferencesClient(api_key=api_key) as client:
            result = await client.search(query="*", limit=1)

        if result.count > 0:
            interference = result.patentInterferenceDataBag[0]
            assert hasattr(interference, "interferenceNumber")
            assert hasattr(interference, "interferenceMetaData")
            assert hasattr(interference, "seniorPartyData")
            assert hasattr(interference, "decisionDocumentData")
