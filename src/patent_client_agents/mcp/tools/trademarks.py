"""USPTO Trademark MCP tools (TMEP, TSDR, trademark assignments).

Phase 1 surface: read-only tools backed by ``patent_client_agents.tmep``,
``patent_client_agents.uspto_tsdr``, and
``patent_client_agents.uspto_trademark_assignments``.

TSDR tools require ``USPTO_TSDR_API_KEY``. TMEP and trademark-assignment
tools need no auth.
"""

from __future__ import annotations

import json
from typing import Annotated

from fastmcp import FastMCP

from law_tools_core.exceptions import ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.tmep import SearchInput, get_section, search
from patent_client_agents.uspto_trademark_assignments import TrademarkAssignmentClient
from patent_client_agents.uspto_tsdr import TsdrClient

trademarks_mcp = FastMCP("Trademarks")


def _dump(obj: object) -> object:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()  # type: ignore[union-attr]
    return obj


def _dump_list(items: list) -> dict:
    return {"results": [_dump(i) for i in items]}


# ---------------------------------------------------------------
# TSDR (Trademark Status & Document Retrieval)
# ---------------------------------------------------------------


@trademarks_mcp.tool(annotations=READ_ONLY)
async def get_trademark_status(
    serial_number: Annotated[str, "USPTO trademark serial number"],
) -> dict:
    """Get trademark status from TSDR.

    Returns current status, filing date, registration date, mark text,
    and status description. Requires ``USPTO_TSDR_API_KEY``.
    """
    async with TsdrClient() as client:
        result = await client.get_status(serial_number)
        return _dump(result)  # type: ignore[return-value]


@trademarks_mcp.tool(annotations=READ_ONLY)
async def get_trademark_documents(
    serial_number: Annotated[str, "USPTO trademark serial number"],
) -> dict:
    """Get prosecution documents for a trademark from TSDR.

    Returns documents filed during prosecution: office actions,
    responses, registration certificates, etc. Requires
    ``USPTO_TSDR_API_KEY``.
    """
    async with TsdrClient() as client:
        docs = await client.get_documents(serial_number)
        return _dump_list(docs)


@trademarks_mcp.tool(annotations=READ_ONLY)
async def batch_trademark_status(
    serial_numbers_json: Annotated[
        str, 'JSON array of serial numbers, e.g. \'["97123456", "97654321"]\''
    ],
) -> dict:
    """Batch check trademark status for multiple marks.

    Accepts a JSON array string of serial numbers. Returns status for
    each. Requires ``USPTO_TSDR_API_KEY``.
    """
    serial_numbers = json.loads(serial_numbers_json)
    if not isinstance(serial_numbers, list):
        raise ValidationError("Expected a JSON array of strings")

    async with TsdrClient() as client:
        result = await client.batch_status(serial_numbers)
        return result


@trademarks_mcp.tool(annotations=READ_ONLY)
async def get_trademark_last_update(
    serial_number: Annotated[str, "USPTO trademark serial number"],
) -> dict:
    """Get the last-update timestamp for a trademark case.

    Returns when the trademark record was last modified at the USPTO.
    Requires ``USPTO_TSDR_API_KEY``.
    """
    async with TsdrClient() as client:
        result = await client.get_last_update(serial_number)
        return _dump(result)  # type: ignore[return-value]


# ---------------------------------------------------------------
# TMEP (Trademark Manual of Examining Procedure)
# ---------------------------------------------------------------


@trademarks_mcp.tool(annotations=READ_ONLY)
async def search_tmep(
    query: Annotated[str, "Search query for the TMEP"],
) -> dict:
    """Search the Trademark Manual of Examining Procedure.

    Returns matching TMEP sections with relevance-ranked snippets.
    Useful for finding examination guidance on trademark registration
    issues.
    """
    result = await search(SearchInput(query=query))
    return _dump(result)  # type: ignore[return-value]


@trademarks_mcp.tool(annotations=READ_ONLY)
async def get_tmep_section(
    section: Annotated[str, "TMEP section number (e.g. '1207', '1207.01(a)') or href"],
) -> dict:
    """Get a specific TMEP section by number.

    Returns the full text of the requested section from the Trademark
    Manual of Examining Procedure.
    """
    result = await get_section(section)
    return _dump(result)  # type: ignore[return-value]


# ---------------------------------------------------------------
# Trademark Assignment Center
# ---------------------------------------------------------------


_TM_ASSIGNMENT_AXES = (
    "assignee",
    "assignor",
    "serial_number",
    "registration_number",
    "reel_frame",
)


@trademarks_mcp.tool(annotations=READ_ONLY)
async def search_trademark_assignments(
    query: Annotated[
        str,
        "Value to search for (e.g. 'Apple Inc', '97123456', '9006/0093').",
    ],
    by: Annotated[
        str,
        "What kind of value `query` is. One of: assignee, assignor, "
        "serial_number, registration_number, reel_frame.",
    ],
    limit: Annotated[
        int,
        "Maximum records to return per request (max 1000).",
    ] = 100,
    start_row: Annotated[
        int,
        "1-based starting row for pagination.",
    ] = 1,
) -> dict:
    """Search USPTO trademark assignment recordations.

    Returns recordations with reel/frame, conveyance, assignors,
    assignees, and affected trademark properties. No auth required.
    """
    axis = by.strip().lower()
    if axis not in _TM_ASSIGNMENT_AXES:
        raise ValidationError(f"`by` must be one of {_TM_ASSIGNMENT_AXES}; got {by!r}")

    async with TrademarkAssignmentClient() as client:
        if axis == "assignee":
            records = await client.search_by_assignee(query, start_row=start_row, limit=limit)
        elif axis == "assignor":
            records = await client.search_by_assignor(query, start_row=start_row, limit=limit)
        elif axis == "serial_number":
            records = await client.search_by_serial(query, start_row=start_row, limit=limit)
        elif axis == "registration_number":
            records = await client.search_by_registration(query, start_row=start_row, limit=limit)
        else:  # reel_frame
            records = await client.search_by_reel_frame(query, start_row=start_row, limit=limit)

    return _dump_list(records)
