"""VCR-recorded integration tests for USPTO ODP clients."""

import os

import pytest

from ip_tools.uspto_odp import (
    ApplicationsClient,
    BulkDataClient,
    PetitionsClient,
    PtabAppealsClient,
    PtabInterferencesClient,
    PtabTrialsClient,
)

# Use real key for recording, fake key for replay (VCR doesn't hit the network)
_API_KEY = os.getenv("USPTO_ODP_API_KEY", "fake-test-key-for-vcr-replay")


class TestApplicationsClient:
    """Integration tests for ODP ApplicationsClient."""

    @pytest.mark.vcr
    async def test_get_application(self):
        async with ApplicationsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.get("16123456")

        assert result is not None
        assert result.count >= 0
        assert isinstance(result.patentBag, list)

    @pytest.mark.vcr
    async def test_search_applications(self):
        async with ApplicationsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.search(query="artificial intelligence", limit=5)

        assert result is not None
        assert result.count >= 0
        assert isinstance(result.patentBag, list)
        assert len(result.patentBag) <= 5

    @pytest.mark.vcr
    async def test_search_returns_application_fields(self):
        async with ApplicationsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.search(query="semiconductor", limit=3)

        assert len(result.patentBag) > 0
        app = result.patentBag[0]
        # Application records should have basic fields
        assert isinstance(app, dict)
        assert "applicationNumberText" in app

    @pytest.mark.vcr
    async def test_get_documents(self):
        """Test retrieving file-wrapper documents for an application."""
        async with ApplicationsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.get_documents("16123456")

        assert result is not None
        assert isinstance(result.documents, list)

    @pytest.mark.vcr
    async def test_get_documents_without_associated(self):
        """Test retrieving documents without associated documents."""
        async with ApplicationsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.get_documents("16123456", include_associated=False)

        assert result is not None
        assert isinstance(result.documents, list)
        assert result.associatedDocuments is None

    @pytest.mark.vcr
    async def test_get_assignment(self):
        """Test retrieving assignment history for an application."""
        async with ApplicationsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.get_assignment("16123456")

        assert result is not None
        assert isinstance(result.assignmentBag, list)
        assert result.applicationNumberText is not None

    @pytest.mark.vcr
    async def test_get_family(self):
        """Test building a patent family graph from an application number."""
        async with ApplicationsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.get_family("16123456")

        assert result is not None
        assert result.rootApplication is not None
        assert isinstance(result.nodes, list)
        assert isinstance(result.edges, list)
        assert len(result.nodes) > 0


class TestPtabTrialsClient:
    """Integration tests for ODP PtabTrialsClient."""

    @pytest.mark.vcr
    async def test_search_proceedings(self):
        async with PtabTrialsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.search_proceedings(limit=5)

        assert result is not None
        assert result.count >= 0
        assert isinstance(result.patentTrialProceedingDataBag, list)
        assert len(result.patentTrialProceedingDataBag) <= 5

    @pytest.mark.vcr
    async def test_search_proceedings_has_data(self):
        async with PtabTrialsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.search_proceedings(limit=3)

        assert len(result.patentTrialProceedingDataBag) > 0

    @pytest.mark.vcr
    async def test_get_proceeding(self):
        """Test retrieving a single PTAB trial proceeding by trial number."""
        async with PtabTrialsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.get_proceeding("IPR2021-00001")

        assert result is not None
        assert result.count >= 1
        assert len(result.patentTrialProceedingDataBag) >= 1

    @pytest.mark.vcr
    async def test_search_documents(self):
        """Test searching PTAB trial documents."""
        async with PtabTrialsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.search_documents(limit=5)

        assert result is not None
        assert result.count >= 0
        assert isinstance(result.patentTrialDocumentDataBag, list)
        assert len(result.patentTrialDocumentDataBag) <= 5

    @pytest.mark.vcr
    async def test_search_decisions(self):
        """Test searching PTAB trial decisions."""
        async with PtabTrialsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.search_decisions(limit=5)

        assert result is not None
        assert result.count >= 0
        assert isinstance(result.patentTrialDocumentDataBag, list)
        assert len(result.patentTrialDocumentDataBag) <= 5

    @pytest.mark.vcr
    async def test_get_documents_by_trial(self):
        """Test retrieving all documents for a specific trial."""
        async with PtabTrialsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.get_documents_by_trial("IPR2021-00001")

        assert result is not None
        assert isinstance(result.patentTrialDocumentDataBag, list)

    @pytest.mark.vcr
    async def test_get_decisions_by_trial(self):
        """Test retrieving all decisions for a specific trial."""
        async with PtabTrialsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.get_decisions_by_trial("IPR2021-00001")

        assert result is not None
        assert isinstance(result.patentTrialDocumentDataBag, list)

    @pytest.mark.vcr
    async def test_download_proceedings(self):
        """Test downloading trial proceedings search results."""
        async with PtabTrialsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.download_proceedings(limit=3)

        assert result is not None
        assert isinstance(result.patentTrialProceedingDataBag, list)


