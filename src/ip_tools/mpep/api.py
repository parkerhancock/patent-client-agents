"""Async API for eMPEP.

Usage
-----
Preferred: use the client as a context manager for proper resource cleanup::

    async with MpepClient() as client:
        results = await client.search(query="obviousness")
        section = await client.get_section(href="d0e122292.html")

One-shot convenience functions (create and close client automatically)::

    results = await search(SearchInput(query="obviousness"))

Legacy: passing client= parameter (deprecated, will be removed in v1.0)::

    client = get_client()
    results = await search(params, client=client)
    await client.close()  # Manual cleanup required
"""

from __future__ import annotations

import warnings

from pydantic import BaseModel, Field

from .client import MpepClient
from .models import MpepSearchResponse, MpepSection, MpepVersion
from .resources import USAGE_RESOURCE_URI, get_usage_resource

__all__ = [
    "MpepClient",
    "MpepSearchResponse",
    "MpepSection",
    "MpepVersion",
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
    include_index: bool = False
    include_notes: bool = False
    include_form_paragraphs: bool = False
    syntax: str = Field(default="adj", description="adj, and, or, exact")
    snippet: str = Field(default="compact", description="compact or full")
    sort: str = Field(default="relevance", description="relevance or outline")
    per_page: int = Field(default=10, ge=1, le=100)
    page: int = Field(default=1, ge=1)


class SectionInput(BaseModel):
    """Input for getting an MPEP section.

    Accepts either a section number (e.g., "2106", "2106.04(a)") or an href
    (e.g., "d0e122292.html"). Section numbers are automatically resolved.
    """

    section: str = Field(
        description="Section number (e.g., '2106') or href (e.g., 'd0e122292.html')"
    )
    version: str = "current"
    highlight_query: str | None = Field(
        default=None,
        description="Optional query for highlighted view",
    )

    # Backwards compatibility: allow 'href' as an alias for 'section'
    def __init__(self, **data):
        # If 'href' is provided but not 'section', use href as section
        if "href" in data and "section" not in data:
            data["section"] = data.pop("href")
        super().__init__(**data)


def get_client() -> MpepClient:
    """Create an MpepClient.

    Prefer using the client as a context manager::

        async with MpepClient() as client:
            ...

    If you use get_client() directly, you are responsible for calling
    ``await client.close()`` when done.
    """
    return MpepClient()


def _warn_client_deprecated() -> None:
    warnings.warn(
        "Passing client= is deprecated and will be removed in v1.0. "
        "Use 'async with MpepClient() as client:' instead.",
        DeprecationWarning,
        stacklevel=3,
    )


async def search(
    params: SearchInput,
    *,
    client: MpepClient | None = None,
) -> MpepSearchResponse:
    """Search the MPEP.

    If no client is provided, creates one internally and closes it after the request.
    """
    search_kwargs = {
        "query": params.query,
        "version": params.version,
        "include_content": True,
        "include_index": params.include_index,
        "include_notes": params.include_notes,
        "include_form_paragraphs": params.include_form_paragraphs,
        "syntax": params.syntax,
        "snippet": params.snippet,
        "sort": params.sort,
        "per_page": params.per_page,
        "page": params.page,
    }

    if client is not None:
        _warn_client_deprecated()
        return await client.search(**search_kwargs)

    async with MpepClient() as cl:
        return await cl.search(**search_kwargs)


async def get_section(
    params: SectionInput | str,
    *,
    client: MpepClient | None = None,
) -> MpepSection:
    """Get a specific MPEP section.

    Args:
        params: Either a SectionInput object or a section number/href string.
            Section numbers (e.g., "2106", "2106.04(a)") are automatically
            resolved to hrefs.
        client: Deprecated. Use MpepClient as context manager instead.

    Returns:
        MpepSection with content.

    Examples:
        # Using section number directly
        section = await get_section("2106")

        # Using SectionInput
        section = await get_section(SectionInput(section="2106.04(a)"))

        # Using href (backwards compatible)
        section = await get_section(SectionInput(href="d0e197244.html"))
    """
    # Handle string input for convenience
    if isinstance(params, str):
        params = SectionInput(section=params)

    if client is not None:
        _warn_client_deprecated()
        return await client.get_section(
            section=params.section,
            version=params.version,
            highlight_query=params.highlight_query,
        )

    async with MpepClient() as cl:
        return await cl.get_section(
            section=params.section,
            version=params.version,
            highlight_query=params.highlight_query,
        )


async def list_versions(
    *,
    client: MpepClient | None = None,
) -> list[MpepVersion]:
    """List available MPEP versions.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.list_versions()

    async with MpepClient() as cl:
        return await cl.list_versions()
