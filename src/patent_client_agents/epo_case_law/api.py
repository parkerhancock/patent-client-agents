"""Async API for the EPO Case Law of the Boards of Appeal.

Preferred: use the client as a context manager::

    async with CaseLawClient() as client:
        results = await client.search(query="inventive step")
        section = await client.get_section("I.D.3")

One-shot functions open and close a client per call::

    results = await search(SearchInput(query="inventive step"))

Passing ``client=`` to them is deprecated and will be removed in v1.0.
"""

from __future__ import annotations

from patent_client_agents.shared.corpus.outline import api as outline_api

from .client import CaseLawClient
from .models import CaseLawSearchResponse, CaseLawSection, CaseLawVersion
from .resources import USAGE_RESOURCE_URI, get_usage_resource

__all__ = [
    "CaseLawClient",
    "CaseLawSearchResponse",
    "CaseLawSection",
    "CaseLawVersion",
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
    """Input for getting an CASELAW section.

    Accepts either a section number (e.g., "2106", "2106.04(a)") or an href
    (e.g., "d0e122292.html"). Section numbers are automatically resolved.
    """


def get_client() -> CaseLawClient:
    """Create a CaseLawClient. Prefer ``async with CaseLawClient() as client:``.

    If you use get_client() directly, you are responsible for calling
    ``await client.close()`` when done.
    """
    return CaseLawClient()


async def search(
    params: SearchInput,
    *,
    client: CaseLawClient | None = None,
) -> CaseLawSearchResponse:
    """Search the EPO Case Law."""
    return await outline_api.search(CaseLawClient, params, client=client)


async def get_section(
    params: SectionInput | str,
    *,
    client: CaseLawClient | None = None,
) -> CaseLawSection:
    """Get one EPO Case Law section by citation, section number, or href."""
    if isinstance(params, str):
        params = SectionInput(section=params)
    return await outline_api.get_section(CaseLawClient, params, client=client)


async def list_versions(
    *,
    client: CaseLawClient | None = None,
) -> list[CaseLawVersion]:
    """List the installed EPO Case Law snapshot."""
    return await outline_api.list_versions(CaseLawClient, client=client)
