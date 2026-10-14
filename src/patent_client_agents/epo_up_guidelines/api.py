"""Async API for the EPO Unitary Patent Guidelines.

Preferred: use the client as a context manager::

    async with UpGuidelinesClient() as client:
        results = await client.search(query="request for unitary effect")
        section = await client.get_section("1.2.1")

One-shot functions open and close a client per call::

    results = await search(SearchInput(query="request for unitary effect"))

Passing ``client=`` to them is deprecated and will be removed in v1.0.
"""

from __future__ import annotations

from patent_client_agents.shared.corpus.outline import api as outline_api

from .client import UpGuidelinesClient
from .models import UpGuidelinesSearchResponse, UpGuidelinesSection, UpGuidelinesVersion
from .resources import USAGE_RESOURCE_URI, get_usage_resource

__all__ = [
    "UpGuidelinesClient",
    "UpGuidelinesSearchResponse",
    "UpGuidelinesSection",
    "UpGuidelinesVersion",
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
    """Input for getting an GUIDELINES section.

    Accepts either a section number (e.g., "2106", "2106.04(a)") or an href
    (e.g., "d0e122292.html"). Section numbers are automatically resolved.
    """


def get_client() -> UpGuidelinesClient:
    """Create a UpGuidelinesClient. Prefer ``async with UpGuidelinesClient() as client:``.

    If you use get_client() directly, you are responsible for calling
    ``await client.close()`` when done.
    """
    return UpGuidelinesClient()


async def search(
    params: SearchInput,
    *,
    client: UpGuidelinesClient | None = None,
) -> UpGuidelinesSearchResponse:
    """Search the UP Guidelines."""
    return await outline_api.search(UpGuidelinesClient, params, client=client)


async def get_section(
    params: SectionInput | str,
    *,
    client: UpGuidelinesClient | None = None,
) -> UpGuidelinesSection:
    """Get one UP Guidelines section by citation, section number, or href."""
    if isinstance(params, str):
        params = SectionInput(section=params)
    return await outline_api.get_section(UpGuidelinesClient, params, client=client)


async def list_versions(
    *,
    client: UpGuidelinesClient | None = None,
) -> list[UpGuidelinesVersion]:
    """List the installed UP Guidelines snapshot."""
    return await outline_api.list_versions(UpGuidelinesClient, client=client)
