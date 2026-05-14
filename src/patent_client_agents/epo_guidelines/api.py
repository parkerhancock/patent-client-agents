"""Async API for eGUIDELINES.

Usage
-----
Preferred: use the client as a context manager for proper resource cleanup::

    async with GuidelinesClient() as client:
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

from .client import GuidelinesClient
from .models import GuidelinesSearchResponse, GuidelinesSection, GuidelinesVersion
from .resources import USAGE_RESOURCE_URI, get_usage_resource

__all__ = [
    "GuidelinesClient",
    "GuidelinesSearchResponse",
    "GuidelinesSection",
    "GuidelinesVersion",
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
    """Input for getting an GUIDELINES section.

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


def get_client() -> GuidelinesClient:
    """Create an GuidelinesClient.

    Prefer using the client as a context manager::

        async with GuidelinesClient() as client:
            ...

    If you use get_client() directly, you are responsible for calling
    ``await client.close()`` when done.
    """
    return GuidelinesClient()


def _warn_client_deprecated() -> None:
    warnings.warn(
        "Passing client= is deprecated and will be removed in v1.0. "
        "Use 'async with GuidelinesClient() as client:' instead.",
        DeprecationWarning,
        stacklevel=3,
    )


async def search(
    params: SearchInput,
    *,
    client: GuidelinesClient | None = None,
) -> GuidelinesSearchResponse:
    """Search the GUIDELINES.

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

    async with GuidelinesClient() as cl:
        return await cl.search(**search_kwargs)


async def get_section(
    params: SectionInput | str,
    *,
    client: GuidelinesClient | None = None,
) -> GuidelinesSection:
    """Get a specific GUIDELINES section.

    Args:
        params: Either a SectionInput object or a section number/href string.
            Section numbers (e.g., "2106", "2106.04(a)") are automatically
            resolved to hrefs.
        client: Deprecated. Use GuidelinesClient as context manager instead.

    Returns:
        GuidelinesSection with content.

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

    async with GuidelinesClient() as cl:
        return await cl.get_section(
            section=params.section,
            version=params.version,
            highlight_query=params.highlight_query,
        )


async def list_versions(
    *,
    client: GuidelinesClient | None = None,
) -> list[GuidelinesVersion]:
    """List available GUIDELINES versions.

    If no client is provided, creates one internally and closes it after the request.
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.list_versions()

    async with GuidelinesClient() as cl:
        return await cl.list_versions()
