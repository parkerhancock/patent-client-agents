"""Tests for USPTO ODP base utilities."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import BaseModel

from law_tools_core.exceptions import ConfigurationError
from patent_client_agents.uspto_odp.clients.base import (
    BASE_URL,
    PaginationModel,
    SearchPayload,
    UsptoOdpBaseClient,
    _format_bool,
    _format_csv,
    _format_date,
    _prune,
    _serialize_model_list,
)
from patent_client_agents.uspto_odp.models import OdpFilter, OdpRangeFilter, OdpSort


class TestBaseUrl:
    """Tests for BASE_URL constant."""

    def test_is_https(self) -> None:
        assert BASE_URL.startswith("https://")

    def test_is_uspto_domain(self) -> None:
        assert "api.uspto.gov" in BASE_URL


class TestPrune:
    """Tests for _prune function."""

    def test_removes_none(self) -> None:
        result = _prune({"a": 1, "b": None, "c": 3})
        assert result == {"a": 1, "c": 3}

    def test_removes_empty_string(self) -> None:
        result = _prune({"a": "value", "b": "", "c": "other"})
        assert result == {"a": "value", "c": "other"}

    def test_removes_empty_list(self) -> None:
        result = _prune({"a": [1, 2], "b": [], "c": "value"})
        assert result == {"a": [1, 2], "c": "value"}

    def test_removes_empty_dict(self) -> None:
        result = _prune({"a": {"x": 1}, "b": {}, "c": "value"})
        assert result == {"a": {"x": 1}, "c": "value"}

    def test_nested_pruning(self) -> None:
        result = _prune({"a": {"x": None, "y": 1}, "b": [None, 2]})
        assert result == {"a": {"y": 1}, "b": [2]}

    def test_preserves_non_empty(self) -> None:
        data = {"a": 1, "b": "text", "c": [1, 2], "d": {"x": "y"}}
        result = _prune(data)
        assert result == data

    def test_handles_deeply_nested(self) -> None:
        result = _prune({"a": {"b": {"c": None, "d": 1}}})
        assert result == {"a": {"b": {"d": 1}}}

    def test_returns_scalar_unchanged(self) -> None:
        assert _prune(42) == 42
        assert _prune("hello") == "hello"


class TestFormatCsv:
    """Tests for _format_csv function."""

    def test_none_returns_none(self) -> None:
        assert _format_csv(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert _format_csv("") is None
        assert _format_csv("  ") is None

    def test_single_string(self) -> None:
        assert _format_csv("value") == "value"
        assert _format_csv("  value  ") == "value"

    def test_list_of_strings(self) -> None:
        assert _format_csv(["a", "b", "c"]) == "a,b,c"

    def test_list_with_whitespace(self) -> None:
        assert _format_csv(["  a  ", " b ", "c"]) == "a,b,c"

    def test_list_with_empty_strings(self) -> None:
        assert _format_csv(["a", "", "b"]) == "a,b"

    def test_empty_list_returns_none(self) -> None:
        assert _format_csv([]) is None

    def test_list_all_empty_returns_none(self) -> None:
        assert _format_csv(["", "  "]) is None

    def test_tuple_of_strings(self) -> None:
        assert _format_csv(("x", "y", "z")) == "x,y,z"


class TestFormatBool:
    """Tests for _format_bool function."""

    def test_none_returns_none(self) -> None:
        assert _format_bool(None) is None

    def test_true_returns_true_string(self) -> None:
        assert _format_bool(True) == "true"

    def test_false_returns_false_string(self) -> None:
        assert _format_bool(False) == "false"


class TestFormatDate:
    """Tests for _format_date function."""

    def test_none_returns_none(self) -> None:
        assert _format_date(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert _format_date("") is None
        assert _format_date("  ") is None

    def test_string_passthrough(self) -> None:
        assert _format_date("2024-01-15") == "2024-01-15"
        assert _format_date("  2024-01-15  ") == "2024-01-15"

    def test_date_object(self) -> None:
        d = date(2024, 1, 15)
        assert _format_date(d) == "2024-01-15"

    def test_date_single_digits(self) -> None:
        d = date(2024, 3, 5)
        assert _format_date(d) == "2024-03-05"


class TestSerializeModelList:
    """Tests for _serialize_model_list function."""

    def test_none_returns_none(self) -> None:
        assert _serialize_model_list(None) is None

    def test_empty_list_returns_none(self) -> None:
        assert _serialize_model_list([]) is None

    def test_dict_list(self) -> None:
        items = [{"a": 1, "b": None}, {"c": 2}]
        result = _serialize_model_list(items)
        # None should be pruned
        assert result == [{"a": 1}, {"c": 2}]

    def test_pydantic_model_list(self) -> None:
        class TestModel(BaseModel):
            name: str
            value: int | None = None

        items = [TestModel(name="test", value=42), TestModel(name="other")]
        result = _serialize_model_list(items)
        assert result == [{"name": "test", "value": 42}, {"name": "other"}]

    def test_unsupported_type_raises(self) -> None:
        with pytest.raises(TypeError, match="Unsupported item type"):
            _serialize_model_list(["string"])  # type: ignore[list-item]


class TestPaginationModel:
    """Tests for PaginationModel."""

    def test_defaults(self) -> None:
        pagination = PaginationModel()
        assert pagination.offset == 0
        assert pagination.limit == 25

    def test_custom_values(self) -> None:
        pagination = PaginationModel(offset=50, limit=100)
        assert pagination.offset == 50
        assert pagination.limit == 100

    def test_offset_minimum(self) -> None:
        with pytest.raises(ValueError):
            PaginationModel(offset=-1)

    def test_limit_minimum(self) -> None:
        with pytest.raises(ValueError):
            PaginationModel(limit=0)


class TestSearchPayload:
    """Tests for SearchPayload model."""

    def test_defaults(self) -> None:
        payload = SearchPayload()
        assert payload.q is None
        assert payload.fields is None
        assert payload.pagination.offset == 0

    def test_with_dict_filters(self) -> None:
        payload = SearchPayload(
            q="search term",
            fields=["field1", "field2"],
            facets=["facet1"],
            filters=[
                {"name": "applicationMetaData.publicationCategoryBag", "value": ["Granted/Issued"]},
            ],
            range_filters=[
                {
                    "field": "applicationMetaData.filingDate",
                    "valueFrom": "2022-01-01",
                    "valueTo": "2023-12-31",
                },
            ],
            sort=[{"field": "applicationMetaData.filingDate", "order": "Desc"}],
        )
        assert payload.q == "search term"
        assert payload.fields == ["field1", "field2"]
        assert payload.filters is not None and len(payload.filters) == 1
        assert payload.rangeFilters is not None and len(payload.rangeFilters) == 1

    def test_with_model_filters(self) -> None:
        payload = SearchPayload(
            q="test",
            filters=[
                OdpFilter(
                    name="applicationMetaData.publicationCategoryBag",
                    value=["Granted/Issued"],
                ),
            ],
            range_filters=[
                OdpRangeFilter(field="applicationMetaData.filingDate", valueFrom="2022-01-01"),
            ],
            sort=[OdpSort(field="applicationMetaData.filingDate", order="Desc")],
        )
        result = payload.model_dump_pruned()
        assert result["filters"] == [
            {"name": "applicationMetaData.publicationCategoryBag", "value": ["Granted/Issued"]},
        ]
        assert result["rangeFilters"] == [
            {"field": "applicationMetaData.filingDate", "valueFrom": "2022-01-01"},
        ]
        assert result["sort"] == [{"field": "applicationMetaData.filingDate", "order": "Desc"}]

    def test_model_dump_pruned(self) -> None:
        payload = SearchPayload(
            q="test",
            fields=None,
            sort=[{"field": "applicationMetaData.filingDate", "order": "Desc"}],
        )
        result = payload.model_dump_pruned()
        assert "q" in result
        assert "sort" in result
        assert "fields" not in result

    def test_model_dump_pruned_no_filters(self) -> None:
        payload = SearchPayload(q="test")
        result = payload.model_dump_pruned()
        assert "q" in result
        assert "filters" not in result
        assert "rangeFilters" not in result
        assert "sort" not in result

    def test_allows_extra_fields(self) -> None:
        payload = SearchPayload(q="test", custom_field="custom")  # type: ignore[call-arg]
        assert payload.model_extra is not None
        assert payload.model_extra["custom_field"] == "custom"


class TestOdpFilterModels:
    """Tests for ODP filter/sort Pydantic models."""

    def test_odp_filter(self) -> None:
        f = OdpFilter(name="applicationMetaData.publicationCategoryBag", value=["Granted/Issued"])
        assert f.name == "applicationMetaData.publicationCategoryBag"
        assert f.value == ["Granted/Issued"]

    def test_odp_filter_default_value(self) -> None:
        f = OdpFilter(name="someName")
        assert f.value == []

    def test_odp_range_filter(self) -> None:
        rf = OdpRangeFilter(
            field="applicationMetaData.filingDate",
            valueFrom="2022-01-01",
            valueTo="2023-12-31",
        )
        assert rf.field == "applicationMetaData.filingDate"
        assert rf.valueFrom == "2022-01-01"
        assert rf.valueTo == "2023-12-31"

    def test_odp_range_filter_partial(self) -> None:
        rf = OdpRangeFilter(field="applicationMetaData.filingDate", valueFrom="2022-01-01")
        assert rf.valueTo is None

    def test_odp_sort(self) -> None:
        s = OdpSort(field="applicationMetaData.filingDate", order="Asc")
        assert s.field == "applicationMetaData.filingDate"
        assert s.order == "Asc"

    def test_odp_sort_default_order(self) -> None:
        s = OdpSort(field="applicationMetaData.filingDate")
        assert s.order == "Desc"

    def test_serialize_odp_models(self) -> None:
        items = [
            OdpFilter(name="field1", value=["val1"]),
            {"name": "field2", "value": ["val2"]},
        ]
        result = _serialize_model_list(items)
        assert result == [
            {"name": "field1", "value": ["val1"]},
            {"name": "field2", "value": ["val2"]},
        ]


class TestUsptoOdpBaseClientInit:
    """Tests for UsptoOdpBaseClient initialization."""

    def test_requires_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("USPTO_ODP_API_KEY", raising=False)
        with pytest.raises(ConfigurationError, match="API key required"):
            UsptoOdpBaseClient()

    def test_uses_env_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("USPTO_ODP_API_KEY", "test_key_from_env")
        client = UsptoOdpBaseClient()
        assert client.api_key == "test_key_from_env"

    def test_uses_parameter_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("USPTO_ODP_API_KEY", raising=False)
        client = UsptoOdpBaseClient(api_key="direct_key")
        assert client.api_key == "direct_key"

    def test_parameter_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("USPTO_ODP_API_KEY", "env_key")
        client = UsptoOdpBaseClient(api_key="param_key")
        assert client.api_key == "param_key"


class TestNormalizeApplicationNumber:
    """Tests for _normalize_application_number method."""

    def test_strips_whitespace(self) -> None:
        client = UsptoOdpBaseClient(api_key="test")
        assert client._normalize_application_number("  12345678  ") == "12345678"

    def test_removes_slashes(self) -> None:
        client = UsptoOdpBaseClient(api_key="test")
        assert client._normalize_application_number("12/345,678") == "12345678"

    def test_removes_commas(self) -> None:
        client = UsptoOdpBaseClient(api_key="test")
        assert client._normalize_application_number("12,345,678") == "12345678"

    def test_removes_spaces(self) -> None:
        client = UsptoOdpBaseClient(api_key="test")
        assert client._normalize_application_number("12 345 678") == "12345678"

    def test_combined_separators(self) -> None:
        client = UsptoOdpBaseClient(api_key="test")
        assert client._normalize_application_number("12/345, 678") == "12345678"
