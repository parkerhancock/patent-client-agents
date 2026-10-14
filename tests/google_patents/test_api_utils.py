"""Tests for Google Patents API utility functions and models."""

from __future__ import annotations

from patent_client_agents.google_patents.api import (
    FigureBounds,
    FigureEntry,
    _clean_list,
    _figure_entries_from_dict,
    _normalize_page,
    _normalize_page_size,
    get_client,
)
from patent_client_agents.google_patents.client import GooglePatentsClient


class TestCleanList:
    """Tests for _clean_list function."""

    def test_none_returns_empty(self) -> None:
        assert _clean_list(None) == []

    def test_empty_list_returns_empty(self) -> None:
        assert _clean_list([]) == []

    def test_strips_whitespace(self) -> None:
        result = _clean_list(["  value  ", "  other  "])
        assert result == ["value", "other"]

    def test_filters_empty_strings(self) -> None:
        result = _clean_list(["value", "", "  ", "other"])
        assert result == ["value", "other"]

    def test_applies_transform(self) -> None:
        result = _clean_list(["us", "ep", "jp"], transform=str.upper)
        assert result == ["US", "EP", "JP"]

    def test_transform_after_strip(self) -> None:
        result = _clean_list(["  us  ", "  jp  "], transform=str.upper)
        assert result == ["US", "JP"]


class TestNormalizePage:
    """Tests for _normalize_page function."""

    def test_none_returns_none(self) -> None:
        assert _normalize_page(None) is None

    def test_positive_page(self) -> None:
        assert _normalize_page(5) == 5

    def test_zero_becomes_one(self) -> None:
        assert _normalize_page(0) == 1

    def test_negative_becomes_one(self) -> None:
        assert _normalize_page(-5) == 1


class TestNormalizePageSize:
    """Tests for _normalize_page_size function."""

    def test_none_returns_none(self) -> None:
        assert _normalize_page_size(None) is None

    def test_valid_page_size(self) -> None:
        assert _normalize_page_size(25) == 25

    def test_zero_becomes_one(self) -> None:
        assert _normalize_page_size(0) == 1

    def test_negative_becomes_one(self) -> None:
        assert _normalize_page_size(-10) == 1

    def test_over_100_becomes_100(self) -> None:
        assert _normalize_page_size(150) == 100


class TestFigureEntriesFromDict:
    """Tests for _figure_entries_from_dict function."""

    def test_empty_list(self) -> None:
        result = _figure_entries_from_dict([])
        assert result == []

    def test_basic_figure(self) -> None:
        figures = [
            {
                "index": 0,
                "page_number": 1,
                "image_id": "fig1",
                "thumbnail_url": "https://example.com/thumb.png",
                "full_image_url": "https://example.com/full.png",
            }
        ]
        result = _figure_entries_from_dict(figures)
        assert len(result) == 1
        assert isinstance(result[0], FigureEntry)
        assert result[0].index == 0
        assert result[0].image_id == "fig1"

    def test_figure_with_callouts(self) -> None:
        figures = [
            {
                "index": 0,
                "callouts": [
                    {
                        "figure_page": 1,
                        "reference_id": "10",
                        "label": "Element 10",
                        "bounds": {"left": 50, "top": 100, "right": 80, "bottom": 120},
                    }
                ],
            }
        ]
        result = _figure_entries_from_dict(figures)
        assert len(result[0].callouts) == 1
        assert result[0].callouts[0].reference_id == "10"
        assert result[0].callouts[0].bounds.left == 50

    def test_figure_with_empty_callouts(self) -> None:
        figures = [{"index": 0, "callouts": []}]
        result = _figure_entries_from_dict(figures)
        assert result[0].callouts == []

    def test_uses_enumerate_index_as_fallback(self) -> None:
        figures = [{"page_number": 1}, {"page_number": 2}]
        result = _figure_entries_from_dict(figures)
        assert result[0].index == 0
        assert result[1].index == 1

    def test_callout_with_none_bounds(self) -> None:
        figures = [
            {
                "index": 0,
                "callouts": [{"figure_page": 1, "bounds": None}],
            }
        ]
        result = _figure_entries_from_dict(figures)
        assert isinstance(result[0].callouts[0].bounds, FigureBounds)


class TestGetClient:
    """Tests for get_client function."""

    def test_returns_google_patents_client(self) -> None:
        client = get_client()
        assert isinstance(client, GooglePatentsClient)

    def test_with_cache_disabled(self) -> None:
        client = get_client(use_cache=False)
        assert isinstance(client, GooglePatentsClient)

    def test_with_cache_enabled(self) -> None:
        client = get_client(use_cache=True)
        assert isinstance(client, GooglePatentsClient)
