"""Async API for the ILPO Israel statutes corpus (MCP-free)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .client import IlpoStatutesClient
from .corpus import CorpusUnavailable
from .models import (
    IlpoCorpusMeta,
    IlpoSearchHit,
    IlpoSearchResponse,
    IlpoSection,
    IlpoStatute,
)
from .resources import USAGE_RESOURCE_URI, get_usage_resource

__all__ = [
    "IlpoStatutesClient",
    "CorpusUnavailable",
    "IlpoStatute",
    "IlpoSection",
    "IlpoCorpusMeta",
    "IlpoSearchHit",
    "IlpoSearchResponse",
    "StatuteSearchInput",
    "SectionInput",
    "get_client",
    "search",
    "get_section",
    "list_statutes",
    "USAGE_RESOURCE_URI",
    "get_usage_resource",
]


class StatuteSearchInput(BaseModel):
    query: str
    statute: str | None = Field(
        default=None,
        description=(
            "Optional statute key — 'patents', 'trademarks', 'designs', "
            "'copyright', 'commercial_torts'. Aliases like 'trade marks' "
            "or 'trade secrets' are accepted (the latter maps to "
            "Commercial Torts Law)."
        ),
    )
    syntax: str = Field(default="and", description="'and', 'or', 'adj', or 'exact'")
    sort: str = Field(default="relevance", description="'relevance' (BM25) or 'outline'")
    per_page: int = Field(default=10, ge=1, le=100)
    page: int = Field(default=1, ge=1)


class SectionInput(BaseModel):
    """Input for fetching one section by citation or (statute, number) pair."""

    citation: str | None = Field(
        default=None,
        description=(
            "Free-text citation like 'Section 3 Patents Law' or "
            "'Article 6 Commercial Torts Law'. When provided, takes "
            "precedence over (statute, section_number)."
        ),
    )
    statute: str | None = Field(default=None)
    section_number: str | None = Field(default=None)


def get_client() -> IlpoStatutesClient:
    return IlpoStatutesClient()


async def search(params: StatuteSearchInput) -> IlpoSearchResponse:
    async with IlpoStatutesClient() as client:
        return await client.search(
            params.query,
            statute=params.statute,
            syntax=params.syntax,
            sort=params.sort,
            per_page=params.per_page,
            page=params.page,
        )


async def get_section(params: SectionInput | str) -> IlpoSection | None:
    if isinstance(params, str):
        params = SectionInput(citation=params)
    async with IlpoStatutesClient() as client:
        if params.citation:
            return await client.get_section_by_citation(params.citation)
        if params.statute and params.section_number:
            return await client.get_section(
                statute=params.statute, section_number=params.section_number
            )
        return None


async def list_statutes() -> list[IlpoStatute]:
    async with IlpoStatutesClient() as client:
        return await client.list_statutes()
