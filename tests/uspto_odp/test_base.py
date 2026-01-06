"""Tests for USPTO ODP base utilities and models."""

from datetime import date

import pytest
from pydantic import BaseModel

from ip_tools.uspto_odp.clients.base import (
    PaginationModel,
    SearchPayload,
    _format_bool,
    _format_csv,
    _format_date,
    _prune,
    _serialize_model_list,
)


class TestPrune:
    """Tests for _prune utility function."""

    def test_removes_none(self):
        """Test that None values are removed."""
        result = _prune({"a": 1, "b": None, "c": "test"})
        assert result == {"a": 1, "c": "test"}

    def test_removes_empty_string(self):
        """Test that empty strings are removed."""
        result = _prune({"a": 1, "b": "", "c": "test"})
        assert result == {"a": 1, "c": "test"}

    def test_removes_empty_list(self):
        """Test that empty lists are removed."""
        result = _prune({"a": 1, "b": [], "c": [1, 2]})
        assert result == {"a": 1, "c": [1, 2]}

    def test_removes_empty_dict(self):
        """Test that empty dicts are removed."""
        result = _prune({"a": 1, "b": {}, "c": {"d": 1}})
        assert result == {"a": 1, "c": {"d": 1}}

    def test_nested_pruning(self):
        """Test that nested structures are pruned."""
        result = _prune(
            {
                "a": {"b": None, "c": 1},
                "d": [None, 1, ""],
            }
        )
        assert result == {"a": {"c": 1}, "d": [1]}

    def test_preserves_zero(self):
        """Test that zero is preserved."""
        result = _prune({"a": 0, "b": None})
        assert result == {"a": 0}

    def test_preserves_false(self):
        """Test that False is preserved."""
        result = _prune({"a": False, "b": None})
        assert result == {"a": False}


class TestFormatCsv:
    """Tests for _format_csv utility function."""

    def test_none_input(self):
        """Test None returns None."""
        assert _format_csv(None) is None

    def test_string_input(self):
        """Test string passthrough."""
        assert _format_csv("test") == "test"

    def test_string_with_whitespace(self):
        """Test string whitespace is stripped."""
        assert _format_csv("  test  ") == "test"

    def test_empty_string(self):
        """Test empty string returns None."""
        assert _format_csv("") is None
        assert _format_csv("   ") is None

    def test_list_input(self):
        """Test list is joined with commas."""
        assert _format_csv(["a", "b", "c"]) == "a,b,c"

    def test_list_strips_whitespace(self):
        """Test list items are stripped."""
        assert _format_csv(["  a  ", "b", "  c"]) == "a,b,c"

    def test_empty_list(self):
        """Test empty list returns None."""
        assert _format_csv([]) is None

    def test_list_with_empty_items(self):
        """Test empty items are filtered."""
        assert _format_csv(["a", "", "b", "  ", "c"]) == "a,b,c"

    def test_tuple_input(self):
        """Test tuple is handled like list."""
        assert _format_csv(("x", "y")) == "x,y"


class TestFormatBool:
    """Tests for _format_bool utility function."""

    def test_none_input(self):
        """Test None returns None."""
        assert _format_bool(None) is None

    def test_true(self):
        """Test True returns 'true'."""
        assert _format_bool(True) == "true"

    def test_false(self):
        """Test False returns 'false'."""
        assert _format_bool(False) == "false"


class TestFormatDate:
    """Tests for _format_date utility function."""

    def test_none_input(self):
        """Test None returns None."""
        assert _format_date(None) is None

    def test_date_object(self):
        """Test date object is formatted."""
        d = date(2024, 3, 15)
        assert _format_date(d) == "2024-03-15"

    def test_string_input(self):
        """Test string passthrough."""
        assert _format_date("2024-03-15") == "2024-03-15"

    def test_string_whitespace(self):
        """Test string whitespace is stripped."""
        assert _format_date("  2024-03-15  ") == "2024-03-15"

    def test_empty_string(self):
        """Test empty string returns None."""
        assert _format_date("") is None
        assert _format_date("   ") is None


class TestSerializeModelList:
    """Tests for _serialize_model_list utility function."""

    def test_none_input(self):
        """Test None returns None."""
        assert _serialize_model_list(None) is None

    def test_empty_list(self):
        """Test empty list returns None."""
        assert _serialize_model_list([]) is None

    def test_dict_list(self):
        """Test list of dicts is serialized."""
        result = _serialize_model_list([{"a": 1}, {"b": 2}])
        assert result == [{"a": 1}, {"b": 2}]

    def test_dict_list_pruned(self):
        """Test dicts are pruned."""
        result = _serialize_model_list([{"a": 1, "b": None}])
        assert result == [{"a": 1}]

    def test_pydantic_model_list(self):
        """Test list of Pydantic models is serialized."""

        class TestModel(BaseModel):
            value: int
            optional: str | None = None

        result = _serialize_model_list([TestModel(value=1), TestModel(value=2)])
        assert result == [{"value": 1}, {"value": 2}]

    def test_invalid_type(self):
        """Test invalid type raises TypeError."""
        with pytest.raises(TypeError):
            _serialize_model_list([1, 2, 3])


class TestPaginationModel:
    """Tests for PaginationModel."""

    def test_defaults(self):
        """Test default values."""
        p = PaginationModel()
        assert p.offset == 0
        assert p.limit == 25

    def test_custom_values(self):
        """Test custom values."""
        p = PaginationModel(offset=100, limit=50)
        assert p.offset == 100
        assert p.limit == 50

    def test_offset_validation(self):
        """Test offset must be >= 0."""
        with pytest.raises(ValueError):
            PaginationModel(offset=-1)

    def test_limit_validation(self):
        """Test limit must be >= 1."""
        with pytest.raises(ValueError):
            PaginationModel(limit=0)


class TestSearchPayload:
    """Tests for SearchPayload model."""

    def test_minimal_payload(self):
        """Test minimal search payload."""
        payload = SearchPayload()
        assert payload.q is None
        assert payload.pagination.offset == 0

    def test_full_payload(self):
        """Test full search payload."""
        payload = SearchPayload(
            q="patent search query",
            fields=["applicationNumber", "title"],
            filters=["status:ACTIVE"],
            sort="filingDate:desc",
            pagination=PaginationModel(offset=50, limit=100),
        )
        assert payload.q == "patent search query"
        assert payload.fields == ["applicationNumber", "title"]
        assert payload.pagination.offset == 50

    def test_model_dump_pruned(self):
        """Test model_dump_pruned removes empty values."""
        payload = SearchPayload(q="test")
        result = payload.model_dump_pruned()

        # Should have q and pagination, but not fields/filters/etc
        assert result["q"] == "test"
        assert "pagination" in result
        assert "fields" not in result
        assert "filters" not in result

    def test_with_range_filters(self):
        """Test rangeFilters field."""
        payload = SearchPayload(rangeFilters=["date:[2020 TO 2024]"])
        assert payload.rangeFilters == ["date:[2020 TO 2024]"]
