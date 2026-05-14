"""EPO Guidelines for Examination MCP tools.

Mirrors the mpep/tmep/mopp pattern: corpus-backed search + per-section
retrieval against a SQLite/FTS5 snapshot of EPO's Guidelines pages.
The EPO equivalent of USPTO's MPEP — covers Parts A-H of the
Guidelines plus the General Part.
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP

from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.epo_guidelines import SearchInput, get_section, search

epo_guidelines_mcp = FastMCP("EPO Guidelines")


def _dump(obj: object) -> object:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()  # type: ignore[union-attr]
    return obj


@epo_guidelines_mcp.tool(annotations=READ_ONLY)
async def search_epo_guidelines(
    query: Annotated[str, "Search query for the EPO Guidelines for Examination"],
) -> dict:
    """Search the EPO Guidelines for Examination.

    Returns matching Guidelines sections with relevance-ranked
    snippets. Covers EPO examination practice for the EPC: Parts
    A (Formalities), B (Search), C (Examination), D (Opposition),
    E (Procedural matters), F (The application), G (Patentability),
    H (Amendments and corrections), plus the General Part.
    """
    result = await search(SearchInput(query=query))
    return _dump(result)  # type: ignore[return-value]


@epo_guidelines_mcp.tool(annotations=READ_ONLY)
async def get_epo_guidelines_section(
    section: Annotated[
        str,
        (
            "EPO Guidelines section identifier. Accepts canonical "
            "citations like 'G-II, 3.1' or 'G-II 3.1' or 'G.II.3.1', "
            "or URL slugs like 'g_ii_3_1'."
        ),
    ],
) -> dict:
    """Get a specific EPO Guidelines section by citation or slug.

    Returns the full text of the requested section. EPO Guidelines
    organize their content as Part (A-H) → Chapter (Roman) →
    Section (numeric) → Subsection (numeric), with one HTML page
    per leaf node.
    """
    result = await get_section(section)
    return _dump(result)  # type: ignore[return-value]
