"""Tests for MPEP utility functions."""

from __future__ import annotations

from ip_tools.mpep.utils import BASE_URL, build_search_params


class TestBuildSearchParams:
    """Tests for build_search_params function."""

    def test_removes_none_values(self) -> None:
        result = build_search_params({"a": 1, "b": None, "c": "value"})
        assert result == {"a": 1, "c": "value"}

    def test_keeps_falsy_values(self) -> None:
        result = build_search_params({"a": 0, "b": "", "c": False})
        assert result == {"a": 0, "b": "", "c": False}

    def test_handles_empty_dict(self) -> None:
        result = build_search_params({})
        assert result == {}

    def test_preserves_all_non_none(self) -> None:
        params = {"q": "patent", "ver": "current", "cnt": 10}
        result = build_search_params(params)
        assert result == params


class TestBaseUrl:
    """Tests for BASE_URL constant."""

    def test_default_url(self) -> None:
        # Default URL should be USPTO MPEP
        assert "mpep.uspto.gov" in BASE_URL

    def test_url_is_https(self) -> None:
        assert BASE_URL.startswith("https://")
