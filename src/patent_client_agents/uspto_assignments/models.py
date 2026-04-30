"""Pydantic models for USPTO Assignment Center API responses."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from pydantic import BaseModel, Field


class Assignor(BaseModel):
    """An assignor (party transferring rights) in an assignment."""

    assignor_name: str = Field(alias="assignorName")
    execution_date: str | None = Field(default=None, alias="executionDate")


class Property(BaseModel):
    """A patent property referenced in an assignment."""

    sequence_number: int | None = Field(default=None, alias="sequenceNumber")
    application_number: str | None = Field(default=None, alias="applicationNumber")
    filing_date: str | None = Field(default=None, alias="fillingDate")  # API typo
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
    """A single assignment recordation from the USPTO Assignment Center."""

    model_config = {"extra": "allow"}

    reel_number: int = Field(alias="reelNumber")
    frame_number: int = Field(alias="frameNumber")
    assignor_execution_date: str | None = Field(default=None, alias="assignorExecutionDate")
    correspondent_name: str | None = Field(default=None, alias="correspondentName")
    assignors: list[Assignor] = Field(default_factory=list)
    assignees: list[str] = Field(default_factory=list)
    conveyance: str | None = None
    conveyance_code: int | None = Field(default=None, alias="conveyanceCode")
    number_of_properties: int = Field(default=0, alias="noOfProperties")
    properties: list[Property] = Field(default_factory=list)

    @property
    def reel_frame(self) -> str:
        """Return reel/frame as a formatted string."""
        return f"{self.reel_number}/{self.frame_number}"


@dataclass
class SearchResults:
    """Result of :meth:`AssignmentCenterClient.search`.

    Behaves as a list of :class:`AssignmentRecord` for the common case
    (``for r in result``, ``len(result)``, ``result[0]``) while also exposing
    ``total`` and ``truncated`` so callers know whether the USPTO ~10k cap
    was hit.
    """

    records: list[AssignmentRecord] = field(default_factory=list)
    total: int = 0
    truncated: bool = False

    def __iter__(self) -> Iterator[AssignmentRecord]:
        return iter(self.records)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> AssignmentRecord:
        return self.records[index]

    def __bool__(self) -> bool:
        return bool(self.records)


__all__ = [
    "Assignor",
    "Property",
    "AssignmentRecord",
    "SearchResults",
]
