"""Async API for EPO OPS CPC utilities.

Usage
-----
Preferred: use the client as a context manager for proper resource cleanup::

    async with EpoOpsClient(api_key="...", api_secret="...") as client:
        result = await client.retrieve_cpc("H04L9/32")
        search = await client.search_cpc("machine learning")

One-shot convenience functions (create and close client automatically)::

    result = await retrieve_cpc("H04L9/32")

Legacy: passing client= parameter (deprecated, will be removed in v1.0)::

    client = get_client()
    result = await retrieve_cpc("H04L9/32", client=client)
    await client.close()  # Manual cleanup required
"""

from __future__ import annotations

import warnings

from patent_client_agents.epo_ops.client import EpoOpsClient, client_from_env
from patent_client_agents.epo_ops.models import (
    ClassificationMappingResponse,
    CpciBiblioResponse,
    CpcMediaResponse,
    CpcRetrievalResponse,
    CpcSearchResponse,
)
from patent_client_agents.epo_ops.resources import (
    CPC_PARAMETERS_GUIDE,
    CPC_PARAMETERS_RESOURCE_URI,
    CQL_GUIDE,
    CQL_GUIDE_RESOURCE_URI,
)

__all__ = [
    "EpoOpsClient",
    "CpcRetrievalResponse",
    "CpcSearchResponse",
    "ClassificationMappingResponse",
    "CpcMediaResponse",
    "CpciBiblioResponse",
    "get_client",
    "retrieve_cpc",
    "search_cpc",
    "map_classification",
    "fetch_media",
    "fetch_biblio_cpci",
    "CQL_GUIDE_RESOURCE_URI",
    "CPC_PARAMETERS_RESOURCE_URI",
    "CQL_GUIDE",
    "CPC_PARAMETERS_GUIDE",
]


def get_client(*, api_key: str | None = None, api_secret: str | None = None) -> EpoOpsClient:
    """Instantiate an EPO OPS client; defaults to env vars if credentials not provided.

    Prefer using the client as a context manager::

        async with EpoOpsClient(api_key="...", api_secret="...") as client:
            ...

    If you use get_client() directly, you are responsible for calling
    ``await client.close()`` when done.
    """
    if api_key is None and api_secret is None:
        return client_from_env()
    if api_key is None or api_secret is None:
        raise ValueError("Both api_key and api_secret are required when provided explicitly.")
    return EpoOpsClient(api_key=api_key, api_secret=api_secret)


def _warn_client_deprecated() -> None:
    warnings.warn(
        "Passing client= is deprecated and will be removed in v1.0. "
        "Use 'async with EpoOpsClient() as client:' instead.",
        DeprecationWarning,
        stacklevel=3,
    )


async def retrieve_cpc(
    symbol: str,
    depth: int | str | None = None,
    ancestors: bool = False,
    navigation: bool = False,
    *,
    client: EpoOpsClient | None = None,
) -> CpcRetrievalResponse:
    """Retrieve CPC classification details for a symbol.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.retrieve_cpc(
            symbol=symbol,
            depth=depth,
            ancestors=ancestors,
            navigation=navigation,
        )

    async with client_from_env() as cl:
        return await cl.retrieve_cpc(
            symbol=symbol,
            depth=depth,
            ancestors=ancestors,
            navigation=navigation,
        )


async def search_cpc(
    query: str,
    range_begin: int = 1,
    range_end: int = 10,
    *,
    client: EpoOpsClient | None = None,
) -> CpcSearchResponse:
    """Search CPC classifications by query.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.search_cpc(query=query, range_begin=range_begin, range_end=range_end)

    async with client_from_env() as cl:
        return await cl.search_cpc(query=query, range_begin=range_begin, range_end=range_end)


async def map_classification(
    input_schema: str,
    symbol: str,
    output_schema: str,
    additional: bool = False,
    *,
    client: EpoOpsClient | None = None,
) -> ClassificationMappingResponse:
    """Map a classification symbol between schemas.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.map_classification(
            input_schema=input_schema,
            symbol=symbol,
            output_schema=output_schema,
            additional=additional,
        )

    async with client_from_env() as cl:
        return await cl.map_classification(
            input_schema=input_schema,
            symbol=symbol,
            output_schema=output_schema,
            additional=additional,
        )


async def fetch_media(
    media_id: str,
    accept: str = "image/gif",
    *,
    client: EpoOpsClient | None = None,
) -> CpcMediaResponse:
    """Fetch CPC media (images) by ID.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.fetch_cpc_media(media_id=media_id, accept=accept)

    async with client_from_env() as cl:
        return await cl.fetch_cpc_media(media_id=media_id, accept=accept)


async def fetch_biblio_cpci(
    number: str,
    doc_type: str = "publication",
    fmt: str = "docdb",
    condensed: bool = False,
    *,
    client: EpoOpsClient | None = None,
) -> CpciBiblioResponse:
    """Fetch CPCI bibliographic data for a patent number.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.fetch_cpci_biblio(
            number=number,
            doc_type=doc_type,
            fmt=fmt,
            condensed=condensed,
        )

    async with client_from_env() as cl:
        return await cl.fetch_cpci_biblio(
            number=number,
            doc_type=doc_type,
            fmt=fmt,
            condensed=condensed,
        )
