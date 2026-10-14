"""Tests for Google Patents Pydantic models."""

from __future__ import annotations

from patent_client_agents.google_patents.client import (
    _resolve_expiration_date,
)


class TestResolveExpirationDate:
    """Tests for _resolve_expiration_date — priority+20y fallback when GP is empty."""

    def test_uses_gp_value_when_present(self) -> None:
        result, estimated = _resolve_expiration_date("2038-03-15", "2018-03-15")
        assert result == "2038-03-15"
        assert estimated is False

    def test_falls_back_to_priority_plus_20_when_gp_empty(self) -> None:
        result, estimated = _resolve_expiration_date("", "2013-03-15")
        assert result == "2033-03-15"
        assert estimated is True

    def test_returns_empty_when_neither_available(self) -> None:
        result, estimated = _resolve_expiration_date("", None)
        assert result == ""
        assert estimated is False

    def test_returns_empty_when_priority_unparseable(self) -> None:
        result, estimated = _resolve_expiration_date("", "not-a-date")
        assert result == ""
        assert estimated is False

    def test_handles_leap_day_priority_in_non_leap_target(self) -> None:
        # 1880-02-29 + 20y → 1900-02-29 doesn't exist (1900 is not a leap year),
        # so the helper clamps to Feb 28.
        result, estimated = _resolve_expiration_date("", "1880-02-29")
        assert result == "1900-02-28"
        assert estimated is True

    def test_priority_with_whitespace_is_stripped(self) -> None:
        result, estimated = _resolve_expiration_date("", "  2010-06-01  ")
        assert result == "2030-06-01"
        assert estimated is True

    def test_empty_priority_string_treated_as_missing(self) -> None:
        result, estimated = _resolve_expiration_date("", "")
        assert result == ""
        assert estimated is False
