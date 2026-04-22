"""Async API for Google Patents.

Usage
-----
Preferred: use the client as a context manager for consistency::

    async with GooglePatentsClient() as client:
        patent = await client.get_patent_data("US7654321B2")
        results = await client.search_patents(keywords=["machine learning"])

One-shot convenience functions (create client automatically)::

    patent = await fetch("US7654321B2")

Legacy: passing client= parameter (deprecated, will be removed in v1.0)::

    client = get_client()
    patent = await fetch("US7654321B2", client=client)
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from law_tools_core.tooling import agent_tool

from .client import (
    ChemicalCompound,
    ChildApplication,
    Concept,
    CountryFiling,
    CpcClassification,
    Definition,
    DetailedNpl,
    ExternalLink,
    FamilyMember,
    GooglePatentsClient,
    GooglePatentsSearchResponse,
    GooglePatentsSearchResult,
    Landscape,
    LegalEvent,
    NonPatentLiterature,
    PatentCitation,
    PatentData,
    PriorityApplication,
)

__all__ = [
    # Client and data models
    "GooglePatentsClient",
    "GooglePatentsSearchResponse",
    "GooglePatentsSearchResult",
    "PatentData",
    # Pydantic models for structured data
    "CpcClassification",
    "PatentCitation",
    "FamilyMember",
    "CountryFiling",
    "PriorityApplication",
    "LegalEvent",
    "NonPatentLiterature",
    "Concept",
    "Landscape",
    "Definition",
    "ChildApplication",
    "DetailedNpl",
    "ChemicalCompound",
    "ExternalLink",
    # Input model for search
    "GooglePatentsSearchInput",
    # Figure models
    "FigureBounds",
    "FigureCallout",
    "FigureEntry",
    # Functions
    "get_client",
    "fetch",
    "fetch_pdf",
    "fetch_figures",
    "search",
]


class FigureBounds(BaseModel):
    left: int | None = None
    top: int | None = None
    right: int | None = None
    bottom: int | None = None


class FigureCallout(BaseModel):
    figure_page: int | None = None
    reference_id: str | None = None
    label: str | None = None
    bounds: FigureBounds = Field(default_factory=FigureBounds)


class FigureEntry(BaseModel):
    index: int
    page_number: int | None = None
    image_id: str | None = None
    thumbnail_url: str | None = None
    full_image_url: str | None = None
    callouts: list[FigureCallout] = Field(default_factory=list)


class GooglePatentsSearchInput(BaseModel):
    keywords: list[str] | None = Field(
        default=None,
        description=("Keyword queries; boolean operators are allowed inside each entry."),
    )
    cpc_codes: list[str] | None = Field(
        default=None,
        description="List of CPC symbols to match (e.g., ['H04L9/32']).",
    )
    inventors: list[str] | None = Field(default=None, description="Inventor names to filter on.")
    assignees: list[str] | None = Field(default=None, description="Assignee or applicant names.")
    country_codes: list[str] | None = Field(
        default=None,
        description="Restrict results to publication country codes (e.g., ['US','EP']).",
    )
    language_codes: list[str] | None = Field(
        default=None, description="Restrict results to languages (e.g., ['en','de'])."
    )
    date_type: str | None = Field(
        default="priority",
        description=(
            "Date field used alongside the before/after filters (priority, filing, or publication)."
        ),
    )
    filed_after: str | None = Field(
        default=None,
        description="Return documents with the selected date on/after this ISO date (YYYY-MM-DD).",
    )
    filed_before: str | None = Field(
        default=None,
        description="Return documents with the selected date on/before this ISO date (YYYY-MM-DD).",
    )
    status: str | None = Field(default=None, description="Status filter (e.g., ACTIVE).")
    patent_type: str | None = Field(default=None, description="Type filter (PATENT, DESIGN, etc.).")
    litigation: str | None = Field(
        default=None,
        description="Litigation filter as supported by Google Patents (e.g., 'true').",
    )
    include_patents: bool = Field(
        default=True,
        description="Include patent documents in the response (set false for NPL-only searches).",
    )
    include_npl: bool = Field(
        default=False,
        description="Include non-patent literature via Google Scholar integration.",
    )
    sort: str | None = Field(
        default=None, description="Sort order: 'new' (newest first) or 'old' (oldest first)."
    )
    dups: str | None = Field(
        default=None,
        description="Duplicate grouping mode (Google Patents 'dups' parameter).",
    )
    page: int | None = Field(default=None, ge=1, description="Page number (1-indexed).")
    page_size: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Number of records per page (default 10, max 100).",
    )
    cluster_results: bool | None = Field(
        default=None, description="Match the 'clustered' toggle in Google Patents results."
    )
    local: str | None = Field(
        default=None,
        description="Value for the undocumented 'local' query flag (rarely needed).",
    )

    model_config = {"populate_by_name": True}


def get_client(*, use_cache: bool = True) -> GooglePatentsClient:
    """Create a GooglePatentsClient with the desired caching behavior.

    Prefer using the client as a context manager::

        async with GooglePatentsClient() as client:
            ...

    If you use get_client() directly, you are responsible for ensuring
    proper cleanup (though this client is stateless, so cleanup is a no-op).
    """
    return GooglePatentsClient(use_cache=use_cache)


def _warn_client_deprecated() -> None:
    warnings.warn(
        "Passing client= is deprecated and will be removed in v1.0. "
        "Use 'async with GooglePatentsClient() as client:' instead.",
        DeprecationWarning,
        stacklevel=3,
    )


def _clean_list(
    values: list[str] | None, *, transform: Callable[[str], str] | None = None
) -> list[str]:
    if not values:
        return []
    cleaned: list[str] = []
    for value in values:
        stripped = value.strip()
        if not stripped:
            continue
        cleaned.append(transform(stripped) if transform else stripped)
    return cleaned


def _normalize_page(page: int | None) -> int | None:
    if page is None:
        return None
    return max(page, 1)


def _normalize_page_size(page_size: int | None) -> int | None:
    if page_size is None:
        return None
    return max(1, min(page_size, 100))


async def fetch(
    patent_number: str,
    *,
    client: GooglePatentsClient | None = None,
    use_cache: bool = True,
) -> PatentData:
    """Fetch metadata, claims, limitations, and HTML for a patent.

    If no client is provided, creates one internally.
    """
    if client is not None:
        _warn_client_deprecated()
        patent = await client.get_patent_data(patent_number)
        if patent is None:
            raise ValueError(f"Failed to fetch patent {patent_number}")
        return patent

    async with GooglePatentsClient(use_cache=use_cache) as cl:
        patent = await cl.get_patent_data(patent_number)
        if patent is None:
            raise ValueError(f"Failed to fetch patent {patent_number}")
        return patent


@agent_tool
async def fetch_pdf(
    patent_number: str,
    *,
    client: GooglePatentsClient | None = None,
    use_cache: bool = True,
) -> bytes:
    """Download the Google Patents PDF for a patent and return raw bytes.

    Retrieves the official PDF document from Google Patents. Note that this
    returns raw PDF bytes - if you need base64 encoding for transmission,
    encode the result using base64.b64encode().

    Args:
        patent_number: Patent publication number (e.g., 'US8206789B2', 'WO2021023456A1')
        client: Optional GooglePatentsClient (deprecated, will be removed in v1.0)
        use_cache: Whether to use cached responses (default: True)

    Returns:
        Raw PDF bytes ready to be written to a file or base64-encoded
    """
    if client is not None:
        _warn_client_deprecated()
        return await client.download_patent_pdf(patent_number, use_cache=use_cache)

    async with GooglePatentsClient(use_cache=use_cache) as cl:
        return await cl.download_patent_pdf(patent_number, use_cache=use_cache)


def _figure_entries_from_dict(figures: list[dict[str, Any]]) -> list[FigureEntry]:
    entries: list[FigureEntry] = []
    for idx, item in enumerate(figures):
        callouts = []
        for callout in item.get("callouts", []):
            bounds = FigureBounds(**(callout.get("bounds") or {}))
            callouts.append(
                FigureCallout(
                    figure_page=callout.get("figure_page"),
                    reference_id=callout.get("reference_id"),
                    label=callout.get("label"),
                    bounds=bounds,
                )
            )
        entries.append(
            FigureEntry(
                index=item.get("index", idx),
                page_number=item.get("page_number"),
                image_id=item.get("image_id"),
                thumbnail_url=item.get("thumbnail_url"),
                full_image_url=item.get("full_image_url"),
                callouts=callouts,
            )
        )
    return entries


@agent_tool
async def fetch_figures(
    patent_number: str,
    *,
    client: GooglePatentsClient | None = None,
    use_cache: bool = True,
) -> list[FigureEntry]:
    """Return metadata for figure images including thumbnails, full-size links, and callouts.

    Extracts figure metadata from the patent document including:
    - Thumbnail URLs for preview
    - Full-size image URLs for high-resolution viewing
    - Figure callouts with bounding boxes and reference labels
    - Page numbers where figures appear

    Args:
        patent_number: Patent publication number (e.g., 'US8206789B2', 'WO2021023456A1')
        client: Optional GooglePatentsClient (deprecated, will be removed in v1.0)
        use_cache: Whether to use cached responses (default: True)

    Returns:
        List of FigureEntry objects with image URLs and callout metadata
    """
    if client is not None:
        _warn_client_deprecated()
        figures = await client.get_patent_figures(patent_number)
        if figures is None:
            raise ValueError(f"Failed to fetch figures for patent {patent_number}")
        return _figure_entries_from_dict(figures)

    async with GooglePatentsClient(use_cache=use_cache) as cl:
        figures = await cl.get_patent_figures(patent_number)
        if figures is None:
            raise ValueError(f"Failed to fetch figures for patent {patent_number}")
        return _figure_entries_from_dict(figures)


@agent_tool
async def search(
    input_data: GooglePatentsSearchInput,
    *,
    client: GooglePatentsClient | None = None,
    use_cache: bool = True,
) -> GooglePatentsSearchResponse:
    """Run an advanced Google Patents search using the same fields available in the web UI.

    Supports comprehensive search capabilities including:
    - Keyword queries with boolean operators
    - CPC classification codes
    - Inventor and assignee name filters
    - Country and language restrictions
    - Date range filters (priority, filing, or publication dates)
    - Status and patent type filters
    - Litigation status filtering
    - Pagination and result clustering

    The input model (GooglePatentsSearchInput) provides detailed field descriptions
    for all search parameters. At least one search criterion must be provided.

    Args:
        input_data: GooglePatentsSearchInput with search criteria and filters
        client: Optional GooglePatentsClient (deprecated, will be removed in v1.0)
        use_cache: Whether to use cached responses (default: True)

    Returns:
        GooglePatentsSearchResponse with matching patents and search metadata

    Raises:
        ValueError: If no search criteria provided or invalid date_type
    """
    keywords = _clean_list(input_data.keywords or [])
    cpc_codes = _clean_list(input_data.cpc_codes or [])
    inventor_values = _clean_list(input_data.inventors or [])
    assignee_values = _clean_list(input_data.assignees or [])
    countries = _clean_list(input_data.country_codes or [], transform=str.upper)
    languages = _clean_list(input_data.language_codes or [], transform=str.lower)

    if not any([keywords, cpc_codes, inventor_values, assignee_values, countries, languages]):
        raise ValueError(
            "Provide at least one keyword, CPC code, inventor, assignee, country, or language "
            "filter."
        )

    date_type = (input_data.date_type or "priority").lower()
    if date_type not in {"priority", "filing", "publication"}:
        raise ValueError("date_type must be 'priority', 'filing', or 'publication'")

    page_size = _normalize_page_size(input_data.page_size)
    page = _normalize_page(input_data.page)

    search_kwargs = {
        "keywords": keywords,
        "cpc_codes": cpc_codes,
        "inventors": inventor_values,
        "assignees": assignee_values,
        "countries": countries,
        "languages": languages,
        "date_type": date_type,
        "filed_after": input_data.filed_after,
        "filed_before": input_data.filed_before,
        "status": input_data.status,
        "patent_type": input_data.patent_type,
        "litigation": input_data.litigation,
        "include_patents": input_data.include_patents,
        "include_npl": input_data.include_npl,
        "sort": input_data.sort,
        "dups": input_data.dups,
        "page": page,
        "page_size": page_size,
        "cluster_results": input_data.cluster_results,
        "local": input_data.local,
    }

    if client is not None:
        _warn_client_deprecated()
        return await client.search_patents(**search_kwargs)

    async with GooglePatentsClient(use_cache=use_cache) as cl:
        return await cl.search_patents(**search_kwargs)
