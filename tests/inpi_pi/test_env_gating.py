"""Tests for env-gated INPI France MCP tool registration.

Verifies that ``patent_client_agents.mcp.tools.inpi_pi`` registers the
four INPI tools only when BOTH ``INPI_USERNAME`` and ``INPI_PASSWORD``
are set (BYOK posture — production deployers must register their own
personal ``data.inpi.fr`` account).

Test strategy: each test ``importlib.reload``s the inpi_pi tool module
under a controlled env, then inspects a fresh ``FastMCP`` instance to
see what got registered. We rebind ``inpi_pi_mcp`` on the module to a
fresh server before reload so each ``@conditional_tool`` decorator
runs against an empty surface.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any, cast

import pytest
from fastmcp import FastMCP

EXPECTED_INPI_TOOLS = {
    "search_inpi_trademarks",
    "get_inpi_trademark",
    "search_inpi_designs",
    "get_inpi_design",
}


def _reload_inpi_with_fresh_mcp() -> ModuleType:
    """Reload the inpi_pi tool module under a fresh FastMCP."""
    import patent_client_agents.mcp.tools.inpi_pi as inpi

    inpi.inpi_pi_mcp = FastMCP("INPI-PI")
    return importlib.reload(inpi)


async def _list_tool_names(inpi_mod: ModuleType) -> set[str]:
    """Return the set of registered tool names on the fresh FastMCP."""
    mcp = cast("Any", inpi_mod).inpi_pi_mcp
    tools = await mcp.list_tools()
    return {t.name for t in tools}


@pytest.fixture
def fresh_state(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Restore the conftest-managed env after each test by reloading once more."""
    yield
    _reload_inpi_with_fresh_mcp()


class TestInpiEnvGating:
    @pytest.mark.asyncio
    async def test_no_tools_when_both_unset(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """With both env vars unset, zero INPI tools register."""
        monkeypatch.delenv("INPI_USERNAME", raising=False)
        monkeypatch.delenv("INPI_PASSWORD", raising=False)

        inpi = _reload_inpi_with_fresh_mcp()
        names = await _list_tool_names(inpi)
        assert names & EXPECTED_INPI_TOOLS == set()

    @pytest.mark.asyncio
    async def test_no_tools_when_username_unset(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """Missing USERNAME → all four tools absent (BOTH required)."""
        monkeypatch.delenv("INPI_USERNAME", raising=False)
        monkeypatch.setenv("INPI_PASSWORD", "pw")

        inpi = _reload_inpi_with_fresh_mcp()
        names = await _list_tool_names(inpi)
        assert names & EXPECTED_INPI_TOOLS == set()

    @pytest.mark.asyncio
    async def test_no_tools_when_password_unset(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """Missing PASSWORD → all four tools absent."""
        monkeypatch.setenv("INPI_USERNAME", "u")
        monkeypatch.delenv("INPI_PASSWORD", raising=False)

        inpi = _reload_inpi_with_fresh_mcp()
        names = await _list_tool_names(inpi)
        assert names & EXPECTED_INPI_TOOLS == set()

    @pytest.mark.asyncio
    async def test_no_tools_when_username_empty(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """Empty USERNAME counts as unset."""
        monkeypatch.setenv("INPI_USERNAME", "")
        monkeypatch.setenv("INPI_PASSWORD", "pw")

        inpi = _reload_inpi_with_fresh_mcp()
        names = await _list_tool_names(inpi)
        assert names & EXPECTED_INPI_TOOLS == set()

    @pytest.mark.asyncio
    async def test_no_tools_when_password_empty(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """Empty PASSWORD counts as unset."""
        monkeypatch.setenv("INPI_USERNAME", "u")
        monkeypatch.setenv("INPI_PASSWORD", "")

        inpi = _reload_inpi_with_fresh_mcp()
        names = await _list_tool_names(inpi)
        assert names & EXPECTED_INPI_TOOLS == set()

    @pytest.mark.asyncio
    async def test_all_tools_registered_when_both_set(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """With both env vars set, every INPI tool registers."""
        monkeypatch.setenv("INPI_USERNAME", "user")
        monkeypatch.setenv("INPI_PASSWORD", "pass")

        inpi = _reload_inpi_with_fresh_mcp()
        names = await _list_tool_names(inpi)
        assert EXPECTED_INPI_TOOLS <= names, f"missing: {EXPECTED_INPI_TOOLS - names}"
