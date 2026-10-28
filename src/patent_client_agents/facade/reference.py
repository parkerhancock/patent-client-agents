"""Consolidated classification, fees & copyright facade tools (public toolset).

Thin dispatchers over the per-source tool functions in
``patent_client_agents.mcp.tools.{cpc,fees,copyright}``. No business logic
lives here: each branch forwards to an existing function that already returns
the §5.9 envelope, so the §5.15 per-module helpers and the canonical templates
stay untouched.

Design note — each domain folds cleanly because the underlying functions share
one routing key per tool and the response is always a §5.9 envelope:

* ``classify_cpc`` (mode = search·lookup·map) — every CPC operation keys on a
  ``symbol`` (lookup/map) or a ``query`` (search); the optional mapping
  schemes only apply to mode='map'.
* ``get_fees`` (mode = schedule·lookup·jurisdictions) — all three key on a
  ``jurisdiction`` (jurisdictions takes none); the fee-filter params only
  apply to mode='lookup'.
* ``copyright`` (mode = search·get) — search keys on a ``query``, get keys on
  a ``public_records_id``; both return a ``ListEnvelope``.

Nothing here diverges enough to need verbatim re-exposure: each domain's
functions take a small, mode-scoped param set, so a single dispatcher with
mode-gated optional params keeps routing unambiguous.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope, ResponseEnvelope
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.mcp.tools.copyright import (
    get_copyright_record,
    search_copyright,
)
from patent_client_agents.mcp.tools.cpc import (
    lookup_cpc,
    map_cpc_classification,
    search_cpc,
)
from patent_client_agents.mcp.tools.fees import (
    FeeLookupEnvelope,
    get_fee_schedule,
    list_fee_jurisdictions,
    lookup_fee,
)

reference_facade_mcp = FastMCP("Classification, fees & copyright")


@reference_facade_mcp.tool(annotations=READ_ONLY)
async def classify_cpc(
    mode: Annotated[
        Literal["search", "lookup", "map"],
        "What to do. 'search' = find candidate CPC symbols by keyword. "
        "'lookup' = get the title/definition for one symbol you already have. "
        "'map' = cross-reference one symbol between schemes (CPC/IPC/USCLS).",
    ],
    query: Annotated[
        str | None,
        "mode='search': keyword(s) describing the technology area (e.g. "
        "'machine learning', 'lithium battery thermal management').",
    ] = None,
    symbol: Annotated[
        str | None,
        "mode='lookup'/'map': the CPC classification symbol (e.g. 'H04L9/32', 'G06F1/00').",
    ] = None,
    from_scheme: Annotated[
        str,
        "mode='map': source scheme — 'cpc', 'ipc', or 'uscls'.",
    ] = "cpc",
    to_scheme: Annotated[
        str,
        "mode='map': target scheme — 'cpc', 'ipc', or 'uscls'.",
    ] = "ipc",
    range_begin: Annotated[int, "mode='search': start of result range (1-indexed)."] = 1,
    range_end: Annotated[int, "mode='search': end of result range."] = 10,
    full: Annotated[
        bool,
        "mode='search': False (default) = lean stub per hit (symbol + title + "
        "parent). True = full upstream record (match percentage, title parts).",
    ] = False,
) -> ResponseEnvelope[dict] | ListEnvelope[dict]:
    """Work with CPC (Cooperative Patent Classification) codes — search, look up, or map them.

    Routes by ``mode``: 'search' finds candidate symbols by keyword (returns a
    ranked list); 'lookup' returns one symbol's official title and hierarchy;
    'map' cross-references one symbol between CPC, IPC, and the US
    Classification System. Find a symbol with mode='search' first, then
    mode='lookup' to read it or mode='map' to translate it.

    Related tools: get_fees.
    """
    if mode == "lookup":
        if not symbol:
            raise ValueError("classify_cpc(mode='lookup') requires symbol.")
        return await lookup_cpc(symbol=symbol)
    if mode == "map":
        if not symbol:
            raise ValueError("classify_cpc(mode='map') requires symbol.")
        return await map_cpc_classification(
            symbol=symbol,
            from_scheme=from_scheme,
            to_scheme=to_scheme,
        )
    if not query:
        raise ValueError("classify_cpc(mode='search') requires query.")
    return await search_cpc(
        query=query,
        range_begin=range_begin,
        range_end=range_end,
        full=full,
    )


@reference_facade_mcp.tool(annotations=READ_ONLY)
async def get_fees(
    mode: Annotated[
        Literal["schedule", "lookup", "jurisdictions"],
        "What to do. 'schedule' = the full published fee schedule for one "
        "office. 'lookup' = filter a schedule down to matching line items. "
        "'jurisdictions' = list which (office, right) schedules are available.",
    ],
    jurisdiction: Annotated[
        str | None,
        "mode='schedule'/'lookup': office or jurisdiction — 'USPTO', 'US', "
        "'EPO', 'EUIPO', or 'EP'. Not used for mode='jurisdictions'.",
    ] = None,
    right: Annotated[
        str,
        "mode='schedule'/'lookup': which IP right's schedule — 'patent' "
        "(default), 'trademark', or 'design'.",
    ] = "patent",
    category: Annotated[
        str | None,
        "mode='lookup': filter to one fee category ('filing', 'search', "
        "'examination', 'grant', 'renewal', 'maintenance', 'excess_claims', "
        "'extension', 'appeal', 'petition', 'opposition'). None = every category.",
    ] = None,
    tier: Annotated[
        str,
        "mode='lookup': entity-tier filter for offices with discounts (USPTO "
        "patents + designs). 'large' (default), 'small', or 'micro'. Ignored "
        "on schedules with no tier dimension.",
    ] = "large",
    year: Annotated[
        int | None,
        "mode='lookup': required when filtering renewal/maintenance fees "
        "(USPTO maintenance: 4, 8, 12; EPO renewals: 2-20; EUIPO design "
        "renewals: 5, 10, 15, 20; TM renewals: 10). None excludes "
        "renewal/maintenance rows.",
    ] = None,
    refresh: Annotated[bool, "Force USPTO source revalidation for schedule/lookup."] = False,
) -> ResponseEnvelope[dict] | FeeLookupEnvelope | ListEnvelope[dict]:
    """Get patent, trademark, and design fees from the USPTO, EPO, and EUIPO.

    Routes by ``mode``: 'schedule' returns one office's full published fee
    schedule; 'lookup' filters a schedule down to line items matching a
    category/tier/year; 'jurisdictions' lists every available (office, right)
    schedule so you know what to ask for. Discover with mode='jurisdictions'
    first, then mode='schedule' or mode='lookup'.

    Related tools: classify_cpc.
    """
    if mode == "schedule":
        if not jurisdiction:
            raise ValueError("get_fees(mode='schedule') requires jurisdiction.")
        return await get_fee_schedule(
            jurisdiction=jurisdiction, right=right, **({"refresh": True} if refresh else {})
        )
    if mode == "lookup":
        if not jurisdiction:
            raise ValueError("get_fees(mode='lookup') requires jurisdiction.")
        return await lookup_fee(
            jurisdiction=jurisdiction,
            category=category,
            tier=tier,
            year=year,
            right=right,
            **({"refresh": True} if refresh else {}),
        )
    if refresh:
        raise ValueError("refresh requires mode=schedule or lookup")
    return await list_fee_jurisdictions()


@reference_facade_mcp.tool(annotations=READ_ONLY)
async def copyright(
    mode: Annotated[
        Literal["search", "get"],
        "What to do. 'search' = find U.S. Copyright Office registrations by "
        "keyword. 'get' = fetch one or more full records by Public Records id.",
    ],
    query: Annotated[
        str | None,
        "mode='search': a title, a claimant/author name, a registration "
        "number (e.g. 'TX 1234567'), or any keyword.",
    ] = None,
    public_records_id: Annotated[
        str | list[str] | None,
        "mode='get': the opaque Public Records id from a search hit's "
        "``public_records_id`` field (NOT a registration number). Single id "
        "or a list for portfolio workflows. Examples: 'voyager_12345'.",
    ] = None,
    field: Annotated[
        str,
        "mode='search': which field to search — 'keyword' (default, all "
        "fields), 'title', or 'name' (claimant/author).",
    ] = "keyword",
    page: Annotated[int, "mode='search': page number (1-based)."] = 1,
    page_size: Annotated[int, "mode='search': results per page (default 10, max ~50)."] = 10,
    full: Annotated[
        bool,
        "mode='search': False (default) = lean stub per hit. True = full "
        "upstream record (every title/claimant/date/class, relevance score).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search U.S. Copyright Office registrations and recorded documents, or fetch one by id.

    Routes by ``mode``: 'search' finds registrations and recorded documents
    (transfers, assignments, licenses) by keyword and returns lean stubs;
    'get' fetches the full record(s) for a Public Records id. Both return a
    ``ListEnvelope``. Search first, then pass a hit's ``public_records_id`` to
    mode='get'.

    Related tools: classify_cpc, get_fees.
    """
    if mode == "get":
        if public_records_id is None:
            raise ValueError("copyright(mode='get') requires public_records_id.")
        return await get_copyright_record(public_records_id=public_records_id)
    if not query:
        raise ValueError("copyright(mode='search') requires query.")
    return await search_copyright(
        query=query,
        field=field,
        page=page,
        page_size=page_size,
        full=full,
    )