class TestPtabAppealsClient:
    """Integration tests for ODP PtabAppealsClient."""

    @pytest.mark.vcr
    async def test_search_appeals(self):
        """Test searching PTAB appeal decisions."""
        async with PtabAppealsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.search(limit=5)

        assert result is not None
        assert result.count >= 0
        assert isinstance(result.patentAppealDataBag, list)
        assert len(result.patentAppealDataBag) <= 5

    @pytest.mark.vcr
    async def test_search_appeals_has_data(self):
        """Test that appeal search returns actual data."""
        async with PtabAppealsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.search(limit=3)

        assert len(result.patentAppealDataBag) > 0

    @pytest.mark.vcr
    async def test_search_appeals_with_query(self):
        """Test searching appeals with a query string."""
        async with PtabAppealsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.search(query="software", limit=3)

        assert result is not None
        assert isinstance(result.patentAppealDataBag, list)

    @pytest.mark.vcr
    async def test_get_appeal_decision(self):
        """Test retrieving a single appeal decision by document identifier.

        First search for an appeal to get a valid document identifier,
        then retrieve it directly.
        """
        async with PtabAppealsClient(api_key=_API_KEY, use_cache=False) as client:
            # First, find a valid appeal
            search_result = await client.search(limit=1)
            assert len(search_result.patentAppealDataBag) > 0
            appeal = search_result.patentAppealDataBag[0]
            # Get the document identifier from documentData
            doc_data = appeal.documentData
            if doc_data and doc_data.documentIdentifier:
                result = await client.get_decision(doc_data.documentIdentifier)
                assert result is not None
                assert len(result.patentAppealDataBag) >= 1

    @pytest.mark.vcr
    async def test_get_decisions_by_appeal_number(self):
        """Test retrieving all decisions for a specific appeal number.

        First search for an appeal to get a valid appeal number,
        then retrieve decisions for it.
        """
        async with PtabAppealsClient(api_key=_API_KEY, use_cache=False) as client:
            search_result = await client.search(limit=1)
            assert len(search_result.patentAppealDataBag) > 0
            appeal = search_result.patentAppealDataBag[0]
            if appeal.appealNumber:
                result = await client.get_decisions_by_number(appeal.appealNumber)
                assert result is not None
                assert isinstance(result.patentAppealDataBag, list)

    @pytest.mark.vcr
    async def test_download_appeals(self):
        """Test downloading appeal decisions search results."""
        async with PtabAppealsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.download(limit=3)

        assert result is not None
        assert isinstance(result.patentAppealDataBag, list)


class TestPtabInterferencesClient:
    """Integration tests for ODP PtabInterferencesClient."""

    @pytest.mark.vcr
    async def test_search_interferences(self):
        """Test searching PTAB interference decisions."""
        async with PtabInterferencesClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.search(limit=5)

        assert result is not None
        assert result.count >= 0
        assert isinstance(result.patentInterferenceDataBag, list)
        assert len(result.patentInterferenceDataBag) <= 5

    @pytest.mark.vcr
    async def test_search_interferences_has_data(self):
        """Test that interference search returns actual data."""
        async with PtabInterferencesClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.search(limit=3)

        assert len(result.patentInterferenceDataBag) > 0

    @pytest.mark.vcr
    async def test_get_interference_decision(self):
        """Test retrieving a single interference decision.

        First search to get a valid document identifier, then retrieve it.
        """
        async with PtabInterferencesClient(api_key=_API_KEY, use_cache=False) as client:
            search_result = await client.search(limit=1)
            assert len(search_result.patentInterferenceDataBag) > 0
            interference = search_result.patentInterferenceDataBag[0]
            doc_data = interference.decisionDocumentData or interference.documentData
            if doc_data and doc_data.documentIdentifier:
                result = await client.get_decision(doc_data.documentIdentifier)
                assert result is not None
                assert len(result.patentInterferenceDataBag) >= 1

    @pytest.mark.vcr
    async def test_get_decisions_by_interference_number(self):
        """Test retrieving all decisions for a specific interference number.

        First search to get a valid interference number, then retrieve decisions.
        """
        async with PtabInterferencesClient(api_key=_API_KEY, use_cache=False) as client:
            search_result = await client.search(limit=1)
            assert len(search_result.patentInterferenceDataBag) > 0
            interference = search_result.patentInterferenceDataBag[0]
            if interference.interferenceNumber:
                result = await client.get_decisions_by_number(interference.interferenceNumber)
                assert result is not None
                assert isinstance(result.patentInterferenceDataBag, list)

    @pytest.mark.vcr
    async def test_download_interferences(self):
        """Test downloading interference decisions search results."""
        async with PtabInterferencesClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.download(limit=3)

        assert result is not None
        assert isinstance(result.patentInterferenceDataBag, list)


