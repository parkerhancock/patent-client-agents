from __future__ import annotations

import importlib
from collections.abc import Iterator
from types import ModuleType
from typing import Any, cast

import pytest
from fastmcp import FastMCP

EXPECTED_TOOLS = {"get_oepm_patent", "get_oepm_trademark", "get_oepm_design"}


def _reload() -> ModuleType:
    import patent_client_agents.mcp.tools.oepm_spain as module

    module.oepm_spain_mcp = FastMCP("OEPM test")
    return importlib.reload(module)


async def _names(module: ModuleType) -> set[str]:
    tools = await cast("Any", module).oepm_spain_mcp.list_tools()
    return {tool.name for tool in tools}


@pytest.fixture
def restore_env() -> Iterator[None]:
    yield
    _reload()


@pytest.mark.asyncio
async def test_tools_need_both_credentials(
    monkeypatch: pytest.MonkeyPatch, restore_env: None
) -> None:
    monkeypatch.delenv("OEPM_CEO_USERNAME", raising=False)
    monkeypatch.setenv("OEPM_CEO_PASSWORD", "password")
    assert not EXPECTED_TOOLS & await _names(_reload())
    monkeypatch.setenv("OEPM_CEO_USERNAME", "user")
    monkeypatch.delenv("OEPM_CEO_PASSWORD", raising=False)
    assert not EXPECTED_TOOLS & await _names(_reload())


@pytest.mark.asyncio
async def test_tools_register_with_both_credentials(
    monkeypatch: pytest.MonkeyPatch, restore_env: None
) -> None:
    monkeypatch.setenv("OEPM_CEO_USERNAME", "user")
    monkeypatch.setenv("OEPM_CEO_PASSWORD", "password")
    assert EXPECTED_TOOLS <= await _names(_reload())
