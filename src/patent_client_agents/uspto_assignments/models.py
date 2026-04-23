"""Pydantic models for USPTO Assignment Center API responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Assignor(BaseModel):
    """An assignor (party transferring rights) in an assignment."""

    assignor_name: str = Field(alias="assignorName")
    execution_date: str | None = Field(default=None, alias="executionDate")


class Property(BaseModel):
    """A patent property referenced in an assignment."""

    sequence_number: int | None = Field(default=None, alias="sequenceNumber")
    application_number: str | None = Field(default=None, alias="applicationNumber")
    filing_date: str | None = Field(default=None, alias="fillingDate")  # Note: API typo
    patent_number: str | None = Field(default=None, alias="patentNumber")
    publication_number: str | None = Field(default=None, alias="publicationNumber")
    publication_date: str | None = Field(default=None, alias="publicationDate")
    pct_number: str | None = Field(default=None, alias="pctNumber")
    international_registration_number: str | None = Field(
        default=None, alias="internationalRegistrationNumber"
    )
    international_publication_date: str | None = Field(
        default=None, alias="internationalPublicationDate"
    )
    invention_title: str | None = Field(default=None, alias="inventionTitle")
    inventors: str | None = None
    issue_date: str | None = Field(default=None, alias="issueDate")


class AssignmentRecord(BaseModel):
    """A single assignment record from the USPTO Assignment Center."""

    reel_number: int = Field(alias="reelNumber")
    frame_number: int = Field(alias="frameNumber")
    assignor_execution_date: str | None = Field(default=None, alias="assignorExecutionDate")
    correspondent_name: str | None = Field(default=None, alias="correspondentName")
    assignors: list[Assignor] = Field(default_factory=list)
    assignees: list[str] = Field(default_factory=list)
    conveyance_text: str | None = Field(default=None, alias="conveyanceText")
    number_of_properties: int = Field(default=0, alias="noOfProperties")
    properties: list[Property] = Field(default_factory=list)

    @property
    def reel_frame(self) -> str:
        """Return reel/frame as a formatted string."""
        return f"{self.reel_number}/{self.frame_number}"


class SearchCriterion(BaseModel):
    """A search criterion echoed back in the response."""

    property: str
    search_by: str = Field(alias="searchBy")


class AssignmentSearchResponse(BaseModel):
    """Response from the Assignment Center search API."""

    search_criteria: list[SearchCriterion] = Field(default_factory=list, alias="searchCriteria")
    data: list[AssignmentRecord] = Field(default_factory=list)

    @property
    def count(self) -> int:
        """Number of records in this response."""
        return len(self.data)


__all__ = [
    "Assignor",
    "Property",
    "AssignmentRecord",
    "SearchCriterion",
    "AssignmentSearchResponse",
]
