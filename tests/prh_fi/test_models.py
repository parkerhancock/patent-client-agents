"""Model-level tests for the PRH (Finland) connector."""

from __future__ import annotations

from datetime import date

import pytest

from patent_client_agents.prh_fi.models import (
    DossierSearchResponse,
    PatentGetRecord,
    PatentSearchResponse,
    TitleTranslation,
    _parse_iso_date,
)


def test_parse_iso_date_valid() -> None:
    assert _parse_iso_date("2026-05-19") == date(2026, 5, 19)


def test_parse_iso_date_passthrough() -> None:
    today = date(2024, 1, 1)
    assert _parse_iso_date(today) is today


def test_parse_iso_date_none_and_empty() -> None:
    assert _parse_iso_date(None) is None
    assert _parse_iso_date("") is None
    assert _parse_iso_date("   ") is None


def test_parse_iso_date_malformed() -> None:
    assert _parse_iso_date("not-a-date") is None
    assert _parse_iso_date("2026/05/19") is None


def test_title_translation_accepts_string_and_list() -> None:
    t1 = TitleTranslation.model_validate({"title": "Plain", "language": "EN"})
    assert t1.title == "Plain"
    t2 = TitleTranslation.model_validate({"title": ["Wrapped"], "language": "FI"})
    assert t2.title == ["Wrapped"]


# Patent search ----------------------------------------------------------


def test_patent_search_envelope_parses(patent_search_payload: dict) -> None:
    r = PatentSearchResponse.model_validate(patent_search_payload)
    assert r.total_results > 0
    assert r.results
    row = r.results[0]
    assert row.application_number
    assert row.dossier_type  # PatentDossier / UM / EP / Spc
    assert row.titles  # trilingual


# Patent GET -------------------------------------------------------------


def test_patent_get_parses(patent_get_payload: dict) -> None:
    rec = PatentGetRecord.model_validate(patent_get_payload)
    assert rec.application_number == "20100001"
    assert rec.examiner and rec.examiner.full_name
    assert rec.patent_title
    assert rec.priority_claims
    assert isinstance(rec.ipc_classifications, list)
    assert all(isinstance(c, str) for c in rec.ipc_classifications)


# Dossier (TM / TMR / Design) -------------------------------------------


def test_tm_search_envelope_parses(tm_search_payload: dict) -> None:
    r = DossierSearchResponse.model_validate(tm_search_payload)
    assert r.total_results > 0
    row = r.results[0]
    assert row.trademark_word
    assert row.dossier_id


def test_tmr_search_envelope_parses(tmr_search_payload: dict) -> None:
    r = DossierSearchResponse.model_validate(tmr_search_payload)
    assert r.total_results == len(r.results)
    # TMR rows carry a free-text targetGroup.
    assert any(row.target_group for row in r.results)


def test_design_search_envelope_parses(design_search_payload: dict) -> None:
    r = DossierSearchResponse.model_validate(design_search_payload)
    assert r.results
    row = r.results[0]
    assert row.locarnos  # Locarno classifications present
    assert row.designs  # at least one embodiment


# Forward-compat ---------------------------------------------------------


@pytest.mark.parametrize(
    "cls, base",
    [
        (PatentSearchResponse, {"totalResults": 0, "results": []}),
        (DossierSearchResponse, {"totalResults": 0, "results": []}),
    ],
)
def test_unknown_top_level_field_passes_through(cls, base) -> None:  # type: ignore[no-untyped-def]
    base["futureField"] = "new"
    obj = cls.model_validate(base)
    dumped = obj.model_dump(by_alias=True)
    assert dumped["futureField"] == "new"
