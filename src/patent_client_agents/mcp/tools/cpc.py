"""CPC (Cooperative Patent Classification) MCP tools.

CPC is the classification vocabulary used to index the patent register.
Per ``coverage/sources.yaml`` it's ``category: registered_ip``, served live
via EPO OPS (the EPO and USPTO jointly maintain the scheme). Provenance
points at ``https://ops.epo.org/3.2/rest-services/classification/...`` so
an attorney can verify a title or mapping against the upstream OPS endpoint.
"""

from __future__ import annotations

from typing import Annotated, Any, cast

from fastmcp import FastMCP

from law_tools_core.envelope import (
    ListEnvelope,
    ResponseEnvelope,
    make_provenance,
)
from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.cpc import map_classification
from patent_client_agents.epo_ops.client import client_from_env

cpc_mcp = FastMCP("CPC")


def _dump(obj: object) -> dict[str, Any]:
    """Serialize a Pydantic model to a dict (or pass through dicts)."""
    if hasattr(obj, "model_dump"):
        return cast("dict[str, Any]", obj.model_dump())  # type: ignore[union-attr]  # ty: ignore[call-non-callable]
    if isinstance(obj, dict):
        return cast("dict[str, Any]", obj)
    raise TypeError(f"_dump expected a Pydantic model or dict, got {type(obj).__name__}")


# ---------------------------------------------------------------------------
# CPC — envelope helpers
# ---------------------------------------------------------------------------

_CPC_BASE = "https://ops.epo.org/3.2"
_CPC_NAME = "Cooperative Patent Classification (CPC)"


def _cpc_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{base}{path}`` on EPO OPS."""
    return make_provenance(source_url=f"{_CPC_BASE}{path}", source_name=_CPC_NAME)


def _first_cpc_item(payload: dict) -> dict | None:
    """Return the first CPC classification item from a retrieval payload, if any."""
    scheme = payload.get("scheme") or {}
    items = scheme.get("items") or []
    if items and isinstance(items, list):
        return items[0]
    return None


def _summarize_cpc_retrieval(symbol: str, payload: dict) -> str:
    """One-line Markdown summary for a CPC retrieval (lookup) response."""
    item = _first_cpc_item(payload) or {}
    title = item.get("title") or "(no title)"
    resolved = item.get("symbol") or symbol
    head = f"**CPC {resolved}** — {title}"
    extras: list[str] = []
    level = item.get("level")
    if level is not None:
        extras.append(f"level {level}")
    if item.get("not_allocatable"):
        extras.append("not allocatable")
    if item.get("breakdown_code"):
        extras.append("breakdown code")
    if extras:
        return f"{head} ({', '.join(extras)})."
    return f"{head}."


def _stub_cpc_search_hit(record: dict) -> dict:
    """Lean projection of a CPC search hit (§5.5): symbol, title, parent symbol."""
    symbol = record.get("classification_symbol")
    parent: str | None = None
    if isinstance(symbol, str) and "/" in symbol:
        # Parent is the symbol with the trailing group removed (e.g.
        # 'H04L9/32' -> 'H04L9/00', the parent main group).
        head = symbol.split("/", 1)[0]
        parent = f"{head}/00" if not symbol.endswith("/00") else None
    return {
        "symbol": symbol,
        "title": record.get("title"),
        "parent_symbol": parent,
    }


def _summarize_cpc_mapping(symbol: str, from_scheme: str, to_scheme: str, payload: dict) -> str:
    """One-line Markdown summary for a CPC ↔ IPC/USCLS mapping response."""
    mappings = payload.get("mappings") or []
    targets: list[str] = []
    target_key = to_scheme.lower()
    for m in mappings:
        if not isinstance(m, dict):
            continue
        val = m.get(target_key) or m.get("ipc") or m.get("cpc") or m.get("ecla")
        if val and val not in targets:
            targets.append(str(val))
    head = f"**CPC mapping {symbol}** ({from_scheme.upper()} → {to_scheme.upper()})"
    if targets:
        return f"{head}: {', '.join(targets)}."
    return f"{head}: no cross-reference found."


# ---------------------------------------------------------------------------
# CPC — MCP tools
# ---------------------------------------------------------------------------


@cpc_mcp.tool(annotations=READ_ONLY)
async def lookup_cpc(
    symbol: Annotated[
        str,
        "CPC classification symbol (e.g. 'H04L9/32', 'G06F1/00'). "
        "Format: section letter + class + subclass + main group + '/' + subgroup.",
    ],
) -> ResponseEnvelope[dict]:
    """Look up the title and definition for a CPC symbol (e.g., 'G06F1/00').

    Returns the official title for one CPC classification symbol plus its
    hierarchy (level, children, ``not_allocatable`` / ``breakdown_code``
    flags). Use this when an agent has a symbol in hand and needs to
    explain what it covers.

    To go the other direction — finding candidate symbols for a technology
    area — use ``search_cpc``. To translate between CPC and IPC (or USCLS),
    use ``map_cpc_classification``.

    Related tools: search_cpc, map_cpc_classification.
    """
    async with client_from_env() as client:
        result = await client.retrieve_cpc(symbol=symbol)

    payload: dict = _dump(result)  # type: ignore[assignment]
    return ResponseEnvelope[dict](
        summary=_summarize_cpc_retrieval(symbol, payload),
        details=payload,
        provenance=_cpc_provenance(f"/rest-services/classification/cpc/{symbol}"),
    )


@cpc_mcp.tool(annotations=READ_ONLY)
async def search_cpc(
    query: Annotated[
        str,
        "Keyword(s) describing the technology area (e.g. 'machine learning', "
        "'lithium battery thermal management').",
    ],
    range_begin: Annotated[int, "Start of result range (1-indexed)."] = 1,
    range_end: Annotated[int, "End of result range."] = 10,
    full: Annotated[
        bool,
        "When False (default), each hit is a lean stub: symbol + title + "
        "parent symbol — enough to triage candidate CPC classes. When True, "
        "every hit carries the full upstream record (percentage match, "
        "structured title parts).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search CPC titles by keyword to find candidate symbols for a technology area.

    Returns ranked CPC classification hits matching the query, with each
    hit's symbol, title, and parent symbol by default. Pass ``full=True``
    for the upstream-shaped row (includes the match percentage). Once an
    agent picks a symbol from the result list, call ``lookup_cpc`` for
    its definition or ``map_cpc_classification`` to cross-reference it.

    Related tools: lookup_cpc, map_cpc_classification.
    """
    async with client_from_env() as client:
        result = await client.search_cpc(query=query, range_begin=range_begin, range_end=range_end)

    payload: dict = _dump(result)  # type: ignore[assignment]
    raw_results = list(payload.get("results") or [])
    items = raw_results if full else [_stub_cpc_search_hit(r) for r in raw_results]
    total = payload.get("total_results")
    shown = len(items)
    more = bool(total and shown + (range_begin - 1) < int(total))
    summary_total = f"{shown} of {total} hits" if total else f"{shown} hits"
    return ListEnvelope[dict](
        summary=f"CPC search — `{query}`: {summary_total}.",
        items=items,
        more_available=more,
        next_cursor=None,
        provenance=_cpc_provenance("/rest-services/classification/cpc/search"),
    )


