"""Async Google Patents API (MCP-free) plus client re-exports."""

from .api import (  # noqa: F401
    FigureBounds,
    FigureCallout,
    FigureEntry,
    GooglePatentsClient,
    GooglePatentsSearchInput,
    GooglePatentsSearchResponse,
    GooglePatentsSearchResult,
    PatentData,
    fetch,
    fetch_figures,
    fetch_pdf,
    get_client,
    search,
)
