from __future__ import annotations

import importlib
from collections.abc import Iterator
from types import ModuleType
from typing import Any, cast

import pytest
from fastmcp import FastMCP

EXPECTED_TOOLS = {
    "search_dpma_patents",
    "get_dpma_patent",
    "search_dpma_trademarks",
    "get_dpma_trademark",
    "search_dpma_designs",
    "get_dpma_design",
}


def _reload() -> ModuleType:
    import patent_client_agents.mcp.tools.dpma_register as module

    module.dpma_register_mcp = FastMCP("DPMA test")
    return importlib.reload(module)


async def _names(module: ModuleType) -> set[str]:
    tools = await cast("Any", module).dpma_register_mcp.list_tools()
    return {tool.name for tool in tools}


@pytest.fixture
def restore_env() -> Iterator[None]:
    yield
    _reload()


@pytest.mark.asyncio
async def test_tools_need_both_credentials(
    monkeypatch: pytest.MonkeyPatch, restore_env: None
) -> None:
    monkeypatch.delenv("DPMA_CONNECTPLUS_USERNAME", raising=False)
    monkeypatch.setenv("DPMA_CONNECTPLUS_PASSWORD", "password")
    assert not EXPECTED_TOOLS & await _names(_reload())

    monkeypatch.setenv("DPMA_CONNECTPLUS_USERNAME", "user")
    monkeypatch.delenv("DPMA_CONNECTPLUS_PASSWORD", raising=False)
    assert not EXPECTED_TOOLS & await _names(_reload())


@pytest.mark.asyncio
async def test_tools_register_with_both_credentials(
    monkeypatch: pytest.MonkeyPatch, restore_env: None
) -> None:
    monkeypatch.setenv("DPMA_CONNECTPLUS_USERNAME", "user")
    monkeypatch.setenv("DPMA_CONNECTPLUS_PASSWORD", "password")
    assert EXPECTED_TOOLS <= await _names(_reload())
