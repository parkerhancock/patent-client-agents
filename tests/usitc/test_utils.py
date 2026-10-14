"""Tests for USITC utility functions."""

from __future__ import annotations

from pathlib import Path

import pytest

from patent_client_agents.usitc.utils import (
    get_env_token,
    normalize_params,
)


class TestGetEnvToken:
    """Tests for get_env_token function."""

    def test_returns_token_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_TOKEN", "my_token_123")
        result = get_env_token("TEST_TOKEN")
        assert result == "my_token_123"

    def test_strips_whitespace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_TOKEN", "  token_with_spaces  ")
        result = get_env_token("TEST_TOKEN")
        assert result == "token_with_spaces"

    def test_returns_none_for_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MISSING_TOKEN", raising=False)
        result = get_env_token("MISSING_TOKEN")
        assert result is None

    def test_reads_token_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        token_file = tmp_path / "edis-token"
        token_file.write_text("  mounted_token_123  \n")
        monkeypatch.delenv("TEST_TOKEN", raising=False)
        monkeypatch.setenv("TEST_TOKEN_FILE", str(token_file))

        assert get_env_token("TEST_TOKEN") == "mounted_token_123"

    def test_direct_token_takes_precedence_over_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        token_file = tmp_path / "edis-token"
        token_file.write_text("mounted_token")
        monkeypatch.setenv("TEST_TOKEN", "direct_token")
        monkeypatch.setenv("TEST_TOKEN_FILE", str(token_file))

        assert get_env_token("TEST_TOKEN") == "direct_token"

    def test_blank_direct_token_falls_back_to_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        token_file = tmp_path / "edis-token"
        token_file.write_text("mounted_token")
        monkeypatch.setenv("TEST_TOKEN", "  ")
        monkeypatch.setenv("TEST_TOKEN_FILE", str(token_file))

        assert get_env_token("TEST_TOKEN") == "mounted_token"

    def test_returns_none_for_missing_token_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("TEST_TOKEN", raising=False)
        monkeypatch.setenv("TEST_TOKEN_FILE", str(tmp_path / "missing"))

        assert get_env_token("TEST_TOKEN") is None


class TestNormalizeParams:
    """Tests for normalize_params function."""

    def test_removes_none_values(self) -> None:
        result = normalize_params({"a": 1, "b": None, "c": "value"})
        assert result == {"a": 1, "c": "value"}

    def test_removes_empty_strings(self) -> None:
        result = normalize_params({"a": 1, "b": "", "c": "value"})
        assert result == {"a": 1, "c": "value"}

    def test_keeps_other_falsy_values(self) -> None:
        result = normalize_params({"a": 0, "b": False})
        assert result == {"a": 0, "b": False}

    def test_handles_empty_dict(self) -> None:
        result = normalize_params({})
        assert result == {}
