"""Async API for the EPO Guidelines for Examination.

Preferred: use the client as a context manager::

    async with GuidelinesClient() as client:
        results = await client.search(query="novelty")
        section = await client.get_section("G-II, 3.1")

One-shot functions open and close a client per call::

    results = await search(SearchInput(query="novelty"))

Passing ``client=`` to them is deprecated and will be removed in v1.0.
"""

from __future__ import annotations

from patent_client_agents.shared.corpus.outline import api as outline_api

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


class SearchInput(outline_api.OutlineSearchInput):
    pass


class SectionInput(outline_api.OutlineSectionInput):
    """Input for getting an GUIDELINES section.

    Accepts either a section number (e.g., "2106", "2106.04(a)") or an href
    (e.g., "d0e122292.html"). Section numbers are automatically resolved.
    """


def get_client() -> GuidelinesClient:
    """Create a GuidelinesClient. Prefer ``async with GuidelinesClient() as client:``.

    If you use get_client() directly, you are responsible for calling
    ``await client.close()`` when done.
    """
    return GuidelinesClient()


async def search(
    params: SearchInput,
    *,
    client: GuidelinesClient | None = None,
) -> GuidelinesSearchResponse:
    """Search the EPO Guidelines."""
    return await outline_api.search(GuidelinesClient, params, client=client)


async def get_section(
    params: SectionInput | str,
    *,
    client: GuidelinesClient | None = None,
) -> GuidelinesSection:
    """Get one EPO Guidelines section by citation, section number, or href."""
    if isinstance(params, str):
        params = SectionInput(section=params)
    return await outline_api.get_section(GuidelinesClient, params, client=client)


async def list_versions(
    *,
    client: GuidelinesClient | None = None,
) -> list[GuidelinesVersion]:
    """List the installed EPO Guidelines snapshot."""
    return await outline_api.list_versions(GuidelinesClient, client=client)
