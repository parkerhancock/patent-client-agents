"""Tests for the INPI MCP resource surface."""

from __future__ import annotations

from patent_client_agents.inpi_pi.resources import (
    USAGE_RESOURCE_URI,
    get_usage_resource,
)


def test_usage_resource_uri_constant() -> None:
    assert USAGE_RESOURCE_URI == "pca://inpi_pi/usage"


def test_usage_resource_returns_human_text() -> None:
    text = get_usage_resource()
    assert isinstance(text, str)
    assert text  # non-empty
    assert "INPI" in text
