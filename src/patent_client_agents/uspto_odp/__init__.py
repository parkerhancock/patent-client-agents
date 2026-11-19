"""USPTO Open Data Portal (ODP) client and models.

This module provides async access to USPTO's Open Data Portal API for:
- Patent applications (search, metadata, documents, family graphs)
- Bulk data downloads
- Petition decisions
- Office action search and trademark decisions and proceedings
- PTAB trials, appeals, and interferences
"""

from .client import UsptoOdpClient
from .clients import (
    ApplicationsClient,
    BulkDataClient,
    OfficeActionSearchClient,
    PetitionsClient,
    PtabAppealsClient,
    PtabInterferencesClient,
    PtabTrialsClient,
    TrademarkDecisionsClient,
)
from .models import (
    # Core application models
    ApplicationResponse,
    BulkDataProductResponse,
    BulkDataSearchResponse,
    DocumentRecord,
    DocumentsResponse,
    OfficeActionResponse,
    PetitionDecisionIdentifierResponse,
    PetitionDecisionResponse,
    PtabAppeal,
    PtabAppealDecisionData,
    PtabAppealDocumentData,
    # PTAB Appeals
    PtabAppealMetaData,
    PtabAppealRequestorData,
    PtabAppealResponse,
    PtabAppellantData,
    PtabDecisionData,
    PtabDerivationPetitionerData,
    PtabDocumentData,
    PtabInterference,
    PtabInterferenceDocumentData,
    # PTAB Interferences
    PtabInterferenceMetaData,
    PtabInterferencePartyData,
    PtabInterferenceResponse,
    PtabPatentOwnerData,
    PtabPetitionerData,
    # PTAB Trial Decisions
    PtabTrialDecision,
    PtabTrialDecisionResponse,
    # PTAB Trial Documents
    PtabTrialDocument,
    PtabTrialDocumentResponse,
    # PTAB Trial Proceedings
    PtabTrialMetaData,
    PtabTrialProceeding,
    PtabTrialProceedingResponse,
    SearchResponse,
    StatusCodeResponse,
    TrademarkDecisionResponse,
)

__all__ = [
    # Client
    "UsptoOdpClient",
    # Domain clients
    "ApplicationsClient",
    "BulkDataClient",
    "OfficeActionSearchClient",
    "PetitionsClient",
    "PtabAppealsClient",
    "PtabInterferencesClient",
    "PtabTrialsClient",
    "TrademarkDecisionsClient",
    # Application models
    "ApplicationResponse",
    "SearchResponse",
    "DocumentsResponse",
    "DocumentRecord",
    # Bulk data models
    "BulkDataProductResponse",
    "BulkDataSearchResponse",
    # Petition models
    "PetitionDecisionResponse",
    "PetitionDecisionIdentifierResponse",
    # Office action, trademark decision, and status code models
    "OfficeActionResponse",
    "TrademarkDecisionResponse",
    "StatusCodeResponse",
    # PTAB Appeal models
    "PtabAppeal",
    "PtabAppealResponse",
    "PtabAppealMetaData",
    "PtabAppealDecisionData",
    "PtabAppealDocumentData",
    "PtabAppealRequestorData",
    "PtabAppellantData",
    "PtabDecisionData",
    "PtabDocumentData",
    # PTAB Interference models
    "PtabInterference",
    "PtabInterferenceResponse",
    "PtabInterferenceMetaData",
    "PtabInterferenceDocumentData",
    "PtabInterferencePartyData",
    "PtabDerivationPetitionerData",
    "PtabPatentOwnerData",
    "PtabPetitionerData",
    # PTAB Trial models
    "PtabTrialProceeding",
    "PtabTrialProceedingResponse",
    "PtabTrialMetaData",
    "PtabTrialDecision",
    "PtabTrialDecisionResponse",
    "PtabTrialDocument",
    "PtabTrialDocumentResponse",
]
