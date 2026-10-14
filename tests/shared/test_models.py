"""Shared Pydantic model pieces used by connector models."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from patent_client_agents.shared.models import (
    ApiModel,
    EmptyStrNone,
    IsoDate,
    IsoTimestampDate,
    YmdDate,
    empty_str_to_none,
    lenient_date,
    parse_iso_date,
    parse_iso_timestamp_date,
    parse_ymd_date,
)

D = date(2024, 3, 15)
UNPARSEABLE = [None, "", "   ", "bad", "2024", "2024-02-30", 12345, 1.5, [], [2024, 3, 15], {}]

# ---------------------------------------------------------------------------
# parse_iso_date
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["2024-03-15", " 2024-03-15 ", "20240315", "  20240315\n"])
def test_parse_iso_date_accepts_iso_and_compact(value: str) -> None:
    assert parse_iso_date(value) == D


@pytest.mark.parametrize("value", [*UNPARSEABLE, "00000000", "20240230", "abcdefgh", "15/03/2024"])
def test_parse_iso_date_returns_none_for_unreadable(value: Any) -> None:
    assert parse_iso_date(value) is None


def test_parse_iso_date_rejects_timestamps() -> None:
    assert parse_iso_date("2024-03-15T10:00:00") is None
    assert parse_iso_date("2024-03-15T10:00:00Z") is None


def test_parse_iso_date_passes_dates_and_truncates_datetimes() -> None:
    assert parse_iso_date(D) is D
    assert parse_iso_date(datetime(2024, 3, 15, 10, 5)) == D


# ---------------------------------------------------------------------------
# parse_iso_timestamp_date
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "2024-03-15",
        "20240315",
        " 2024-03-15 ",
        "2024-03-15T10:00:00",
        "2024-03-15T10:00:00Z",
        "2024-03-15T23:30:00-05:00",
        "2024-03-15 10:00:00",
    ],
)
def test_parse_iso_timestamp_date_accepts_dates_and_timestamps(value: str) -> None:
    assert parse_iso_timestamp_date(value) == D


def test_parse_iso_timestamp_date_keeps_written_date_without_tz_conversion() -> None:
    assert parse_iso_timestamp_date("2024-03-15T23:30:00-05:00") == D


@pytest.mark.parametrize("value", [*UNPARSEABLE, "00000000", "15/03/2024"])
def test_parse_iso_timestamp_date_returns_none_for_unreadable(value: Any) -> None:
    assert parse_iso_timestamp_date(value) is None


def test_parse_iso_timestamp_date_passes_dates_and_truncates_datetimes() -> None:
    assert parse_iso_timestamp_date(D) is D
    assert parse_iso_timestamp_date(datetime(2024, 3, 15, 10, 5, tzinfo=UTC)) == D


# ---------------------------------------------------------------------------
# lenient_date / parse_ymd_date
# ---------------------------------------------------------------------------


def test_lenient_date_tries_formats_in_order() -> None:
    day_first = lenient_date("%d/%m/%Y", "%m/%d/%Y")
    month_first = lenient_date("%m/%d/%Y", "%d/%m/%Y")
    assert day_first("01/02/2024") == date(2024, 2, 1)
    assert month_first("01/02/2024") == date(2024, 1, 2)


def test_lenient_date_strips_whitespace_and_rejects_other_formats() -> None:
    parse = lenient_date("%Y/%m/%d", "%Y-%m-%d")
    assert parse(" 2024/03/15 ") == D
    assert parse("2024-03-15") == D
    assert parse("20240315") is None
    assert parse("0/0/0") is None
    assert parse("0000/00/00") is None


@pytest.mark.parametrize("value", UNPARSEABLE)
def test_lenient_date_returns_none_for_unreadable(value: Any) -> None:
    assert lenient_date("%Y-%m-%d")(value) is None


def test_lenient_date_truncates_datetimes_by_default() -> None:
    assert lenient_date("%Y-%m-%d")(datetime(2024, 3, 15, 10, 5)) == D
    assert lenient_date("%Y-%m-%d")(D) is D


def test_lenient_date_keep_datetime_returns_datetime_unchanged() -> None:
    dt = datetime(2024, 3, 15, 10, 5)
    assert lenient_date("%Y-%m-%d", keep_datetime=True)(dt) is dt


def test_parse_ymd_date() -> None:
    assert parse_ymd_date("2024-03-15") == D
    assert parse_ymd_date("20240315") is None
    assert parse_ymd_date("2024/03/15") is None
    assert parse_ymd_date("2024-03-15T10:00:00") is None


# ---------------------------------------------------------------------------
# empty_str_to_none
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["", " ", "\t\n"])
def test_empty_str_to_none_blanks(value: str) -> None:
    assert empty_str_to_none(value) is None


@pytest.mark.parametrize("value", [None, "x", " x ", 0, ["a"], b""])
def test_empty_str_to_none_passes_everything_else(value: Any) -> None:
    assert empty_str_to_none(value) == value


# ---------------------------------------------------------------------------
# Annotated types on a model
# ---------------------------------------------------------------------------


class _Row(BaseModel):
    iso: IsoDate = None
    stamp: IsoTimestampDate = None
    ymd: YmdDate = None
    name: EmptyStrNone = None


def test_annotated_types_coerce_on_validation() -> None:
    row = _Row.model_validate(
        {"iso": "20240315", "stamp": "2024-03-15T10:00:00Z", "ymd": "2024-03-15", "name": "  "}
    )
    assert (row.iso, row.stamp, row.ymd, row.name) == (D, D, D, None)


def test_annotated_types_turn_unreadable_dates_into_none() -> None:
    row = _Row.model_validate({"iso": "00000000", "stamp": "bad", "ymd": "2024/03/15"})
    assert (row.iso, row.stamp, row.ymd) == (None, None, None)


def test_ymd_date_leaves_datetime_to_pydantic() -> None:
    assert _Row(ymd=datetime(2024, 3, 15)).ymd == D
    with pytest.raises(ValidationError):
        _Row(ymd=datetime(2024, 3, 15, 10, 5))


def test_ymd_date_accepts_midnight_aware_datetime() -> None:
    assert _Row(ymd=datetime(2024, 3, 15, tzinfo=timezone(timedelta(hours=5)))).ymd == D


def test_annotated_types_do_not_change_json_schema() -> None:
    class Plain(BaseModel):
        iso: date | None = None
        stamp: date | None = None
        ymd: date | None = None
        name: str | None = None

    schema = _Row.model_json_schema()
    plain = Plain.model_json_schema()
    assert schema["properties"] == plain["properties"]


# ---------------------------------------------------------------------------
# ApiModel
# ---------------------------------------------------------------------------


class _Camel(ApiModel):
    application_number: str | None = None
    t3_publication_date: str | None = None
    title: str | None = None
    odd_key: str | None = Field(default=None, alias="ODDKey")


def test_api_model_generates_camel_aliases() -> None:
    props = _Camel.model_json_schema(by_alias=True)["properties"]
    assert list(props) == ["applicationNumber", "t3PublicationDate", "title", "ODDKey"]


def test_api_model_accepts_alias_or_field_name() -> None:
    by_alias = _Camel.model_validate({"applicationNumber": "1", "ODDKey": "x"})
    by_name = _Camel(application_number="1", odd_key="x")
    assert by_alias == by_name
    assert by_alias.model_dump(by_alias=True, exclude_none=True) == {
        "applicationNumber": "1",
        "ODDKey": "x",
    }


def test_api_model_leaves_extra_to_subclass() -> None:
    class Strict(ApiModel):
        model_config = ConfigDict(extra="forbid")
        some_field: int = 0

    assert ApiModel.model_config.get("extra") is None
    with pytest.raises(ValidationError):
        Strict.model_validate({"someField": 1, "other": 2})
    assert Strict.model_validate({"someField": 1}).some_field == 1
