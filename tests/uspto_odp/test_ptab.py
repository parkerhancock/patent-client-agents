"""Integration tests for USPTO ODP PTAB clients.

Tests use VCR cassettes to record/replay HTTP interactions.
Run with --vcr-record=once to record cassettes for the first time.

Recording requires USPTO_ODP_API_KEY. Replay does not: the X-API-KEY
header is scrubbed from cassettes and is not part of request matching,
so a placeholder key is used when the variable is unset.
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
def api_key(request: pytest.FixtureRequest) -> str:
    """Real key from the environment, or a placeholder for cassette replay."""
    key = os.environ.get("USPTO_ODP_API_KEY")
    if key:
        return key
    if request.config.getoption("--vcr-record", default="none") != "none":
        pytest.skip("USPTO_ODP_API_KEY not set (required to record cassettes)")
    return "test_odp_key"


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

        assert result.count == 18058
        assert len(result.patentTrialProceedingDataBag) == 5
        proceeding = result.patentTrialProceedingDataBag[0]
        assert proceeding.trialNumber == "IPR2026-00338"
        assert proceeding.trialMetaData is not None
        assert proceeding.trialMetaData.trialTypeCode == "IPR"
        assert proceeding.patentOwnerData is not None
        assert proceeding.patentOwnerData.patentNumber == "8738103"

    @pytest.mark.asyncio
    async def test_search_proceedings_with_facets(self, vcr_cassette, api_key) -> None:
        """Search proceedings with facets."""
        async with PtabTrialsClient(api_key=api_key) as client:
            result = await client.search_proceedings(
                query="trialMetaData.trialTypeCode:IPR",
                facets=["trialMetaData.trialStatusCategory"],
                limit=5,
            )

        assert result.count == 18058
        assert len(result.patentTrialProceedingDataBag) == 5
        # Facets should be returned when requested
        assert result.facets is not None
        buckets = result.facets["trialMetaData.trialStatusCategory"]
        assert buckets[0] == {"value": "Institution Denied", "count": 5541}
        assert {"value": "Final Written Decision", "count": 5477} in buckets

    @pytest.mark.asyncio
    async def test_get_proceeding(self, vcr_cassette, api_key) -> None:
        """Get a specific trial proceeding by number."""
        async with PtabTrialsClient(api_key=api_key) as client:
            result = await client.get_proceeding("IPR2025-01319")

        assert result.count == 1
        assert len(result.patentTrialProceedingDataBag) == 1
        proceeding = result.patentTrialProceedingDataBag[0]
        assert proceeding.trialNumber == "IPR2025-01319"
        assert proceeding.trialMetaData is not None
        assert proceeding.trialMetaData.trialStatusCategory == "Discretionary Denial"
        assert proceeding.patentOwnerData is not None
        assert proceeding.patentOwnerData.patentNumber == "11703443"
        assert proceeding.regularPetitionerData is not None
        assert proceeding.regularPetitionerData.realPartyInInterestName == (
            "Cytek Biosciences, Inc."
        )

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

        assert result.count == 20384
        assert len(result.patentTrialDocumentDataBag) == 5
        decision = result.patentTrialDocumentDataBag[0]
        assert decision.trialNumber == "IPR2022-01002"
        assert decision.decisionData is not None
        assert decision.decisionData.decisionTypeCategory == "Decision"
        assert decision.decisionData.trialOutcomeCategory == (
            "Final Written Decision On CAFC Remand"
        )

    @pytest.mark.asyncio
    async def test_get_decisions_by_trial(self, vcr_cassette, api_key) -> None:
        """Get all decisions for a specific trial."""
        async with PtabTrialsClient(api_key=api_key) as client:
            result = await client.get_decisions_by_trial("IPR2025-01319")

        assert result.count == 1
        assert len(result.patentTrialDocumentDataBag) == 1
        decision = result.patentTrialDocumentDataBag[0]
        assert decision.trialNumber == "IPR2025-01319"
        assert decision.decisionData is not None
        assert decision.decisionData.trialOutcomeCategory == "Institution Denied"
        assert decision.decisionData.decisionIssueDate == "2025-11-20"

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

        assert result.count == 829136
        assert len(result.patentTrialDocumentDataBag) == 5
        document = result.patentTrialDocumentDataBag[0]
        assert document.trialNumber == "IPR2026-00338"
        assert document.documentData is not None
        assert document.documentData.filingPartyCategory == "PETITIONER"
        assert document.documentData.documentNumber == 1026

    @pytest.mark.asyncio
    async def test_get_documents_by_trial(self, vcr_cassette, api_key) -> None:
        """Get all documents for a specific trial."""
        async with PtabTrialsClient(api_key=api_key) as client:
            result = await client.get_documents_by_trial("IPR2025-01319")

        assert result.count == 242
        assert len(result.patentTrialDocumentDataBag) == 25
        assert all(d.trialNumber == "IPR2025-01319" for d in result.patentTrialDocumentDataBag)
        document = result.patentTrialDocumentDataBag[0]
        assert document.documentData is not None
        assert document.documentData.documentIdentifier == "171314592"
        assert document.documentData.documentNumber == 15

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

        assert result.count == 13470
        assert len(result.patentAppealDataBag) == 5
        appeal = result.patentAppealDataBag[0]
        assert appeal.appealNumber == "2026000736"
        assert appeal.decisionData is not None
        assert appeal.decisionData.appealOutcomeCategory == "Reversed"
        assert appeal.appellantData is not None
        assert appeal.appellantData.technologyCenterNumber == "2800"

    @pytest.mark.asyncio
    async def test_search_with_facets(self, vcr_cassette, api_key) -> None:
        """Search appeals with facets."""
        async with PtabAppealsClient(api_key=api_key) as client:
            result = await client.search(
                query="appellantData.technologyCenterNumber:2800",
                facets=["decisionData.decisionTypeCategory"],
                limit=5,
            )

        assert result.count == 13470
        assert len(result.patentAppealDataBag) == 5
        assert result.facets is not None
        assert result.facets["decisionData.decisionTypeCategory"] == [
            {"value": "Decision", "count": 12996},
            {"value": "Rehearing Decision", "count": 444},
            {"value": "Reconsideration", "count": 30},
        ]

    @pytest.mark.asyncio
    async def test_search_with_sort(self, vcr_cassette, api_key) -> None:
        """Search appeals with a dict-shaped sort directive.

        Regression: the live API rejects string sort expressions, and the
        client's serializer raises TypeError on them — sort must be an
        OdpSort or a {"field", "order"} dict.
        """
        async with PtabAppealsClient(api_key=api_key) as client:
            result = await client.search(
                query="appellantData.technologyCenterNumber:2800",
                sort={"field": "appealNumber", "order": "asc"},
                limit=5,
            )

        assert result.count > 0
        assert len(result.patentAppealDataBag) == 5
        numbers = [a.appealNumber for a in result.patentAppealDataBag]
        assert all(numbers)
        assert numbers == sorted(numbers)

    @pytest.mark.asyncio
    async def test_get_decisions_by_number(self, vcr_cassette, api_key) -> None:
        """Get decisions for a specific appeal number."""
        async with PtabAppealsClient(api_key=api_key) as client:
            result = await client.get_decisions_by_number("2026000120")

        assert result.count == 1
        assert len(result.patentAppealDataBag) == 1
        appeal = result.patentAppealDataBag[0]
        assert appeal.appealNumber == "2026000120"
        assert appeal.decisionData is not None
        assert appeal.decisionData.appealOutcomeCategory == "Affirmed"
        assert appeal.appellantData is not None
        assert appeal.appellantData.realPartyInInterestName == "Siemens Aktiengesellschaft"

    @pytest.mark.asyncio
    async def test_download(self, vcr_cassette, api_key) -> None:
        """Download appeal decisions search results.

        Regression: the download endpoint keys its records as
        ``patentTrialData`` (not ``patentAppealDataBag``) and omits
        ``count``; before normalization the client silently returned an
        empty bag for every real download.
        """
        async with PtabAppealsClient(api_key=api_key) as client:
            result = await client.download(
                query="appellantData.technologyCenterNumber:2800",
                limit=5,
                file_format="json",
            )

        assert result.count == 5
        assert len(result.patentAppealDataBag) == 5
        appeal = result.patentAppealDataBag[0]
        assert appeal.appealNumber
        assert appeal.decisionData is not None


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

        assert result.count == 1812
        assert len(result.patentInterferenceDataBag) == 5
        interference = result.patentInterferenceDataBag[0]
        assert interference.interferenceNumber == "106130"
        assert interference.seniorPartyData is not None
        assert interference.seniorPartyData.applicationNumberText == "14443829"

    @pytest.mark.asyncio
    async def test_search_with_fields(self, vcr_cassette, api_key) -> None:
        """Search interferences requesting specific fields."""
        async with PtabInterferencesClient(api_key=api_key) as client:
            result = await client.search(
                query="*",
                fields=["interferenceNumber", "interferenceMetaData"],
                limit=5,
            )

        assert result.count == 1812
        assert len(result.patentInterferenceDataBag) == 5
        interference = result.patentInterferenceDataBag[0]
        assert interference.interferenceNumber == "106130"
        assert interference.interferenceMetaData is not None
        assert interference.interferenceMetaData.declarationDate == "2021-01-26"
        # Only the requested fields come back.
        assert interference.seniorPartyData is None

    @pytest.mark.asyncio
    async def test_search_with_sort(self, vcr_cassette, api_key) -> None:
        """Search interferences with a dict-shaped sort directive.

        Regression: the live API rejects string sort expressions, and the
        client's serializer raises TypeError on them — sort must be an
        OdpSort or a {"field", "order"} dict.
        """
        async with PtabInterferencesClient(api_key=api_key) as client:
            result = await client.search(
                query="*",
                sort={"field": "interferenceNumber", "order": "asc"},
                limit=5,
            )

        assert result.count > 0
        assert len(result.patentInterferenceDataBag) == 5
        numbers = [i.interferenceNumber for i in result.patentInterferenceDataBag]
        assert all(numbers)
        assert numbers == sorted(numbers)

    @pytest.mark.asyncio
    async def test_get_decisions_by_number(self, vcr_cassette, api_key) -> None:
        """Get decisions for a specific interference number."""
        async with PtabInterferencesClient(api_key=api_key) as client:
            result = await client.get_decisions_by_number("105801")

        assert result.count == 1
        assert len(result.patentInterferenceDataBag) == 1
        interference = result.patentInterferenceDataBag[0]
        assert interference.interferenceNumber == "105801"
        assert interference.interferenceMetaData is not None
        assert interference.interferenceMetaData.interferenceStyleName == "Pippin V. THOMAS"
        assert interference.seniorPartyData is not None
        assert interference.seniorPartyData.patentNumber == "5752011"

    @pytest.mark.asyncio
    async def test_download(self, vcr_cassette, api_key) -> None:
        """Download interference decisions search results.

        Regression: the download endpoint keys its records as
        ``interferenceData`` (not ``patentInterferenceDataBag``) and omits
        ``count``; before normalization the client silently returned an
        empty bag for every real download.
        """
        async with PtabInterferencesClient(api_key=api_key) as client:
            result = await client.download(
                query="*",
                limit=5,
                file_format="json",
            )

        assert result.count == 5
        assert len(result.patentInterferenceDataBag) == 5
        interference = result.patentInterferenceDataBag[0]
        assert interference.interferenceNumber
        assert interference.documentData is not None


class TestPtabModels:
    """Tests for PTAB response model parsing."""

    @pytest.mark.asyncio
    async def test_trial_proceeding_model_fields(self, vcr_cassette, api_key) -> None:
        """Verify trial proceeding model parses all expected fields."""
        async with PtabTrialsClient(api_key=api_key) as client:
            result = await client.search_proceedings(query="*", limit=1)

        assert result.count == 19246
        proceeding = result.patentTrialProceedingDataBag[0]
        assert proceeding.trialNumber == "IPR2026-00338"
        assert proceeding.trialMetaData is not None
        assert proceeding.trialMetaData.petitionFilingDate == "2026-04-21"
        assert proceeding.patentOwnerData is not None
        assert proceeding.patentOwnerData.applicationNumberText == "11614429"
        assert proceeding.regularPetitionerData is not None
        assert proceeding.regularPetitionerData.realPartyInInterestName == "Johnson Controls Inc."

    @pytest.mark.asyncio
    async def test_appeal_model_fields(self, vcr_cassette, api_key) -> None:
        """Verify appeal model parses all expected fields."""
        async with PtabAppealsClient(api_key=api_key) as client:
            result = await client.search(query="*", limit=1)

        assert result.count == 163252
        appeal = result.patentAppealDataBag[0]
        assert appeal.appealNumber == "2026001340"
        assert appeal.appealMetaData is not None
        assert appeal.appealMetaData.applicationTypeCategory == "REEXAM"
        assert appeal.appellantData is not None
        assert appeal.appellantData.applicationNumberText == "90019181"
        assert appeal.decisionData is not None
        assert appeal.decisionData.decisionIssueDate == "2026-04-15"

    @pytest.mark.asyncio
    async def test_interference_model_fields(self, vcr_cassette, api_key) -> None:
        """Verify interference model parses all expected fields."""
        async with PtabInterferencesClient(api_key=api_key) as client:
            result = await client.search(query="*", limit=1)

        assert result.count == 1812
        interference = result.patentInterferenceDataBag[0]
        assert interference.interferenceNumber == "106130"
        assert interference.interferenceMetaData is not None
        assert interference.interferenceMetaData.declarationDate == "2021-01-26"
        assert interference.seniorPartyData is not None
        assert interference.seniorPartyData.applicationNumberText == "14443829"
        # The search payload carries the decision under ``documentData``.
        assert interference.documentData is not None
        assert interference.documentData.documentTitleText == "Judgment 37 C.F.R. § 41.127(a)"


class TestPtabDownloadNormalization:
    """No-network tests for the PTAB download envelope normalization.

    Fixture payloads are trimmed from live /search/download captures
    (2026-07-20): records arrive under a flat key (``patentTrialData`` for
    trials and appeals, ``interferenceData`` for interferences) with no
    ``count``.
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

    def test_appeals_download_envelope(self) -> None:
        from patent_client_agents.uspto_odp.clients.base import _normalize_download_bag
        from patent_client_agents.uspto_odp.models import PtabAppealResponse

        data = {
            "patentTrialData": [
                {
                    "decisionData": {
                        "decisionTypeCategory": "Decision",
                        "appealOutcomeCategory": "Reversed",
                        "decisionIssueDate": "2026-04-21",
                    },
                    "appealNumber": "2026000736",
                    "appellantData": {
                        "realPartyInInterestName": "Raytheon Company",
                        "technologyCenterNumber": "2800",
                        "applicationNumberText": "18354034",
                    },
                }
            ]
        }
        result = PtabAppealResponse.model_validate(
            _normalize_download_bag(data, "patentAppealDataBag")
        )
        assert result.count == 1
        appeal = result.patentAppealDataBag[0]
        assert appeal.appealNumber == "2026000736"
        assert appeal.decisionData is not None
        assert appeal.decisionData.appealOutcomeCategory == "Reversed"
        assert appeal.appellantData is not None
        assert appeal.appellantData.technologyCenterNumber == "2800"

    def test_interferences_download_envelope(self) -> None:
        from patent_client_agents.uspto_odp.clients.base import _normalize_download_bag
        from patent_client_agents.uspto_odp.models import PtabInterferenceResponse

        data = {
            "interferenceData": [
                {
                    "interferenceNumber": "106130",
                    "interferenceMetaData": {
                        "interferenceStyleName": "KAPLAN v. CANI",
                    },
                    "documentData": {
                        "decisionTypeCategory": "Decision",
                        "decisionIssueDate": "2025-01-28",
                        "interferenceOutcomeCategory": "Judgment",
                    },
                    "seniorPartyData": {
                        "realPartyInInterestName": "UNIVERSITÉ CATHOLIQUE DE LOUVAIN",
                        "applicationNumberText": "14443829",
                    },
                }
            ]
        }
        result = PtabInterferenceResponse.model_validate(
            _normalize_download_bag(
                data, "patentInterferenceDataBag", records_key="interferenceData"
            )
        )
        assert result.count == 1
        interference = result.patentInterferenceDataBag[0]
        assert interference.interferenceNumber == "106130"
        assert interference.documentData is not None
        assert interference.documentData.interferenceOutcomeCategory == "Judgment"
        assert interference.seniorPartyData is not None
        assert interference.seniorPartyData.applicationNumberText == "14443829"

    @pytest.mark.asyncio
    async def test_string_sort_raises_type_error(self) -> None:
        """A plain string sort is rejected client-side, never sent to the API."""
        async with PtabTrialsClient(api_key="test-key") as client:
            with pytest.raises(TypeError, match="Unsupported item type"):
                await client.search_proceedings(sort="trialNumber asc", limit=5)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_appeals_string_sort_raises_type_error(self) -> None:
        async with PtabAppealsClient(api_key="test-key") as client:
            with pytest.raises(TypeError, match="Unsupported item type"):
                await client.search(sort="appealNumber asc", limit=5)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_interferences_string_sort_raises_type_error(self) -> None:
        async with PtabInterferencesClient(api_key="test-key") as client:
            with pytest.raises(TypeError, match="Unsupported item type"):
                await client.search(sort="interferenceNumber asc", limit=5)  # type: ignore[arg-type]
