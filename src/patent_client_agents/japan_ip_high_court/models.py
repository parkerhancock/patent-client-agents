"""Models for the Japan Intellectual Property High Court case lists."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel


class JapanIpHighCourtCase(BaseModel):
    """One case in the court's pending or closed patent and utility-model workbook."""

    case_status: Literal["pending", "closed"]
    case_number: str
    filing_year: int | None = None
    era_name: str
    era_year: int
    case_type: str
    serial_number: int
    proceeding_type: str
    subject_identifier: str
    subject_identifier_type: str
    division: str
    scheduled_judgment_date: date | None = None
    termination_date: date | None = None
    disposition: str | None = None
    appeal_filed: bool | None = None
    appeal_result: str | None = None


class JapanIpHighCourtCaseList(BaseModel):
    """Normalized contents of the court's weekly workbook."""

    as_of_date: date | None = None
    pending_count: int
    closed_count: int
    cases: list[JapanIpHighCourtCase]


__all__ = ["JapanIpHighCourtCase", "JapanIpHighCourtCaseList"]
