"""Pydantic model tests for KIPRIS Plus row classes.

Covers:

* ``_parse_kipris_date`` validator across all accepted forms (``YYYYMMDD``,
  ``YYYY-MM-DD``, sentinel ``"00000000"``, empty/None, ``date``/``datetime``,
  unsupported types).
* Alias round-trip: camelCase XML keys deserialize into snake_case
  attributes; ``model_dump(by_alias=True)`` reconstructs the XML shape.
* Empty-string coercion: ``<applicantName></applicantName>`` → ``None``
  via the ``_coerce_empty`` validator.
* Optional-field defaults: every field defaults to ``None`` so a minimal
  ``{}`` dict validates.
* ``extra="ignore"`` swallows unknown XML elements (forward-compat).
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from patent_client_agents.kipo_kipris.models import (
    DesignRow,
    PatentUtilityRow,
    TrademarkRow,
    _empty_str_to_none,
    _parse_kipris_date,
)

# ──────────────────────────────────────────────────────────────────────
# _parse_kipris_date validator
# ──────────────────────────────────────────────────────────────────────


class TestParseKiprisDate:
    def test_yyyymmdd_valid(self) -> None:
        assert _parse_kipris_date("20240315") == date(2024, 3, 15)

    def test_yyyymmdd_with_whitespace(self) -> None:
        assert _parse_kipris_date("  20240315  ") == date(2024, 3, 15)

    def test_iso_8601_valid(self) -> None:
        assert _parse_kipris_date("2024-03-15") == date(2024, 3, 15)

    def test_empty_string_returns_none(self) -> None:
        assert _parse_kipris_date("") is None

    def test_whitespace_only_returns_none(self) -> None:
        assert _parse_kipris_date("   ") is None

    def test_none_returns_none(self) -> None:
        assert _parse_kipris_date(None) is None

    def test_sentinel_zeros_returns_none(self) -> None:
        assert _parse_kipris_date("00000000") is None

    def test_yyyymmdd_invalid_day_returns_none(self) -> None:
        # February 30th — not a valid calendar date.
        assert _parse_kipris_date("20240230") is None

    def test_malformed_string_returns_none(self) -> None:
        assert _parse_kipris_date("not-a-date") is None

    def test_short_digit_string_returns_none(self) -> None:
        assert _parse_kipris_date("2024") is None

    def test_eight_chars_but_non_digit_returns_none(self) -> None:
        assert _parse_kipris_date("abcdefgh") is None

    def test_already_date_passthrough(self) -> None:
        d = date(2024, 1, 1)
        assert _parse_kipris_date(d) is d

    def test_datetime_converted_to_date(self) -> None:
        dt = datetime(2024, 6, 1, 12, 30, 0)
        assert _parse_kipris_date(dt) == date(2024, 6, 1)

    def test_unsupported_type_returns_none(self) -> None:
        assert _parse_kipris_date(12345) is None
        assert _parse_kipris_date([2024, 1, 1]) is None


# ──────────────────────────────────────────────────────────────────────
# _empty_str_to_none helper
# ──────────────────────────────────────────────────────────────────────


class TestEmptyStrToNone:
    def test_empty_string(self) -> None:
        assert _empty_str_to_none("") is None

    def test_whitespace_only(self) -> None:
        assert _empty_str_to_none("   ") is None

    def test_non_empty_passthrough(self) -> None:
        assert _empty_str_to_none("hello") == "hello"

    def test_none_passthrough(self) -> None:
        assert _empty_str_to_none(None) is None

    def test_non_string_passthrough(self) -> None:
        # Non-string values are returned as-is.
        assert _empty_str_to_none(42) == 42


# ──────────────────────────────────────────────────────────────────────
# PatentUtilityRow
# ──────────────────────────────────────────────────────────────────────


class TestPatentUtilityRow:
    def test_alias_roundtrip(self) -> None:
        raw = {
            "applicationNumber": "1020230012345",
            "applicationDate": "20230105",
            "publicationNumber": "1024567890000",
            "publicationDate": "20240310",
            "openNumber": "1020230112345",
            "openDate": "20230715",
            "registerNumber": "1024567890000",
            "registerDate": "20240310",
            "registerStatus": "등록",
            "inventionTitle": "리튬 이온 배터리 모듈",
            "inventionTitleEnglish": "Lithium Ion Battery Module",
            "astrtCont": "본 발명은 ...",
            "applicantName": "삼성전자",
            "inventorName": "홍길동;김철수",
            "agentName": "특허법인 명륜",
            "ipcNumber": "H01M 10/0525",
        }
        row = PatentUtilityRow.model_validate(raw)
        assert row.application_number == "1020230012345"
        assert row.application_date == date(2023, 1, 5)
        assert row.publication_date == date(2024, 3, 10)
        assert row.register_status == "등록"
        assert row.invention_title_english == "Lithium Ion Battery Module"
        # by_alias round-trips back to camelCase
        dumped = row.model_dump(by_alias=True)
        assert dumped["applicationNumber"] == "1020230012345"
        assert dumped["inventionTitleEnglish"] == "Lithium Ion Battery Module"

    def test_empty_strings_become_none(self) -> None:
        raw = {
            "applicationNumber": "1020230098765",
            "registerNumber": "",
            "applicantName": "   ",
            "agentName": "",
        }
        row = PatentUtilityRow.model_validate(raw)
        assert row.application_number == "1020230098765"
        assert row.register_number is None
        assert row.applicant_name is None
        assert row.agent_name is None

    def test_all_optional_defaults(self) -> None:
        row = PatentUtilityRow.model_validate({})
        assert row.application_number is None
        assert row.application_date is None
        assert row.invention_title is None
        assert row.applicant_name is None
        assert row.ipc_number is None

    def test_extra_fields_ignored(self) -> None:
        raw = {
            "applicationNumber": "X",
            "unknownFutureField": "ignored",
            "anotherUnknown": 42,
        }
        # Must not raise.
        row = PatentUtilityRow.model_validate(raw)
        assert row.application_number == "X"

    def test_sentinel_date_zeroed(self) -> None:
        row = PatentUtilityRow.model_validate(
            {"applicationDate": "00000000", "publicationDate": ""}
        )
        assert row.application_date is None
        assert row.publication_date is None

    def test_snake_case_keys_work_via_populate_by_name(self) -> None:
        row = PatentUtilityRow.model_validate(
            {
                "application_number": "from-snake",
                "invention_title": "snake-title",
            }
        )
        assert row.application_number == "from-snake"
        assert row.invention_title == "snake-title"


# ──────────────────────────────────────────────────────────────────────
# TrademarkRow
# ──────────────────────────────────────────────────────────────────────


class TestTrademarkRow:
    def test_alias_roundtrip(self) -> None:
        raw = {
            "applicationNumber": "4020230123456",
            "applicationDate": "20230320",
            "registrationNumber": "4000123456",
            "registrationDate": "20240401",
            "registrationPublicNumber": "4000123456-0000",
            "title": "GALAXY",
            "bigDrawing": "https://example.test/big.gif",
            "classificationCode": "09;42",
            "viennaCode": "26.04.01",
            "applicantName": "삼성전자주식회사",
            "agentName": "특허법인 광장",
            "regPrivilegeName": "삼성전자주식회사",
        }
        row = TrademarkRow.model_validate(raw)
        assert row.application_number == "4020230123456"
        assert row.application_date == date(2023, 3, 20)
        assert row.title == "GALAXY"
        assert row.big_drawing == "https://example.test/big.gif"
        assert row.classification_code == "09;42"
        assert row.reg_privilege_name == "삼성전자주식회사"
        dumped = row.model_dump(by_alias=True)
        assert dumped["bigDrawing"] == "https://example.test/big.gif"
        assert dumped["regPrivilegeName"] == "삼성전자주식회사"

    def test_unregistered_mark_has_empty_dates(self) -> None:
        row = TrademarkRow.model_validate(
            {
                "applicationNumber": "4020230654321",
                "applicationDate": "20230815",
                "registrationNumber": "",
                "registrationDate": "",
                "title": "GRAM",
            }
        )
        assert row.registration_number is None
        assert row.registration_date is None

    def test_all_optional_defaults(self) -> None:
        row = TrademarkRow.model_validate({})
        assert row.application_number is None
        assert row.title is None
        assert row.big_drawing is None


# ──────────────────────────────────────────────────────────────────────
# DesignRow
# ──────────────────────────────────────────────────────────────────────


class TestDesignRow:
    def test_alias_roundtrip(self) -> None:
        raw = {
            "applicationNumber": "3020230012345",
            "applicationDate": "20230210",
            "registrationNumber": "3000987654",
            "registrationDate": "20240120",
            "registerStatus": "등록",
            "articleName": "휴대용 전화기",
            "drawing": "https://example.test/drawing.jpg",
            "locCode": "14-03",
            "applicantName": "삼성전자주식회사",
            "inventorName": "박디자인",
            "agentName": "특허법인 명륜",
        }
        row = DesignRow.model_validate(raw)
        assert row.application_number == "3020230012345"
        assert row.application_date == date(2023, 2, 10)
        assert row.article_name == "휴대용 전화기"
        assert row.loc_code == "14-03"
        assert row.inventor_name == "박디자인"
        dumped = row.model_dump(by_alias=True)
        assert dumped["articleName"] == "휴대용 전화기"
        assert dumped["locCode"] == "14-03"

    def test_all_optional_defaults(self) -> None:
        row = DesignRow.model_validate({})
        assert row.application_number is None
        assert row.article_name is None
        assert row.drawing is None

    def test_iso_date_form_accepted(self) -> None:
        row = DesignRow.model_validate(
            {"applicationDate": "2023-02-10", "registrationDate": "2024-01-20"}
        )
        assert row.application_date == date(2023, 2, 10)
        assert row.registration_date == date(2024, 1, 20)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("20240101", date(2024, 1, 1)),
        ("2024-01-01", date(2024, 1, 1)),
        ("", None),
        (None, None),
        ("00000000", None),
        ("bad", None),
    ],
)
def test_date_validator_parametrized(raw: str | None, expected: date | None) -> None:
    """Cross-row spot check of the date validator on PatentUtilityRow."""
    row = PatentUtilityRow.model_validate({"applicationDate": raw})
    assert row.application_date == expected


# ──────────────────────────────────────────────────────────────────────
# resources.py usage-resource stub
# ──────────────────────────────────────────────────────────────────────


def test_usage_resource_uri_and_body() -> None:
    """The chunk-2 stub resource exposes URI + body for downstream MCP wiring."""
    from patent_client_agents.kipo_kipris.resources import (
        USAGE_RESOURCE_URI,
        get_usage_resource,
    )

    assert USAGE_RESOURCE_URI == "pca://kipo_kipris/usage"
    body = get_usage_resource()
    assert isinstance(body, str)
    assert "KIPRIS" in body
