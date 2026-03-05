"""USPTO ODP Pydantic models.

This module provides strongly-typed Pydantic models for USPTO Open Data Portal API responses.
Models are organized by domain:

- applications: Patent applications, documents, family graphs
- bulkdata: Bulk data products
- petitions: Petition decisions
- ptab: PTAB trials, appeals, interferences

For backward compatibility, the old untyped models are still available.
New code should use the typed models where possible.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# Import new strongly-typed models
from .applications import (
    Address,
    Applicant,
    ApplicationEvent,
    ApplicationMetaData,
    ApplicationRecord,
    ApplicationResponse,
    Assignee,
    AssigneeAddress,
    Assignment,
    AssignmentResponse,
    Assignor,
    Attorney,
    ChildContinuity,
    ContinuityBag,
    CustomerNumberCorrespondenceData,
    DocumentMetaData,
    DocumentRecord,
    DocumentsResponse,
    EntityStatusData,
    FamilyEdge,
    FamilyGraphResponse,
    FamilyNode,
    ForeignPriority,
    Inventor,
    ParentContinuity,
    PatentTermAdjustmentData,
    PatentTermAdjustmentHistory,
    PersonName,
    RecordAttorney,
    SearchResponse,
    TelecommunicationAddress,
)
from .base import FlexibleModel, StrictModel

# =============================================================================
# Legacy Models (Backward Compatibility)
# =============================================================================
# These models are kept for backward compatibility with existing code.
# New code should use the strongly-typed models above.


class _BaseModel(BaseModel):
    """Legacy base model with extra='allow' for backward compatibility."""

    model_config = {"extra": "allow"}


# =============================================================================
# Bulk Data Models
# =============================================================================


class BulkDataFile(_BaseModel):
    fileName: str | None = None
    fileSize: int | None = None
    fileDataFromDate: str | None = None
    fileDataToDate: str | None = None
    fileTypeText: str | None = None
    fileDownloadURI: str | None = None
    fileReleaseDate: str | None = None
    fileDate: str | None = None
    fileLastModifiedDateTime: str | None = None


class ProductFileBag(_BaseModel):
    count: int | None = None
    fileDataBag: list[BulkDataFile] = Field(default_factory=list)


class BulkDataProduct(_BaseModel):
    productIdentifier: str
    productDescriptionText: str | None = None
    productTitleText: str | None = None
    productFrequencyText: str | None = None
    daysOfWeekText: str | None = None
    productLabelArrayText: list[str] | None = None
    productDataSetArrayText: list[str] | None = None
    productDataSetCategoryArrayText: list[str] | None = None
    productFromDate: str | None = None
    productToDate: str | None = None
    productTotalFileSize: int | None = None
    productFileTotalQuantity: int | None = None
    lastModifiedDateTime: str | None = None
    mimeTypeIdentifierArrayText: list[str] | None = None
    productFileBag: ProductFileBag | None = None


class BulkDataProductResponse(_BaseModel):
    count: int = 0
    bulkDataProductBag: list[BulkDataProduct] = Field(default_factory=list)


class BulkDataSearchResponse(BulkDataProductResponse):
    facets: dict[str, Any] | None = None


# =============================================================================
# Petition Decision Models
# =============================================================================


class PetitionDecisionFilter(_BaseModel):
    name: str
    value: list[str] = Field(default_factory=list)


class PetitionDecisionRange(_BaseModel):
    field: str
    valueFrom: str | None = None
    valueTo: str | None = None


class PetitionDecisionSort(_BaseModel):
    field: str
    order: str = "asc"


class PetitionDecisionDocument(_BaseModel):
    applicationNumberText: str | None = None
    officialDate: str | None = None
    documentIdentifier: str | None = None
    documentCode: str | None = None
    documentCodeDescriptionText: str | None = None
    documentDirectionCategory: str | None = None
    downloadOptionBag: list[dict[str, Any]] | None = None


class PetitionDecision(_BaseModel):
    petitionDecisionRecordIdentifier: str | None = None
    applicationNumberText: str | None = None
    businessEntityStatusCategory: str | None = None
    customerNumber: int | None = None
    decisionDate: str | None = None
    decisionPetitionTypeCode: int | None = None
    decisionTypeCode: str | None = None
    decisionPetitionTypeCodeDescriptionText: str | None = None
    finalDecidingOfficeName: str | None = None
    firstApplicantName: str | None = None
    firstInventorToFileIndicator: bool | None = None
    groupArtUnitNumber: str | None = None
    technologyCenter: str | None = None
    inventionTitle: str | None = None
    inventorBag: list[str] | None = None
    actionTakenByCourtName: str | None = None
    courtActionIndicator: bool | None = None
    lastIngestionDateTime: str | None = None
    patentNumber: str | None = None
    petitionIssueConsideredTextBag: list[Any] | None = None
    petitionMailDate: str | None = None
    prosecutionStatusCode: str | int | None = None
    prosecutionStatusCodeDescriptionText: str | None = None
    ruleBag: list[str] | None = None
    statuteBag: list[str] | None = None


class PetitionDecisionWithDocuments(PetitionDecision):
    documentBag: list[PetitionDecisionDocument] | None = None


class PetitionDecisionResponse(_BaseModel):
    count: int = 0
    petitionDecisionDataBag: list[PetitionDecision] = Field(default_factory=list)
    facets: list[dict[str, Any]] | None = None


class PetitionDecisionIdentifierResponse(_BaseModel):
    count: int = 0
    petitionDecisionDataBag: list[PetitionDecisionWithDocuments] = Field(default_factory=list)


# =============================================================================
# PTAB Trial Models (ODP v3.0)
# =============================================================================


class PtabTrialMetaData(_BaseModel):
    """Metadata for PTAB trial proceedings."""

    trialTypeCode: str | None = None
    trialStatusCategory: str | None = None
    petitionFilingDate: str | None = None
    trialLastModifiedDateTime: str | None = None
    accordedFilingDate: str | None = None
    institutionDecisionDate: str | None = None
    latestDecisionDate: str | None = None
    terminationDate: str | None = None


class PtabPatentOwnerData(_BaseModel):
    """Patent owner/respondent data in PTAB proceedings."""

    patentNumber: str | None = None
    applicationNumberText: str | None = None
    realPartyInInterestName: str | None = None
    grantDate: str | None = None
    patentOwnerName: str | None = None
    inventorName: str | None = None
    counselName: str | None = None
    technologyCenterNumber: str | None = None
    groupArtUnitNumber: str | None = None


class PtabPetitionerData(_BaseModel):
    """Regular petitioner data in PTAB proceedings."""

    realPartyInInterestName: str | None = None
    counselName: str | None = None


class PtabDerivationPetitionerData(_BaseModel):
    """Derivation petitioner data (for DER proceedings only)."""

    patentNumber: str | None = None
    grantDate: str | None = None
    realPartyInInterestName: str | None = None
    patentOwnerName: str | None = None
    inventorName: str | None = None
    counselName: str | None = None
    technologyCenterNumber: str | None = None
    groupArtUnitNumber: str | None = None
    applicationNumberText: str | None = None


class PtabDocumentData(_BaseModel):
    """Document metadata in PTAB proceedings."""

    documentIdentifier: str | None = None
    documentName: str | None = None
    documentSizeQuantity: int | None = None
    documentTypeDescriptionText: str | None = None
    documentFilingDate: str | None = None
    documentNumber: int | str | None = None
    filingPartyCategory: str | None = None
    documentTitleText: str | None = None
    fileDownloadURI: str | None = None
    downloadURI: str | None = None
    documentCategory: str | None = None
    documentOCRText: str | None = None
    mimeTypeIdentifier: str | None = None
    documentStatus: str | None = None


class PtabDecisionData(_BaseModel):
    """Decision data in PTAB proceedings."""

    trialOutcomeCategory: str | None = None
    decisionTypeCategory: str | None = None
    decisionIssueDate: str | None = None
    issueTypeBag: list[str] | str | None = None
    statuteAndRuleBag: list[str] | str | None = None


class PtabTrialProceeding(_BaseModel):
    """A PTAB trial proceeding (IPR, PGR, CBM, DER)."""

    trialNumber: str | None = None
    trialRecordIdentifier: str | None = None
    lastModifiedDateTime: str | None = None
    trialMetaData: PtabTrialMetaData | None = None
    patentOwnerData: PtabPatentOwnerData | None = None
    regularPetitionerData: PtabPetitionerData | None = None
    respondentData: PtabPatentOwnerData | None = None
    derivationPetitionerData: PtabDerivationPetitionerData | None = None
    fileDownloadURI: str | None = None


class PtabTrialProceedingResponse(_BaseModel):
    """Response from PTAB trial proceedings search."""

    count: int = 0
    requestIdentifier: str | None = None
    patentTrialProceedingDataBag: list[PtabTrialProceeding] = Field(default_factory=list)
    facets: list[dict[str, Any]] | None = None


class PtabTrialDocument(_BaseModel):
    """A PTAB trial document (filings, exhibits, etc.)."""

    trialNumber: str | None = None
    trialTypeCode: str | None = None
    trialDocumentCategory: str | None = None
    lastModifiedDateTime: str | None = None
    trialMetaData: PtabTrialMetaData | None = None
    patentOwnerData: PtabPatentOwnerData | None = None
    regularPetitionerData: PtabPetitionerData | None = None
    respondentData: PtabPatentOwnerData | None = None
    derivationPetitionerData: PtabDerivationPetitionerData | None = None
    documentData: PtabDocumentData | None = None


class PtabTrialDocumentResponse(_BaseModel):
    """Response from PTAB trial documents search."""

    count: int = 0
    requestIdentifier: str | None = None
    patentTrialDocumentDataBag: list[PtabTrialDocument] = Field(default_factory=list)
    facets: list[dict[str, Any]] | None = None


class PtabTrialDecision(_BaseModel):
    """A PTAB trial decision."""

    trialNumber: str | None = None
    trialTypeCode: str | None = None
    trialDocumentCategory: str | None = None
    lastModifiedDateTime: str | None = None
    trialMetaData: PtabTrialMetaData | None = None
    patentOwnerData: PtabPatentOwnerData | None = None
    regularPetitionerData: PtabPetitionerData | None = None
    respondentData: PtabPatentOwnerData | None = None
    derivationPetitionerData: PtabDerivationPetitionerData | None = None
    documentData: PtabDocumentData | None = None
    decisionData: PtabDecisionData | None = None


class PtabTrialDecisionResponse(_BaseModel):
    """Response from PTAB trial decisions search."""

    count: int = 0
    requestIdentifier: str | None = None
    patentTrialDocumentDataBag: list[PtabTrialDecision] = Field(default_factory=list)
    facets: list[dict[str, Any]] | None = None


# =============================================================================
# PTAB Appeals Models (ODP v3.0)
# =============================================================================


class PtabAppealMetaData(_BaseModel):
    """Metadata for PTAB appeals."""

    appealFilingDate: str | None = None
    docketNoticeMailedDate: str | None = None
    appealLastModifiedDate: str | None = None
    applicationTypeCategory: str | None = None
    fileDownloadURI: str | None = None


class PtabAppealDecisionData(_BaseModel):
    """Decision data for PTAB appeals."""

    appealOutcomeCategory: str | None = None
    decisionIssueDate: str | None = None
    decisionTypeCategory: str | None = None
    issueTypeBag: list[str] | None = None
    statuteAndRuleBag: list[str] | None = None


class PtabAppellantData(_BaseModel):
    """Appellant data in PTAB appeals."""

    realPartyInInterestName: str | None = None
    applicationNumberText: str | None = None
    patentOwnerName: str | None = None
    inventorName: str | None = None
    counselName: str | None = None
    publicationNumber: str | None = None
    publicationDate: str | None = None
    patentNumber: str | None = None
    technologyCenterNumber: str | None = None
    groupArtUnitNumber: str | None = None


class PtabAppealRequestorData(_BaseModel):
    """Requestor data for reexamination appeals."""

    thirdPartyName: str | None = None


class PtabAppealDocumentData(_BaseModel):
    """Document data for PTAB appeals."""

    documentFilingDate: str | None = None
    documentIdentifier: str | None = None
    documentName: str | None = None
    documentSizeQuantity: int | None = None
    documentOCRText: str | None = None
    documentTypeCategory: str | None = None
    documentTypeDescriptionText: str | None = None
    downloadURI: str | None = None
    fileDownloadURI: str | None = None


class PtabAppeal(_BaseModel):
    """A PTAB appeal decision."""

    appealNumber: str | None = None
    lastModifiedDateTime: str | None = None
    appealDocumentCategory: str | None = None
    decisionData: PtabAppealDecisionData | None = None
    appealMetaData: PtabAppealMetaData | None = None
    appellantData: PtabAppellantData | None = Field(default=None, alias="appelantData")
    requestorData: PtabAppealRequestorData | None = None
    documentData: PtabAppealDocumentData | None = None

    model_config = {"extra": "allow", "populate_by_name": True}


class PtabAppealResponse(_BaseModel):
    """Response from PTAB appeals search."""

    count: int = 0
    requestIdentifier: str | None = None
    patentAppealDataBag: list[PtabAppeal] = Field(default_factory=list)
    facets: list[dict[str, Any]] | None = None


# =============================================================================
# PTAB Interferences Models (ODP v3.0)
# =============================================================================


class PtabInterferenceMetaData(_BaseModel):
    """Metadata for PTAB interferences."""

    interferenceStyleName: str | None = None


class PtabInterferencePartyData(_BaseModel):
    """Party data for PTAB interferences (senior or junior party)."""

    patentOwnerName: str | None = None
    realPartyInInterestName: str | None = None
    patentNumber: str | None = None
    applicationNumberText: str | None = None
    grantDate: str | None = None
    inventorName: str | None = None
    counselName: str | None = None
    publicationNumber: str | None = None
    publicationDate: str | None = None
    technologyCenterNumber: str | None = None
    groupArtUnitNumber: str | None = None


class PtabInterferenceDocumentData(_BaseModel):
    """Document/decision data for PTAB interferences."""

    documentIdentifier: str | None = None
    documentName: str | None = None
    documentSizeQuantity: int | None = None
    documentTitleText: str | None = None
    documentOCRText: str | None = None
    decisionTypeCategory: str | None = None
    interferenceOutcomeCategory: str | None = None
    decisionIssueDate: str | None = None
    issueTypeBag: list[str] | None = None
    statuteAndRuleBag: list[str] | None = None
    fileDownloadURI: str | None = None


class PtabInterference(_BaseModel):
    """A PTAB interference decision."""

    interferenceNumber: str | None = None
    lastModifiedDateTime: str | None = None
    lastIngestionDateTime: str | None = None
    interferenceMetaData: PtabInterferenceMetaData | None = None
    seniorPartyData: PtabInterferencePartyData | None = None
    juniorPartyData: PtabInterferencePartyData | None = None
    additionalPartyDataBag: list[dict[str, Any]] | None = None
    decisionDocumentData: PtabInterferenceDocumentData | None = None
    documentData: PtabInterferenceDocumentData | None = None


class PtabInterferenceResponse(_BaseModel):
    """Response from PTAB interferences search."""

    count: int = 0
    requestIdentifier: str | None = None
    patentInterferenceDataBag: list[PtabInterference] = Field(default_factory=list)
    facets: list[dict[str, Any]] | None = None


__all__ = [
    # Base models
    "StrictModel",
    "FlexibleModel",
    # Strongly-typed application models
    "Address",
    "TelecommunicationAddress",
    "PersonName",
    "Inventor",
    "Applicant",
    "Attorney",
    "Assignor",
    "Assignee",
    "AssigneeAddress",
    "Assignment",
    "AssignmentResponse",
    "ParentContinuity",
    "ChildContinuity",
    "ContinuityBag",
    "ForeignPriority",
    "PatentTermAdjustmentHistory",
    "PatentTermAdjustmentData",
    "ApplicationEvent",
    "DocumentMetaData",
    "EntityStatusData",
    "CustomerNumberCorrespondenceData",
    "RecordAttorney",
    "ApplicationMetaData",
    "ApplicationRecord",
    "SearchResponse",
    "ApplicationResponse",
    "DocumentRecord",
    "DocumentsResponse",
    "FamilyNode",
    "FamilyEdge",
    "FamilyGraphResponse",
    # Bulk Data
    "BulkDataFile",
    "BulkDataProduct",
    "BulkDataProductResponse",
    "BulkDataSearchResponse",
    # Petition Decisions
    "PetitionDecisionFilter",
    "PetitionDecisionRange",
    "PetitionDecisionSort",
    "PetitionDecisionDocument",
    "PetitionDecision",
    "PetitionDecisionWithDocuments",
    "PetitionDecisionResponse",
    "PetitionDecisionIdentifierResponse",
    # PTAB Trials
    "PtabTrialMetaData",
    "PtabPatentOwnerData",
    "PtabPetitionerData",
    "PtabDerivationPetitionerData",
    "PtabDocumentData",
    "PtabDecisionData",
    "PtabTrialProceeding",
    "PtabTrialProceedingResponse",
    "PtabTrialDocument",
    "PtabTrialDocumentResponse",
    "PtabTrialDecision",
    "PtabTrialDecisionResponse",
    # PTAB Appeals
    "PtabAppealMetaData",
    "PtabAppealDecisionData",
    "PtabAppellantData",
    "PtabAppealRequestorData",
    "PtabAppealDocumentData",
    "PtabAppeal",
    "PtabAppealResponse",
    # PTAB Interferences
    "PtabInterferenceMetaData",
    "PtabInterferencePartyData",
    "PtabInterferenceDocumentData",
    "PtabInterference",
    "PtabInterferenceResponse",
]
