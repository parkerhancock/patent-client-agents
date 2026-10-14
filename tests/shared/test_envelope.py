"""Shared envelope helpers used by every MCP tool module."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import BaseModel, ConfigDict, Field

from patent_client_agents.shared.envelope import dump, dump_any


class _Record(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    serial_number: str = Field(alias="serialNumber")
    filed: date
    raw: dict | None = None


RECORD = _Record(serial_number="97123456", filed=date(2024, 1, 2), raw={"x": 1})


def test_dump_uses_field_names_and_python_values_by_default() -> None:
    assert dump(RECORD) == {
        "serial_number": "97123456",
        "filed": date(2024, 1, 2),
        "raw": {"x": 1},
    }


def test_dump_passes_model_dump_options_through() -> None:
    assert dump(RECORD, by_alias=True, mode="json", exclude={"raw"}) == {
        "serialNumber": "97123456",
        "filed": "2024-01-02",
    }


def test_dump_passes_dicts_through_and_rejects_other_types() -> None:
    assert dump({"k": 1}) == {"k": 1}
    with pytest.raises(TypeError, match="Pydantic model or dict"):
        dump(object())


def test_dump_any_maps_lists_and_passes_other_values_through() -> None:
    assert dump_any(None) is None
    assert dump_any([RECORD, "x"]) == [dump(RECORD), "x"]
    assert dump_any(3) == 3
