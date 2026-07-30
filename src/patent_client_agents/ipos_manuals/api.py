"""Async API for the IPOS Singapore manuals corpus (MCP-free)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .client import IposManualsClient
from .corpus import CorpusUnavailable
from .models import (
    IposManual,
    IposManualsCorpusMeta,
    IposManualSearchHit,
    IposManualSearchResponse,
    IposManualSection,
)
from .resources import USAGE_RESOURCE_URI, get_usage_resource

__all__ = [
    "IposManualsClient",
    "CorpusUnavailable",
    "IposManual",
    "IposManualSection",
    "IposManualsCorpusMeta",
    "IposManualSearchHit",
    "IposManualSearchResponse",
    "ManualSearchInput",
    "ManualSectionInput",
    "get_client",
    "search",
    "get_section",
    "get_by_citation",
    "list_manuals",
    "USAGE_RESOURCE_URI",
    "get_usage_resource",
]


class ManualSearchInput(BaseModel):
    query: str
    manual: str | None = Field(
        default=None,
        description=(
            "Optional manual key — 'peg', 'tm', or 'designs'. Aliases "
            "like 'Patent Examination Guidelines' or 'TM Work Manual' "
            "are accepted."
        ),
    )
    syntax: str = Field(default="and", description="'and', 'or', 'adj', or 'exact'")
    sort: str = Field(default="relevance", description="'relevance' (BM25) or 'manual'")
    per_page: int = Field(default=10, ge=1, le=100)
    page: int = Field(default=1, ge=1)


class ManualSectionInput(BaseModel):
    citation: str | None = Field(
        default=None,
        description="Free-form citation, e.g. 'IPOS PEG 1.5.3'.",
    )
    manual: str | None = Field(default=None, description="Manual key or alias.")
    section_label: str | None = Field(
        default=None,
        description="Section label as it appears upstream, e.g. '1.5.3', '4.A.2'.",
    )


def get_client() -> IposManualsClient:
    return IposManualsClient()


async def search(params: ManualSearchInput) -> IposManualSearchResponse:
    async with IposManualsClient() as client:
        return await client.search(
            params.query,
            manual=params.manual,
            syntax=params.syntax,
            sort=params.sort,
            per_page=params.per_page,
            page=params.page,
        )


async def get_section(params: ManualSectionInput | str) -> IposManualSection | None:
    if isinstance(params, str):
        params = ManualSectionInput(citation=params)
    async with IposManualsClient() as client:
        if params.citation:
            return await client.get_by_citation(params.citation)
        if params.manual and params.section_label:
            return await client.get_section(
                manual=params.manual,
                section_label=params.section_label,
            )
        return None


async def get_by_citation(citation: str) -> IposManualSection | None:
    async with IposManualsClient() as client:
        return await client.get_by_citation(citation)


async def list_manuals() -> list[IposManual]:
    async with IposManualsClient() as client:
        return await client.list_manuals()
