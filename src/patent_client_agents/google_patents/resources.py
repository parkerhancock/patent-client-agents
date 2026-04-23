"""Static resources for Google Patents MCP server."""

from __future__ import annotations

from importlib import resources as importlib_resources

SEARCH_GUIDE_RESOURCE_URI = "resource://google-patents/search-guide"


def get_search_guide() -> str:
    return (
        importlib_resources.files("google_patents_mcp.data")
        .joinpath("search_guide.md")
        .read_text(encoding="utf-8")
    )