class TestBulkDataClient:
    """Integration tests for ODP BulkDataClient."""

    @pytest.mark.vcr
    async def test_search_bulk_data(self):
        async with BulkDataClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.search(limit=5)

        assert result is not None
        assert result.count >= 0
        assert isinstance(result.bulkDataProductBag, list)
        assert len(result.bulkDataProductBag) <= 5

    @pytest.mark.vcr
    async def test_search_bulk_data_has_products(self):
        async with BulkDataClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.search(limit=3)

        assert len(result.bulkDataProductBag) > 0

    @pytest.mark.vcr
    async def test_get_product(self):
        """Test retrieving a specific bulk data product by identifier."""
        async with BulkDataClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.get_product("PTFWPRE")

        assert result is not None
        assert isinstance(result.bulkDataProductBag, list)

    @pytest.mark.vcr
    async def test_get_product_with_params(self):
        """Test retrieving a bulk data product with additional parameters."""
        async with BulkDataClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.get_product(
                "PTFWPRE",
                limit=2,
                include_files=True,
            )

        assert result is not None
        assert isinstance(result.bulkDataProductBag, list)

    @pytest.mark.vcr
    async def test_search_bulk_data_with_query(self):
        """Test searching bulk data with a query string."""
        async with BulkDataClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.search(query="patent", limit=3)

        assert result is not None
        assert isinstance(result.bulkDataProductBag, list)


class TestPetitionsClient:
    """Integration tests for ODP PetitionsClient."""

    @pytest.mark.vcr
    async def test_search_petitions(self):
        async with PetitionsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.search(limit=5)

        assert result is not None
        assert result.count >= 0
        assert isinstance(result.petitionDecisionDataBag, list)
        assert len(result.petitionDecisionDataBag) <= 5

    @pytest.mark.vcr
    async def test_search_petitions_has_data(self):
        async with PetitionsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.search(limit=3)

        assert len(result.petitionDecisionDataBag) > 0

    @pytest.mark.vcr
    async def test_get_petition(self):
        """Test retrieving a specific petition decision.

        First search to get a valid petition decision ID, then retrieve it.
        """
        async with PetitionsClient(api_key=_API_KEY, use_cache=False) as client:
            search_result = await client.search(limit=1)
            assert len(search_result.petitionDecisionDataBag) > 0
            petition = search_result.petitionDecisionDataBag[0]
            if petition.petitionDecisionRecordIdentifier:
                result = await client.get(petition.petitionDecisionRecordIdentifier)
                assert result is not None
                assert isinstance(result.petitionDecisionDataBag, list)

    @pytest.mark.vcr
    async def test_get_petition_with_documents(self):
        """Test retrieving a petition decision including documents.

        First search to get a valid ID, then retrieve with include_documents=True.
        """
        async with PetitionsClient(api_key=_API_KEY, use_cache=False) as client:
            search_result = await client.search(limit=1)
            assert len(search_result.petitionDecisionDataBag) > 0
            petition = search_result.petitionDecisionDataBag[0]
            if petition.petitionDecisionRecordIdentifier:
                result = await client.get(
                    petition.petitionDecisionRecordIdentifier,
                    include_documents=True,
                )
                assert result is not None
                assert isinstance(result.petitionDecisionDataBag, list)

    @pytest.mark.vcr
    async def test_download_petitions(self):
        """Test downloading petition decisions search results."""
        async with PetitionsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.download(limit=3)

        assert result is not None
        assert isinstance(result.petitionDecisionDataBag, list)

    @pytest.mark.vcr
    async def test_search_petitions_with_query(self):
        """Test searching petitions with a query string."""
        async with PetitionsClient(api_key=_API_KEY, use_cache=False) as client:
            result = await client.search(q="revival", limit=3)

        assert result is not None
        assert isinstance(result.petitionDecisionDataBag, list)
