"""Client for USPTO ODP office action and citation endpoints.

These endpoints are on the Open Data Portal at api.uspto.gov, using
X-API-KEY auth and Solr/Lucene query syntax via form-urlencoded POST.

Endpoints:
    - /api/v1/patent/oa/oa_rejections/v2/records
    - /api/v1/patent/oa/oa_citations/v2/records
    - /api/v1/patent/oa/oa_actions/v1/records
    - /api/v1/patent/oa/enriched_cited_reference_metadata/v3/records
"""

from __future__ import annotations

from typing import Any

from patent_client_agents.uspto_odp.clients.base import UsptoOdpBaseClient

from .models import (
    CitationSearchResponse,
    EnrichedCitation,
    EnrichedCitationSearchResponse,
    OfficeActionCitation,
    OfficeActionRejection,
    OfficeActionText,
    OfficeActionTextSearchResponse,
    RejectionSearchResponse,
)


class OfficeActionClient(UsptoOdpBaseClient):
    """Client for USPTO ODP office action endpoints.

    Requires a USPTO ODP API key (``USPTO_ODP_API_KEY`` env var or ``api_key`` param).

    All search methods accept a ``criteria`` string using Lucene query syntax.
    Common query patterns::

        # By application number
        patentApplicationNumber:16123456

        # By rejection type
        hasRej103:1 AND nationalClass:438

        # Date ranges
        submissionDate:[2023-01-01T00:00:00 TO 2024-12-31T23:59:59]

        # Wildcard
        patentApplicationNumber:16*
    """

    CACHE_NAME = "uspto_office_actions"

    async def _search_dataset(
        self,
        dataset_path: str,
        criteria: str,
        start: int = 0,
        rows: int = 25,
    ) -> dict[str, Any]:
        """Execute an ODP office action search.

        Args:
            dataset_path: API path under /api/v1/patent/oa/.
            criteria: Lucene query string.
            start: Starting record offset.
            rows: Number of records to return.

        Returns:
            Parsed JSON with ``response.numFound``, ``response.start``,
            ``response.docs`` structure.
        """
        form_data = {
            "criteria": criteria,
            "start": str(start),
            "rows": str(rows),
        }
        result = await self._request_json(
            "POST",
            dataset_path,
            data=form_data,
            context=f"search {dataset_path}",
        )
        return result

    async def search_rejections(
        self,
        criteria: str,
        *,
        start: int = 0,
        rows: int = 25,
    ) -> RejectionSearchResponse:
        """Search office action rejections.

        Args:
            criteria: Lucene query (e.g. "patentApplicationNumber:16123456").
            start: Result offset for pagination.
            rows: Maximum results to return.

        Returns:
            RejectionSearchResponse with matching rejection records.
        """
        raw = await self._search_dataset(
            "/api/v1/patent/oa/oa_rejections/v2/records", criteria, start, rows
        )
        response = raw.get("response", {})
        docs = response.get("docs", [])
        return RejectionSearchResponse(
            num_found=response.get("numFound", 0),
            start=response.get("start", 0),
            results=[OfficeActionRejection.model_validate(doc) for doc in docs],
        )

    async def search_citations(
        self,
        criteria: str,
        *,
        start: int = 0,
        rows: int = 25,
    ) -> CitationSearchResponse:
        """Search office action citations.

        Args:
            criteria: Lucene query (e.g. "patentApplicationNumber:16123456").
            start: Result offset for pagination.
            rows: Maximum results to return.

        Returns:
            CitationSearchResponse with matching citation records.
        """
        raw = await self._search_dataset(
            "/api/v1/patent/oa/oa_citations/v2/records", criteria, start, rows
        )
        response = raw.get("response", {})
        docs = response.get("docs", [])
        return CitationSearchResponse(
            num_found=response.get("numFound", 0),
            start=response.get("start", 0),
            results=[OfficeActionCitation.model_validate(doc) for doc in docs],
        )

    async def search_office_action_text(
        self,
        criteria: str,
        *,
        start: int = 0,
        rows: int = 25,
    ) -> OfficeActionTextSearchResponse:
        """Search and retrieve full office action text.

        Args:
            criteria: Lucene query (e.g. "patentApplicationNumber:16123456").
            start: Result offset for pagination.
            rows: Maximum results to return.

        Returns:
            OfficeActionTextSearchResponse with matching records including bodyText.
        """
        raw = await self._search_dataset(
            "/api/v1/patent/oa/oa_actions/v1/records", criteria, start, rows
        )
        response = raw.get("response", {})
        docs = response.get("docs", [])
        return OfficeActionTextSearchResponse(
            num_found=response.get("numFound", 0),
            start=response.get("start", 0),
            results=[OfficeActionText.model_validate(doc) for doc in docs],
        )

    async def search_enriched_citations(
        self,
        criteria: str,
        *,
        start: int = 0,
        rows: int = 25,
    ) -> EnrichedCitationSearchResponse:
        """Search enriched citation metadata.

        Args:
            criteria: Lucene query (e.g. "patentApplicationNumber:16123456").
            start: Result offset for pagination.
            rows: Maximum results to return.

        Returns:
            EnrichedCitationSearchResponse with matching enriched citation records.
        """
        raw = await self._search_dataset(
            "/api/v1/patent/oa/enriched_cited_reference_metadata/v3/records",
            criteria,
            start,
            rows,
        )
        response = raw.get("response", {})
        docs = response.get("docs", [])
        return EnrichedCitationSearchResponse(
            num_found=response.get("numFound", 0),
            start=response.get("start", 0),
            results=[EnrichedCitation.model_validate(doc) for doc in docs],
        )


__all__ = ["OfficeActionClient"]
