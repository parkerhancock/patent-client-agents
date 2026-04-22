"""Async API for USPTO BDSS/ODP bulk data.

Usage
-----
Preferred: use the client as a context manager for proper resource cleanup::

    async with UsptoOdpClient() as client:
        results = await client.search_bulk_datasets(query="grant")
        product = await client.get_bulk_dataset_product("grantTar")

One-shot convenience functions (create and close client automatically)::

    results = await search_products(q="grant")

Legacy: passing client= parameter (deprecated, will be removed in v1.0)::

    client = get_client()
    results = await search_products(q="grant", client=client)
    await client.close()  # Manual cleanup required
"""

from __future__ import annotations

import warnings
from datetime import date
from typing import Any

from ip_tools.uspto_odp import UsptoOdpClient
from ip_tools.uspto_odp.models import BulkDataProductResponse, BulkDataSearchResponse

__all__ = [
    "UsptoOdpClient",
    "BulkDataSearchResponse",
    "BulkDataProductResponse",
    "get_client",
    "search_products",
    "get_product",
]


def get_client(api_key: str | None = None) -> UsptoOdpClient:
    """Instantiate a USPTO ODP client, defaulting to env var `USPTO_ODP_API_KEY`.

    Prefer using the client as a context manager::

        async with UsptoOdpClient() as client:
            ...

    If you use get_client() directly, you are responsible for calling
    ``await client.close()`` when done.
    """
    return UsptoOdpClient(api_key=api_key)


def _warn_client_deprecated() -> None:
    warnings.warn(
        "Passing client= is deprecated and will be removed in v1.0. "
        "Use 'async with UsptoOdpClient() as client:' instead.",
        DeprecationWarning,
        stacklevel=3,
    )


async def search_products(
    *,
    q: str | None = None,
    sort: str | None = None,
    offset: int = 0,
    limit: int = 25,
    facets: list[str] | None = None,
    fields: list[str] | None = None,
    filters: list[str] | None = None,
    range_filters: list[str] | None = None,
    client: UsptoOdpClient | None = None,
) -> BulkDataSearchResponse:
    """Search USPTO bulk data products.

    If no client is provided, creates one internally and closes it after the request.
    """
    kwargs = {
        "query": q,
        "sort": sort,
        "offset": offset,
        "limit": limit,
        "facets": facets,
        "fields": fields,
        "filters": filters,
        "range_filters": range_filters,
    }

    if client is not None:
        _warn_client_deprecated()
        return await client.search_bulk_datasets(**kwargs)

    async with UsptoOdpClient() as cl:
        return await cl.search_bulk_datasets(**kwargs)


async def get_product(
    product_identifier: str,
    *,
    file_data_from_date: date | str | None = None,
    file_data_to_date: date | str | None = None,
    offset: int | None = None,
    limit: int | None = None,
    include_files: bool | None = None,
    latest_only: bool | None = None,
    client: UsptoOdpClient | None = None,
    **kwargs: Any,
) -> BulkDataProductResponse:
    """Get a specific USPTO bulk data product.

    If no client is provided, creates one internally and closes it after the request.
    """
    product_kwargs = {
        "file_from_date": file_data_from_date,
        "file_to_date": file_data_to_date,
        "offset": offset,
        "limit": limit,
        "include_files": include_files,
        "latest_only": latest_only,
        **kwargs,
    }

    if client is not None:
        _warn_client_deprecated()
        return await client.get_bulk_dataset_product(product_identifier, **product_kwargs)

    async with UsptoOdpClient() as cl:
        return await cl.get_bulk_dataset_product(product_identifier, **product_kwargs)
