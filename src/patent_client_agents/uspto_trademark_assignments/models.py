"""Pydantic models for USPTO Trademark Assignment Center API responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Assignor(BaseModel):
    """An assignor (party transferring rights) in an assignment."""

    assignor_name: str = Field(alias="assignorName")
    execution_date: str | None = Field(default=None, alias="executionDate")


class TrademarkProperty(BaseModel):
    """A trademark property referenced in an assignment."""

    sequence_number: int | None = Field(default=None, alias="sequenceNumber")
    serial_number: int | None = Field(default=None, alias="serialNumber")
    registration_number: int | None = Field(default=None, alias="registrationNumber")
    mark: str | None = None
    current_owner: str | None = Field(default=None, alias="currentOwner")
    registrant_name: str | None = Field(default=None, alias="registrantName")
    application_filing_date: str | None = Field(default=None, alias="applicationFilingDate")
    registration_date: str | None = Field(default=None, alias="registrationDate")
    international_registration_number: str | None = Field(
        default=None, alias="internationalRegistrationNumber"
    )


class TrademarkAssignmentRecord(BaseModel):
    """A single trademark assignment record from the USPTO Assignment Center."""

    reel_number: int = Field(alias="reelNumber")
    frame_number: str = Field(alias="frameNumber")
    assignor_execution_date: str | None = Field(default=None, alias="assignorExecutionDate")
    correspondent_name: str | None = Field(default=None, alias="correspondentName")
    domestic_representative: str | None = Field(default=None, alias="domesticRepresentative")
    assignors: list[Assignor] = Field(default_factory=list)
    assignees: list[str] = Field(default_factory=list)
    number_of_properties: int = Field(default=0, alias="noOfProperties")
    properties: list[TrademarkProperty] = Field(default_factory=list)

    @property
    def reel_frame(self) -> str:
        """Return reel/frame as a formatted string."""
        return f"{self.reel_number}/{self.frame_number}"


class SearchCriterion(BaseModel):
    """A search criterion echoed back in the response."""

    property: str
    search_by: str = Field(alias="searchBy")


class TrademarkAssignmentSearchResponse(BaseModel):
    """Response from the Trademark Assignment Center search API."""

    search_criteria: list[SearchCriterion] = Field(default_factory=list, alias="searchCriteria")
    data: list[TrademarkAssignmentRecord] = Field(default_factory=list)

    @property
    def count(self) -> int:
        """Number of records in this response."""
        return len(self.data)


__all__ = [
    "Assignor",
    "TrademarkProperty",
    "TrademarkAssignmentRecord",
    "SearchCriterion",
    "TrademarkAssignmentSearchResponse",
]
