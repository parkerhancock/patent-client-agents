"""Tests for Google Patents API utility functions and models."""

from __future__ import annotations

from patent_client_agents.google_patents.api import (
    FigureBounds,
    FigureCallout,
    FigureEntry,
    GooglePatentsSearchInput,
    _clean_list,
    _figure_entries_from_dict,
    _normalize_page,
    _normalize_page_size,
    get_client,
)
from patent_client_agents.google_patents.client import GooglePatentsClient


class TestFigureBounds:
    """Tests for FigureBounds model."""

    def test_creates_full_bounds(self) -> None:
        bounds = FigureBounds(left=10, top=20, right=100, bottom=150)
        assert bounds.left == 10
        assert bounds.top == 20
        assert bounds.right == 100
        assert bounds.bottom == 150

    def test_defaults_all_none(self) -> None:
        bounds = FigureBounds()
        assert bounds.left is None
        assert bounds.top is None
        assert bounds.right is None
        assert bounds.bottom is None


class TestFigureCallout:
    """Tests for FigureCallout model."""

    def test_creates_full_callout(self) -> None:
        callout = FigureCallout(
            figure_page=1,
            reference_id="10",
            label="Element 10",
            bounds=FigureBounds(left=50, top=100, right=80, bottom=120),
        )
        assert callout.figure_page == 1
        assert callout.reference_id == "10"
        assert callout.label == "Element 10"
        assert callout.bounds.left == 50

    def test_defaults(self) -> None:
        callout = FigureCallout()
        assert callout.figure_page is None
        assert callout.reference_id is None
        assert callout.label is None
        assert isinstance(callout.bounds, FigureBounds)


class TestFigureEntry:
    """Tests for FigureEntry model."""

    def test_creates_full_entry(self) -> None:
        entry = FigureEntry(
            index=0,
            page_number=5,
            image_id="fig1",
            thumbnail_url="https://example.com/thumb.png",
            full_image_url="https://example.com/full.png",
            callouts=[FigureCallout(reference_id="1", label="Part 1")],
        )
        assert entry.index == 0
        assert entry.page_number == 5
        assert entry.image_id == "fig1"
        assert len(entry.callouts) == 1

    def test_defaults(self) -> None:
        entry = FigureEntry(index=0)
        assert entry.page_number is None
        assert entry.image_id is None
        assert entry.thumbnail_url is None
        assert entry.full_image_url is None
        assert entry.callouts == []


class TestGooglePatentsSearchInput:
    """Tests for GooglePatentsSearchInput model."""

    def test_creates_full_input(self) -> None:
        input_data = GooglePatentsSearchInput(
            keywords=["machine learning", "neural network"],
            cpc_codes=["G06N3/08"],
            inventors=["John Doe"],
            assignees=["Tech Corp"],
            country_codes=["US", "EP"],
            language_codes=["en"],
            date_type="filing",
            filed_after="2020-01-01",
            filed_before="2023-12-31",
            status="ACTIVE",
            patent_type="PATENT",
            litigation="true",
            include_patents=True,
            include_npl=True,
            sort="new",
            dups="family",
            page=1,
            page_size=25,
            cluster_results=True,
            local="en",
        )
        assert input_data.keywords == ["machine learning", "neural network"]
        assert input_data.cpc_codes == ["G06N3/08"]
        assert input_data.date_type == "filing"
        assert input_data.page_size == 25

    def test_defaults(self) -> None:
        input_data = GooglePatentsSearchInput()
        assert input_data.keywords is None
        assert input_data.cpc_codes is None
        assert input_data.date_type == "priority"
        assert input_data.include_patents is True
        assert input_data.include_npl is False
        assert input_data.page is None
        assert input_data.page_size is None

    def test_populate_by_name(self) -> None:
        input_data = GooglePatentsSearchInput.model_validate({"keywords": ["test"]})
        assert input_data.keywords == ["test"]


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
