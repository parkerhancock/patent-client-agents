"""UKIPO Manual of Patent Practice (MoPP) MCP tools.

Mirrors the mpep/tmep pattern: corpus-backed search + per-section
retrieval against a SQLite/FTS5 snapshot of gov.uk's MoPP pages.
Sibling of the USPTO MPEP — covers the UK Patents Act 1977 + UKIPO
examination practice.
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP

from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.ukipo_mopp import SearchInput, get_section, search

ukipo_mopp_mcp = FastMCP("UKIPO MoPP")


def _dump(obj: object) -> object:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()  # type: ignore[union-attr]
    return obj


@ukipo_mopp_mcp.tool(annotations=READ_ONLY)
async def search_mopp(
    query: Annotated[str, "Search query for the UK Manual of Patent Practice"],
) -> dict:
    """Search the UKIPO Manual of Patent Practice (MoPP).

    Returns matching MoPP sections with relevance-ranked snippets.
    Covers UK Patents Act 1977 examination practice, patentability,
    SPCs, and adjacent procedural guidance — the UK equivalent of
    the USPTO's MPEP.
    """
    result = await search(SearchInput(query=query))
    return _dump(result)  # type: ignore[return-value]


@ukipo_mopp_mcp.tool(annotations=READ_ONLY)
async def get_mopp_section(
    section: Annotated[
        str,
        (
            "MoPP section identifier. Accepts a PA 1977 section number "
            "('1', '14', '100', '4A') or a gov.uk slug "
            "('section-1-patentability', 'glossary-of-terms-...')."
        ),
    ],
) -> dict:
    """Get a specific MoPP section by number or slug.

    Returns the full text of the requested section. MoPP organizes
    its sections by PA 1977 section number; subsection citations
    (e.g. '1.07', '14.99') are within each page's body.
    """
    result = await get_section(section)
    return _dump(result)  # type: ignore[return-value]
