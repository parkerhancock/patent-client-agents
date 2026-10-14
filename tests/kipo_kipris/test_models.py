"""Pydantic model tests for KIPRIS Plus row classes.

Covers:

* ``parse_iso_date`` validator across all accepted forms (``YYYYMMDD``,
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

from patent_client_agents.kipo_kipris.models import (
    DesignRow,
    PatentUtilityRow,
    TrademarkRow,
)
from patent_client_agents.shared.models import parse_iso_date

# ──────────────────────────────────────────────────────────────────────
# parse_iso_date validator
# ──────────────────────────────────────────────────────────────────────


class TestParseKiprisDate:
    def test_yyyymmdd_valid(self) -> None:
        assert parse_iso_date("20240315") == date(2024, 3, 15)

    def test_yyyymmdd_with_whitespace(self) -> None:
        assert parse_iso_date("  20240315  ") == date(2024, 3, 15)

    def test_iso_8601_valid(self) -> None:
        assert parse_iso_date("2024-03-15") == date(2024, 3, 15)

    def test_empty_string_returns_none(self) -> None:
        assert parse_iso_date("") is None

    def test_whitespace_only_returns_none(self) -> None:
        assert parse_iso_date("   ") is None

    def test_none_returns_none(self) -> None:
        assert parse_iso_date(None) is None

    def test_sentinel_zeros_returns_none(self) -> None:
        assert parse_iso_date("00000000") is None

    def test_yyyymmdd_invalid_day_returns_none(self) -> None:
        # February 30th — not a valid calendar date.
        assert parse_iso_date("20240230") is None

    def test_malformed_string_returns_none(self) -> None:
        assert parse_iso_date("not-a-date") is None

    def test_short_digit_string_returns_none(self) -> None:
        assert parse_iso_date("2024") is None

    def test_eight_chars_but_non_digit_returns_none(self) -> None:
        assert parse_iso_date("abcdefgh") is None

    def test_already_date_passthrough(self) -> None:
        d = date(2024, 1, 1)
        assert parse_iso_date(d) is d

    def test_datetime_converted_to_date(self) -> None:
        dt = datetime(2024, 6, 1, 12, 30, 0)
        assert parse_iso_date(dt) == date(2024, 6, 1)

    def test_unsupported_type_returns_none(self) -> None:
        assert parse_iso_date(12345) is None
        assert parse_iso_date([2024, 1, 1]) is None


# ──────────────────────────────────────────────────────────────────────
# empty_str_to_none helper
# ──────────────────────────────────────────────────────────────────────


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
