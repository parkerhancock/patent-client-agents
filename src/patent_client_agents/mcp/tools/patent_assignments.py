"""USPTO Patent Assignment MCP tools.

The trademark-assignment half of the original combined ``assignments``
module lives with ``law-tools``; this file carries only the patent-side
tools backed by ``patent_client_agents.uspto_assignments``.
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP

from patent_client_agents.uspto_assignments import AssignmentCenterClient
from law_tools_core.mcp.annotations import READ_ONLY

patent_assignments_mcp = FastMCP("PatentAssignments")


def _dump(obj: object) -> object:
    """Serialize a Pydantic model or pass through."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()  # type: ignore[union-attr]
    return obj


def _dump_list(items: list) -> dict:
    """Serialize a list of Pydantic models."""
    return {"results": [_dump(i) for i in items]}


@patent_assignments_mcp.tool(annotations=READ_ONLY)
async def search_patent_assignments_by_assignee(
    name: Annotated[str, "Assignee name (company or person receiving rights)"],
) -> dict:
    """Search USPTO patent assignments by assignee name.

    Returns assignment records showing who acquired rights
    to patents, including reel/frame, dates, and properties.
    """
    async with AssignmentCenterClient() as client:
        records = await client.search_by_assignee(name)
        return _dump_list(records)


@patent_assignments_mcp.tool(annotations=READ_ONLY)
async def search_patent_assignments_by_patent(
    patent_number: Annotated[str, "USPTO patent number"],
) -> dict:
    """Get patent assignment history for a patent number.

    Returns the chain of title showing all recorded
    assignments for the specified patent.
    """
    async with AssignmentCenterClient() as client:
        records = await client.search_by_patent(patent_number)
        return _dump_list(records)


@patent_assignments_mcp.tool(annotations=READ_ONLY)
async def search_patent_assignments_by_application(
    application_number: Annotated[str, "USPTO application number"],
) -> dict:
    """Get patent assignment history by application number.

    Returns all recorded assignments for the specified
    patent application.
    """
    async with AssignmentCenterClient() as client:
        records = await client.search_by_application(application_number)
        return _dump_list(records)


@patent_assignments_mcp.tool(annotations=READ_ONLY)
async def search_patent_assignments_by_assignor(
    name: Annotated[str, "Assignor name (party transferring rights)"],
) -> dict:
    """Search USPTO patent assignments by assignor name.

    Returns assignment records showing who transferred
    patent rights, including reel/frame, dates, and
    properties.
    """
    async with AssignmentCenterClient() as client:
        records = await client.search_by_assignor(name)
        return _dump_list(records)


@patent_assignments_mcp.tool(annotations=READ_ONLY)
async def search_patent_assignments_by_reel_frame(
    reel_frame: Annotated[str, "Reel/frame identifier (e.g. '52614/446')"],
) -> dict:
    """Search USPTO patent assignments by reel/frame number.

    Returns assignment records matching the recording number.
    """
    async with AssignmentCenterClient() as client:
        records = await client.search_by_reel_frame(reel_frame)
        return _dump_list(records)


@patent_assignments_mcp.tool(annotations=READ_ONLY)
async def search_all_patent_assignments(
    query: Annotated[str, "Assignee or assignor name to search"],
    search_by: Annotated[str, "Search field: 'assignee' or 'assignor'"] = "assignee",
) -> dict:
    """Paginated search through all matching patent assignments.

    Automatically paginates to retrieve all results.
    """
    async with AssignmentCenterClient() as client:
        kwargs = {}
        if search_by == "assignor":
            kwargs["assignor_name"] = query
        else:
            kwargs["assignee_name"] = query
        records = await client.search_all(**kwargs)
        return _dump_list(records)


@patent_assignments_mcp.tool(annotations=READ_ONLY)
async def search_patent_assignments(
    query: Annotated[
        str, "Search query — assignee name, assignor name, patent number, or application number"
    ],
) -> dict:
    """General patent assignment search.

    Attempts to search by assignee name. Use the more
    specific tools for patent number or application
    number lookups.
    """
    async with AssignmentCenterClient() as client:
        records = await client.search(assignee_name=query)
        return _dump_list(records)
