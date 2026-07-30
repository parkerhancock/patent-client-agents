"""Async API for the IPOS Singapore statutes corpus (MCP-free)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .client import IposStatutesClient
from .corpus import CorpusUnavailable
from .models import (
    IposCorpusMeta,
    IposSection,
    IposStatute,
    IposStatuteSearchHit,
    IposStatuteSearchResponse,
)
from .resources import USAGE_RESOURCE_URI, get_usage_resource

__all__ = [
    "IposStatutesClient",
    "CorpusUnavailable",
    "IposStatute",
    "IposSection",
    "IposCorpusMeta",
    "IposStatuteSearchHit",
    "IposStatuteSearchResponse",
    "StatuteSearchInput",
    "SectionInput",
    "get_client",
    "search",
    "get_section",
    "get_by_citation",
    "list_statutes",
    "USAGE_RESOURCE_URI",
    "get_usage_resource",
]


class StatuteSearchInput(BaseModel):
    query: str
    statute: str | None = Field(
        default=None,
        description=(
            "Optional statute key — 'patents', 'tm', 'designs', or "
            "'copyright'. Aliases like 'Patents Act' / 'TMA1998' are "
            "accepted."
        ),
    )
    syntax: str = Field(default="and", description="'and', 'or', 'adj', or 'exact'")
    sort: str = Field(default="relevance", description="'relevance' (BM25) or 'statute'")
    per_page: int = Field(default=10, ge=1, le=100)
    page: int = Field(default=1, ge=1)


class SectionInput(BaseModel):
    """Input for fetching a single IPOS section.

    Either ``citation`` (free-form, e.g. ``"Section 13 Patents Act"``) or
    the discrete ``statute`` + ``section_label`` pair must be provided.
    """

    citation: str | None = Field(
        default=None,
        description="Free-form citation, e.g. 'Section 13 Patents Act'.",
    )
    statute: str | None = Field(
        default=None,
        description="Statute key or alias.",
    )
    section_label: str | None = Field(
        default=None,
        description="Section label as it appears upstream, e.g. '13', '13A', '27(1)'.",
    )


def get_client() -> IposStatutesClient:
    return IposStatutesClient()


async def search(params: StatuteSearchInput) -> IposStatuteSearchResponse:
    async with IposStatutesClient() as client:
        return await client.search(
            params.query,
            statute=params.statute,
            syntax=params.syntax,
            sort=params.sort,
            per_page=params.per_page,
            page=params.page,
        )


async def get_section(params: SectionInput | str) -> IposSection | None:
    """Fetch a single section.

    Accepts either a :class:`SectionInput` or a bare citation string for
    convenience.
    """
    if isinstance(params, str):
        params = SectionInput(citation=params)
    async with IposStatutesClient() as client:
        if params.citation:
            return await client.get_by_citation(params.citation)
        if params.statute and params.section_label:
            return await client.get_section(
                statute=params.statute,
                section_label=params.section_label,
            )
        return None


async def get_by_citation(citation: str) -> IposSection | None:
    async with IposStatutesClient() as client:
        return await client.get_by_citation(citation)


async def list_statutes() -> list[IposStatute]:
    async with IposStatutesClient() as client:
        return await client.list_statutes()
