"""Backward-compatible facade over domain-specific USPTO ODP clients.

This module maintains the original UsptoOdpClient interface for backward
compatibility. For new code, prefer the domain-specific clients:

- ApplicationsClient: Patent applications, documents, family graphs
- BulkDataClient: Bulk data products
- PetitionsClient: Petition decisions
- PtabTrialsClient: PTAB trial proceedings, decisions, documents
- PtabAppealsClient: PTAB ex parte appeals
- PtabInterferencesClient: PTAB interferences
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any, Self

import httpx

from .clients import (
    ApplicationsClient,
    BulkDataClient,
    PetitionsClient,
    PtabAppealsClient,
    PtabInterferencesClient,
    PtabTrialsClient,
)
from .clients.applications import (  # noqa: F401
    _merge_application_metadata,
    _normalize_patent_response,
)

# Re-export for backward compatibility
from .clients.base import (  # noqa: F401
    PaginationModel,
    SearchPayload,
)
from .models import (
    ApplicationResponse,
    AssignmentResponse,
    BulkDataProductResponse,
    BulkDataSearchResponse,
    DocumentsResponse,
    FamilyGraphResponse,
    OdpFilter,
    OdpRangeFilter,
    OdpSort,
    PetitionDecisionFilter,
    PetitionDecisionIdentifierResponse,
    PetitionDecisionRange,
    PetitionDecisionResponse,
    PetitionDecisionSort,
    PtabAppealResponse,
    PtabInterferenceResponse,
    PtabTrialDecisionResponse,
    PtabTrialDocumentResponse,
    PtabTrialProceedingResponse,
    SearchResponse,
)


class UsptoOdpClient:
    """Unified client for USPTO Open Data Portal.

    This class maintains backward compatibility with the original monolithic client.
    It delegates to domain-specific clients internally.

    For new code, prefer using the domain-specific clients directly:

    - ApplicationsClient: Patent applications
    - BulkDataClient: Bulk data products
    - PetitionsClient: Petition decisions
    - PtabTrialsClient: PTAB trials
    - PtabAppealsClient: PTAB appeals
    - PtabInterferencesClient: PTAB interferences

    Example:
        # Old style (still works)
        async with UsptoOdpClient() as client:
            result = await client.search_applications(query="cancer")

        # New style (preferred)
        async with ApplicationsClient() as client:
            result = await client.search(query="cancer")
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = "https://api.uspto.gov",
        cache_path: Path | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize the client.

        Args:
            api_key: USPTO ODP API key. Falls back to USPTO_ODP_API_KEY env var.
            base_url: Override the default base URL.
            cache_path: Custom path for the cache directory.
            client: Existing httpx.AsyncClient to use (for testing).
        """
        # Common kwargs for all sub-clients
        kwargs: dict[str, Any] = {
            "base_url": base_url,
        }
        if cache_path:
            kwargs["cache_path"] = cache_path
        if client:
            kwargs["client"] = client

        self._applications = ApplicationsClient(api_key=api_key, **kwargs)
        self._bulkdata = BulkDataClient(api_key=api_key, **kwargs)
        self._petitions = PetitionsClient(api_key=api_key, **kwargs)
        self._ptab_trials = PtabTrialsClient(api_key=api_key, **kwargs)
        self._ptab_appeals = PtabAppealsClient(api_key=api_key, **kwargs)
        self._ptab_interferences = PtabInterferencesClient(api_key=api_key, **kwargs)

        # Expose api_key for compatibility
        self.api_key = self._applications.api_key
        self.base_url = self._applications.base_url

    async def close(self) -> None:
        """Close all underlying clients."""
        await self._applications.close()
        await self._bulkdata.close()
        await self._petitions.close()
        await self._ptab_trials.close()
        await self._ptab_appeals.close()
        await self._ptab_interferences.close()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # =========================================================================
    # Applications API (delegated to ApplicationsClient)
    # =========================================================================

    def _normalize_application_number(self, application_number: str) -> str:
        """Normalize application number (for compatibility)."""
        return self._applications._normalize_application_number(application_number)

    async def search_applications(
        self,
        *,
        query: str | None = None,
        fields: list[str] | None = None,
        facets: list[str] | None = None,
        filters: Sequence[OdpFilter | dict[str, Any]] | None = None,
        range_filters: Sequence[OdpRangeFilter | dict[str, Any]] | None = None,
        sort: Sequence[OdpSort | dict[str, Any]] | None = None,
        limit: int = 25,
        offset: int = 0,
        raw_payload: dict[str, Any] | None = None,
    ) -> SearchResponse:
        """Search patent applications."""
        return await self._applications.search(
            query=query,
            fields=fields,
            facets=facets,
            filters=filters,
            range_filters=range_filters,
            sort=sort,
            limit=limit,
            offset=offset,
            raw_payload=raw_payload,
        )

    async def get_application(self, application_number: str) -> ApplicationResponse:
        """Get a single application by number."""
        return await self._applications.get(application_number)

    async def get_documents(
        self,
        application_number: str,
        *,
        include_associated: bool = True,
    ) -> DocumentsResponse:
        """List file-wrapper documents for an application."""
        return await self._applications.get_documents(
            application_number, include_associated=include_associated
        )

    async def get_family(
        self, identifier: str, *, identifier_type: str = "patent", batch_size: int = 25
    ) -> FamilyGraphResponse:
        """Build a patent family graph."""
        return await self._applications.get_family(
            identifier, identifier_type=identifier_type, batch_size=batch_size
        )

    async def get_assignment(self, application_number: str) -> AssignmentResponse:
        """Get assignment history for an application."""
        return await self._applications.get_assignment(application_number)

    async def download_document(
        self,
        application_number: str,
        document_identifier: str,
        *,
        output_path: str | Path | None = None,
    ) -> bytes:
        """Download a file-wrapper document PDF.

        Args:
            application_number: The application number (e.g., "10827445").
            document_identifier: The document identifier from DocumentRecord.
            output_path: Optional path to save the PDF.

        Returns:
            The PDF content as bytes.

        Example:
            >>> async with UsptoOdpClient() as client:
            ...     docs = await client.get_documents("10827445")
            ...     for doc in docs.documents:
            ...         if doc.documentCode == "CTRS":
            ...             pdf = await client.download_document(
            ...                 "10827445", doc.documentIdentifier
            ...             )
        """
        return await self._applications.download_document(
            application_number, document_identifier, output_path=output_path
        )

    async def download_documents(
        self,
        application_number: str,
        *,
        document_codes: Sequence[str] | None = None,
        output_dir: str | Path | None = None,
    ) -> list[tuple[Any, bytes]]:
        """Download multiple file-wrapper documents for an application.

        Args:
            application_number: The application number.
            document_codes: Optional list of document codes to filter by.
            output_dir: Optional directory to save PDFs.

        Returns:
            List of (DocumentRecord, bytes) tuples.
        """
        return await self._applications.download_documents(
            application_number, document_codes=document_codes, output_dir=output_dir
        )

    # =========================================================================
    # Bulk Data API (delegated to BulkDataClient)
    # =========================================================================

    async def search_bulk_datasets(
        self,
        *,
        query: str | None = None,
        sort: str | None = None,
        offset: int = 0,
        limit: int = 25,
        facets: str | Sequence[str] | None = None,
        fields: str | Sequence[str] | None = None,
        filters: str | Sequence[str] | None = None,
        range_filters: str | Sequence[str] | None = None,
    ) -> BulkDataSearchResponse:
        """Search bulk data products."""
        return await self._bulkdata.search(
            query=query,
            sort=sort,
            offset=offset,
            limit=limit,
            facets=facets,
            fields=fields,
            filters=filters,
            range_filters=range_filters,
        )

    async def get_bulk_dataset_product(
        self,
        product_identifier: str,
        *,
        file_from_date: date | str | None = None,
        file_to_date: date | str | None = None,
        offset: int | None = None,
        limit: int | None = None,
        include_files: bool | None = None,
        latest_only: bool | None = None,
    ) -> BulkDataProductResponse:
        """Get a specific bulk data product."""
        return await self._bulkdata.get_product(
            product_identifier,
            file_from_date=file_from_date,
            file_to_date=file_to_date,
            offset=offset,
            limit=limit,
            include_files=include_files,
            latest_only=latest_only,
        )

    # =========================================================================
    # Petitions API (delegated to PetitionsClient)
    # =========================================================================

    async def search_petitions(
        self,
        *,
        q: str | None = None,
        filters: Sequence[PetitionDecisionFilter | dict[str, Any]] | None = None,
        range_filters: Sequence[PetitionDecisionRange | dict[str, Any]] | None = None,
        sort: Sequence[PetitionDecisionSort | dict[str, Any]] | None = None,
        fields: Sequence[str] | None = None,
        facets: Sequence[str] | None = None,
        limit: int | None = 25,
        offset: int | None = 0,
    ) -> PetitionDecisionResponse:
        """Search petition decisions."""
        return await self._petitions.search(
            q=q,
            filters=filters,
            range_filters=range_filters,
            sort=sort,
            fields=fields,
            facets=facets,
            limit=limit,
            offset=offset,
        )

    async def download_petitions(
        self,
        *,
        q: str | None = None,
        filters: Sequence[PetitionDecisionFilter | dict[str, Any]] | None = None,
        range_filters: Sequence[PetitionDecisionRange | dict[str, Any]] | None = None,
        sort: Sequence[PetitionDecisionSort | dict[str, Any]] | None = None,
        fields: Sequence[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        file_format: str | None = None,
    ) -> PetitionDecisionResponse:
        """Download petition decisions search results."""
        return await self._petitions.download(
            q=q,
            filters=filters,
            range_filters=range_filters,
            sort=sort,
            fields=fields,
            limit=limit,
            offset=offset,
            file_format=file_format,
        )

    async def get_petition(
        self,
        petition_decision_record_identifier: str,
        *,
        include_documents: bool = False,
    ) -> PetitionDecisionIdentifierResponse:
        """Get a specific petition decision."""
        return await self._petitions.get(
            petition_decision_record_identifier,
            include_documents=include_documents,
        )

    # =========================================================================
    # PTAB Trial Proceedings (delegated to PtabTrialsClient)
    # =========================================================================

    async def search_trial_proceedings(
        self,
        *,
        query: str | None = None,
        fields: Sequence[str] | None = None,
        facets: Sequence[str] | None = None,
        filters: Sequence[str] | None = None,
        range_filters: Sequence[str] | None = None,
        sort: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> PtabTrialProceedingResponse:
        """Search PTAB trial proceedings."""
        return await self._ptab_trials.search_proceedings(
            query=query,
            fields=fields,
            facets=facets,
            filters=filters,
            range_filters=range_filters,
            sort=sort,
            limit=limit,
            offset=offset,
        )

    async def get_trial_proceeding(self, trial_number: str) -> PtabTrialProceedingResponse:
        """Get a single PTAB trial proceeding."""
        return await self._ptab_trials.get_proceeding(trial_number)

    async def download_trial_proceedings(
        self,
        *,
        query: str | None = None,
        fields: Sequence[str] | None = None,
        filters: Sequence[str] | None = None,
        range_filters: Sequence[str] | None = None,
        sort: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        file_format: str | None = None,
    ) -> PtabTrialProceedingResponse:
        """Download PTAB trial proceedings search results."""
        return await self._ptab_trials.download_proceedings(
            query=query,
            fields=fields,
            filters=filters,
            range_filters=range_filters,
            sort=sort,
            limit=limit,
            offset=offset,
            file_format=file_format,
        )

    # =========================================================================
    # PTAB Trial Decisions (delegated to PtabTrialsClient)
    # =========================================================================

    async def search_trial_decisions(
        self,
        *,
        query: str | None = None,
        fields: Sequence[str] | None = None,
        facets: Sequence[str] | None = None,
        filters: Sequence[str] | None = None,
        range_filters: Sequence[str] | None = None,
        sort: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> PtabTrialDecisionResponse:
        """Search PTAB trial decisions."""
        return await self._ptab_trials.search_decisions(
            query=query,
            fields=fields,
            facets=facets,
            filters=filters,
            range_filters=range_filters,
            sort=sort,
            limit=limit,
            offset=offset,
        )

    async def get_trial_decision(self, document_identifier: str) -> PtabTrialDecisionResponse:
        """Get a single PTAB trial decision."""
        return await self._ptab_trials.get_decision(document_identifier)

    async def get_trial_decisions_by_trial(self, trial_number: str) -> PtabTrialDecisionResponse:
        """Get all decisions for a PTAB trial."""
        return await self._ptab_trials.get_decisions_by_trial(trial_number)

    async def download_trial_decisions(
        self,
        *,
        query: str | None = None,
        fields: Sequence[str] | None = None,
        filters: Sequence[str] | None = None,
        range_filters: Sequence[str] | None = None,
        sort: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        file_format: str | None = None,
    ) -> PtabTrialDecisionResponse:
        """Download PTAB trial decisions search results."""
        return await self._ptab_trials.download_decisions(
            query=query,
            fields=fields,
            filters=filters,
            range_filters=range_filters,
            sort=sort,
            limit=limit,
            offset=offset,
            file_format=file_format,
        )

    # =========================================================================
    # PTAB Trial Documents (delegated to PtabTrialsClient)
    # =========================================================================

    async def search_trial_documents(
        self,
        *,
        query: str | None = None,
        fields: Sequence[str] | None = None,
        facets: Sequence[str] | None = None,
        filters: Sequence[str] | None = None,
        range_filters: Sequence[str] | None = None,
        sort: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> PtabTrialDocumentResponse:
        """Search PTAB trial documents."""
        return await self._ptab_trials.search_documents(
            query=query,
            fields=fields,
            facets=facets,
            filters=filters,
            range_filters=range_filters,
            sort=sort,
            limit=limit,
            offset=offset,
        )

    async def get_trial_document(self, document_identifier: str) -> PtabTrialDocumentResponse:
        """Get a single PTAB trial document."""
        return await self._ptab_trials.get_document(document_identifier)

    async def get_trial_documents_by_trial(self, trial_number: str) -> PtabTrialDocumentResponse:
        """Get all documents for a PTAB trial."""
        return await self._ptab_trials.get_documents_by_trial(trial_number)

    async def download_trial_documents(
        self,
        *,
        query: str | None = None,
        fields: Sequence[str] | None = None,
        filters: Sequence[str] | None = None,
        range_filters: Sequence[str] | None = None,
        sort: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        file_format: str | None = None,
    ) -> PtabTrialDocumentResponse:
        """Download PTAB trial documents search results."""
        return await self._ptab_trials.download_documents(
            query=query,
            fields=fields,
            filters=filters,
            range_filters=range_filters,
            sort=sort,
            limit=limit,
            offset=offset,
            file_format=file_format,
        )

    # =========================================================================
    # PTAB Appeals (delegated to PtabAppealsClient)
    # =========================================================================

    async def search_appeal_decisions(
        self,
        *,
        query: str | None = None,
        fields: Sequence[str] | None = None,
        facets: Sequence[str] | None = None,
        filters: Sequence[str] | None = None,
        range_filters: Sequence[str] | None = None,
        sort: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> PtabAppealResponse:
        """Search PTAB appeal decisions."""
        return await self._ptab_appeals.search(
            query=query,
            fields=fields,
            facets=facets,
            filters=filters,
            range_filters=range_filters,
            sort=sort,
            limit=limit,
            offset=offset,
        )

    async def get_appeal_decision(self, document_identifier: str) -> PtabAppealResponse:
        """Get a single PTAB appeal decision."""
        return await self._ptab_appeals.get_decision(document_identifier)

    async def get_appeal_decisions_by_number(self, appeal_number: str) -> PtabAppealResponse:
        """Get all decisions for a PTAB appeal."""
        return await self._ptab_appeals.get_decisions_by_number(appeal_number)

    async def download_appeal_decisions(
        self,
        *,
        query: str | None = None,
        fields: Sequence[str] | None = None,
        filters: Sequence[str] | None = None,
        range_filters: Sequence[str] | None = None,
        sort: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        file_format: str | None = None,
    ) -> PtabAppealResponse:
        """Download PTAB appeal decisions search results."""
        return await self._ptab_appeals.download(
            query=query,
            fields=fields,
            filters=filters,
            range_filters=range_filters,
            sort=sort,
            limit=limit,
            offset=offset,
            file_format=file_format,
        )

    # =========================================================================
    # PTAB Interferences (delegated to PtabInterferencesClient)
    # =========================================================================

    async def search_interference_decisions(
        self,
        *,
        query: str | None = None,
        fields: Sequence[str] | None = None,
        facets: Sequence[str] | None = None,
        filters: Sequence[str] | None = None,
        range_filters: Sequence[str] | None = None,
        sort: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> PtabInterferenceResponse:
        """Search PTAB interference decisions."""
        return await self._ptab_interferences.search(
            query=query,
            fields=fields,
            facets=facets,
            filters=filters,
            range_filters=range_filters,
            sort=sort,
            limit=limit,
            offset=offset,
        )

    async def get_interference_decision(self, document_identifier: str) -> PtabInterferenceResponse:
        """Get a single PTAB interference decision."""
        return await self._ptab_interferences.get_decision(document_identifier)

    async def get_interference_decisions_by_number(
        self, interference_number: str
    ) -> PtabInterferenceResponse:
        """Get all decisions for a PTAB interference."""
        return await self._ptab_interferences.get_decisions_by_number(interference_number)

    async def download_interference_decisions(
        self,
        *,
        query: str | None = None,
        fields: Sequence[str] | None = None,
        filters: Sequence[str] | None = None,
        range_filters: Sequence[str] | None = None,
        sort: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        file_format: str | None = None,
    ) -> PtabInterferenceResponse:
        """Download PTAB interference decisions search results."""
        return await self._ptab_interferences.download(
            query=query,
            fields=fields,
            filters=filters,
            range_filters=range_filters,
            sort=sort,
            limit=limit,
            offset=offset,
            file_format=file_format,
        )


# Re-export constants for backward compatibility
BASE_URL = "https://api.uspto.gov"

__all__ = [
    "UsptoOdpClient",
    "BASE_URL",
    "PaginationModel",
    "SearchPayload",
]
