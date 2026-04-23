"""Manual of Patent Examining Procedure MCP tools.

Split from the combined ``reference`` module — the federal-rules and
cross-source citation-router tools stay in law-tools.
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP

from patent_client_agents.mpep import SearchInput, get_section, search
from law_tools_core.mcp.annotations import READ_ONLY

mpep_mcp = FastMCP("MPEP")


def _dump(obj: object) -> object:
    """Serialize a Pydantic model or pass through."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()  # type: ignore[union-attr]
    return obj


@mpep_mcp.tool(annotations=READ_ONLY)
async def search_mpep(
    query: Annotated[str, "Search query for the MPEP"],
) -> dict:
    """Search the Manual of Patent Examining Procedure.

    Returns matching MPEP sections with relevance-ranked
    snippets. Covers patentability, examination procedures,
    and patent law guidance.
    """
    result = await search(SearchInput(query=query))
    return _dump(result)  # type: ignore[return-value]


@mpep_mcp.tool(annotations=READ_ONLY)
async def get_mpep_section(
    section: Annotated[str, "MPEP section number (e.g. '2106', '2106.04(a)') or href"],
) -> dict:
    """Get a specific MPEP section by number.

    Returns the full text of the requested section.
    Accepts section numbers like '2106' or hrefs like
    'd0e122292.html'.
    """
    result = await get_section(section)
    return _dump(result)  # type: ignore[return-value]
