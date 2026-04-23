"""Async API for USPTO Patent Public Search (PPUBS).

Usage
-----
Preferred: use the client as a context manager for proper resource cleanup::

    async with PublicSearchClient() as client:
        results = await client.search_biblio(query="machine learning")
        doc = await client.get_document(guid, source="US-PGPUB")

One-shot convenience functions (create and close client automatically)::

    results = await search(query="machine learning")

Legacy: passing client= parameter (deprecated, will be removed in v1.0)::

    client = get_client()
    results = await search(query="machine learning", client=client)
    await client.close()  # Manual cleanup required
"""

from __future__ import annotations

import warnings

from pydantic import BaseModel, Field

from .client import PublicSearchClient
from .models import PublicSearchBiblioPage, PublicSearchDocument
from .resources import (
    SEARCH_GUIDE_RESOURCE_URI,
    SEARCHABLE_INDEX_RESOURCE_URI,
    get_search_guide,
    get_searchable_indexes_resource,
)

__all__ = [
    "PublicSearchClient",
    "PublicSearchBiblioPage",
    "PublicSearchDocument",
    "PdfResponse",
    "get_client",
    "search",
    "get_document",
    "download_pdf",
    "resolve_publication",
    "resolve_and_download_pdf",
    "SEARCH_GUIDE_RESOURCE_URI",
    "SEARCHABLE_INDEX_RESOURCE_URI",
    "get_search_guide",
    "get_searchable_indexes_resource",
]


class PdfResponse(BaseModel):
    guid: str
    publication_number: str | None = None
    patent_title: str | None = None
    pdf_base64: str = Field(description="Base64-encoded PDF bytes")


def get_client() -> PublicSearchClient:
    """Create a PublicSearchClient.

    Prefer using the client as a context manager::

        async with PublicSearchClient() as client:
            ...

    If you use get_client() directly, you are responsible for calling
    ``await client.close()`` when done.
    """
    return PublicSearchClient()


def _warn_client_deprecated() -> None:
    warnings.warn(
        "Passing client= is deprecated and will be removed in v1.0. "
        "Use 'async with PublicSearchClient() as client:' instead.",
        DeprecationWarning,
        stacklevel=3,
    )


async def search(
    query: str,
    start: int = 0,
    limit: int = 100,
    sort: str = "date_publ desc",
    default_operator: str = "OR",
    sources: list[str] | None = None,
    expand_plurals: bool = True,
    british_equivalents: bool = True,
    *,
    client: PublicSearchClient | None = None,
) -> PublicSearchBiblioPage:
    """Search USPTO Patent Public Search.

    If no client is provided, creates one internally and closes it after the request.
    """
    kwargs = {
        "query": query,
        "start": start,
        "limit": limit,
        "sort": sort,
        "default_operator": default_operator,
        "sources": sources,
        "expand_plurals": expand_plurals,
        "british_equivalents": british_equivalents,
    }

    if client is not None:
        _warn_client_deprecated()
        return await client.search_biblio(**kwargs)

    async with PublicSearchClient() as cl:
        return await cl.search_biblio(**kwargs)


async def get_document(
    guid: str,
    source: str,
    *,
    client: PublicSearchClient | None = None,
) -> PublicSearchDocument:
    """Get a document by GUID and source.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.get_document(guid, source=source)

    async with PublicSearchClient() as cl:
        return await cl.get_document(guid, source=source)


async def download_pdf(
    *,
    guid: str | None = None,
    source: str | None = None,
    publication_number: str | None = None,
    client: PublicSearchClient | None = None,
) -> PdfResponse:
    """Download a patent document as PDF.

    Provide either publication_number or both guid and source.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        if publication_number:
            document = await client.resolve_document_by_publication_number(publication_number)
        else:
            if not guid or not source:
                raise ValueError("Provide either publication_number or both guid and source.")
            document = await client.get_document(guid, source=source)
        pdf_b64 = await client.download_pdf_base64(document)
        return PdfResponse(
            guid=document.guid or "",
            publication_number=document.publication_number,
            patent_title=document.patent_title,
            pdf_base64=pdf_b64,
        )

    async with PublicSearchClient() as cl:
        if publication_number:
            document = await cl.resolve_document_by_publication_number(publication_number)
        else:
            if not guid or not source:
                raise ValueError("Provide either publication_number or both guid and source.")
            document = await cl.get_document(guid, source=source)
        pdf_b64 = await cl.download_pdf_base64(document)
        return PdfResponse(
            guid=document.guid or "",
            publication_number=document.publication_number,
            patent_title=document.patent_title,
            pdf_base64=pdf_b64,
        )


async def resolve_publication(
    publication_number: str,
    *,
    client: PublicSearchClient | None = None,
) -> PublicSearchDocument:
    """Resolve a publication number to a document.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.resolve_document_by_publication_number(publication_number)

    async with PublicSearchClient() as cl:
        return await cl.resolve_document_by_publication_number(publication_number)


async def resolve_and_download_pdf(
    publication_number: str,
    *,
    client: PublicSearchClient | None = None,
) -> PdfResponse:
    """Resolve a publication number and download the PDF.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        document = await client.resolve_document_by_publication_number(publication_number)
        pdf_b64 = await client.download_pdf_base64(document)
        return PdfResponse(
            guid=document.guid or "",
            publication_number=document.publication_number,
            patent_title=document.patent_title,
            pdf_base64=pdf_b64,
        )

    async with PublicSearchClient() as cl:
        document = await cl.resolve_document_by_publication_number(publication_number)
        pdf_b64 = await cl.download_pdf_base64(document)
        return PdfResponse(
            guid=document.guid or "",
            publication_number=document.publication_number,
            patent_title=document.patent_title,
            pdf_base64=pdf_b64,
        )
