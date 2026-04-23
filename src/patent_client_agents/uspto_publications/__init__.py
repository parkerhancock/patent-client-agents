"""Async API for USPTO Patent Public Search (PPUBS) without MCP wiring."""

from .api import (  # noqa: F401
    PdfResponse,
    PublicSearchBiblioPage,
    PublicSearchClient,
    PublicSearchDocument,
    download_pdf,
    get_document,
    resolve_and_download_pdf,
    resolve_publication,
    search,
)
from .resources import (  # noqa: F401
    SEARCH_GUIDE_RESOURCE_URI,
    SEARCHABLE_INDEX_RESOURCE_URI,
    get_search_guide,
    get_searchable_indexes_resource,
)

__all__ = [
    "PublicSearchClient",
    "PublicSearchBiblioPage",
    "PublicSearchDocument",
    "PdfResponse",
    "search",
    "get_document",
    "download_pdf",
    "resolve_publication",
    "resolve_and_download_pdf",
    "SEARCH_GUIDE_RESOURCE_URI",
    "SEARCHABLE_INDEX_RESOURCE_URI",
    "get_search_guide",
    "get_searchable_indexes_resource",
]
