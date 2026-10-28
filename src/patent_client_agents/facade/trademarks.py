"""Consolidated Trademarks facade tools (public toolset).

Thin dispatchers over the per-source trademark tool functions in
``patent_client_agents.mcp.tools.trademarks``. No business logic lives here:
each branch forwards to an existing function that already returns the §5.9
envelope, so the §5.15 per-module helpers and the canonical templates stay
untouched.

Design note — the two source searches have distinct query languages: TESS
search keys on ``search_by`` (wordmark/owner/goods_services) with
``paginate_all``/``max_results``; assignment search keys on ``by``
(assignee/assignor/serial/registration/reel_frame) with ``limit``/``start_row``.
Folding both into one positional ``search_trademarks`` would need a fat
optional-param bag that hurts routing, so the TESS search keeps its own
dispatcher and ``search_trademark_assignments`` is re-exposed verbatim — full
schema preserved (see bottom of file).

The ``get_*`` side is near-uniform: a single serial/registration identifier
(or list for portfolio workflows) in, ``ListEnvelope`` out. One ``get_trademark``
dispatcher folds all four TESS/TSDR fetch facets, narrowing the ``documents``
view to a single serial number (the only single-only source signature).
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.mcp.tools.trademarks import (
    get_trademark as _get_trademark,
)
from patent_client_agents.mcp.tools.trademarks import (
    get_trademark_documents,
    get_trademark_last_update,
    get_trademark_status,
    search_trademark_assignments,
)
from patent_client_agents.mcp.tools.trademarks import (
    search_trademarks as _search_trademarks,
)

trademarks_facade_mcp = FastMCP("Trademarks")


@trademarks_facade_mcp.tool(annotations=READ_ONLY)
async def search_trademarks(
    query: Annotated[
        str,
        "Search query — a wordmark, owner name, or goods/services description.",
    ],
    search_by: Annotated[
        Literal["wordmark", "owner", "goods_services"],
        "Which field to search. 'wordmark' (default) — trademark text; "
        "'owner' — registrant name; 'goods_services' — goods/services "
        "description.",
    ] = "wordmark",
    paginate_all: Annotated[
        bool,
        "When true, auto-paginates through all matching results "
        "(wordmark/owner only). Ignored for goods_services.",
    ] = False,
    max_results: Annotated[
        int,
        "Cap on total results when paginate_all=True.",
    ] = 500,
    full: Annotated[
        bool,
        "False (default) = lean stub per hit (serial, wordmark, owner, "
        "status, dates, registration number). True = full TESS record per "
        "hit (large; prefer get_trademark for one).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search USPTO trademarks by wordmark, owner, or goods/services (TESS).

    Returns lean stubs by default. Use ``get_trademark`` for a full record or
    current status by serial/registration number. For assignment recordations
    (reel/frame, assignor/assignee chains) use ``search_trademark_assignments``.

    Related tools: get_trademark, search_trademark_assignments.
    """
    return await _search_trademarks(
        query=query,
        search_by=search_by,
        paginate_all=paginate_all,
        max_results=max_results,
        full=full,
    )


@trademarks_facade_mcp.tool(annotations=READ_ONLY)
async def get_trademark(
    identifier: Annotated[
        str | list[str],
        "USPTO trademark serial number (8 digits, e.g. '97123456') or "
        "registration number (6-7 digits, e.g. '1234567'). Pass a list for "
        "portfolio workflows; the response shape stays a ListEnvelope. "
        "view='documents' accepts a single serial number only.",
    ],
    view: Annotated[
        Literal["record", "status", "documents", "last_update"],
        "Which facet to fetch. 'record' (default) = full TESS register record "
        "(wordmark, owner, goods/services, dates). 'status' = current TSDR "
        "status. 'documents' = TSDR prosecution documents (single serial). "
        "'last_update' = TSDR last-modified timestamp.",
    ] = "record",
) -> ListEnvelope[dict]:
    """Fetch one or more USPTO trademarks by serial or registration number.

    Always returns a ``ListEnvelope`` (stable shape for one id or many). For
    the full register record use view='record' (TESS); for current status,
    prosecution documents, or last-update timestamps use the TSDR views
    (status/documents/last_update). Find identifiers with ``search_trademarks``.

    Related tools: search_trademarks, search_trademark_assignments.
    """
    if view == "status":
        return await get_trademark_status(identifier)
    if view == "documents":
        if not isinstance(identifier, str):
            raise ValidationError(
                "get_trademark(view='documents') accepts a single serial number only, not a list."
            )
        return await get_trademark_documents(identifier)
    if view == "last_update":
        return await get_trademark_last_update(identifier)
    return await _get_trademark(identifier)


# Heterogeneous-signature search kept standalone (see module docstring): the
# assignment search has its own axis enum (assignee/assignor/serial/
# registration/reel_frame) and pagination shape (limit/start_row) that don't
# fold into search_trademarks without a fat optional-param bag that hurts
# routing. Re-expose it verbatim on the facade — full schema preserved.
trademarks_facade_mcp.tool(annotations=READ_ONLY)(search_trademark_assignments)
