"""Async API for PatentsView.

Usage
-----
Preferred: use the client as a context manager::

    async with PatentsViewClient() as client:
        results = await client.search_patents(query, fields=["patent_id", "patent_title"])

One-shot convenience functions (create client automatically)::

    patent = await get_patent("US10123456B2")
    count = await get_forward_citation_count("10123456")
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .client import (
    DEFAULT_CITATION_FIELDS,
    DEFAULT_CLAIM_FIELDS,
    DEFAULT_PATENT_DETAIL_FIELDS,
    DEFAULT_PATENT_FIELDS,
    Assignee,
    Citation,
    CitationsResponse,
    Claim,
    ClaimsResponse,
    CpcClassification,
    Examiner,
    Inventor,
    Patent,
    PatentsResponse,
    PatentsViewClient,
    PatentWithDetails,
)
from .query import PatentsViewQuery

__all__ = [
    # Client
    "PatentsViewClient",
    # Models
    "Patent",
    "PatentWithDetails",
    "Inventor",
    "Assignee",
    "Examiner",
    "CpcClassification",
    "Citation",
    "Claim",
    # Response models
    "PatentsResponse",
    "CitationsResponse",
    "ClaimsResponse",
    # Input models
    "PatentsSearchInput",
    # Query builder
    "PatentsViewQuery",
    # Functions
    "get_client",
    "search_patents",
    "get_patent",
    "get_citations",
    "get_claims",
    "get_forward_citation_count",
    "get_independent_claims",
    "get_shortest_independent_claim_length",
    # Field defaults
    "DEFAULT_PATENT_FIELDS",
    "DEFAULT_PATENT_DETAIL_FIELDS",
    "DEFAULT_CITATION_FIELDS",
    "DEFAULT_CLAIM_FIELDS",
]


class PatentsSearchInput(BaseModel):
    """Input model for patent searches.

    Provides a structured way to specify search parameters. You can either
    provide a raw query dict or use the convenience fields (cpc_codes,
    assignees, etc.) which will be combined with AND logic.
    """

    query: dict[str, Any] | None = Field(
        default=None,
        description="Raw PatentsView query dict. If provided, other filters are ignored.",
    )
    cpc_codes: list[str] | None = Field(
        default=None,
        description="CPC classification codes to filter by (e.g., ['H04L63']).",
    )
    assignees: list[str] | None = Field(
        default=None,
        description="Assignee organization names to filter by.",
    )
    inventors: list[str] | None = Field(
        default=None,
        description="Inventor names to filter by.",
    )
    keywords: list[str] | None = Field(
        default=None,
        description="Keywords to search in patent title.",
    )
    date_after: str | None = Field(
        default=None,
        description="Return patents granted on or after this date (YYYY-MM-DD).",
    )
    date_before: str | None = Field(
        default=None,
        description="Return patents granted on or before this date (YYYY-MM-DD).",
    )
    patent_type: str | None = Field(
        default=None,
        description="Patent type filter (utility, design, plant, reissue).",
    )
    fields: list[str] | None = Field(
        default=None,
        description="Fields to return in results.",
    )
    sort_by: str | None = Field(
        default=None,
        description="Field to sort by (e.g., 'patent_date', 'patent_num_cited_by_us_patents').",
    )
    sort_order: str = Field(
        default="desc",
        description="Sort order: 'asc' or 'desc'.",
    )
    per_page: int = Field(
        default=25,
        ge=1,
        le=1000,
        description="Results per page (max 1000).",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number (1-indexed).",
    )

    model_config = {"populate_by_name": True}


def get_client(*, use_cache: bool = True) -> PatentsViewClient:
    """Create a PatentsViewClient.

    Prefer using the client as a context manager::

        async with PatentsViewClient() as client:
            ...

    If you use get_client() directly, remember to call client.close() when done.
    """
    return PatentsViewClient(use_cache=use_cache)


def _build_query_from_input(input_data: PatentsSearchInput) -> dict[str, Any]:
    """Build query dict from PatentsSearchInput."""
    if input_data.query is not None:
        return input_data.query

    builder = PatentsViewQuery()

    if input_data.cpc_codes:
        for cpc in input_data.cpc_codes:
            builder.cpc(cpc)

    if input_data.assignees:
        for assignee in input_data.assignees:
            builder.assignee(assignee)

    if input_data.inventors:
        for inventor in input_data.inventors:
            builder.inventor(inventor)

    if input_data.keywords:
        for keyword in input_data.keywords:
            builder.title(keyword)

    if input_data.date_after:
        builder.since(input_data.date_after)

    if input_data.date_before:
        builder.until(input_data.date_before)

    if input_data.patent_type:
        builder.patent_type(input_data.patent_type)

    return builder.build()


async def search_patents(
    input_data: PatentsSearchInput,
    *,
    use_cache: bool = True,
) -> PatentsResponse:
    """Search patents using PatentsView API.

    Args:
        input_data: Search parameters (query, filters, pagination)
        use_cache: Whether to use HTTP caching

    Returns:
        PatentsResponse with matching patents and counts
    """
    query = _build_query_from_input(input_data)
    if not query:
        raise ValueError(
            "Provide at least one search criterion (query, cpc_codes, assignees, etc.)"
        )

    sort = None
    if input_data.sort_by:
        sort = [{input_data.sort_by: input_data.sort_order}]

    async with PatentsViewClient(use_cache=use_cache) as client:
        return await client.search_patents(
            query=query,
            fields=input_data.fields,
            sort=sort,
            per_page=input_data.per_page,
            page=input_data.page,
        )


async def get_patent(
    patent_number: str,
    *,
    fields: list[str] | None = None,
    use_cache: bool = True,
) -> PatentWithDetails | None:
    """Get a single patent by number.

    Args:
        patent_number: Patent number (e.g., "US10123456B2" or "10123456")
        fields: Fields to return
        use_cache: Whether to use HTTP caching

    Returns:
        PatentWithDetails or None if not found
    """
    async with PatentsViewClient(use_cache=use_cache) as client:
        return await client.get_patent(patent_number, fields=fields)


async def get_citations(
    patent_id: str,
    *,
    direction: str = "citing",
    per_page: int = 100,
    page: int = 1,
    use_cache: bool = True,
) -> CitationsResponse:
    """Get citation relationships for a patent.

    Args:
        patent_id: PatentsView patent_id (not patent_number)
        direction: "citing" (patents that cite this one) or
                  "cited" (patents cited by this one)
        per_page: Results per page
        page: Page number
        use_cache: Whether to use HTTP caching

    Returns:
        CitationsResponse with citations
    """
    async with PatentsViewClient(use_cache=use_cache) as client:
        return await client.get_citations(
            patent_id,
            direction=direction,
            per_page=per_page,
            page=page,
        )


async def get_claims(
    patent_id: str,
    *,
    per_page: int = 100,
    page: int = 1,
    use_cache: bool = True,
) -> ClaimsResponse:
    """Get claims for a patent.

    Args:
        patent_id: PatentsView patent_id (not patent_number)
        per_page: Results per page
        page: Page number
        use_cache: Whether to use HTTP caching

    Returns:
        ClaimsResponse with claims
    """
    async with PatentsViewClient(use_cache=use_cache) as client:
        return await client.get_claims(patent_id, per_page=per_page, page=page)


# -----------------------------------------------------------------------------
# Quality Metrics Convenience Functions
# -----------------------------------------------------------------------------


async def get_forward_citation_count(
    patent_number: str,
    *,
    use_cache: bool = True,
) -> int:
    """Get the number of patents that cite this patent.

    Args:
        patent_number: Patent number (e.g., "US10123456B2")
        use_cache: Whether to use HTTP caching

    Returns:
        Forward citation count, or 0 if patent not found
    """
    async with PatentsViewClient(use_cache=use_cache) as client:
        patent = await client.get_patent(
            patent_number,
            fields=["patent_id", "patent_num_cited_by_us_patents"],
        )
        if patent and patent.patent_num_cited_by_us_patents is not None:
            return patent.patent_num_cited_by_us_patents
        return 0


async def get_independent_claims(
    patent_id: str,
    *,
    use_cache: bool = True,
) -> list[Claim]:
    """Get independent claims for a patent.

    Args:
        patent_id: PatentsView patent_id
        use_cache: Whether to use HTTP caching

    Returns:
        List of independent claims
    """
    async with PatentsViewClient(use_cache=use_cache) as client:
        result = await client.get_claims(patent_id, per_page=1000)
        return [c for c in result.claims if c.is_independent]


async def get_shortest_independent_claim_length(
    patent_id: str,
    *,
    use_cache: bool = True,
) -> int:
    """Get word count of shortest independent claim.

    Args:
        patent_id: PatentsView patent_id
        use_cache: Whether to use HTTP caching

    Returns:
        Word count of shortest independent claim, or 0 if no claims found
    """
    claims = await get_independent_claims(patent_id, use_cache=use_cache)
    if not claims:
        return 0
    return min(c.word_count for c in claims)
