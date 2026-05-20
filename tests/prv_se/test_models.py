"""Model-level tests for the PRV (Sweden) connector.

Validates each Pydantic model against the committed live-capture
fixtures and exercises the shared date validator.
"""

from __future__ import annotations

from datetime import date

import pytest

from patent_client_agents.prv_se.models import (
    DesignSearchResponse,
    PatentGetRecord,
    PatentSearchResponse,
    RegistryEntry,
    SpcSearchResponse,
    TrademarkSearchResponse,
    _parse_iso_date,
)

# ----------------------------------------------------------------------
# Date validator
# ----------------------------------------------------------------------


def test_parse_iso_date_valid() -> None:
    assert _parse_iso_date("2026-05-18") == date(2026, 5, 18)


def test_parse_iso_date_passthrough() -> None:
    today = date(2024, 1, 1)
    assert _parse_iso_date(today) is today


def test_parse_iso_date_none() -> None:
    assert _parse_iso_date(None) is None


def test_parse_iso_date_empty_string() -> None:
    assert _parse_iso_date("") is None
    assert _parse_iso_date("   ") is None


def test_parse_iso_date_malformed() -> None:
    assert _parse_iso_date("2026/05/18") is None
    assert _parse_iso_date("not-a-date") is None


def test_parse_iso_date_unsupported_type() -> None:
    assert _parse_iso_date(12345) is None


# ----------------------------------------------------------------------
# Patent search envelope + row
# ----------------------------------------------------------------------


def test_patent_search_envelope_parses(patents_search_payload: dict) -> None:
    result = PatentSearchResponse.model_validate(patents_search_payload)
    assert result.total_hits > 0
    assert result.total_pages >= 1
    assert result.hits == len(result.search_patent_dtos)
    assert result.page == 0


def test_patent_search_row_fields(patents_search_payload: dict) -> None:
    result = PatentSearchResponse.model_validate(patents_search_payload)
    row = result.search_patent_dtos[0]
    assert row.application_number_formatted
    assert row.application_type == "NAT"
    assert row.title
    assert isinstance(row.filing_date, date)
    assert row.applicants and row.applicants[0].name


# ----------------------------------------------------------------------
# Patent get record
# ----------------------------------------------------------------------


def test_patent_get_parses(patent_get_payload: dict) -> None:
    rec = PatentGetRecord.model_validate(patent_get_payload)
    assert rec.application_number_formatted == "SE2615555-6"
    assert rec.status_display_text_en == "Processing"
    assert rec.status_display_text_sv == "Under behandling"
    assert isinstance(rec.filing_date, date)
    assert rec.registry_entries_sv  # at least one timeline entry
    assert rec.publications and rec.publications[0].url


def test_patent_get_drawing_block(patent_get_payload: dict) -> None:
    rec = PatentGetRecord.model_validate(patent_get_payload)
    assert rec.first_drawing is not None
    assert rec.first_drawing.data is not None
    assert len(rec.first_drawing.data) > 1000  # base64 image


def test_registry_entry_date_alias() -> None:
    entry = RegistryEntry.model_validate({"date": "2026-05-06", "event": "x"})
    assert entry.entry_date == date(2026, 5, 6)
    # Round-trip with alias keeps the upstream "date" key.
    dumped = entry.model_dump(by_alias=True)
    assert dumped["date"] == date(2026, 5, 6)


# ----------------------------------------------------------------------
# Trademark search envelope + row
# ----------------------------------------------------------------------


def test_trademark_search_envelope_parses(tm_search_payload: dict) -> None:
    result = TrademarkSearchResponse.model_validate(tm_search_payload)
    assert result.total_hits > 0
    assert result.trademarks
    row = result.trademarks[0]
    assert row.application_number
    assert row.dossier_type_en == "National trademark"


# ----------------------------------------------------------------------
# Design search envelope + row
# ----------------------------------------------------------------------


def test_design_search_envelope_parses(design_search_payload: dict) -> None:
    result = DesignSearchResponse.model_validate(design_search_payload)
    assert result.total_hits > 0
    assert result.designs
    row = result.designs[0]
    assert row.application_number
    assert row.classes  # Locarno classifications


# ----------------------------------------------------------------------
# SPC search envelope + row
# ----------------------------------------------------------------------


def test_spc_search_envelope_parses(spc_search_payload: dict) -> None:
    result = SpcSearchResponse.model_validate(spc_search_payload)
    assert result.total_hits > 0
    assert result.search_spc_dtos
    row = result.search_spc_dtos[0]
    assert row.id_spc
    assert row.application_number_formatted  # base patent
    assert row.application_number_spc_formatted  # SPC application
    assert row.substance
    assert isinstance(row.valid_from_date, date)
    assert isinstance(row.valid_until_date, date)
    assert row.applicants and row.applicants[0].name


# ----------------------------------------------------------------------
# Forward-compat: unknown fields don't break validation
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "model_cls, base",
    [
        (
            PatentSearchResponse,
            {"totalHits": 1, "totalPages": 1, "hits": 0, "page": 0, "searchPatentDTOS": []},
        ),
        (
            TrademarkSearchResponse,
            {"totalHits": 1, "totalPages": 1, "hits": 0, "page": 0, "trademarks": []},
        ),
        (
            DesignSearchResponse,
            {"totalHits": 1, "totalPages": 1, "hits": 0, "page": 0, "designs": []},
        ),
        (
            SpcSearchResponse,
            {"totalHits": 1, "totalPages": 1, "hits": 0, "page": 0, "searchSpcDTOS": []},
        ),
    ],
)
def test_unknown_top_level_field_passes_through(model_cls, base) -> None:  # type: ignore[no-untyped-def]
    base["futureUpstreamField"] = ["whatever"]
    result = model_cls.model_validate(base)
    dumped = result.model_dump(by_alias=True)
    assert dumped["futureUpstreamField"] == ["whatever"]
