"""Parser tests for the Japan IP High Court workbook."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mcp_data_core.exceptions import NotFoundError, ParseError
from patent_client_agents.japan_ip_high_court import (
    find_case,
    normalize_case_number,
    parse_case_workbook,
)

PENDING_ROW = [
    "令和",
    7.0,
    "年（行ケ）第",
    10011.0,
    "号",
    "審決取消（特許）",
    "特願2022-700422",
    "知財高裁",
    "第２部",
    46309.0,
]
CLOSED_ROW = [
    45148.0,
    "令和",
    4.0,
    "年（行ケ）第",
    10108.0,
    "号",
    "審決取消（特許）",
    "特許6806401",
    "知財高裁",
    "第２部",
    "判決（請求棄却）",
    "無",
    "",
]


class _FakeSheet:
    def __init__(self, rows: list[list[object]]) -> None:
        self._rows = rows
        self.nrows = len(rows)

    def row_values(self, index: int) -> list[object]:
        return self._rows[index]

    def cell_value(self, row: int, column: int) -> object:
        return self._rows[row][column]


class _FakeBook:
    datemode = 0

    def __init__(self) -> None:
        blank_pending = [[""] * 10 for _ in range(3)]
        blank_pending[1][8] = 46248.0
        blank_closed = [[""] * 13 for _ in range(3)]
        blank_closed[1][11] = 46248.0
        self._sheets = {
            "係属中事件一覧表": _FakeSheet([*blank_pending, PENDING_ROW]),
            "終局事件一覧表": _FakeSheet([*blank_closed, CLOSED_ROW]),
        }

    def sheet_names(self) -> list[str]:
        return list(self._sheets)

    def sheet_by_name(self, name: str) -> _FakeSheet:
        return self._sheets[name]


def test_parse_both_workbook_sheets() -> None:
    with patch(
        "patent_client_agents.japan_ip_high_court.client.xlrd.open_workbook",
        return_value=_FakeBook(),
    ):
        result = parse_case_workbook(b"representative workbook")

    assert result.as_of_date.isoformat() == "2026-08-14"
    assert result.pending_count == 1
    assert result.closed_count == 1
    pending, closed = result.cases
    assert pending.case_number == "令和7年（行ケ）第10011号"
    assert pending.filing_year == 2025
    assert pending.case_type == "行ケ"
    assert pending.subject_identifier_type == "patent_application"
    assert pending.scheduled_judgment_date.isoformat() == "2026-10-14"
    assert closed.termination_date.isoformat() == "2023-08-10"
    assert closed.appeal_filed is False
    assert closed.disposition == "判決（請求棄却）"


def test_utility_model_identifier_is_classified() -> None:
    pending_row = [*PENDING_ROW]
    pending_row[6] = "実用新案3236826"
    book = _FakeBook()
    book._sheets["係属中事件一覧表"]._rows[3] = pending_row
    with patch(
        "patent_client_agents.japan_ip_high_court.client.xlrd.open_workbook",
        return_value=book,
    ):
        result = parse_case_workbook(b"representative workbook")

    assert result.cases[0].subject_identifier_type == "utility_model"


def test_case_lookup_normalizes_width_and_spaces() -> None:
    with patch(
        "patent_client_agents.japan_ip_high_court.client.xlrd.open_workbook",
        return_value=_FakeBook(),
    ):
        case_list = parse_case_workbook(b"representative workbook")

    assert normalize_case_number(" 令和7年 (行ケ) 第10011号 ") == normalize_case_number(
        "令和7年（行ケ）第10011号"
    )
    case = find_case(case_list, "令和7年 (行ケ) 第10011号", case_status="pending")
    assert case.serial_number == 10011


def test_case_lookup_honors_status() -> None:
    with patch(
        "patent_client_agents.japan_ip_high_court.client.xlrd.open_workbook",
        return_value=_FakeBook(),
    ):
        case_list = parse_case_workbook(b"representative workbook")

    with pytest.raises(NotFoundError):
        find_case(case_list, "令和7年（行ケ）第10011号", case_status="closed")


def test_parser_rejects_missing_sheet() -> None:
    book = _FakeBook()
    del book._sheets["終局事件一覧表"]
    with (
        patch(
            "patent_client_agents.japan_ip_high_court.client.xlrd.open_workbook",
            return_value=book,
        ),
        pytest.raises(ParseError, match="missing sheet"),
    ):
        parse_case_workbook(b"bad workbook")
