"""Async API for the USPTO eMPEP without MCP wiring."""

from .api import (  # noqa: F401
    USAGE_RESOURCE_URI,
    MpepClient,
    MpepSearchResponse,
    MpepSection,
    MpepVersion,
    SearchInput,
    SectionInput,
    get_client,
    get_section,
    get_usage_resource,
    list_versions,
    search,
)
from .corpus import CorpusUnavailable

__all__ = [
    "MpepClient",
    "MpepSearchResponse",
    "MpepSection",
    "MpepVersion",
    "SearchInput",
    "SectionInput",
    "CorpusUnavailable",
    "search",
    "get_section",
    "list_versions",
    "get_client",
    "USAGE_RESOURCE_URI",
    "get_usage_resource",
]
