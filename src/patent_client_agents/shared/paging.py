"""Bounded paging parameters for MCP search tools (§5).

Each alias carries its bounds as pydantic ``Field`` constraints, so they
appear in the tool's JSON schema and FastMCP rejects out-of-range values
before the tool body runs. Tools keep their own defaults::

    async def search_x(query: str, limit: Limit100 = 25, offset: Offset = 0): ...

Calling a tool function directly from Python skips that validation, as it
does for every other annotated constraint.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

Limit100 = Annotated[int, Field(ge=1, le=100, description="Maximum hits to return (1-100).")]
"""A page size from 1 through 100."""

Offset = Annotated[int, Field(ge=0, description="Result offset for pagination.")]
"""A zero-based row offset into the result set."""

__all__ = ["Limit100", "Offset"]
