"""Consolidated litigation & administrative-proceedings facade tools (public toolset).

Thin dispatchers over the per-forum tool functions in
``patent_client_agents.mcp.tools.{uspto,cafc,usitc,upc}``. No business logic
lives here: each branch forwards to an existing function that already returns
the §5.9 envelope, so the §5.15 per-module helpers and canonical templates stay
untouched.

Design note — this is the most heterogeneous domain (PTAB, CAFC, USITC, UPC),
so only homogeneous signatures fold; everything else is re-exposed verbatim
(EPO-facade precedent).

* ``search_litigation`` folds only the *free-text-query* searches that share a
  ``query``/``limit``/``full`` core: PTAB (``type`` picks record kind) and CAFC
  opinions (``patent_only`` flag). The other four "searches" are pure
  structured-filter queries with **no** query axis — UPC decisions paginate by
  filter-IDs; USITC investigations and USITC documents take distinct filter
  bags; CAFC patent-opinions takes a date range. Folding those would need a fat
  optional-param bag that reintroduces the argument-shape ambiguity this
  consolidation exists to remove, so each is re-exposed verbatim.
* ``get_litigation`` folds the three uniform fetchers — PTAB, USITC
  investigation, UPC decision — that are all single-identifier-in,
  ``ListEnvelope``-out (PTAB additionally takes ``type`` for the record kind).
* The ``list_*`` metadata tools (PTAB children, USITC attachments / IDS, UPC
  divisions / languages) each have a distinct argument shape — hierarchical
  parent lookup, document-id lookup, filter bag, and no-arg vocabulary
  enumerators respectively. They don't collapse into one ``detail`` mode
  without an ambiguous param bag, so the smallest honest surface is to
  re-expose them verbatim. ``list_upc_instruments`` is excluded: it enumerates
  the UPC *statutes* corpus, which lives in the legal-references facade
  alongside ``search_upc_statutes`` / ``get_upc_section``.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.mcp.tools.cafc import (
    search_cafc_opinions,
    search_cafc_patent_opinions,
)
from patent_client_agents.mcp.tools.upc import (
    get_upc_decision,
    search_upc_decisions,
)
from patent_client_agents.mcp.tools.usitc import (
    get_usitc_investigation,
    list_usitc_attachments,
    search_usitc_documents,
    search_usitc_investigations,
)
from patent_client_agents.mcp.tools.uspto import (
    get_ptab,
    list_ptab_children,
    search_ptab,
)
from patent_client_agents.usitc.utils import get_env_token

litigation_facade_mcp = FastMCP("Litigation")

# USITC EDIS is gated on USITC_EDIS_TOKEN or USITC_EDIS_TOKEN_FILE upstream (see
# patent_client_agents.mcp.tools.usitc) so the public demo at
# mcp.patentclient.com advertises no ITC surface. The facade MUST mirror
# that gate rather than inherit it: ``conditional_tool`` suppresses
# registration on ``usitc_mcp``, but the underlying functions stay
# importable by design, so the verbatim re-exports below would put ITC
# back on the public surface through the facade. The ``get_litigation``
# forum enum is built to match — offering forum='usitc' when the EDIS
# tools are absent would route agents into a dead branch.
EDIS_ENABLED = bool(get_env_token("USITC_EDIS_TOKEN"))

if EDIS_ENABLED:
    _LitigationForum = Literal["ptab", "usitc", "upc"]
    _FORUM_DESC = (
        "Which tribunal the identifier names. 'ptab' = USPTO Patent Trial and "
        "Appeal Board record. 'usitc' = U.S. International Trade Commission "
        "Section 337 investigation. 'upc' = Unified Patent Court decision."
    )
    _IDENTIFIER_DESC = (
        "The record identifier, or a list for portfolio workflows. By forum: "
        "ptab → trial number (e.g. 'IPR2024-00001') or a document identifier "
        "for non-proceeding ptab_type; usitc → investigation number in EDIS "
        "format (e.g. '337-1234', without the 'TA-' infix); upc → canonical "
        "case id (e.g. 'UPC_CFI_1747/2025', 'UPC_CoA_335/2023')."
    )
else:
    _LitigationForum = Literal["ptab", "upc"]
    _FORUM_DESC = (
        "Which tribunal the identifier names. 'ptab' = USPTO Patent Trial and "
        "Appeal Board record. 'upc' = Unified Patent Court decision."
    )
    _IDENTIFIER_DESC = (
        "The record identifier, or a list for portfolio workflows. By forum: "
        "ptab → trial number (e.g. 'IPR2024-00001') or a document identifier "
        "for non-proceeding ptab_type; upc → canonical case id "
        "(e.g. 'UPC_CFI_1747/2025', 'UPC_CoA_335/2023')."
    )


@litigation_facade_mcp.tool(annotations=READ_ONLY)
async def search_litigation(
    forum: Annotated[
        Literal["ptab", "cafc"],
        "Which tribunal's free-text index to search. 'ptab' = USPTO Patent "
        "Trial and Appeal Board records (AIA trials, ex parte appeals, pre-AIA "
        "interferences). 'cafc' = U.S. Court of Appeals for the Federal Circuit "
        "opinions and orders. For UPC decisions or CAFC patent-only-by-date "
        "use the dedicated structured-filter tools.",
    ],
    query: Annotated[str, "Free-text search query."],
    limit: Annotated[int, "Maximum source rows per page (CAFC: 1-100)."] = 25,
    full: Annotated[
        bool,
        "False (default) = lean stub per hit (small). True = full record per "
        "hit (large; prefer get_litigation for a single record).",
    ] = False,
    ptab_type: Annotated[
        Literal[
            "proceeding",
            "trial_decision",
            "trial_document",
            "appeal_decision",
            "interference_decision",
        ],
        "forum='ptab' only: which PTAB record kind to search. 'proceeding' = "
        "AIA trials (IPR/PGR/CBM/DER); 'trial_decision'/'trial_document' = "
        "filings in those trials; 'appeal_decision' = ex parte appeals; "
        "'interference_decision' = pre-AIA interferences.",
    ] = "proceeding",
    patent_only: Annotated[
        bool,
        "forum='cafc' only: case-name heuristic; can miss patent cases.",
    ] = False,
    offset: Annotated[int, "Number of source records to skip (PTAB or CAFC)."] = 0,
    next_cursor: Annotated[
        str | None,
        "Continuation from the previous response; overrides offset and limit. "
        "Keep forum, query, ptab_type, and patent_only unchanged.",
    ] = None,
) -> ListEnvelope[dict]:
    """Search a patent tribunal's records by free text — PTAB proceedings/decisions or Federal Circuit opinions.

    Routes to the right tribunal by ``forum``. Only the two free-text
    searches fold here; for UPC decisions or Federal Circuit
    patent-opinions-by-date use the dedicated ``search_upc_decisions`` /
    ``search_cafc_patent_opinions``. For one record by identifier use
    ``get_litigation``.

    Related tools: get_litigation, search_upc_decisions,
    search_cafc_patent_opinions.
    """
    if forum == "ptab":
        return await search_ptab(
            type=ptab_type,
            query=query,
            limit=limit,
            full=full,
            offset=offset,
            next_cursor=next_cursor,
        )
    return await search_cafc_opinions(
        query=query,
        patent_only=patent_only,
        limit=limit,
        full=full,
        offset=offset,
        next_cursor=next_cursor,
    )


@litigation_facade_mcp.tool(annotations=READ_ONLY)
async def get_litigation(
    forum: Annotated[_LitigationForum, _FORUM_DESC],
    identifier: Annotated[str | list[str], _IDENTIFIER_DESC],
    ptab_type: Annotated[
        Literal[
            "proceeding",
            "trial_decision",
            "trial_document",
            "appeal_decision",
            "interference_decision",
        ],
        "forum='ptab' only: what the identifier names. 'proceeding' takes a "
        "trial number; the others take a document identifier from "
        "search_litigation(forum='ptab').",
    ] = "proceeding",
) -> ListEnvelope[dict]:
    """Fetch one tribunal record by identifier — a PTAB record, USITC investigation, or UPC decision.

    Always returns a ``ListEnvelope`` (stable shape whether you pass one id
    or many). Find identifiers with ``search_litigation`` (PTAB/CAFC) or the
    structured-filter search ``search_upc_decisions``. For child records of a
    PTAB trial use ``list_ptab_children``.

    Related tools: search_litigation, list_ptab_children, search_upc_decisions.
    """
    if forum == "ptab":
        return await get_ptab(type=ptab_type, identifier=identifier)
    if forum == "usitc":
        return await get_usitc_investigation(investigation_number=identifier)
    return await get_upc_decision(case_id=identifier)


# Heterogeneous searches kept standalone (see module docstring): UPC decisions,
# USITC investigations, and USITC documents are pure structured-filter queries
# with no shared free-text ``query`` axis; CAFC patent-opinions filters by date
# range. Folding them into search_litigation needs a fat optional-param bag that
# hurts routing. Re-expose verbatim — full schema preserved.
litigation_facade_mcp.tool(annotations=READ_ONLY)(search_cafc_patent_opinions)
litigation_facade_mcp.tool(annotations=READ_ONLY)(search_upc_decisions)
if EDIS_ENABLED:
    litigation_facade_mcp.tool(annotations=READ_ONLY)(search_usitc_investigations)
    litigation_facade_mcp.tool(annotations=READ_ONLY)(search_usitc_documents)

# Per-record sub-resource navigation lists kept on the public surface: each
# takes a parent record id and enumerates its children. list_usitc_attachments
# feeds download_document(source='usitc_attachment'); list_ptab_children
# navigates related PTAB proceedings. Re-expose verbatim — full schema preserved.
litigation_facade_mcp.tool(annotations=READ_ONLY)(list_ptab_children)
if EDIS_ENABLED:
    litigation_facade_mcp.tool(annotations=READ_ONLY)(list_usitc_attachments)

# Gated OFF the curated facade (still present in the full ``ip_mcp``
# build): global-vocabulary / niche discovery enumerators — list_ids_investigations
# (IDS filter query), list_upc_divisions / list_upc_languages (fixed UPC
# vocabularies whose valid values belong in the UPC search tools' param docs),
# and list_upc_instruments (UPC statute vocabulary). Low-signal on a curated
# directory surface; power users reach them via the full build.
