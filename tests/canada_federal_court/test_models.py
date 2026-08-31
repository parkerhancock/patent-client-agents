from __future__ import annotations

from patent_client_agents.canada_federal_court.client import assess_docket_status
from patent_client_agents.canada_federal_court.models import FederalCourtDocketEntry


def _entry(summary: str, *, number: int = 1) -> FederalCourtDocketEntry:
    return FederalCourtDocketEntry.model_validate(
        {
            "COURT_NO": "T-1-26",
            "RE_NO": number,
            "RECORDED_ENTRY": summary,
            "CAN_PUBLISH_DOCUMENT": "N",
            "IS_CONFIDENTIAL": "N",
        }
    )


def test_status_is_likely_pending_only_for_explicit_prospective_language() -> None:
    status = assess_docket_status([_entry("Case management conference scheduled")])
    assert status.assessment == "likely_pending"
    assert "prospective phrase" in status.basis


def test_status_remains_unknown_for_ordinary_recent_activity() -> None:
    status = assess_docket_status([_entry("Defence filed")])
    assert status.assessment == "unknown"


def test_completed_case_management_conference_is_not_treated_as_pending() -> None:
    status = assess_docket_status([_entry("Case management conference held yesterday")])
    assert status.assessment == "unknown"


def test_status_is_never_described_as_official() -> None:
    status = assess_docket_status([])
    assert status.assessment == "unknown"
    assert "no official status field" in status.basis


def test_final_decision_is_treated_as_terminal_language() -> None:
    status = assess_docket_status([_entry("Final Decision entered")])
    assert status.assessment == "likely_closed"
