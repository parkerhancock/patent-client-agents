"""USPTO ODP PTAB Trials client."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ..models import (
    PtabTrialDecisionResponse,
    PtabTrialDocumentResponse,
    PtabTrialProceedingResponse,
)
from .base import PaginationModel, SearchPayload, UsptoOdpBaseClient, _prune


class PtabTrialsClient(UsptoOdpBaseClient):
    """Client for USPTO ODP PTAB Trials API.

    Provides methods to search and retrieve PTAB trial proceedings (IPR, PGR, CBM, DER),
    trial decisions, and trial documents.
    """

    # =========================================================================
    # Trial Proceedings
    # =========================================================================

    async def search_proceedings(
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
        """Search PTAB trial proceedings (IPR, PGR, CBM, DER).

        Args:
            query: Lucene-style search query.
            fields: Fields to return in response.
            facets: Fields to aggregate.
            filters: Filter expressions (e.g., "trialTypeCode:IPR").
            range_filters: Range filter expressions.
            sort: Sort expression (e.g., "petitionFilingDate desc").
            limit: Maximum results to return.
            offset: Number of results to skip.

        Returns:
            PtabTrialProceedingResponse with matching proceedings.
        """
        payload = SearchPayload(
            q=query,
            fields=list(fields) if fields else None,
            facets=list(facets) if facets else None,
            filters=list(filters) if filters else None,
            range_filters=list(range_filters) if range_filters else None,
            sort=[sort] if sort else None,
            pagination=PaginationModel(offset=offset, limit=limit),
        ).model_dump_pruned()

        data = await self._search_with_payload(
            "/api/v1/patent/trials/proceedings/search",
            payload,
            empty_bag_key="patentTrialProceedingDataBag",
            context="search trial proceedings",
        )
        data.setdefault("patentTrialProceedingDataBag", [])
        return PtabTrialProceedingResponse(**data)

    async def get_proceeding(self, trial_number: str) -> PtabTrialProceedingResponse:
        """Get a single PTAB trial proceeding by trial number.

        Args:
            trial_number: The trial number (e.g., "IPR2024-00001").

        Returns:
            PtabTrialProceedingResponse with the proceeding data.
        """
        from law_tools_core.exceptions import ValidationError

        trial_number = trial_number.strip()
        if not trial_number:
            raise ValidationError("trial_number is required")

        data = await self._request_json(
            "GET",
            f"/api/v1/patent/trials/proceedings/{trial_number}",
            context=f"get trial proceeding {trial_number}",
        )
        # Wrap single result in response format
        if "patentTrialProceedingDataBag" not in data:
            data = {"count": 1, "patentTrialProceedingDataBag": [data]}
        return PtabTrialProceedingResponse(**data)

    async def download_proceedings(
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
        """Download PTAB trial proceedings search results.

        Args:
            query: Lucene-style search query.
            fields: Fields to return.
            filters: Filter expressions.
            range_filters: Range filter expressions.
            sort: Sort expression.
            limit: Maximum results.
            offset: Results to skip.
            file_format: Output format ("json" or "csv").

        Returns:
            PtabTrialProceedingResponse with results.
        """
        payload: dict[str, Any] = {}
        if query:
            payload["q"] = query
        if fields:
            payload["fields"] = list(fields)
        if filters:
            payload["filters"] = list(filters)
        if range_filters:
            payload["rangeFilters"] = list(range_filters)
        if sort:
            payload["sort"] = sort
        if limit is not None or offset is not None:
            pagination: dict[str, Any] = {}
            if offset is not None:
                pagination["offset"] = offset
            if limit is not None:
                pagination["limit"] = limit
            payload["pagination"] = pagination
        if file_format:
            payload["format"] = file_format

        data = await self._search_with_payload(
            "/api/v1/patent/trials/proceedings/search/download",
            _prune(payload),
            empty_bag_key="patentTrialProceedingDataBag",
            context="download trial proceedings",
        )
        data.setdefault("patentTrialProceedingDataBag", [])
        return PtabTrialProceedingResponse(**data)

    # =========================================================================
    # Trial Decisions
    # =========================================================================

    async def search_decisions(
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
        """Search PTAB trial decisions.

        Args:
            query: Lucene-style search query.
            fields: Fields to return.
            facets: Fields to aggregate.
            filters: Filter expressions.
            range_filters: Range filter expressions.
            sort: Sort expression.
            limit: Maximum results.
            offset: Results to skip.

        Returns:
            PtabTrialDecisionResponse with matching decisions.
        """
        payload = SearchPayload(
            q=query,
            fields=list(fields) if fields else None,
            facets=list(facets) if facets else None,
            filters=list(filters) if filters else None,
            range_filters=list(range_filters) if range_filters else None,
            sort=[sort] if sort else None,
            pagination=PaginationModel(offset=offset, limit=limit),
        ).model_dump_pruned()

        data = await self._search_with_payload(
            "/api/v1/patent/trials/decisions/search",
            payload,
            empty_bag_key="patentTrialDocumentDataBag",
            context="search trial decisions",
        )
        data.setdefault("patentTrialDocumentDataBag", [])
        return PtabTrialDecisionResponse(**data)

    async def get_decision(self, document_identifier: str) -> PtabTrialDecisionResponse:
        """Get a single PTAB trial decision by document identifier.

        Args:
            document_identifier: The document identifier.

        Returns:
            PtabTrialDecisionResponse with the decision data.
        """
        from law_tools_core.exceptions import ValidationError

        document_identifier = document_identifier.strip()
        if not document_identifier:
            raise ValidationError("document_identifier is required")

        data = await self._request_json(
            "GET",
            f"/api/v1/patent/trials/decisions/{document_identifier}",
            context=f"get trial decision {document_identifier}",
        )
        if "patentTrialDocumentDataBag" not in data:
            data = {"count": 1, "patentTrialDocumentDataBag": [data]}
        return PtabTrialDecisionResponse(**data)

    async def get_decisions_by_trial(self, trial_number: str) -> PtabTrialDecisionResponse:
        """Get all decisions for a PTAB trial by trial number.

        Args:
            trial_number: The trial number (e.g., "IPR2024-00001").

        Returns:
            PtabTrialDecisionResponse with all decisions for the trial.
        """
        from law_tools_core.exceptions import ValidationError

        trial_number = trial_number.strip()
        if not trial_number:
            raise ValidationError("trial_number is required")

        data = await self._request_json(
            "GET",
            f"/api/v1/patent/trials/{trial_number}/decisions",
            context=f"get decisions for trial {trial_number}",
        )
        data.setdefault("patentTrialDocumentDataBag", [])
        return PtabTrialDecisionResponse(**data)

    async def download_decisions(
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
        payload: dict[str, Any] = {}
        if query:
            payload["q"] = query
        if fields:
            payload["fields"] = list(fields)
        if filters:
            payload["filters"] = list(filters)
        if range_filters:
            payload["rangeFilters"] = list(range_filters)
        if sort:
            payload["sort"] = sort
        if limit is not None or offset is not None:
            pagination: dict[str, Any] = {}
            if offset is not None:
                pagination["offset"] = offset
            if limit is not None:
                pagination["limit"] = limit
            payload["pagination"] = pagination
        if file_format:
            payload["format"] = file_format

        data = await self._search_with_payload(
            "/api/v1/patent/trials/decisions/search/download",
            _prune(payload),
            empty_bag_key="patentTrialDocumentDataBag",
            context="download trial decisions",
        )
        data.setdefault("patentTrialDocumentDataBag", [])
        return PtabTrialDecisionResponse(**data)

    # =========================================================================
    # Trial Documents
    # =========================================================================

    async def search_documents(
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
        """Search PTAB trial documents (filings, exhibits, etc.).

        Args:
            query: Lucene-style search query.
            fields: Fields to return.
            facets: Fields to aggregate.
            filters: Filter expressions.
            range_filters: Range filter expressions.
            sort: Sort expression.
            limit: Maximum results.
            offset: Results to skip.

        Returns:
            PtabTrialDocumentResponse with matching documents.
        """
        payload = SearchPayload(
            q=query,
            fields=list(fields) if fields else None,
            facets=list(facets) if facets else None,
            filters=list(filters) if filters else None,
            range_filters=list(range_filters) if range_filters else None,
            sort=[sort] if sort else None,
            pagination=PaginationModel(offset=offset, limit=limit),
        ).model_dump_pruned()

        data = await self._search_with_payload(
            "/api/v1/patent/trials/documents/search",
            payload,
            empty_bag_key="patentTrialDocumentDataBag",
            context="search trial documents",
        )
        data.setdefault("patentTrialDocumentDataBag", [])
        return PtabTrialDocumentResponse(**data)

    async def get_document(self, document_identifier: str) -> PtabTrialDocumentResponse:
        """Get a single PTAB trial document by document identifier.

        Args:
            document_identifier: The document identifier.

        Returns:
            PtabTrialDocumentResponse with the document data.
        """
        from law_tools_core.exceptions import ValidationError

        document_identifier = document_identifier.strip()
        if not document_identifier:
            raise ValidationError("document_identifier is required")

        data = await self._request_json(
            "GET",
            f"/api/v1/patent/trials/documents/{document_identifier}",
            context=f"get trial document {document_identifier}",
        )
        if "patentTrialDocumentDataBag" not in data:
            data = {"count": 1, "patentTrialDocumentDataBag": [data]}
        return PtabTrialDocumentResponse(**data)

    async def get_documents_by_trial(self, trial_number: str) -> PtabTrialDocumentResponse:
        """Get all documents for a PTAB trial by trial number.

        Args:
            trial_number: The trial number (e.g., "IPR2024-00001").

        Returns:
            PtabTrialDocumentResponse with all documents for the trial.
        """
        from law_tools_core.exceptions import ValidationError

        trial_number = trial_number.strip()
        if not trial_number:
            raise ValidationError("trial_number is required")

        data = await self._request_json(
            "GET",
            f"/api/v1/patent/trials/{trial_number}/documents",
            context=f"get documents for trial {trial_number}",
        )
        data.setdefault("patentTrialDocumentDataBag", [])
        return PtabTrialDocumentResponse(**data)

    async def download_documents(
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
        payload: dict[str, Any] = {}
        if query:
            payload["q"] = query
        if fields:
            payload["fields"] = list(fields)
        if filters:
            payload["filters"] = list(filters)
        if range_filters:
            payload["rangeFilters"] = list(range_filters)
        if sort:
            payload["sort"] = sort
        if limit is not None or offset is not None:
            pagination: dict[str, Any] = {}
            if offset is not None:
                pagination["offset"] = offset
            if limit is not None:
                pagination["limit"] = limit
            payload["pagination"] = pagination
        if file_format:
            payload["format"] = file_format

        data = await self._search_with_payload(
            "/api/v1/patent/trials/documents/search/download",
            _prune(payload),
            empty_bag_key="patentTrialDocumentDataBag",
            context="download trial documents",
        )
        data.setdefault("patentTrialDocumentDataBag", [])
        return PtabTrialDocumentResponse(**data)

    # =========================================================================
    # Document PDF Download
    # =========================================================================

    async def download_document_pdf(
        self,
        document_identifier: str,
        *,
        output_path: str | Path | None = None,
    ) -> bytes:
        """Download a PTAB trial document PDF by its document identifier.

        The document identifier is available from :pyattr:`PtabDocumentData.documentIdentifier`
        or :pyattr:`PtabDocumentData.fileDownloadURI`.

        Args:
            document_identifier: The document identifier (e.g., from
                ``get_documents_by_trial``).  If a full URI is provided
                (starting with ``/``), it is used directly; otherwise
                the standard download path is constructed.
            output_path: Optional path to save the PDF. Parent directories
                are created if needed.

        Returns:
            The PDF content as bytes.

        Example:
            >>> async with PtabTrialsClient() as client:
            ...     docs = await client.get_documents_by_trial("IPR2024-00001")
            ...     for doc_data in docs.patentTrialDocumentDataBag or []:
            ...         pdf = await client.download_document_pdf(
            ...             doc_data.documentIdentifier,
            ...             output_path=f"ptab_{doc_data.documentIdentifier}.pdf",
            ...         )
        """
        if document_identifier.startswith("/"):
            path = document_identifier
        else:
            path = f"/api/v1/patent/trials/documents/{document_identifier}/download"

        response = await self._request(
            "GET",
            path,
            context=f"download PTAB document {document_identifier}",
            timeout=120.0,
        )

        content = response.content

        if output_path is not None:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(content)

        return content


__all__ = ["PtabTrialsClient"]
