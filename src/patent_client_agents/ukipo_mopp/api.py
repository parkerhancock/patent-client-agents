"""Async API for the UKIPO Manual of Patent Practice.

Preferred: use the client as a context manager::

    async with MoppClient() as client:
        results = await client.search(query="sufficiency")
        section = await client.get_section("14")

One-shot functions open and close a client per call::

    results = await search(SearchInput(query="sufficiency"))

Passing ``client=`` to them is deprecated and will be removed in v1.0.
"""

from __future__ import annotations

from patent_client_agents.shared.corpus.outline import api as outline_api

from .client import MoppClient
from .models import MoppSearchResponse, MoppSection, MoppVersion
from .resources import USAGE_RESOURCE_URI, get_usage_resource

__all__ = [
    "MoppClient",
    "MoppSearchResponse",
    "MoppSection",
    "MoppVersion",
    "SearchInput",
    "SectionInput",
    "get_client",
    "search",
    "get_section",
    "list_versions",
    "USAGE_RESOURCE_URI",
    "get_usage_resource",
]


class SearchInput(outline_api.OutlineSearchInput):
    pass


class SectionInput(outline_api.OutlineSectionInput):
    """Input for getting an MOPP section.

    Accepts either a section number (e.g., "2106", "2106.04(a)") or an href
    (e.g., "d0e122292.html"). Section numbers are automatically resolved.
    """


def get_client() -> MoppClient:
    """Create a MoppClient. Prefer ``async with MoppClient() as client:``.

    If you use get_client() directly, you are responsible for calling
    ``await client.close()`` when done.
    """
    return MoppClient()


async def search(
    params: SearchInput,
    *,
    client: MoppClient | None = None,
) -> MoppSearchResponse:
    """Search the MoPP."""
    return await outline_api.search(MoppClient, params, client=client)


async def get_section(
    params: SectionInput | str,
    *,
    client: MoppClient | None = None,
) -> MoppSection:
    """Get one MoPP section by citation, section number, or href."""
    if isinstance(params, str):
        params = SectionInput(section=params)
    return await outline_api.get_section(MoppClient, params, client=client)


async def list_versions(
    *,
    client: MoppClient | None = None,
) -> list[MoppVersion]:
    """List the installed MoPP snapshot."""
    return await outline_api.list_versions(MoppClient, client=client)
