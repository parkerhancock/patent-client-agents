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
    async def test_search_proceedings_with_sort(self, vcr_cassette, api_key) -> None:
        """Search proceedings with a dict-shaped sort directive.

        Regression: the live API rejects string sort expressions, and the
        client's serializer raises TypeError on them — sort must be an
        OdpSort or a {"field", "order"} dict (a "direction" key 400s).
        """
        async with PtabTrialsClient(api_key=api_key) as client:
            result = await client.search_proceedings(
                sort={"field": "trialNumber", "order": "asc"},
                limit=5,
            )

        assert result.count > 0
        assert len(result.patentTrialProceedingDataBag) == 5
        numbers = [p.trialNumber for p in result.patentTrialProceedingDataBag]
        assert all(numbers)
        assert numbers == sorted(numbers)

    @pytest.mark.asyncio
    async def test_download_proceedings(self, vcr_cassette, api_key) -> None:
        """Download proceedings search results.

        Regression: the download endpoint keys its records as
        ``patentTrialData`` (not ``patentTrialProceedingDataBag``) and omits
        ``count``; before normalization the client silently returned an
        empty bag for every real download.
        """
        async with PtabTrialsClient(api_key=api_key) as client:
            result = await client.download_proceedings(
                query="trialMetaData.trialTypeCode:IPR",
                limit=5,
                file_format="json",
            )

        assert result.count == 5
        assert len(result.patentTrialProceedingDataBag) == 5
        proceeding = result.patentTrialProceedingDataBag[0]
        assert proceeding.trialNumber
        assert proceeding.trialMetaData is not None

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

    @pytest.mark.asyncio
    async def test_download_decisions(self, vcr_cassette, api_key) -> None:
        """Download decisions search results (same ``patentTrialData`` envelope)."""
        async with PtabTrialsClient(api_key=api_key) as client:
            result = await client.download_decisions(
                query="decisionData.decisionTypeCategory:Decision",
                limit=5,
                file_format="json",
            )

        assert result.count == 5
        assert len(result.patentTrialDocumentDataBag) == 5
        decision = result.patentTrialDocumentDataBag[0]
        assert decision.trialNumber
        assert decision.decisionData is not None

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

    @pytest.mark.asyncio
    async def test_download_documents(self, vcr_cassette, api_key) -> None:
        """Download documents search results (same ``patentTrialData`` envelope)."""
        async with PtabTrialsClient(api_key=api_key) as client:
            result = await client.download_documents(
                query="documentData.filingPartyCategory:Petitioner",
                limit=5,
                file_format="json",
            )

        assert result.count == 5
        assert len(result.patentTrialDocumentDataBag) == 5
        document = result.patentTrialDocumentDataBag[0]
        assert document.trialNumber
        assert document.documentData is not None


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


class TestPtabDownloadNormalization:
    """No-network tests for the trials download envelope normalization.

    Fixture payloads are trimmed from live /search/download captures
    (2026-07-20): records arrive under ``patentTrialData`` with no ``count``.
    """

    def test_proceedings_download_envelope(self) -> None:
        from patent_client_agents.uspto_odp.clients.ptab_trials import (
            _normalize_download_bag,
        )
        from patent_client_agents.uspto_odp.models import PtabTrialProceedingResponse

        data = {
            "patentTrialData": [
                {
                    "patentOwnerData": {
                        "patentNumber": "11755816",
                        "technologyCenterNumber": "2100",
                        "applicationNumberText": "17830566",
                    },
                    "trialMetaData": {
                        "trialStatusCategory": "Pending",
                        "petitionFilingDate": "2026-07-16",
                    },
                    "trialNumber": "IPR2026-00428",
                }
            ]
        }
        result = PtabTrialProceedingResponse.model_validate(
            _normalize_download_bag(data, "patentTrialProceedingDataBag")
        )
        assert result.count == 1
        proceeding = result.patentTrialProceedingDataBag[0]
        assert proceeding.trialNumber == "IPR2026-00428"
        assert proceeding.trialMetaData is not None
        assert proceeding.trialMetaData.trialStatusCategory == "Pending"
        assert proceeding.patentOwnerData is not None
        assert proceeding.patentOwnerData.patentNumber == "11755816"

    def test_decisions_download_envelope(self) -> None:
        from patent_client_agents.uspto_odp.clients.ptab_trials import (
            _normalize_download_bag,
        )
        from patent_client_agents.uspto_odp.models import PtabTrialDecisionResponse

        data = {
            "patentTrialData": [
                {
                    "decisionData": {
                        "decisionTypeCategory": "Decision",
                        "trialOutcomeCategory": "Final Written Decision",
                        "decisionIssueDate": "2026-07-20",
                    },
                    "patentOwnerData": {"technologyCenterNumber": "2800"},
                    "trialNumber": "IPR2025-00228",
                }
            ]
        }
        result = PtabTrialDecisionResponse.model_validate(
            _normalize_download_bag(data, "patentTrialDocumentDataBag")
        )
        assert result.count == 1
        decision = result.patentTrialDocumentDataBag[0]
        assert decision.trialNumber == "IPR2025-00228"
        assert decision.decisionData is not None
        assert decision.decisionData.trialOutcomeCategory == "Final Written Decision"

    def test_search_shaped_payload_passes_through(self) -> None:
        """A search-shaped payload (404 fallback or future API fix) is untouched."""
        from patent_client_agents.uspto_odp.clients.ptab_trials import (
            _normalize_download_bag,
        )

        data = {"count": 0, "patentTrialProceedingDataBag": []}
        assert _normalize_download_bag(data, "patentTrialProceedingDataBag") == {
            "count": 0,
            "patentTrialProceedingDataBag": [],
        }

    @pytest.mark.asyncio
    async def test_string_sort_raises_type_error(self) -> None:
        """A plain string sort is rejected client-side, never sent to the API."""
        async with PtabTrialsClient(api_key="test-key") as client:
            with pytest.raises(TypeError, match="Unsupported item type"):
                await client.search_proceedings(sort="trialNumber asc", limit=5)  # type: ignore[arg-type]
