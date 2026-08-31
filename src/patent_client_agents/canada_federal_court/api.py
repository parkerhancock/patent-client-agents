"""MCP-free convenience API for the Canadian Federal Court connector."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator

from .client import CanadaFederalCourtClient
from .models import (
    CourtDivision,
    FederalCourtCaseRecord,
    FederalCourtCaseSearchResponse,
    FederalCourtDocketResponse,
)


class PartyCaseSearchInput(BaseModel):
    party_name: str = Field(min_length=2)
    division: CourtDivision = "t"
    filed_from: date | None = None
    filed_to: date | None = None
    patent_only: bool = True
    limit: int = Field(default=25, ge=1, le=100)

    @model_validator(mode="after")
    def _validate_dates(self) -> PartyCaseSearchInput:
        if (self.filed_from is None) != (self.filed_to is None):
            raise ValueError("filed_from and filed_to must be supplied together")
        if self.filed_from and self.filed_to and self.filed_from > self.filed_to:
            raise ValueError("filed_from must be on or before filed_to")
        return self


class CaseLookupInput(BaseModel):
    court_number: str = Field(min_length=3)
    division: CourtDivision = "t"


class DocketLookupInput(CaseLookupInput):
    limit: int = Field(default=100, ge=1, le=500)


async def search_party_cases(params: PartyCaseSearchInput) -> FederalCourtCaseSearchResponse:
    async with CanadaFederalCourtClient() as client:
        return await client.search_party_cases(**params.model_dump())


async def get_case(params: CaseLookupInput | str) -> FederalCourtCaseRecord:
    if isinstance(params, str):
        params = CaseLookupInput(court_number=params)
    async with CanadaFederalCourtClient() as client:
        return await client.get_case(**params.model_dump())


async def list_docket_entries(params: DocketLookupInput | str) -> FederalCourtDocketResponse:
    if isinstance(params, str):
        params = DocketLookupInput(court_number=params)
    async with CanadaFederalCourtClient() as client:
        return await client.list_docket_entries(**params.model_dump())


__all__ = [
    "CaseLookupInput",
    "DocketLookupInput",
    "PartyCaseSearchInput",
    "get_case",
    "list_docket_entries",
    "search_party_cases",
]
