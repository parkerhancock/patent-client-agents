"""Async API for CanLII.

Mirror of :mod:`patent_client_agents.mpep.api` shape: Pydantic input
models plus module-level coroutines that create + close a client
internally so callers don't need to manage the context manager unless
they want to batch many calls.

Usage::

    from patent_client_agents.canlii import (
        CanLIIClient,
        BrowseCasesInput,
        browse_cases,
        get_case,
    )

    # one-shot
    cases = await browse_cases(BrowseCasesInput(database_id="onca", result_count=20))

    # batch with one client / one cache
    async with CanLIIClient() as cl:
        for db in (await cl.list_case_databases()).case_databases:
            ...
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from patent_client_agents.shared.api import one_shot

from .client import CanLIIClient
from .models import (
    CaseDatabase,
    CaseDatabaseList,
    CaseId,
    CaseList,
    CaseMetadata,
    CaseRef,
    CitedCasesResponse,
    CitedLegislationRef,
    CitedLegislationsResponse,
    CitingCasesResponse,
    Language,
    LegislationDatabase,
    LegislationDatabaseList,
    LegislationList,
    LegislationMetadata,
    LegislationPart,
    LegislationRef,
    LegislationType,
)
from .resources import USAGE_RESOURCE_URI, get_usage_resource

__all__ = [
    # Client
    "CanLIIClient",
    "get_client",
    # Inputs
    "BrowseCasesInput",
    "GetCaseInput",
    "GetCitatorInput",
    "BrowseLegislationInput",
    "GetLegislationInput",
    # Functions
    "list_case_databases",
    "browse_cases",
    "get_case",
    "get_cited_cases",
    "get_citing_cases",
    "get_cited_legislations",
    "list_legislation_databases",
    "browse_legislation",
    "get_legislation",
    # Models
    "CaseDatabase",
    "CaseDatabaseList",
    "CaseId",
    "CaseList",
    "CaseMetadata",
    "CaseRef",
    "CitedCasesResponse",
    "CitedLegislationRef",
    "CitedLegislationsResponse",
    "CitingCasesResponse",
    "Language",
    "LegislationDatabase",
    "LegislationDatabaseList",
    "LegislationList",
    "LegislationMetadata",
    "LegislationPart",
    "LegislationRef",
    "LegislationType",
    # Resources
    "USAGE_RESOURCE_URI",
    "get_usage_resource",
]


class BrowseCasesInput(BaseModel):
    database_id: str = Field(
        description="CanLII database code (e.g. 'onca' for Ontario Court of Appeal, "
        "'fct' for Federal Court, 'tmob-comc' for Trade-marks Opposition Board)"
    )
    offset: int = Field(default=0, ge=0)
    result_count: int = Field(default=100, ge=1, le=10_000)
    language: Language = "en"
    published_before: str | None = Field(default=None, description="ISO date YYYY-MM-DD")
    published_after: str | None = Field(default=None, description="ISO date YYYY-MM-DD")
    modified_before: str | None = Field(default=None, description="ISO date YYYY-MM-DD")
    modified_after: str | None = Field(default=None, description="ISO date YYYY-MM-DD")
    changed_before: str | None = Field(default=None, description="ISO date YYYY-MM-DD")
    changed_after: str | None = Field(default=None, description="ISO date YYYY-MM-DD")
    decision_date_before: str | None = Field(default=None, description="ISO date YYYY-MM-DD")
    decision_date_after: str | None = Field(default=None, description="ISO date YYYY-MM-DD")


class GetCaseInput(BaseModel):
    database_id: str
    case_id: str
    language: Language = "en"


class GetCitatorInput(BaseModel):
    database_id: str
    case_id: str


class BrowseLegislationInput(BaseModel):
    database_id: str
    language: Language = "en"


class GetLegislationInput(BaseModel):
    database_id: str
    legislation_id: str
    language: Language = "en"


def get_client() -> CanLIIClient:
    """Create a CanLIIClient. Prefer using the context-manager form directly."""
    return CanLIIClient()


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


@one_shot(get_client, CanLIIClient.list_case_databases)
async def list_case_databases(language: Language = "en") -> CaseDatabaseList: ...


async def browse_cases(params: BrowseCasesInput) -> CaseList:
    async with CanLIIClient() as client:
        return await client.browse_cases(**params.model_dump())


async def get_case(params: GetCaseInput) -> CaseMetadata:
    async with CanLIIClient() as client:
        return await client.get_case(**params.model_dump())


# ---------------------------------------------------------------------------
# Citator
# ---------------------------------------------------------------------------


async def get_cited_cases(params: GetCitatorInput) -> CitedCasesResponse:
    async with CanLIIClient() as client:
        return await client.get_cited_cases(**params.model_dump())


async def get_citing_cases(params: GetCitatorInput) -> CitingCasesResponse:
    async with CanLIIClient() as client:
        return await client.get_citing_cases(**params.model_dump())


async def get_cited_legislations(params: GetCitatorInput) -> CitedLegislationsResponse:
    async with CanLIIClient() as client:
        return await client.get_cited_legislations(**params.model_dump())


# ---------------------------------------------------------------------------
# Legislation
# ---------------------------------------------------------------------------


@one_shot(get_client, CanLIIClient.list_legislation_databases)
async def list_legislation_databases(language: Language = "en") -> LegislationDatabaseList: ...


async def browse_legislation(params: BrowseLegislationInput) -> LegislationList:
    async with CanLIIClient() as client:
        return await client.browse_legislation(**params.model_dump())


async def get_legislation(params: GetLegislationInput) -> LegislationMetadata:
    async with CanLIIClient() as client:
        return await client.get_legislation(**params.model_dump())
