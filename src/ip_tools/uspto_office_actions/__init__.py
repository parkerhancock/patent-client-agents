"""USPTO Office Action Dataset API client.

Provides access to office action rejections, citations, full text, and
enriched citation metadata via the USPTO Dataset API.
"""

from .client import OfficeActionClient
from .models import (
    CitationSearchResponse,
    EnrichedCitation,
    EnrichedCitationSearchResponse,
    OfficeActionCitation,
    OfficeActionRejection,
    OfficeActionText,
    OfficeActionTextSearchResponse,
    RejectionSearchResponse,
)

__all__ = [
    "OfficeActionClient",
    "CitationSearchResponse",
    "EnrichedCitation",
    "EnrichedCitationSearchResponse",
    "OfficeActionCitation",
    "OfficeActionRejection",
    "OfficeActionText",
    "OfficeActionTextSearchResponse",
    "RejectionSearchResponse",
]
