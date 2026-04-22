"""Async API for USPTO petitions (ODP).

Usage
-----
Preferred: use the client as a context manager for proper resource cleanup::

    async with UsptoOdpClient() as client:
        results = await client.search_petitions(q="continuation")
        petition = await client.get_petition("12345")

One-shot convenience functions (create and close client automatically)::

    results = await search_petitions(q="continuation")

Legacy: passing client= parameter (deprecated, will be removed in v1.0)::

    client = get_client()
    results = await search_petitions(q="continuation", client=client)
    await client.close()  # Manual cleanup required
"""

from __future__ import annotations

import warnings

from ip_tools.uspto_odp import UsptoOdpClient
from ip_tools.uspto_odp.models import PetitionDecisionIdentifierResponse, PetitionDecisionResponse

__all__ = [
    "UsptoOdpClient",
    "PetitionDecisionResponse",
    "PetitionDecisionIdentifierResponse",
    "get_client",
    "search_petitions",
    "get_petition",
    "download_petitions",
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


async def search_petitions(
    *,
    q: str | None = None,
    filters: list[dict[str, object]] | None = None,
    range_filters: list[dict[str, object]] | None = None,
    sort: list[dict[str, object]] | None = None,
    fields: list[str] | None = None,
    facets: list[str] | None = None,
    limit: int | None = 25,
    offset: int | None = 0,
    client: UsptoOdpClient | None = None,
) -> PetitionDecisionResponse:
    """Search USPTO petition decisions.

    If no client is provided, creates one internally and closes it after the request.
    """
    kwargs = {
        "q": q,
        "filters": filters,
        "range_filters": range_filters,
        "sort": sort,
        "fields": fields,
        "facets": facets,
        "limit": limit,
        "offset": offset,
    }

    if client is not None:
        _warn_client_deprecated()
        return await client.search_petitions(**kwargs)

    async with UsptoOdpClient() as cl:
        return await cl.search_petitions(**kwargs)


async def get_petition(
    petition_decision_record_identifier: str,
    *,
    include_documents: bool = False,
    client: UsptoOdpClient | None = None,
) -> PetitionDecisionIdentifierResponse:
    """Get a specific petition decision by identifier.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.get_petition(
            petition_decision_record_identifier,
            include_documents=include_documents,
        )

    async with UsptoOdpClient() as cl:
        return await cl.get_petition(
            petition_decision_record_identifier,
            include_documents=include_documents,
        )


async def download_petitions(
    *,
    q: str | None = None,
    filters: list[dict[str, object]] | None = None,
    range_filters: list[dict[str, object]] | None = None,
    sort: list[dict[str, object]] | None = None,
    fields: list[str] | None = None,
    limit: int | None = None,
    offset: int | None = None,
    file_format: str | None = None,
    client: UsptoOdpClient | None = None,
) -> PetitionDecisionResponse:
    """Download petition decisions.

    If no client is provided, creates one internally and closes it after the request.
    """
    kwargs = {
        "q": q,
        "filters": filters,
        "range_filters": range_filters,
        "sort": sort,
        "fields": fields,
        "limit": limit,
        "offset": offset,
        "file_format": file_format,
    }

    if client is not None:
        _warn_client_deprecated()
        return await client.download_petitions(**kwargs)

    async with UsptoOdpClient() as cl:
        return await cl.download_petitions(**kwargs)
