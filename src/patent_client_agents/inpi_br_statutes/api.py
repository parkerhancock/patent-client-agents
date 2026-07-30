"""Async API for the INPI Brazil LPI (Lei 9.279/1996) corpus.

Usage
-----
Preferred: use the client as a context manager for proper resource cleanup::

    async with InpiBrStatutesClient() as client:
        results = await client.search(query="segredo industrial")
        section = await client.get_section("Art. 195")

One-shot convenience functions (create and close client automatically)::

    results = await search(SearchInput(query="segredo industrial"))
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .client import InpiBrStatutesClient
from .models import InpiBrSearchResponse, InpiBrSection, InpiBrVersion
from .resources import USAGE_RESOURCE_URI, get_usage_resource

__all__ = [
    "InpiBrStatutesClient",
    "InpiBrSearchResponse",
    "InpiBrSection",
    "InpiBrVersion",
    "SearchInput",
    "SectionInput",
    "get_client",
    "search",
    "get_section",
    "list_versions",
    "USAGE_RESOURCE_URI",
    "get_usage_resource",
]


class SearchInput(BaseModel):
    query: str
    version: str = "current"
    syntax: str = Field(default="adj", description="adj, and, or, exact")
    sort: str = Field(default="relevance", description="relevance or outline")
    per_page: int = Field(default=10, ge=1, le=100)
    page: int = Field(default=1, ge=1)


class SectionInput(BaseModel):
    """Input for getting an LPI Article.

    Accepts citation forms (``Art. 6``, ``Article 6``, ``Artigo 6``,
    optionally with ``LPI`` suffix) or URL slugs (``art6``).
    """

    section: str = Field(
        description="Citation (e.g. 'Art. 6', 'Article 195') or slug (e.g. 'art195')"
    )
    version: str = "current"


def get_client() -> InpiBrStatutesClient:
    """Create an InpiBrStatutesClient.

    Prefer using the client as a context manager::

        async with InpiBrStatutesClient() as client:
            ...
    """
    return InpiBrStatutesClient()


async def search(params: SearchInput) -> InpiBrSearchResponse:
    """Search the LPI corpus. Opens and closes a client internally."""
    async with InpiBrStatutesClient() as cl:
        return await cl.search(
            query=params.query,
            version=params.version,
            syntax=params.syntax,
            sort=params.sort,
            per_page=params.per_page,
            page=params.page,
        )


async def get_section(params: SectionInput | str) -> InpiBrSection:
    """Get a specific LPI Article by citation or slug."""
    if isinstance(params, str):
        params = SectionInput(section=params)

    async with InpiBrStatutesClient() as cl:
        return await cl.get_section(params.section, version=params.version)


async def list_versions() -> list[InpiBrVersion]:
    """List available LPI corpus versions."""
    async with InpiBrStatutesClient() as cl:
        return await cl.list_versions()
