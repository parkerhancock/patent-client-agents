"""USPTO Open Data Portal (ODP) client and models.

This module provides async access to USPTO's Open Data Portal API for:
- Patent applications (search, metadata, documents, family graphs)
- Bulk data downloads
- Petition decisions
- PTAB trials, appeals, and interferences
"""

from .client import UsptoOdpClient
from .clients import (
    ApplicationsClient,
    BulkDataClient,
    PetitionsClient,
    PtabAppealsClient,
    PtabInterferencesClient,
    PtabTrialsClient,
)
from .models import (
    # Core application models
    ApplicationResponse,
    BulkDataProductResponse,
    BulkDataSearchResponse,
    DocumentRecord,
    DocumentsResponse,
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
)

__all__ = [
    # Client
    "UsptoOdpClient",
    # Domain clients
    "ApplicationsClient",
    "BulkDataClient",
    "PetitionsClient",
    "PtabAppealsClient",
    "PtabInterferencesClient",
    "PtabTrialsClient",
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
