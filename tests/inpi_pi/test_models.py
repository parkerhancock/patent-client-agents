"""Tests for the Pydantic row models in :mod:`patent_client_agents.inpi_pi.models`.

Covers:

* Alias roundtrip — INPI PascalCase JSON → snake_case Python.
* ISO date parser edge cases (8-digit, ISO-8601, sentinels, garbage).
* Optional defaults preserved when the field is absent.
* ``extra="ignore"`` behavior — unknown elements don't raise.
* Empty-string string fields coerce to ``None``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pytest

from patent_client_agents.inpi_pi.models import (
    InpiDesignRow,
    InpiTrademarkRow,
    _empty_str_to_none,
    _parse_iso_date,
)

# ---------------------------------------------------------------------------
# _parse_iso_date
# ---------------------------------------------------------------------------


class TestParseIsoDate:
    @pytest.mark.parametrize("value", [None, "", "   ", "00000000"])
    def test_empty_or_sentinel(self, value: Any) -> None:
        assert _parse_iso_date(value) is None

    def test_iso_8601_string(self) -> None:
        assert _parse_iso_date("2024-03-15") == date(2024, 3, 15)

    def test_yyyymmdd_string(self) -> None:
        assert _parse_iso_date("20240315") == date(2024, 3, 15)

    def test_invalid_yyyymmdd_returns_none(self) -> None:
        # Month 99 → datetime.strptime raises → returns None
        assert _parse_iso_date("20249915") is None

    def test_random_string_returns_none(self) -> None:
        assert _parse_iso_date("hello") is None

    def test_passthrough_date(self) -> None:
        d = date(2024, 1, 1)
        assert _parse_iso_date(d) == d

    def test_datetime_truncates_to_date(self) -> None:
        dt = datetime(2024, 1, 1, 12, 30, 0)
        assert _parse_iso_date(dt) == date(2024, 1, 1)

    def test_non_string_returns_none(self) -> None:
        assert _parse_iso_date(12345) is None
        assert _parse_iso_date([]) is None


# ---------------------------------------------------------------------------
# _empty_str_to_none
# ---------------------------------------------------------------------------


class TestEmptyStrToNone:
    def test_empty_string(self) -> None:
        assert _empty_str_to_none("") is None

    def test_whitespace_only(self) -> None:
        assert _empty_str_to_none("   ") is None

    def test_non_empty_preserved(self) -> None:
        assert _empty_str_to_none("hello") == "hello"

    def test_non_string_passthrough(self) -> None:
        assert _empty_str_to_none(None) is None
        assert _empty_str_to_none(0) == 0
        assert _empty_str_to_none(["a"]) == ["a"]


# ---------------------------------------------------------------------------
# InpiTrademarkRow
# ---------------------------------------------------------------------------


class TestInpiTrademarkRow:
    def test_pascal_case_aliases_roundtrip(self) -> None:
        row = InpiTrademarkRow.model_validate(
            {
                "ApplicationNumber": "4216963",
                "Mark": "EXAMPLE",
                "ApplicationDate": "2015-09-01",
                "RegistrationNumber": "4216963",
                "RegistrationDate": "20160115",  # 8-digit form
                "MarkImageURI": "https://example.test/img",
                "KindMark": "Individual",
                "ClassNumber": ["9", "42"],
                "ViennaClass": ["03.07.17"],
                "ApplicantName": ["ACME SAS"],
                "HolderName": [],
                "RepresentativeName": "Cabinet Patent",
                "MarkCurrentStatusCode": "registered",
            }
        )
        assert row.application_number == "4216963"
        assert row.mark_text == "EXAMPLE"
        assert row.application_date == date(2015, 9, 1)
        assert row.registration_date == date(2016, 1, 15)
        assert row.nice_classes == ["9", "42"]
        assert row.applicant_names == ["ACME SAS"]
        assert row.agent_name == "Cabinet Patent"
        assert row.status == "registered"

    def test_minimal_payload_all_optional(self) -> None:
        row = InpiTrademarkRow()
        assert row.application_number is None
        assert row.mark_text is None
        assert row.nice_classes == []
        assert row.applicant_names == []
        assert row.priority_claims == []

    def test_extra_fields_ignored(self) -> None:
        row = InpiTrademarkRow.model_validate(
            {
                "ApplicationNumber": "X",
                "UnknownField": "ignored",
                "NewExperimentalField": [1, 2, 3],
            }
        )
        assert row.application_number == "X"
        # No attribute leak from extras
        assert not hasattr(row, "UnknownField")
        assert not hasattr(row, "NewExperimentalField")

    def test_empty_string_fields_become_none(self) -> None:
        row = InpiTrademarkRow.model_validate(
            {
                "ApplicationNumber": "",  # empty → None
                "Mark": "  ",  # whitespace → None
                "RepresentativeName": "",
                "MarkCurrentStatusCode": "",
            }
        )
        assert row.application_number is None
        assert row.mark_text is None
        assert row.agent_name is None
        assert row.status is None

    def test_sentinel_date_becomes_none(self) -> None:
        row = InpiTrademarkRow.model_validate(
            {
                "ApplicationNumber": "X",
                "ApplicationDate": "00000000",
                "ExpiryDate": "",
            }
        )
        assert row.application_date is None
        assert row.expiry_date is None

    def test_populate_by_name(self) -> None:
        """Python attribute name also accepted via populate_by_name=True."""
        row = InpiTrademarkRow.model_validate({"application_number": "ABC", "mark_text": "X"})
        assert row.application_number == "ABC"
        assert row.mark_text == "X"

    def test_priority_claims_passthrough(self) -> None:
        claims = [{"country": "US", "number": "12345", "date": "2014-01-01"}]
        row = InpiTrademarkRow.model_validate({"ApplicationNumber": "X", "PriorityDetails": claims})
        assert row.priority_claims == claims


# ---------------------------------------------------------------------------
# InpiDesignRow
# ---------------------------------------------------------------------------


class TestInpiDesignRow:
    def test_pascal_case_aliases_roundtrip(self) -> None:
        row = InpiDesignRow.model_validate(
            {
                "DesignApplicationNumber": "FR20140182",
                "DesignReference": "001",
                "DesignApplicationDate": "2014-05-20",
                "RegistrationNumber": "FR20140182",
                "RegistrationDate": "20140810",
                "ExpiryDate": "20240520",
                "DesignTitle": "Chaise pliante",
                "DesignRepresentationSheetURIs": [
                    "https://example.test/img/1",
                    "https://example.test/img/2",
                ],
                "ClassNumber": ["0601"],
                "ApplicantName": ["Mobilier France"],
                "DesignerName": ["Jean Designer"],
                "RepresentativeName": "Cabinet Design",
                "DesignCurrentStatusCode": "registered",
            }
        )
        assert row.application_number == "FR20140182"
        assert row.design_reference == "001"
        assert row.design_title == "Chaise pliante"
        assert row.image_urls == [
            "https://example.test/img/1",
            "https://example.test/img/2",
        ]
        assert row.loc_classes == ["0601"]
        assert row.designer_names == ["Jean Designer"]
        assert row.applicant_names == ["Mobilier France"]
        assert row.agent_name == "Cabinet Design"
        assert row.status == "registered"

    def test_minimal_payload_all_optional(self) -> None:
        row = InpiDesignRow()
        assert row.application_number is None
        assert row.design_reference is None
        assert row.image_urls == []
        assert row.loc_classes == []

    def test_extra_fields_ignored(self) -> None:
        row = InpiDesignRow.model_validate(
            {
                "DesignApplicationNumber": "X",
                "Unknown": "ignored",
            }
        )
        assert row.application_number == "X"

    def test_empty_strings_to_none(self) -> None:
        row = InpiDesignRow.model_validate(
            {
                "DesignApplicationNumber": "",
                "DesignTitle": "  ",
                "DesignReference": "",
                "DesignCurrentStatusCode": "",
            }
        )
        assert row.application_number is None
        assert row.design_title is None
        assert row.design_reference is None
        assert row.status is None

    def test_dates_xml_8digit_and_iso(self) -> None:
        row = InpiDesignRow.model_validate(
            {
                "DesignApplicationDate": "20140520",  # XML
                "RegistrationDate": "2014-08-10",  # JSON
                "ExpiryDate": "20240520",
                "PublicationDate": "",
            }
        )
        assert row.application_date == date(2014, 5, 20)
        assert row.registration_date == date(2014, 8, 10)
        assert row.expiry_date == date(2024, 5, 20)
        assert row.publication_date is None

    def test_populate_by_name(self) -> None:
        row = InpiDesignRow.model_validate({"application_number": "ABC", "design_title": "X"})
        assert row.application_number == "ABC"
        assert row.design_title == "X"

    def test_priority_claims_passthrough(self) -> None:
        claims = [{"country": "WO", "number": "123", "date": "2013-01-01", "holder_name": "X"}]
        row = InpiDesignRow.model_validate(
            {"DesignApplicationNumber": "X", "PriorityDetails": claims}
        )
        assert row.priority_claims == claims
