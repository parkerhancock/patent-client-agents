"""Tests for env-gated KIPO KIPRIS MCP tool registration.

Verifies that ``patent_client_agents.mcp.tools.kipo_kipris`` registers
the 9 KIPO tools only when ``KIPO_KIPRIS_API_KEY`` is set (ToS §11
BYOK — per-user keys only).

Test strategy: each test ``importlib.reload``s the kipo_kipris module
under a controlled env, then inspects a fresh ``FastMCP`` instance to
see what got registered. We rebind ``kipo_kipris_mcp`` on the module
to a fresh server before reload so each ``@conditional_tool``
decorator runs against an empty surface — that way the assertions are
about what *this reload* would have registered.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any, cast

import pytest
from fastmcp import FastMCP

# Names the chunk-3 surface registers — all 9 KIPO tools.
EXPECTED_KIPO_TOOLS = {
    "search_kipo_patents",
    "search_kipo_patents_advanced",
    "get_kipo_patent",
    "search_kipo_trademarks",
    "search_kipo_trademarks_advanced",
    "get_kipo_trademark",
    "search_kipo_designs",
    "search_kipo_designs_advanced",
    "get_kipo_design",
}


def _reload_kipo_with_fresh_mcp() -> ModuleType:
    """Reload the kipo_kipris tool module under a fresh FastMCP."""
    import patent_client_agents.mcp.tools.kipo_kipris as kipo

    kipo.kipo_kipris_mcp = FastMCP("KIPO — KIPRIS Plus")
    return importlib.reload(kipo)


async def _list_tool_names(kipo_mod: ModuleType) -> set[str]:
    """Return the set of registered tool names on the fresh FastMCP."""
    mcp = cast("Any", kipo_mod).kipo_kipris_mcp
    tools = await mcp.list_tools()
    return {t.name for t in tools}


@pytest.fixture
def fresh_state(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Restore the conftest-managed env after each test by reloading once more."""
    yield
    _reload_kipo_with_fresh_mcp()


class TestKipoEnvGating:
    @pytest.mark.asyncio
    async def test_no_tools_registered_when_env_unset(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """With KIPO_KIPRIS_API_KEY unset, zero KIPO tools register."""
        monkeypatch.delenv("KIPO_KIPRIS_API_KEY", raising=False)

        kipo = _reload_kipo_with_fresh_mcp()

        names = await _list_tool_names(kipo)
        assert names & EXPECTED_KIPO_TOOLS == set()

    @pytest.mark.asyncio
    async def test_no_tools_registered_when_env_empty_string(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """Empty-string KIPO_KIPRIS_API_KEY is treated as absent."""
        monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "")

        kipo = _reload_kipo_with_fresh_mcp()

        names = await _list_tool_names(kipo)
        assert names & EXPECTED_KIPO_TOOLS == set()

    @pytest.mark.asyncio
    async def test_all_tools_registered_when_env_set(
        self, monkeypatch: pytest.MonkeyPatch, fresh_state: None
    ) -> None:
        """With KIPO_KIPRIS_API_KEY set, every KIPO tool registers."""
        monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "some-service-key")

        kipo = _reload_kipo_with_fresh_mcp()

        names = await _list_tool_names(kipo)
        assert EXPECTED_KIPO_TOOLS <= names, f"missing tools: {EXPECTED_KIPO_TOOLS - names}"
