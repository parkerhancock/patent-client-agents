"""Tests for the shared paging parameter types."""

from __future__ import annotations

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from patent_client_agents.shared.paging import Limit100, Offset


@pytest.mark.parametrize("value", [1, 25, 100])
def test_limit100_accepts_in_range(value: int) -> None:
    assert TypeAdapter(Limit100).validate_python(value) == value


@pytest.mark.parametrize("value", [0, -1, 101])
def test_limit100_rejects_out_of_range(value: int) -> None:
    with pytest.raises(PydanticValidationError):
        TypeAdapter(Limit100).validate_python(value)


def test_offset_bounds() -> None:
    assert TypeAdapter(Offset).validate_python(0) == 0
    assert TypeAdapter(Offset).validate_python(10_000) == 10_000
    with pytest.raises(PydanticValidationError):
        TypeAdapter(Offset).validate_python(-1)


def _server() -> FastMCP:
    mcp = FastMCP("paging-test")

    @mcp.tool
    async def page(limit: Limit100 = 25, offset: Offset = 0) -> dict:
        return {"limit": limit, "offset": offset}

    return mcp


async def test_tool_schema_carries_bounds_and_descriptions() -> None:
    async with Client(_server()) as client:
        (tool,) = await client.list_tools()
    props = tool.input_schema["properties"]
    assert props["limit"] == {
        "default": 25,
        "description": "Maximum hits to return (1-100).",
        "maximum": 100,
        "minimum": 1,
        "type": "integer",
    }
    assert props["offset"] == {
        "default": 0,
        "description": "Result offset for pagination.",
        "minimum": 0,
        "type": "integer",
    }


async def test_tool_call_rejects_out_of_range_before_body_runs() -> None:
    async with Client(_server()) as client:
        ok = await client.call_tool("page", {"limit": 100, "offset": 7})
        assert ok.structured_content == {"limit": 100, "offset": 7}
        with pytest.raises(ToolError, match="less than or equal to 100"):
            await client.call_tool("page", {"limit": 101})
        with pytest.raises(ToolError, match="greater than or equal to 0"):
            await client.call_tool("page", {"offset": -1})
