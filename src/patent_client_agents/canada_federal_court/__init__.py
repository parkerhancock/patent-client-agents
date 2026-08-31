"""Official Canadian Federal Court case-file and docket connector."""

from .api import (
    CaseLookupInput,
    DocketLookupInput,
    PartyCaseSearchInput,
    get_case,
    list_docket_entries,
    search_party_cases,
)
from .client import COURT_FILES_URL, CanadaFederalCourtClient, assess_docket_status
from .models import (
    CourtDivision,
    DocketStatus,
    FederalCourtCase,
    FederalCourtCaseRecord,
    FederalCourtCaseSearchResponse,
    FederalCourtDocketEntry,
    FederalCourtDocketResponse,
    FederalCourtIntellectualProperty,
    FederalCourtParty,
    FederalCourtRelatedCase,
)

__all__ = [
    "COURT_FILES_URL",
    "CaseLookupInput",
    "CanadaFederalCourtClient",
    "CourtDivision",
    "DocketLookupInput",
    "DocketStatus",
    "FederalCourtCase",
    "FederalCourtCaseRecord",
    "FederalCourtCaseSearchResponse",
    "FederalCourtDocketEntry",
    "FederalCourtDocketResponse",
    "FederalCourtIntellectualProperty",
    "FederalCourtParty",
    "FederalCourtRelatedCase",
    "PartyCaseSearchInput",
    "assess_docket_status",
    "get_case",
    "list_docket_entries",
    "search_party_cases",
]
