"""Base class for USPTO ODP clients with shared utilities."""

from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from mcp_data_core.base_client import BaseAsyncClient
from mcp_data_core.exceptions import ConfigurationError, NotFoundError

BASE_URL = "https://api.uspto.gov"

# ODP release this client is verified against. Bump when re-reviewing
# https://data.uspto.gov/support/release and confirming no regressions.
# Checking tip: compare to the current release number on that page; every
# minor bump has typically been additive, but 3.6 (2026-04-10) removed
# `countryOrStateCode` from the Assignment API and standardized PCT
# numbers — so review each bump before advancing this constant.
ODP_TRACKED_RELEASE = "3.6"
ODP_LAST_REVIEWED = "2026-04-14"


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


def _normalize_download_bag(
    data: dict[str, Any], bag_key: str, records_key: str = "patentTrialData"
) -> dict[str, Any]:
    """Normalize a PTAB ``/search/download`` response to the search shape.

    The download endpoints return records under a flat key and omit ``count``
    (confirmed live 2026-07-20: trials and appeals use ``patentTrialData``,
    interferences uses ``interferenceData``), unlike the search endpoints'
    per-API ``*DataBag`` envelopes the response models expect.
    """
    records = data.pop(records_key, None)
    if records is not None and bag_key not in data:
        data[bag_key] = records
    data.setdefault(bag_key, [])
    data.setdefault("count", len(data[bag_key]))
    return data


# Sentinel lower bound for a range filter that only specifies valueTo — well
# before any USPTO filing date.
_RANGE_FILTER_EPOCH = "1776-01-01"


def _serialize_range_filters(items: Sequence[Any] | None) -> list[dict[str, Any]] | None:
    """Serialize rangeFilters, filling in an omitted bound.

    ODP's applications-search endpoint rejects a rangeFilters entry missing
    either bound with a bare HTTP 400 (confirmed live against
    /api/v1/patent/applications/search: valueFrom alone -> 400, valueFrom +
    valueTo -> 200) -- a one-sided "since X" filter needs an explicit
    open-ended valueTo, not an omitted key. `_serialize_model_list` (used
    for `filters`/`sort` too, where omitting a key is fine) would otherwise
    prune a caller-omitted valueTo/valueFrom away entirely via `_prune`.
    """
    serialized = _serialize_model_list(items)
    if serialized is None:
        return None
    today = date.today().isoformat()
    for rf in serialized:
        if "valueFrom" in rf and "valueTo" not in rf:
            rf["valueTo"] = today
        elif "valueTo" in rf and "valueFrom" not in rf:
            rf["valueFrom"] = _RANGE_FILTER_EPOCH
    return serialized


class PaginationModel(BaseModel):
    """Pagination parameters for ODP searches."""

    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=25, ge=1)


class SearchPayload(BaseModel):
    """Standard search payload for ODP POST endpoints.

    Filters, rangeFilters, and sort accept JSON-object lists (OdpFilter, OdpRangeFilter,
    OdpSort models or plain dicts). These are serialized via _serialize_model_list.
    """

    q: str | None = None
    fields: list[str] | None = None
    facets: list[str] | None = None
    filters: list[Any] | None = None
    range_filters: list[Any] | None = Field(default=None, alias="rangeFilters")
    sort: list[Any] | None = None
    pagination: PaginationModel = Field(default_factory=PaginationModel)

    model_config = {"populate_by_name": True, "extra": "allow"}

    def model_dump_pruned(self) -> dict[str, Any]:
        """Dump model with empty values removed, serializing nested models."""
        data: dict[str, Any] = {}
        if self.q is not None:
            data["q"] = self.q
        if self.fields is not None:
            data["fields"] = self.fields
        if self.facets is not None:
            data["facets"] = self.facets
        if (filters := _serialize_model_list(self.filters)) is not None:
            data["filters"] = filters
        if (range_filters := _serialize_model_list(self.range_filters)) is not None:
            data["rangeFilters"] = range_filters
        if (sort := _serialize_model_list(self.sort)) is not None:
            data["sort"] = sort
        data["pagination"] = _prune(self.pagination.model_dump())
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

    def _build_url(self, path: str) -> str:
        """Pass absolute URLs through unchanged (e.g. grant XML fileLocationURI)."""
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return super()._build_url(path)

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
        try:
            return await self._request_json("POST", endpoint, json=payload, context=context)
        except NotFoundError:
            return {"count": 0, empty_bag_key: []}

    async def _get_with_404_handling(
        self,
        endpoint: str,
        empty_bag_key: str,
        context: str = "",
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a GET request, handling 404 as empty result."""
        try:
            return await self._request_json("GET", endpoint, params=params, context=context)
        except NotFoundError:
            return {"count": 0, empty_bag_key: []}


__all__ = [
    "UsptoOdpBaseClient",
    "SearchPayload",
    "PaginationModel",
    "_prune",
    "_format_csv",
    "_format_bool",
    "_format_date",
    "_normalize_download_bag",
    "_serialize_model_list",
    "_serialize_range_filters",
]
