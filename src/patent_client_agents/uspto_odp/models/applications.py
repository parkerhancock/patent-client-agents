"""Strongly-typed models for USPTO ODP Patent Applications API."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .base import FlexibleModel, StrictModel

# =============================================================================
# Address Models
# =============================================================================


class Address(StrictModel):
    """A postal address."""

    nameLineOneText: str | None = None
    nameLineTwoText: str | None = None
    addressLineOneText: str | None = None
    addressLineTwoText: str | None = None
    cityName: str | None = None
    geographicRegionName: str | None = None
    geographicRegionCode: str | None = None
    postalCode: str | None = None
    countryCode: str | None = None
    countryName: str | None = None
    postalAddressCategory: str | None = None


class TelecommunicationAddress(StrictModel):
    """A phone/fax number."""

    telecommunicationNumber: str | None = None
    extensionNumber: str | None = None
    telecomTypeCode: str | None = None


# =============================================================================
# Person/Entity Models
# =============================================================================


class PersonName(StrictModel):
    """Common name fields for a person."""

    firstName: str | None = None
    middleName: str | None = None
    lastName: str | None = None
    namePrefix: str | None = None
    nameSuffix: str | None = None
    preferredName: str | None = None
    countryCode: str | None = None


class Inventor(PersonName):
    """An inventor on a patent application."""

    inventorNameText: str | None = None
    correspondenceAddressBag: list[Address] = Field(default_factory=list)


class Applicant(PersonName):
    """An applicant on a patent application."""

    applicantNameText: str | None = None
    correspondenceAddressBag: list[Address] = Field(default_factory=list)


class Attorney(PersonName):
    """An attorney or agent of record."""

    registrationNumber: str | None = None
    activeIndicator: str | None = None
    registeredPractitionerCategory: str | None = None
    attorneyAddressBag: list[Address] = Field(default_factory=list)
    telecommunicationAddressBag: list[TelecommunicationAddress] = Field(default_factory=list)


# =============================================================================
# Assignment Models
# =============================================================================


class Assignor(StrictModel):
    """An assignor in an assignment transaction."""

    assignorName: str | None = None
    executionDate: str | None = None


class AssigneeAddress(StrictModel):
    """Address for an assignee."""

    addressLineOneText: str | None = None
    addressLineTwoText: str | None = None
    cityName: str | None = None
    geographicRegionName: str | None = None
    geographicRegionCode: str | None = None
    countryName: str | None = None
    postalCode: str | None = None


class Assignee(StrictModel):
    """An assignee in an assignment transaction."""

    assigneeNameText: str | None = None
    assigneeAddress: AssigneeAddress | None = None


class Assignment(StrictModel):
    """An assignment record."""

    reelNumber: int | None = None
    frameNumber: int | None = None
    reelAndFrameNumber: str | None = None
    pageTotalQuantity: int | None = None
    assignmentDocumentLocationURI: str | None = None
    assignmentReceivedDate: str | None = None
    assignmentRecordedDate: str | None = None
    assignmentMailedDate: str | None = None
    conveyanceText: str | None = None
    assignorBag: list[Assignor] = Field(default_factory=list)
    assigneeBag: list[Assignee] = Field(default_factory=list)


class AssignmentResponse(StrictModel):
    """Response from the assignment endpoint."""

    applicationNumberText: str | None = None
    assignmentBag: list[Assignment] = Field(default_factory=list)
    requestIdentifier: str | None = None


# =============================================================================
# Continuity Models
# =============================================================================


class ParentContinuity(StrictModel):
    """A parent application in the continuity chain."""

    parentApplicationNumberText: str | None = None
    parentPatentNumber: str | None = None
    parentApplicationFilingDate: str | None = None
    parentApplicationStatusCode: int | None = None
    parentApplicationStatusDescriptionText: str | None = None
    childApplicationNumberText: str | None = None
    claimParentageTypeCode: str | None = None
    claimParentageTypeCodeDescriptionText: str | None = None
    firstInventorToFileIndicator: bool | None = None


class ChildContinuity(StrictModel):
    """A child application in the continuity chain."""

    childApplicationNumberText: str | None = None
    childPatentNumber: str | None = None
    childApplicationFilingDate: str | None = None
    childApplicationStatusCode: int | None = None
    childApplicationStatusDescriptionText: str | None = None
    parentApplicationNumberText: str | None = None
    claimParentageTypeCode: str | None = None
    claimParentageTypeCodeDescriptionText: str | None = None
    firstInventorToFileIndicator: bool | None = None


class ContinuityBag(StrictModel):
    """Container for parent and child continuity relationships."""

    parentContinuityBag: list[ParentContinuity] = Field(default_factory=list)
    childContinuityBag: list[ChildContinuity] = Field(default_factory=list)


# =============================================================================
# Foreign Priority Models
# =============================================================================


class ForeignPriority(StrictModel):
    """A foreign priority claim."""

    ipOfficeName: str | None = None
    filingDate: str | None = None
    applicationNumberText: str | None = None


# =============================================================================
# Patent Term Adjustment Models
# =============================================================================


class PatentTermAdjustmentHistory(StrictModel):
    """A single PTA history event."""

    eventDate: str | None = None
    eventDescriptionText: str | None = None
    eventSequenceNumber: int | None = None
    applicantDayDelayQuantity: int | None = None
    ipOfficeDayDelayQuantity: int | None = None
    originatingEventSequenceNumber: int | None = None
    ptaPTECode: str | None = None


class PatentTermAdjustmentData(StrictModel):
    """Patent term adjustment data."""

    aDelayQuantity: int | None = None
    bDelayQuantity: int | None = None
    cDelayQuantity: int | None = None
    overlappingDayQuantity: int | None = None
    nonOverlappingDayQuantity: int | None = None
    applicantDayDelayQuantity: int | None = None
    adjustmentTotalQuantity: int | None = None
    patentTermAdjustmentHistoryDataBag: list[PatentTermAdjustmentHistory] = Field(
        default_factory=list
    )


# =============================================================================
# Event/Transaction Models
# =============================================================================


class ApplicationEvent(StrictModel):
    """A prosecution event or transaction."""

    eventCode: str | None = None
    eventDescriptionText: str | None = None
    eventDate: str | None = None


# =============================================================================
# Document Metadata Models
# =============================================================================


class DocumentMetaData(StrictModel):
    """Metadata for a publication document (pgpub or grant)."""

    zipFileName: str | None = None
    xmlFileName: str | None = None
    productIdentifier: str | None = None
    fileLocationURI: str | None = None
    fileCreateDateTime: str | None = None


# =============================================================================
# Entity Status Models
# =============================================================================


class EntityStatusData(StrictModel):
    """Entity status information."""

    smallEntityStatusIndicator: bool | None = None
    businessEntityStatusCategory: str | None = None


# =============================================================================
# Attorney of Record Models
# =============================================================================


class CustomerNumberCorrespondenceData(StrictModel):
    """Customer number correspondence data."""

    patronIdentifier: int | None = None
    organizationStandardName: str | None = None
    powerOfAttorneyAddressBag: list[Address] = Field(default_factory=list)
    telecommunicationAddressBag: list[TelecommunicationAddress] = Field(default_factory=list)


class RecordAttorney(StrictModel):
    """Attorney of record information."""

    customerNumberCorrespondenceData: list[CustomerNumberCorrespondenceData] = Field(
        default_factory=list
    )
    powerOfAttorneyBag: list[Attorney] = Field(default_factory=list)
    attorneyBag: list[Attorney] = Field(default_factory=list)


# =============================================================================
# Application Metadata Model
# =============================================================================


class ApplicationMetaData(StrictModel):
    """Nested metadata for a patent application."""

    # Status and identification
    applicationStatusCode: int | None = None
    applicationStatusDescriptionText: str | None = None
    applicationStatusDate: str | None = None
    applicationConfirmationNumber: int | None = None

    # Dates
    filingDate: str | None = None
    effectiveFilingDate: str | None = None
    grantDate: str | None = None

    # Application type
    applicationTypeCode: str | None = None
    applicationTypeLabelName: str | None = None
    applicationTypeCategory: str | None = None

    # Title and patent number
    inventionTitle: str | None = None
    patentNumber: str | None = None

    # Classification
    groupArtUnitNumber: str | None = None
    uspcSymbolText: str | None = None
    cpcClassificationBag: list[str] = Field(default_factory=list, alias="class")

    # Examiner
    examinerNameText: str | None = None
    customerNumber: int | None = None

    # Names
    firstApplicantName: str | None = None
    firstInventorName: str | None = None
    docketNumber: str | None = None

    # Flags
    nationalStageIndicator: bool | None = None
    firstInventorToFileIndicator: str | None = None

    # Publications
    earliestPublicationNumber: str | None = None
    earliestPublicationDate: str | None = None
    publicationDateBag: list[str] = Field(default_factory=list)
    publicationSequenceNumberBag: list[str] = Field(default_factory=list)
    publicationCategoryBag: list[str] = Field(default_factory=list)

    # PCT
    pctPublicationNumber: str | None = None
    pctPublicationDate: str | None = None

    # International registration
    internationalRegistrationNumber: str | None = None
    internationalRegistrationPublicationDate: str | None = None

    # Entity status (nested)
    entityStatusData: EntityStatusData | None = None

    # People
    inventorBag: list[Inventor] = Field(default_factory=list)
    applicantBag: list[Applicant] = Field(default_factory=list)

    # CPC classifications (alternative field name)
    cpcClassificationBag_: list[str] = Field(default_factory=list, alias="cpcClassificationBag")


# =============================================================================
# Main Application Record Model
# =============================================================================


class ApplicationRecord(FlexibleModel):
    """A patent application record from USPTO ODP.

    This model uses FlexibleModel to allow unknown fields to pass through,
    ensuring backward compatibility while providing typed access to known fields.

    After _merge_application_metadata is applied, metadata fields are flattened
    to the top level, so we include them here as well.
    """

    # Primary identifier
    applicationNumberText: str | None = None

    # Nested metadata (before flattening)
    applicationMetaData: ApplicationMetaData | None = None

    # Flattened metadata fields (after _merge_application_metadata)
    applicationStatusCode: int | None = None
    applicationStatusDescriptionText: str | None = None
    applicationStatusDate: str | None = None
    filingDate: str | None = None
    effectiveFilingDate: str | None = None
    grantDate: str | None = None
    applicationTypeCode: str | None = None
    applicationTypeLabelName: str | None = None
    applicationTypeCategory: str | None = None
    inventionTitle: str | None = None
    patentNumber: str | None = None
    groupArtUnitNumber: str | None = None
    examinerNameText: str | None = None
    customerNumber: int | None = None
    firstApplicantName: str | None = None
    firstInventorName: str | None = None
    docketNumber: str | None = None
    nationalStageIndicator: bool | None = None
    firstInventorToFileIndicator: str | None = None
    smallEntityStatusIndicator: bool | None = None
    businessEntityStatusCategory: str | None = None

    # Continuity (can be nested or at top level after flattening)
    continuityBag: ContinuityBag | None = None
    parentContinuityBag: list[ParentContinuity] = Field(default_factory=list)
    childContinuityBag: list[ChildContinuity] = Field(default_factory=list)

    # Other relationships
    foreignPriorityBag: list[ForeignPriority] = Field(default_factory=list)
    assignmentBag: list[Assignment] = Field(default_factory=list)
    correspondenceAddressBag: list[Address] = Field(default_factory=list)

    # Attorney of record
    recordAttorney: RecordAttorney | None = None

    # Patent term adjustment
    patentTermAdjustmentData: PatentTermAdjustmentData | None = None

    # Events
    eventDataBag: list[ApplicationEvent] = Field(default_factory=list)

    # Document metadata
    pgpubDocumentMetaData: DocumentMetaData | None = None
    grantDocumentMetaData: DocumentMetaData | None = None

    # Ingestion timestamp
    lastIngestionDateTime: str | None = None


# =============================================================================
# Response Models
# =============================================================================


class SearchResponse(FlexibleModel):
    """Response from patent application search.

    Note: patentBag contains dict[str, Any] for backward compatibility.
    Use patentRecords for typed access to ApplicationRecord objects.
    """

    count: int = 0
    patentBag: list[dict[str, Any]] = Field(default_factory=list)
    requestIdentifier: str | None = None

    @property
    def patentRecords(self) -> list[ApplicationRecord]:
        """Get typed ApplicationRecord objects from patentBag."""
        return [ApplicationRecord.model_validate(item) for item in self.patentBag]


class ApplicationResponse(SearchResponse):
    """Response from single application lookup."""

    pass


# =============================================================================
# Document Models
# =============================================================================


class DocumentRecord(FlexibleModel):
    """A file wrapper document record."""

    documentIdentifier: str | None = None
    documentCode: str | None = None
    documentCodeDescriptionText: str | None = None
    documentDate: str | None = None
    pageCount: int | None = None
    mailRoomDate: str | None = None
    directionCategory: str | None = None
    documentCategoryCode: str | None = None
    downloadOptionBag: list[dict[str, Any]] | None = None


class DocumentsResponse(FlexibleModel):
    """Response from documents endpoint."""

    documents: list[DocumentRecord] = Field(default_factory=list)
    associatedDocuments: list[dict[str, Any]] | None = None


# =============================================================================
# Family Graph Models
# =============================================================================


class FamilyNode(StrictModel):
    """A node in the patent family graph."""

    applicationNumber: str
    dataSource: str = Field(default="unknown")
    patentNumber: str | None = None
    filingDate: str | None = None
    grantDate: str | None = None
    statusCode: int | None = None
    statusText: str | None = None
    title: str | None = None


class FamilyEdge(StrictModel):
    """An edge in the patent family graph."""

    fromApplication: str
    toApplication: str
    relationshipCode: str | None = None
    relationshipDescription: str | None = None
    parentFilingDate: str | None = None
    childFilingDate: str | None = None
    parentPatentNumber: str | None = None
    childPatentNumber: str | None = None


class FamilyGraphResponse(StrictModel):
    """Response from family graph endpoint."""

    rootApplication: str
    nodes: list[FamilyNode] = Field(default_factory=list)
    edges: list[FamilyEdge] = Field(default_factory=list)
    missingApplications: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    # Address/Contact
    "Address",
    "TelecommunicationAddress",
    # People
    "PersonName",
    "Inventor",
    "Applicant",
    "Attorney",
    # Assignments
    "Assignor",
    "Assignee",
    "AssigneeAddress",
    "Assignment",
    # Continuity
    "ParentContinuity",
    "ChildContinuity",
    "ContinuityBag",
    # Other
    "ForeignPriority",
    "PatentTermAdjustmentHistory",
    "PatentTermAdjustmentData",
    "ApplicationEvent",
    "DocumentMetaData",
    "EntityStatusData",
    "CustomerNumberCorrespondenceData",
    "RecordAttorney",
    "ApplicationMetaData",
    # Main models
    "ApplicationRecord",
    "SearchResponse",
    "ApplicationResponse",
    "DocumentRecord",
    "DocumentsResponse",
    "FamilyNode",
    "FamilyEdge",
    "FamilyGraphResponse",
]
