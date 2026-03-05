"""Base class for USPTO ODP clients with shared utilities."""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from ip_tools.core.base_client import BaseAsyncClient
from ip_tools.core.exceptions import ConfigurationError, NotFoundError

logger = logging.getLogger(__name__)

BASE_URL = "https://api.uspto.gov"


def _prune(value: Any) -> Any:
    """Remove empty values from nested dicts/lists."""
    sentinel = (None, [], {}, "")
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if item in sentinel:
                continue
            pruned = _prune(item)
            if pruned not in sentinel:
                result[str(key)] = pruned
        return result
    if isinstance(value, list):
        items: list[Any] = []
        for item in value:
            if item in sentinel:
                continue
            pruned = _prune(item)
            if pruned not in sentinel:
                items.append(pruned)
        return items
    return value


def _format_csv(value: str | Sequence[str] | None) -> str | None:
    """Format a sequence as comma-separated string."""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    parts = [str(item).strip() for item in value if str(item).strip()]
    if not parts:
        return None
    return ",".join(parts)


def _format_bool(value: bool | None) -> str | None:
    """Format boolean for query params."""
    if value is None:
        return None
    return "true" if value else "false"


def _format_date(value: date | str | None) -> str | None:
    """Format date as YYYY-MM-DD string."""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value.strftime("%Y-%m-%d")


def _serialize_model_list(items: Sequence[Any] | None) -> list[dict[str, Any]] | None:
    """Serialize a list of Pydantic models or dicts."""
    if not items:
        return None
    serialized: list[dict[str, Any]] = []
    for item in items:
        if hasattr(item, "model_dump"):
            serialized.append(_prune(item.model_dump()))
        elif isinstance(item, dict):
            serialized.append(_prune(item))
        else:
            raise TypeError(f"Unsupported item type for serialization: {type(item)!r}")
    return serialized


class PaginationModel(BaseModel):
    """Pagination parameters for ODP searches."""

    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=25, ge=1)


class SearchPayload(BaseModel):
    """Standard search payload for ODP POST endpoints."""

    q: str | None = None
    fields: list[str] | None = None
    facets: list[str] | None = None
    filters: list[str] | None = None
    rangeFilters: list[str] | None = Field(default=None, alias="range_filters")
    sort: str | None = None
    pagination: PaginationModel = Field(default_factory=PaginationModel)

    model_config = {"populate_by_name": True, "extra": "allow"}

    def model_dump_pruned(self) -> dict[str, Any]:
        """Dump model with empty values removed."""
        data = self.model_dump(by_alias=True)
        return _prune(data)


class UsptoOdpBaseClient(BaseAsyncClient):
    """Base client for USPTO Open Data Portal APIs.

    Handles API key authentication and common utilities.
    """

    DEFAULT_BASE_URL = BASE_URL
    CACHE_NAME = "uspto_odp"

    def __init__(
        self,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the client.

        Args:
            api_key: USPTO ODP API key. Falls back to USPTO_ODP_API_KEY env var.
            **kwargs: Additional arguments passed to BaseAsyncClient.

        Raises:
            ConfigurationError: If no API key is provided or found in environment.
        """
        resolved_key = api_key or os.getenv("USPTO_ODP_API_KEY")
        if not resolved_key:
            logger.error("No USPTO ODP API key provided")
            raise ConfigurationError(
                "USPTO ODP API key required. "
                "Set USPTO_ODP_API_KEY environment variable or pass api_key parameter."
            )

        headers = {
            "X-API-KEY": resolved_key,
            "Accept": "application/json",
        }
        super().__init__(headers=headers, **kwargs)
        self.api_key = resolved_key

    def _normalize_application_number(self, application_number: str) -> str:
        """Normalize application number by removing separators."""
        normalized = application_number.strip().replace("/", "").replace(",", "").replace(" ", "")
        return normalized

    async def _search_with_payload(
        self,
        endpoint: str,
        payload: dict[str, Any],
        empty_bag_key: str,
        context: str = "",
    ) -> dict[str, Any]:
        """Execute a search POST request, handling 404 as empty result."""
        logger.debug("POST %s payload=%s", endpoint, context or payload)
        try:
            result = await self._request_json("POST", endpoint, json=payload, context=context)
            logger.debug("POST %s returned count=%s", endpoint, result.get("count"))
            return result
        except NotFoundError:
            logger.debug("POST %s returned 404, returning empty result", endpoint)
            return {"count": 0, empty_bag_key: []}

    async def _get_with_404_handling(
        self,
        endpoint: str,
        empty_bag_key: str,
        context: str = "",
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a GET request, handling 404 as empty result."""
        logger.debug("GET %s context=%s", endpoint, context)
        try:
            result = await self._request_json("GET", endpoint, params=params, context=context)
            logger.debug("GET %s returned count=%s", endpoint, result.get("count"))
            return result
        except NotFoundError:
            logger.debug("GET %s returned 404, returning empty result", endpoint)
            return {"count": 0, empty_bag_key: []}


__all__ = [
    "UsptoOdpBaseClient",
    "SearchPayload",
    "PaginationModel",
    "_prune",
    "_format_csv",
    "_format_bool",
    "_format_date",
    "_serialize_model_list",
]
