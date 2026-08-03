from __future__ import annotations

import importlib
from collections.abc import Iterator
from types import ModuleType
from typing import Any, cast

import pytest
from fastmcp import FastMCP

EXPECTED_TOOLS = {
    "search_ipi_patents",
    "get_ipi_patent",
    "search_ipi_patent_publications",
    "search_ipi_trademarks",
    "get_ipi_trademark",
    "search_ipi_spcs",
    "get_ipi_spc",
    "search_ipi_spc_publications",
}


def _reload() -> ModuleType:
    import patent_client_agents.mcp.tools.ipi_swissreg as module

    module.ipi_swissreg_mcp = FastMCP("IPI test")
    return importlib.reload(module)


async def _names(module: ModuleType) -> set[str]:
    tools = await cast("Any", module).ipi_swissreg_mcp.list_tools()
    return {tool.name for tool in tools}


@pytest.fixture
def restore_env() -> Iterator[None]:
    yield
    _reload()


@pytest.mark.asyncio
async def test_tools_need_both_credentials(
    monkeypatch: pytest.MonkeyPatch, restore_env: None
) -> None:
    monkeypatch.delenv("IPI_DATA_USERNAME", raising=False)
    monkeypatch.setenv("IPI_DATA_PASSWORD", "password")
    assert not EXPECTED_TOOLS & await _names(_reload())
    monkeypatch.setenv("IPI_DATA_USERNAME", "user")
    monkeypatch.delenv("IPI_DATA_PASSWORD", raising=False)
    assert not EXPECTED_TOOLS & await _names(_reload())


@pytest.mark.asyncio
async def test_totp_is_optional_for_tool_registration(
    monkeypatch: pytest.MonkeyPatch, restore_env: None
) -> None:
    monkeypatch.setenv("IPI_DATA_USERNAME", "user")
    monkeypatch.setenv("IPI_DATA_PASSWORD", "password")
    monkeypatch.delenv("IPI_DATA_TOTP_TOKEN", raising=False)
    assert EXPECTED_TOOLS <= await _names(_reload())
