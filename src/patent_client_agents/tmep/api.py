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

from patent_client_agents.shared.corpus.outline import api as outline_api

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


class SectionInput(outline_api.OutlineSectionInput):
    """Input for getting a TMEP section.

    Accepts either a section number (e.g., "1207", "1207.01(a)") or an href
    (e.g., "TMEP-1200d1e8145.html"). Section numbers are automatically resolved.
    """

    section: str = Field(
        description="Section number (e.g., '1207') or href (e.g., 'TMEP-1200d1e8145.html')"
    )


async def search(params: SearchInput) -> TmepSearchResponse:
    """Search the TMEP. Creates a client internally and closes it after the request."""
    return await outline_api.search(TmepClient, params)


async def get_section(params: SectionInput | str) -> TmepSection:
    """Get one TMEP section by section number (``"1207.01"``) or href.

    Creates a client internally and closes it after the request.
    """
    if isinstance(params, str):
        params = SectionInput(section=params)
    return await outline_api.get_section(TmepClient, params)


async def list_versions() -> list[TmepVersion]:
    """List the installed TMEP snapshot."""
    return await outline_api.list_versions(TmepClient)
