"""Async API for TMEP (Trademark Manual of Examining Procedure).

Usage
-----
Preferred: use the client as a context manager for proper resource cleanup::

    async with TmepClient() as client:
        results = await client.search(query="likelihood of confusion")
        section = await client.get_section(href="TMEP-1200d1e8145.html")

One-shot convenience functions (create and close client automatically)::

    results = await search(SearchInput(query="likelihood of confusion"))
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .client import TmepClient
from .models import TmepSearchResponse, TmepSection, TmepVersion
from .resources import USAGE_RESOURCE_URI, get_usage_resource

__all__ = [
    "TmepClient",
    "TmepSearchResponse",
    "TmepSection",
    "TmepVersion",
    "SearchInput",
    "SectionInput",
    "search",
    "get_section",
    "list_versions",
    "USAGE_RESOURCE_URI",
    "get_usage_resource",
]


class SearchInput(BaseModel):
    """Input parameters for TMEP search."""

    query: str
    version: str = "current"
    include_index: bool = False
    include_notes: bool = False
    syntax: str = Field(default="adj", description="adj, and, or, exact")
    snippet: str = Field(default="compact", description="compact or full")
    sort: str = Field(default="relevance", description="relevance or outline")
    per_page: int = Field(default=10, ge=1, le=100)
    page: int = Field(default=1, ge=1)


class SectionInput(BaseModel):
    """Input for getting a TMEP section.

    Accepts either a section number (e.g., "1207", "1207.01(a)") or an href
    (e.g., "TMEP-1200d1e8145.html"). Section numbers are automatically resolved.
    """

    section: str = Field(
        description="Section number (e.g., '1207') or href (e.g., 'TMEP-1200d1e8145.html')"
    )
    version: str = "current"
    highlight_query: str | None = Field(
        default=None,
        description="Optional query for highlighted view",
    )

    # Backwards compatibility: allow 'href' as an alias for 'section'
    def __init__(self, **data):
        if "href" in data and "section" not in data:
            data["section"] = data.pop("href")
        super().__init__(**data)


async def search(params: SearchInput) -> TmepSearchResponse:
    """Search the TMEP.

    Creates a client internally and closes it after the request.

    Args:
        params: Search parameters.

    Returns:
        TmepSearchResponse with search hits.
    """
    async with TmepClient() as client:
        return await client.search(
            query=params.query,
            version=params.version,
            include_content=True,
            include_index=params.include_index,
            include_notes=params.include_notes,
            syntax=params.syntax,
            snippet=params.snippet,
            sort=params.sort,
            per_page=params.per_page,
            page=params.page,
        )


async def get_section(params: SectionInput | str) -> TmepSection:
    """Get a specific TMEP section.

    Creates a client internally and closes it after the request.

    Args:
        params: Either a SectionInput object or a section number/href string.
            Section numbers (e.g., "1207", "1207.01(a)") are automatically
            resolved to hrefs.

    Returns:
        TmepSection with content.

    Examples:
        # Using section number directly
        section = await get_section("1207")

        # Using SectionInput
        section = await get_section(SectionInput(section="1207.01"))

        # Using href (backwards compatible)
        section = await get_section(SectionInput(href="TMEP-1200d1e8145.html"))
    """
    # Handle string input for convenience
    if isinstance(params, str):
        params = SectionInput(section=params)

    async with TmepClient() as client:
        return await client.get_section(
            section=params.section,
            version=params.version,
            highlight_query=params.highlight_query,
        )


async def list_versions() -> list[TmepVersion]:
    """List available TMEP versions.

    Creates a client internally and closes it after the request.

    Returns:
        List of TmepVersion objects.
    """
    async with TmepClient() as client:
        return await client.list_versions()
