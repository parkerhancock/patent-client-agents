"""Async API for EPO OPS services.

Usage
-----
Preferred: use the client as a context manager for proper resource cleanup::

    async with EpoOpsClient(api_key="...", api_secret="...") as client:
        results = await client.search_published(query="ti=solar")
        biblio = await client.fetch_biblio(number="EP1000000A1")

One-shot convenience functions (create and close client automatically)::

    results = await search_published(query="ti=solar")

Legacy: passing client= parameter (deprecated, will be removed in v1.0)::

    client = get_client()
    results = await search_published(query="ti=solar", client=client)
    await client.close()  # Manual cleanup required
"""

from __future__ import annotations

import warnings

from .client import EpoOpsClient, client_from_env
from .models import (
    BiblioResponse,
    FamilyResponse,
    FamilySearchResponse,
    FullTextResponse,
    LegalEventsResponse,
    NumberConversionResponse,
    PdfDownloadResponse,
    SearchResponse,
)
from .resources import (
    CPC_PARAMETERS_GUIDE,
    CPC_PARAMETERS_RESOURCE_URI,
    CQL_GUIDE,
    CQL_GUIDE_RESOURCE_URI,
    OPS_SWAGGER_RESOURCE_URI,
    get_ops_swagger_spec,
)

__all__ = [
    "EpoOpsClient",
    "SearchResponse",
    "FamilySearchResponse",
    "BiblioResponse",
    "FullTextResponse",
    "FamilyResponse",
    "LegalEventsResponse",
    "PdfDownloadResponse",
    "NumberConversionResponse",
    "get_client",
    "search_published",
    "search_families",
    "fetch_biblio",
    "fetch_fulltext",
    "fetch_family",
    "fetch_family_details",
    "fetch_legal_events",
    "convert_number",
    "number_service",
    "download_pdf",
    "CQL_GUIDE_RESOURCE_URI",
    "CQL_GUIDE",
    "CPC_PARAMETERS_RESOURCE_URI",
    "CPC_PARAMETERS_GUIDE",
    "OPS_SWAGGER_RESOURCE_URI",
    "get_ops_swagger_spec",
]


def get_client(*, api_key: str | None = None, api_secret: str | None = None) -> EpoOpsClient:
    """Instantiate an EPO OPS client using env vars if not explicitly provided.

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


async def search_published(
    query: str,
    range_begin: int = 1,
    range_end: int = 25,
    *,
    client: EpoOpsClient | None = None,
) -> SearchResponse:
    """Search published patent documents.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.search_published(
            query=query, range_begin=range_begin, range_end=range_end
        )

    async with client_from_env() as cl:
        return await cl.search_published(query=query, range_begin=range_begin, range_end=range_end)


async def search_families(
    query: str,
    range_begin: int = 1,
    range_end: int = 100,
    *,
    client: EpoOpsClient | None = None,
) -> FamilySearchResponse:
    """Search patent families.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.search_families(
            query=query, range_begin=range_begin, range_end=range_end
        )

    async with client_from_env() as cl:
        return await cl.search_families(query=query, range_begin=range_begin, range_end=range_end)


async def fetch_biblio(
    number: str,
    doc_type: str = "publication",
    fmt: str = "docdb",
    *,
    client: EpoOpsClient | None = None,
) -> BiblioResponse:
    """Fetch bibliographic data for a patent document.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.fetch_biblio(number=number, doc_type=doc_type, fmt=fmt)

    async with client_from_env() as cl:
        return await cl.fetch_biblio(number=number, doc_type=doc_type, fmt=fmt)


async def fetch_fulltext(
    number: str,
    section: str = "claims",
    doc_type: str = "publication",
    fmt: str = "docdb",
    *,
    client: EpoOpsClient | None = None,
) -> FullTextResponse:
    """Fetch full text (claims or description) for a patent document.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.fetch_fulltext(
            number=number, section=section, doc_type=doc_type, fmt=fmt
        )

    async with client_from_env() as cl:
        return await cl.fetch_fulltext(number=number, section=section, doc_type=doc_type, fmt=fmt)


async def fetch_family(
    number: str,
    doc_type: str = "publication",
    fmt: str = "docdb",
    constituents: str | None = None,
    *,
    client: EpoOpsClient | None = None,
) -> FamilyResponse:
    """Fetch patent family data.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.fetch_family(
            number=number,
            doc_type=doc_type,
            fmt=fmt,
            constituents=constituents,
        )

    async with client_from_env() as cl:
        return await cl.fetch_family(
            number=number,
            doc_type=doc_type,
            fmt=fmt,
            constituents=constituents,
        )


async def fetch_family_details(
    number: str,
    doc_type: str = "publication",
    fmt: str = "docdb",
    constituents: str | None = None,
    *,
    client: EpoOpsClient | None = None,
) -> FamilyResponse:
    """Fetch patent family details (alias for fetch_family).

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.fetch_family(
            number=number,
            doc_type=doc_type,
            fmt=fmt,
            constituents=constituents,
        )

    async with client_from_env() as cl:
        return await cl.fetch_family(
            number=number,
            doc_type=doc_type,
            fmt=fmt,
            constituents=constituents,
        )


async def fetch_legal_events(
    number: str,
    doc_type: str = "publication",
    fmt: str = "docdb",
    *,
    client: EpoOpsClient | None = None,
) -> LegalEventsResponse:
    """Fetch legal events for a patent document.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.fetch_legal_events(number=number, doc_type=doc_type, fmt=fmt)

    async with client_from_env() as cl:
        return await cl.fetch_legal_events(number=number, doc_type=doc_type, fmt=fmt)


async def convert_number(
    number: str,
    doc_type: str = "publication",
    input_format: str = "original",
    output_format: str = "docdb",
    *,
    client: EpoOpsClient | None = None,
) -> NumberConversionResponse:
    """Convert a patent number between formats.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.convert_number(
            number=number,
            doc_type=doc_type,
            input_format=input_format,
            output_format=output_format,
        )

    async with client_from_env() as cl:
        return await cl.convert_number(
            number=number,
            doc_type=doc_type,
            input_format=input_format,
            output_format=output_format,
        )


async def number_service(
    number: str,
    doc_type: str = "publication",
    input_format: str = "original",
    output_format: str = "docdb",
    *,
    client: EpoOpsClient | None = None,
) -> NumberConversionResponse:
    """Number service (alias for convert_number).

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.convert_number(
            number=number,
            doc_type=doc_type,
            input_format=input_format,
            output_format=output_format,
        )

    async with client_from_env() as cl:
        return await cl.convert_number(
            number=number,
            doc_type=doc_type,
            input_format=input_format,
            output_format=output_format,
        )


async def download_pdf(
    number: str,
    doc_type: str = "publication",
    fmt: str = "docdb",
    *,
    client: EpoOpsClient | None = None,
) -> PdfDownloadResponse:
    """Download PDF for a patent document.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.download_pdf(number=number, doc_type=doc_type, fmt=fmt)

    async with client_from_env() as cl:
        return await cl.download_pdf(number=number, doc_type=doc_type, fmt=fmt)
