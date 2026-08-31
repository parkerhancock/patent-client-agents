"""Client for the Japan Intellectual Property High Court case workbook."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any, Literal

import httpx
import xlrd

from mcp_data_core import BaseAsyncClient
from mcp_data_core.exceptions import NotFoundError, ParseError

from .models import JapanIpHighCourtCase, JapanIpHighCourtCaseList

DEFAULT_BASE_URL = "https://www.courts.go.jp"
WORKBOOK_PATH = "/ip/vc-files/ip/jikenitiran.xls"
WORKBOOK_URL = f"{DEFAULT_BASE_URL}{WORKBOOK_PATH}"
PENDING_SHEET = "係属中事件一覧表"
CLOSED_SHEET = "終局事件一覧表"

_HEADERS = {
    "Accept": "application/vnd.ms-excel,application/octet-stream;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.7",
    "Referer": f"{DEFAULT_BASE_URL}/ip/",
    "User-Agent": "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)",
}
_ERA_START_YEAR = {"令和": 2018, "平成": 1988, "昭和": 1925}
_CASE_TYPE_RE = re.compile(r"年[（(]([^）)]+)[）)]第$")


def normalize_case_number(value: str) -> str:
    """Normalize spacing and width variants for exact case-number matching."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).casefold()


def _integer(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise ParseError(f"Unexpected boolean in {field}")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ParseError(f"Could not parse {field}: {value!r}") from exc
    if isinstance(value, float) and value != number:
        raise ParseError(f"Expected an integer in {field}: {value!r}")
    return number


def _excel_date(value: Any, *, datemode: int) -> date | None:
    if value in (None, ""):
        return None
    try:
        return xlrd.xldate_as_datetime(float(value), datemode).date()
    except (TypeError, ValueError, OverflowError, xlrd.XLDateError) as exc:
        raise ParseError(f"Could not parse workbook date: {value!r}") from exc


def _case_type(case_number_prefix: str) -> str:
    match = _CASE_TYPE_RE.search(case_number_prefix)
    return match.group(1) if match else case_number_prefix.strip()


def _filing_year(era_name: str, era_year: int) -> int | None:
    start = _ERA_START_YEAR.get(era_name)
    return start + era_year if start is not None else None


def _subject_identifier_type(value: str) -> str:
    if value.startswith("特許"):
        return "patent"
    if value.startswith("特願"):
        return "patent_application"
    if value.startswith(("実用新案登録", "実用新案")):
        return "utility_model"
    if value.startswith("実願"):
        return "utility_model_application"
    if value.startswith("異議"):
        return "patent_opposition"
    return "other"


def _case_fields(
    values: list[Any],
    *,
    offset: int,
) -> dict[str, Any]:
    era_name = str(values[offset]).strip()
    era_year = _integer(values[offset + 1], field="era year")
    prefix = str(values[offset + 2]).strip()
    serial_number = _integer(values[offset + 3], field="case serial number")
    suffix = str(values[offset + 4]).strip()
    case_number = f"{era_name}{era_year}{prefix}{serial_number}{suffix}"
    return {
        "case_number": case_number,
        "filing_year": _filing_year(era_name, era_year),
        "era_name": era_name,
        "era_year": era_year,
        "case_type": _case_type(prefix),
        "serial_number": serial_number,
    }


def _parse_pending_row(values: list[Any], *, datemode: int) -> JapanIpHighCourtCase:
    fields = _case_fields(values, offset=0)
    subject_identifier = str(values[6]).strip()
    return JapanIpHighCourtCase(
        case_status="pending",
        **fields,
        proceeding_type=str(values[5]).strip(),
        subject_identifier=subject_identifier,
        subject_identifier_type=_subject_identifier_type(subject_identifier),
        division=f"{values[7]}{values[8]}".strip(),
        scheduled_judgment_date=_excel_date(values[9], datemode=datemode),
    )


def _parse_closed_row(values: list[Any], *, datemode: int) -> JapanIpHighCourtCase:
    fields = _case_fields(values, offset=1)
    subject_identifier = str(values[7]).strip()
    appeal_text = str(values[11]).strip()
    return JapanIpHighCourtCase(
        case_status="closed",
        **fields,
        proceeding_type=str(values[6]).strip(),
        subject_identifier=subject_identifier,
        subject_identifier_type=_subject_identifier_type(subject_identifier),
        division=f"{values[8]}{values[9]}".strip(),
        termination_date=_excel_date(values[0], datemode=datemode),
        disposition=str(values[10]).strip() or None,
        appeal_filed={"有": True, "無": False}.get(appeal_text),
        appeal_result=str(values[12]).strip() or None,
    )


def parse_case_workbook(workbook_data: bytes) -> JapanIpHighCourtCaseList:
    """Parse both official workbook sheets into typed case records."""
    try:
        book = xlrd.open_workbook(file_contents=workbook_data)
    except (xlrd.XLRDError, ValueError, TypeError) as exc:
        raise ParseError("Could not open Japan IP High Court case workbook") from exc

    missing = {PENDING_SHEET, CLOSED_SHEET}.difference(book.sheet_names())
    if missing:
        raise ParseError(f"Japan IP High Court workbook is missing sheet(s): {sorted(missing)}")

    pending_sheet = book.sheet_by_name(PENDING_SHEET)
    closed_sheet = book.sheet_by_name(CLOSED_SHEET)
    pending: list[JapanIpHighCourtCase] = []
    closed: list[JapanIpHighCourtCase] = []

    for row_index in range(3, pending_sheet.nrows):
        values = pending_sheet.row_values(row_index)
        if len(values) >= 10 and isinstance(values[3], (int, float)):
            pending.append(_parse_pending_row(values, datemode=book.datemode))
    for row_index in range(3, closed_sheet.nrows):
        values = closed_sheet.row_values(row_index)
        if len(values) >= 13 and isinstance(values[4], (int, float)):
            closed.append(_parse_closed_row(values, datemode=book.datemode))

    as_of_dates = [
        value
        for value in (
            _excel_date(pending_sheet.cell_value(1, 8), datemode=book.datemode),
            _excel_date(closed_sheet.cell_value(1, 11), datemode=book.datemode),
        )
        if value is not None
    ]
    return JapanIpHighCourtCaseList(
        as_of_date=max(as_of_dates, default=None),
        pending_count=len(pending),
        closed_count=len(closed),
        cases=[*pending, *closed],
    )


def find_case(
    case_list: JapanIpHighCourtCaseList,
    case_number: str,
    *,
    case_status: Literal["pending", "closed", "all"] = "all",
) -> JapanIpHighCourtCase:
    """Find one normalized case number in a parsed workbook."""
    target = normalize_case_number(case_number)
    for case in case_list.cases:
        if case_status != "all" and case.case_status != case_status:
            continue
        if normalize_case_number(case.case_number) == target:
            return case
    raise NotFoundError(f"Japan IP High Court case not found: {case_number}")


class JapanIpHighCourtClient(BaseAsyncClient):
    """Read-only client for the weekly patent and utility-model case workbook."""

    DEFAULT_BASE_URL = DEFAULT_BASE_URL
    CACHE_NAME = "japan_ip_high_court"
    DEFAULT_TIMEOUT = 60.0

    def __init__(self, *, client: httpx.AsyncClient | None = None, **kwargs: Any) -> None:
        kwargs.setdefault("ttl_seconds", 21_600)
        super().__init__(client=client, headers=_HEADERS, **kwargs)
        if client is not None:
            client.headers.update(_HEADERS)

    async def list_cases(self) -> JapanIpHighCourtCaseList:
        response = await self._request(
            "GET",
            WORKBOOK_PATH,
            context="Japan IP High Court case workbook",
        )
        return parse_case_workbook(response.content)

    async def get_case(
        self,
        case_number: str,
        *,
        case_status: Literal["pending", "closed", "all"] = "all",
    ) -> JapanIpHighCourtCase:
        return find_case(await self.list_cases(), case_number, case_status=case_status)


__all__ = [
    "CLOSED_SHEET",
    "DEFAULT_BASE_URL",
    "PENDING_SHEET",
    "WORKBOOK_URL",
    "JapanIpHighCourtClient",
    "find_case",
    "normalize_case_number",
    "parse_case_workbook",
]
