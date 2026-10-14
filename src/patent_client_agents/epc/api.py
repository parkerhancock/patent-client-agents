"""Async API for the European Patent Convention.

Preferred: use the client as a context manager::

    async with EpcClient() as client:
        results = await client.search(query="novelty")
        section = await client.get_section("Article 54")

One-shot functions open and close a client per call::

    results = await search(SearchInput(query="novelty"))

Passing ``client=`` to them is deprecated and will be removed in v1.0.
"""

from __future__ import annotations

from patent_client_agents.shared.corpus.outline import api as outline_api

from .client import EpcClient
from .models import EpcSearchResponse, EpcSection, EpcVersion
from .resources import USAGE_RESOURCE_URI, get_usage_resource

__all__ = [
    "EpcClient",
    "EpcSearchResponse",
    "EpcSection",
    "EpcVersion",
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
    """Input for getting an EPC section.

    Accepts either a section number (e.g., "2106", "2106.04(a)") or an href
    (e.g., "d0e122292.html"). Section numbers are automatically resolved.
    """


def get_client() -> EpcClient:
    """Create a EpcClient. Prefer ``async with EpcClient() as client:``.

    If you use get_client() directly, you are responsible for calling
    ``await client.close()`` when done.
    """
    return EpcClient()


async def search(
    params: SearchInput,
    *,
    client: EpcClient | None = None,
) -> EpcSearchResponse:
    """Search the EPC."""
    return await outline_api.search(EpcClient, params, client=client)


async def get_section(
    params: SectionInput | str,
    *,
    client: EpcClient | None = None,
) -> EpcSection:
    """Get one EPC section by citation, section number, or href."""
    if isinstance(params, str):
        params = SectionInput(section=params)
    return await outline_api.get_section(EpcClient, params, client=client)


async def list_versions(
    *,
    client: EpcClient | None = None,
) -> list[EpcVersion]:
    """List the installed EPC snapshot."""
    return await outline_api.list_versions(EpcClient, client=client)
