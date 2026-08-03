from __future__ import annotations

import importlib
from collections.abc import Iterator
from types import ModuleType
from typing import Any, cast

import pytest
from fastmcp import FastMCP

EXPECTED_TOOLS = {
    "search_thai_dip_patents",
    "get_thai_dip_patent",
    "search_thai_dip_trademarks",
    "get_thai_dip_trademark",
    "search_thai_dip_copyrights",
    "get_thai_dip_copyright",
    "search_thai_dip_songs",
    "search_thai_dip_geographical_indications",
    "get_thai_dip_geographical_indication",
}


def _reload() -> ModuleType:
    import patent_client_agents.mcp.tools.thai_dip as module

    module.thai_dip_mcp = FastMCP("DIP test")
    return importlib.reload(module)


async def _names(module: ModuleType) -> set[str]:
    tools = await cast("Any", module).thai_dip_mcp.list_tools()
    return {tool.name for tool in tools}


@pytest.fixture
def restore_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    yield
    monkeypatch.setenv("DIP_DATA_EXCHANGE_TOKEN", "test-token")
    _reload()


@pytest.mark.asyncio
async def test_tools_require_token(monkeypatch: pytest.MonkeyPatch, restore_env: None) -> None:
    monkeypatch.delenv("DIP_DATA_EXCHANGE_TOKEN", raising=False)
    assert not EXPECTED_TOOLS & await _names(_reload())


@pytest.mark.asyncio
async def test_tools_register_with_token(
    monkeypatch: pytest.MonkeyPatch, restore_env: None
) -> None:
    monkeypatch.setenv("DIP_DATA_EXCHANGE_TOKEN", "token")
    assert EXPECTED_TOOLS <= await _names(_reload())
