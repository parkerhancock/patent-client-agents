from __future__ import annotations

import importlib
from collections.abc import Iterator
from types import ModuleType
from typing import Any, cast

import pytest
from fastmcp import FastMCP

EXPECTED_TOOLS = {
    "get_iponz_patent",
    "list_iponz_patents_updated",
    "get_iponz_trademark",
    "list_iponz_trademarks_updated",
    "get_iponz_design",
    "list_iponz_designs_updated",
    "list_iponz_designs_registered",
}


def _reload() -> ModuleType:
    import patent_client_agents.mcp.tools.iponz_new_zealand as module

    module.iponz_new_zealand_mcp = FastMCP("IPONZ test")
    return importlib.reload(module)


async def _names(module: ModuleType) -> set[str]:
    tools = await cast("Any", module).iponz_new_zealand_mcp.list_tools()
    return {tool.name for tool in tools}


@pytest.fixture
def restore_env() -> Iterator[None]:
    yield
    _reload()


@pytest.mark.asyncio
async def test_tools_require_subscription_key(
    monkeypatch: pytest.MonkeyPatch, restore_env: None
) -> None:
    monkeypatch.delenv("IPONZ_SUBSCRIPTION_KEY", raising=False)
    assert not EXPECTED_TOOLS & await _names(_reload())


@pytest.mark.asyncio
async def test_tools_register_with_subscription_key(
    monkeypatch: pytest.MonkeyPatch, restore_env: None
) -> None:
    monkeypatch.setenv("IPONZ_SUBSCRIPTION_KEY", "mock-key")
    monkeypatch.delenv("IPONZ_ACCESS_TOKEN", raising=False)
    assert EXPECTED_TOOLS <= await _names(_reload())
