"""Resource helpers for USPTO PPUBS shared API."""

from __future__ import annotations

from importlib import resources

SEARCH_GUIDE_RESOURCE_URI = "resource://uspto-publications/search-guide"
SEARCHABLE_INDEX_RESOURCE_URI = "resource://uspto-publications/searchable-indexes"


def get_search_guide() -> str:
    return (
        resources.files("patent_client_agents.uspto_publications.docs")
        .joinpath("search_guide.md")
        .read_text(encoding="utf-8")
    )


def get_searchable_indexes_resource() -> str:
    return (
        resources.files("patent_client_agents.uspto_publications.docs")
        .joinpath("searchable_indexes.md")
        .read_text(encoding="utf-8")
    )