@cpc_mcp.tool(annotations=READ_ONLY)
async def map_cpc_classification(
    symbol: Annotated[
        str,
        "Classification symbol to map (e.g. 'H04L9/32', 'G06F1/00').",
    ],
    from_scheme: Annotated[
        str,
        "Source scheme: 'cpc', 'ipc', or 'uscls'.",
    ],
    to_scheme: Annotated[
        str,
        "Target scheme: 'cpc', 'ipc', or 'uscls'.",
    ],
) -> ResponseEnvelope[dict]:
    """Convert a CPC symbol to its IPC equivalent and related cross-references.

    Uses EPO OPS concordance data to translate one classification symbol
    between schemes — typically CPC ↔ IPC, occasionally to/from the US
    Classification System. Returns the structured mapping(s) found; an
    empty ``mappings`` list means upstream had no cross-reference for
    this symbol.

    Use ``lookup_cpc`` first if you need to confirm what the source
    symbol covers, or ``search_cpc`` to find candidate symbols by
    keyword before mapping.

    Related tools: lookup_cpc, search_cpc.
    """
    result = await map_classification(
        input_schema=from_scheme,
        symbol=symbol,
        output_schema=to_scheme,
    )
    payload: dict = _dump(result)  # type: ignore[assignment]
    path = f"/rest-services/classification/map/{from_scheme.lower()}/{symbol}/{to_scheme.lower()}"
    return ResponseEnvelope[dict](
        summary=_summarize_cpc_mapping(symbol, from_scheme, to_scheme, payload),
        details=payload,
        provenance=_cpc_provenance(path),
    )
