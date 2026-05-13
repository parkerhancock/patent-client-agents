"""USPTO Trademark Manual of Examining Procedure (TMEP) client."""

from .api import (
    USAGE_RESOURCE_URI,
    SearchInput,
    SectionInput,
    TmepClient,
    TmepSearchResponse,
    TmepSection,
    TmepVersion,
    get_section,
    get_usage_resource,
    list_versions,
    search,
)
from .corpus import CorpusUnavailable

__all__ = [
    "TmepClient",
    "TmepSearchResponse",
    "TmepSection",
    "TmepVersion",
    "SearchInput",
    "SectionInput",
    "CorpusUnavailable",
    "search",
    "get_section",
    "list_versions",
    "USAGE_RESOURCE_URI",
    "get_usage_resource",
]
