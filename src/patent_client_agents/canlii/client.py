"""Async client for the CanLII REST API.

Spec: https://github.com/canlii/API_documentation/blob/master/EN.md

Auth is a free API key issued via the CanLII feedback form, passed on every
request as the ``api_key`` query parameter. Pass via the ``CANLII_API_KEY``
environment variable or the ``api_key`` constructor argument.

Pagination uses ``offset`` + ``resultCount`` (max 10000). The API enforces
a 10 MB response cap; very wide queries that hit it surface as a
``TOO_LONG`` error envelope which we surface as :class:`ApiError`.
"""

from __future__ import annotations

import os
from typing import Any

from mcp_data_core import BaseAsyncClient
from mcp_data_core.exceptions import ApiError, ConfigurationError

from .models import (
    CaseDatabaseList,
    CaseList,
    CaseMetadata,
    CitedCasesResponse,
    CitedLegislationsResponse,
    CitingCasesResponse,
    Language,
    LegislationDatabaseList,
    LegislationList,
    LegislationMetadata,
)

_MAX_RESULT_COUNT = 10_000


class CanLIIClient(BaseAsyncClient):
    """Async client for ``api.canlii.org``.

    See module docstring for the auth + pagination contract.
    """

    DEFAULT_BASE_URL: str = os.getenv("CANLII_BASE_URL", "https://api.canlii.org/v1")
    CACHE_NAME: str = "canlii"
    DEFAULT_TIMEOUT: float = 30.0

    def __init__(
        self,
        *,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_key = api_key or os.getenv("CANLII_API_KEY")
        if not resolved_key:
            raise ConfigurationError(
                "CanLII API key not provided. Set CANLII_API_KEY or pass api_key=..."
            )
        self._api_key = resolved_key
        super().__init__(
            headers={
                "Accept": "application/json",
                "User-Agent": "patent-client-agents-canlii/0.1",
            },
            **kwargs,
        )

    async def _get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a GET with ``api_key`` injected, raise on TOO_LONG envelopes."""
        merged = dict(params or {})
        merged["api_key"] = self._api_key
        # Drop None values so optional date filters can be unconditionally passed in.
        merged = {k: v for k, v in merged.items() if v is not None}

        payload = await self._request_json("GET", path, params=merged, context=path)
        if isinstance(payload, dict) and payload.get("error") == "TOO_LONG":
            raise ApiError(
                payload.get("message", "CanLII response exceeded the 10 MB cap"),
                status_code=413,
                response_body=str(payload)[:500],
            )
        return payload

    # ------------------------------------------------------------------
    # Cases
    # ------------------------------------------------------------------

    async def list_case_databases(self, *, language: Language = "en") -> CaseDatabaseList:
        """List every court/tribunal database CanLII indexes."""
        data = await self._get_json(f"/caseBrowse/{language}/")
        return CaseDatabaseList.model_validate(data)

    async def browse_cases(
        self,
        *,
        database_id: str,
        offset: int = 0,
        result_count: int = 100,
        language: Language = "en",
        published_before: str | None = None,
        published_after: str | None = None,
        modified_before: str | None = None,
        modified_after: str | None = None,
        changed_before: str | None = None,
        changed_after: str | None = None,
        decision_date_before: str | None = None,
        decision_date_after: str | None = None,
    ) -> CaseList:
        """List cases from ``database_id`` with optional date filters.

        Dates are ISO-8601 (YYYY-MM-DD) strings. ``result_count`` is capped at
        10000 by the upstream API.
        """
        if result_count > _MAX_RESULT_COUNT:
            raise ValueError(f"result_count must be <= {_MAX_RESULT_COUNT}")
        params = {
            "offset": offset,
            "resultCount": result_count,
            "publishedBefore": published_before,
            "publishedAfter": published_after,
            "modifiedBefore": modified_before,
            "modifiedAfter": modified_after,
            "changedBefore": changed_before,
            "changedAfter": changed_after,
            "decisionDateBefore": decision_date_before,
            "decisionDateAfter": decision_date_after,
        }
        data = await self._get_json(f"/caseBrowse/{language}/{database_id}/", params)
        return CaseList.model_validate(data)

    async def get_case(
        self,
        *,
        database_id: str,
        case_id: str,
        language: Language = "en",
    ) -> CaseMetadata:
        """Fetch metadata for a single case."""
        data = await self._get_json(f"/caseBrowse/{language}/{database_id}/{case_id}/")
        return CaseMetadata.model_validate(data)

    # ------------------------------------------------------------------
    # Citator
    # ------------------------------------------------------------------

    async def get_cited_cases(self, *, database_id: str, case_id: str) -> CitedCasesResponse:
        """Cases that ``case_id`` cites. (Citator endpoint is English-only.)"""
        data = await self._get_json(f"/caseCitator/en/{database_id}/{case_id}/citedCases")
        return CitedCasesResponse.model_validate(data)

    async def get_citing_cases(self, *, database_id: str, case_id: str) -> CitingCasesResponse:
        """Cases that cite ``case_id``."""
        data = await self._get_json(f"/caseCitator/en/{database_id}/{case_id}/citingCases")
        return CitingCasesResponse.model_validate(data)

    async def get_cited_legislations(
        self, *, database_id: str, case_id: str
    ) -> CitedLegislationsResponse:
        """Legislation that ``case_id`` cites."""
        data = await self._get_json(f"/caseCitator/en/{database_id}/{case_id}/citedLegislations")
        return CitedLegislationsResponse.model_validate(data)

    # ------------------------------------------------------------------
    # Legislation
    # ------------------------------------------------------------------

    async def list_legislation_databases(
        self, *, language: Language = "en"
    ) -> LegislationDatabaseList:
        """List every legislation database (statutes / regulations / annual statutes)."""
        data = await self._get_json(f"/legislationBrowse/{language}/")
        return LegislationDatabaseList.model_validate(data)

    async def browse_legislation(
        self,
        *,
        database_id: str,
        language: Language = "en",
    ) -> LegislationList:
        """List statutes / regulations within ``database_id``."""
        data = await self._get_json(f"/legislationBrowse/{language}/{database_id}/")
        return LegislationList.model_validate(data)

    async def get_legislation(
        self,
        *,
        database_id: str,
        legislation_id: str,
        language: Language = "en",
    ) -> LegislationMetadata:
        """Fetch metadata for a single statute or regulation."""
        data = await self._get_json(
            f"/legislationBrowse/{language}/{database_id}/{legislation_id}/"
        )
        return LegislationMetadata.model_validate(data)


__all__ = ["CanLIIClient"]
