"""Async API for eMPEP.

Preferred: use the client as a context manager::

    async with MpepClient() as client:
        results = await client.search(query="obviousness")
        section = await client.get_section("2106")

One-shot functions open and close a client per call::

    results = await search(SearchInput(query="obviousness"))

Passing ``client=`` to them is deprecated and will be removed in v1.0.
"""

from __future__ import annotations

from patent_client_agents.shared.corpus.outline import api as outline_api

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


class SearchInput(outline_api.OutlineSearchInput):
    pass


class SectionInput(outline_api.OutlineSectionInput):
    """Input for getting an MPEP section.

    Accepts either a section number (e.g., "2106", "2106.04(a)") or an href
    (e.g., "d0e122292.html"). Section numbers are automatically resolved.
    """


def get_client() -> MpepClient:
    """Create a MpepClient. Prefer ``async with MpepClient() as client:``.

    If you use get_client() directly, you are responsible for calling
    ``await client.close()`` when done.
    """
    return MpepClient()


async def search(
    params: SearchInput,
    *,
    client: MpepClient | None = None,
) -> MpepSearchResponse:
    """Search the MPEP."""
    return await outline_api.search(MpepClient, params, client=client)


async def get_section(
    params: SectionInput | str,
    *,
    client: MpepClient | None = None,
) -> MpepSection:
    """Get one MPEP section by citation, section number, or href."""
    if isinstance(params, str):
        params = SectionInput(section=params)
    return await outline_api.get_section(MpepClient, params, client=client)


async def list_versions(
    *,
    client: MpepClient | None = None,
) -> list[MpepVersion]:
    """List the installed MPEP snapshot."""
    return await outline_api.list_versions(MpepClient, client=client)
