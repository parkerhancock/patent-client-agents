"""Async API for the PCT-EPO Guidelines.

Preferred: use the client as a context manager::

    async with PctGuidelinesClient() as client:
        results = await client.search(query="unity of invention")
        section = await client.get_section("B-IV, 1")

One-shot functions open and close a client per call::

    results = await search(SearchInput(query="unity of invention"))

Passing ``client=`` to them is deprecated and will be removed in v1.0.
"""

from __future__ import annotations

from patent_client_agents.shared.corpus.outline import api as outline_api

from .client import PctGuidelinesClient
from .models import PctGuidelinesSearchResponse, PctGuidelinesSection, PctGuidelinesVersion
from .resources import USAGE_RESOURCE_URI, get_usage_resource

__all__ = [
    "PctGuidelinesClient",
    "PctGuidelinesSearchResponse",
    "PctGuidelinesSection",
    "PctGuidelinesVersion",
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


def get_client() -> PctGuidelinesClient:
    """Create a PctGuidelinesClient. Prefer ``async with PctGuidelinesClient() as client:``.

    If you use get_client() directly, you are responsible for calling
    ``await client.close()`` when done.
    """
    return PctGuidelinesClient()


async def search(
    params: SearchInput,
    *,
    client: PctGuidelinesClient | None = None,
) -> PctGuidelinesSearchResponse:
    """Search the PCT-EPO Guidelines."""
    return await outline_api.search(PctGuidelinesClient, params, client=client)


async def get_section(
    params: SectionInput | str,
    *,
    client: PctGuidelinesClient | None = None,
) -> PctGuidelinesSection:
    """Get one PCT-EPO Guidelines section by citation, section number, or href."""
    if isinstance(params, str):
        params = SectionInput(section=params)
    return await outline_api.get_section(PctGuidelinesClient, params, client=client)


async def list_versions(
    *,
    client: PctGuidelinesClient | None = None,
) -> list[PctGuidelinesVersion]:
    """List the installed PCT-EPO Guidelines snapshot."""
    return await outline_api.list_versions(PctGuidelinesClient, client=client)
