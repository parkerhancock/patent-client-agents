"""CanLII (Canadian Legal Information Institute) MCP tools.

Read-only access to Canadian courts / tribunals / statutes / regulations
via the CanLII REST API. Env-gated: tools only register when
``CANLII_API_KEY`` is set (matches the JPO env-gating pattern).

CONNECTOR_STANDARDS.md classification: ``category=substantive_law``,
``transport=mcp_proxy``, ``update_strategy=live_proxy`` (per
``coverage/sources.yaml``). Live-proxy substantive-law connectors carry
the standard provenance fields only — ``corpus_synced_at`` /
``corpus_version`` are reserved for ``mcp_local`` corpora.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, cast

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.exceptions import ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
from law_tools_core.mcp.conditional import conditional_tool
from patent_client_agents.canlii import (
    BrowseCasesInput,
    BrowseLegislationInput,
    CanLIIClient,
    GetCaseInput,
    GetCitatorInput,
    GetLegislationInput,
    Language,
)

canlii_mcp = FastMCP("CanLII")

_CANLII_REQUIRED_ENV: list[str] = ["CANLII_API_KEY"]

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). CanLII is substantive
# law served by live proxy (§4 / coverage/sources.yaml), so provenance
# carries the standard fields only — no corpus_synced_at / corpus_version.
# ──────────────────────────────────────────────────────────────────────

_CANLII_BASE = "https://api.canlii.org"
_CANLII_NAME = "CanLII (Canadian Legal Information Institute)"

# Bounded fan-out for list-accepting get_canlii_case / get_canlii_legislation
# (§5.4). CanLII is rate-limited; 5 concurrent fetches keeps headroom while
# still parallelizing portfolio workflows.
_CANLII_FANOUT_CONCURRENCY = 5


def _canlii_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{base}{path}``."""
    return make_provenance(
        source_url=f"{_CANLII_BASE}{path}",
        source_name=_CANLII_NAME,
    )


def _dump(obj: object) -> dict[str, Any]:
    """Serialize a Pydantic model to a dict (or pass through dicts).

    Every caller passes a Pydantic model from the upstream client; the
    fallback exists to be defensive if a dict slips through. Typed as
    ``dict[str, Any]`` so call sites can use ``.get(...)`` without
    per-call narrowing.
    """
    if hasattr(obj, "model_dump"):
        return cast("dict[str, Any]", obj.model_dump())  # type: ignore[union-attr]  # ty: ignore[call-non-callable]
    if isinstance(obj, dict):
        return cast("dict[str, Any]", obj)
    raise TypeError(f"_dump expected a Pydantic model or dict, got {type(obj).__name__}")


def _stub_case_ref(record: dict) -> dict:
    """Lean projection of a CanLII case-list row (§5.5).

    Surfaces ~5 scalars an agent can quote without paging the full record:
    case_id (language-scoped), citation, title (style of cause), database,
    and (when present) jurisdiction. The full record carries decision date
    and keywords too; use ``get_canlii_case`` for those.
    """
    case_id_obj = record.get("case_id") or record.get("caseId") or {}
    if isinstance(case_id_obj, dict):
        case_id = case_id_obj.get("en") or case_id_obj.get("fr")
    else:
        case_id = case_id_obj
    return {
        "case_id": case_id,
        "citation": record.get("citation"),
        "title": record.get("title"),
        "database_id": record.get("database_id") or record.get("databaseId"),
    }


def _stub_legislation_ref(record: dict) -> dict:
    """Lean projection of a CanLII legislation-list row (§5.5)."""
    return {
        "legislation_id": record.get("legislation_id") or record.get("legislationId"),
        "title": record.get("title"),
        "citation": record.get("citation"),
        "type": record.get("type"),
        "database_id": record.get("database_id") or record.get("databaseId"),
    }


def _summarize_case(record: dict) -> str:
    """One-line Markdown summary of a single CanLII case-metadata record."""
    case_id = record.get("case_id") or record.get("caseId") or "(no case_id)"
    citation = record.get("citation") or "(no citation)"
    title = record.get("title") or "(no title)"
    decision_date = record.get("decision_date") or record.get("decisionDate")
    head = f"**CanLII {citation}** — {title}"
    line = f"Case ID: {case_id}."
    if decision_date:
        line += f" Decision date: {decision_date}."
    return f"{head}\n{line}"


def _summarize_legislation(record: dict) -> str:
    """One-line Markdown summary of a single CanLII legislation record."""
    leg_id = record.get("legislation_id") or record.get("legislationId") or "(no id)"
    title = record.get("title") or "(no title)"
    citation = record.get("citation") or ""
    leg_type = record.get("type") or "(unknown type)"
    repealed = record.get("repealed")
    head = f"**CanLII {leg_id}** — {title}"
    parts: list[str] = [f"Type: {leg_type}"]
    if citation:
        parts.append(f"Cite: {citation}")
    if repealed:
        parts.append(f"Repealed: {repealed}")
    return f"{head}\n{'. '.join(parts)}."


# ---------------------------------------------------------------------------
# Discovery (vocabulary enumerators — list_* per §5.8)
# ---------------------------------------------------------------------------


@conditional_tool(canlii_mcp, requires_env=_CANLII_REQUIRED_ENV, annotations=READ_ONLY)
async def list_canlii_case_databases(
    language: Annotated[Language, "Output language: 'en' or 'fr'"] = "en",
) -> ListEnvelope[dict]:
    """List every court / tribunal database CanLII (Canadian Legal Information Institute) indexes.

    Returns a flat list of ``{database_id, jurisdiction, name}``. IP-relevant
    examples: ``fct`` (Federal Court), ``fca`` (Federal Court of Appeal),
    ``csc-scc`` (Supreme Court of Canada), ``tmob-comc`` (Trade-marks
    Opposition Board), ``cab-cab`` (Commissioner of Patents — Patent Appeal
    Board). Pass any returned ``database_id`` to ``search_canlii_cases``.

    Related tools: search_canlii_cases, get_canlii_case,
    list_canlii_legislation_databases.
    """
    async with CanLIIClient() as client:
        response = await client.list_case_databases(language=language)
    items = [_dump(db) for db in response.case_databases]
    return ListEnvelope[dict](
        summary=f"CanLII case databases ({language}): {len(items)} courts / tribunals.",
        items=items,
        provenance=_canlii_provenance(f"/v1/caseBrowse/{language}/"),
    )


@conditional_tool(canlii_mcp, requires_env=_CANLII_REQUIRED_ENV, annotations=READ_ONLY)
async def list_canlii_legislation_databases(
    language: Annotated[Language, "Output language: 'en' or 'fr'"] = "en",
) -> ListEnvelope[dict]:
    """List every legislation database (statutes / regulations) CanLII indexes.

    IP-relevant examples: ``cas`` (federal statutes — the Patent Act lives
    here as ``rsc-1985-c-p-4``; the Trademarks Act as ``rsc-1985-c-t-13``),
    ``car`` (federal regulations). Pass any returned ``database_id`` to
    ``search_canlii_legislation``.

    Related tools: search_canlii_legislation, get_canlii_legislation,
    list_canlii_case_databases.
    """
    async with CanLIIClient() as client:
        response = await client.list_legislation_databases(language=language)
    items = [_dump(db) for db in response.legislation_databases]
    return ListEnvelope[dict](
        summary=f"CanLII legislation databases ({language}): {len(items)} databases.",
        items=items,
        provenance=_canlii_provenance(f"/v1/legislationBrowse/{language}/"),
    )


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


@conditional_tool(canlii_mcp, requires_env=_CANLII_REQUIRED_ENV, annotations=READ_ONLY)
async def search_canlii_cases(
    database_id: Annotated[str, "CanLII database code (e.g. 'fct', 'tmob-comc')"],
    offset: Annotated[int, "Record number to start from (0 = most recent)"] = 0,
    result_count: Annotated[int, "Page size (1-10000)"] = 100,
    language: Annotated[Language, "'en' or 'fr'"] = "en",
    published_after: Annotated[
        str | None, "ISO date YYYY-MM-DD — only return docs published on/after this date"
    ] = None,
    published_before: Annotated[str | None, "ISO date YYYY-MM-DD"] = None,
    decision_date_after: Annotated[
        str | None,
        "ISO date YYYY-MM-DD — only return decisions handed down on/after this date",
    ] = None,
    decision_date_before: Annotated[str | None, "ISO date YYYY-MM-DD"] = None,
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: case_id, "
        "citation, title (style of cause), database_id. When True, returns "
        "the upstream CaseRef shape (which adds the language-scoped CaseId "
        "object); for full case metadata (decision date, keywords, URL), "
        "call ``get_canlii_case``.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search a CanLII (Canadian Legal Information Institute) database, newest first.

    Filter-driven listing of court / tribunal decisions in one CanLII
    database. Use ``list_canlii_case_databases`` to discover
    ``database_id`` values. Date filters are optional and can be combined
    (e.g. ``decision_date_after`` + ``decision_date_before`` for a window).
    Pass any hit's ``case_id`` to ``get_canlii_case`` for full metadata
    (decision date, docket number, keywords, canonical URL).

    Related tools: get_canlii_case, list_canlii_case_databases,
    get_canlii_cited_cases, get_canlii_citing_cases.
    """
    params = BrowseCasesInput(
        database_id=database_id,
        offset=offset,
        result_count=result_count,
        language=language,
        published_after=published_after,
        published_before=published_before,
        decision_date_after=decision_date_after,
        decision_date_before=decision_date_before,
    )
    async with CanLIIClient() as client:
        response = await client.browse_cases(**params.model_dump())

    dumped = _dump(response)
    raw_cases = list(dumped.get("cases") or [])
    items = raw_cases if full else [_stub_case_ref(c) for c in raw_cases]
    return ListEnvelope[dict](
        summary=(
            f"CanLII cases — database `{database_id}` ({language}): "
            f"{len(items)} hit{'s' if len(items) != 1 else ''}."
        ),
        items=items,
        more_available=len(raw_cases) == result_count,
        next_cursor=None,
        provenance=_canlii_provenance(f"/v1/caseBrowse/{language}/{database_id}/"),
    )


@conditional_tool(canlii_mcp, requires_env=_CANLII_REQUIRED_ENV, annotations=READ_ONLY)
async def get_canlii_case(
    database_id: Annotated[str, "CanLII database code (e.g. 'csc-scc' for Supreme Court)"],
    case_id: Annotated[
        str | list[str],
        "CanLII case identifier (e.g. '2008scc9'), or a list of identifiers for "
        "portfolio workflows. Examples: '2008scc9', ['2008scc9', '2020fca100']. "
        "When a list is supplied, each entry resolves against the same "
        "``database_id`` (use separate calls if your portfolio spans multiple "
        "databases).",
    ],
    language: Annotated[Language, "'en' or 'fr'"] = "en",
) -> ListEnvelope[dict]:
    """Get CanLII (Canadian Legal Information Institute) case metadata by case_id.

    Returns title (style of cause), citation, docket number, decision
    date, keywords, and a canonical CanLII landing-page ``url`` per
    case. Does not return the full opinion text — follow the ``url``
    for the rendered decision. Accepts either a single ``case_id`` or
    a list (§5.4); the response is always a ListEnvelope so the shape
    is stable. Bounded concurrent fan-out internally; order matches
    the input.

    Related tools: search_canlii_cases, get_canlii_cited_cases,
    get_canlii_citing_cases, get_canlii_cited_legislations.
    """
    ids = [case_id] if isinstance(case_id, str) else list(case_id)
    if not ids:
        raise ValidationError("get_canlii_case requires at least one case_id")

    semaphore = asyncio.Semaphore(_CANLII_FANOUT_CONCURRENCY)

    async def _fetch_one(client: CanLIIClient, cid: str) -> dict:
        async with semaphore:
            params = GetCaseInput(database_id=database_id, case_id=cid, language=language)
            return _dump(await client.get_case(**params.model_dump()))  # type: ignore[return-value]

    async with CanLIIClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, cid) for cid in ids])

    if len(results) == 1:
        summary = _summarize_case(results[0])
        path = f"/v1/caseBrowse/{language}/{database_id}/{ids[0]}/"
    else:
        summary = (
            f"Fetched {len(results)} CanLII cases from `{database_id}` "
            f"({language}): {', '.join(ids)}"
        )
        path = f"/v1/caseBrowse/{language}/{database_id}/"

    return ListEnvelope[dict](
        summary=summary,
        items=results,
        provenance=_canlii_provenance(path),
    )


# ---------------------------------------------------------------------------
# Citator
# ---------------------------------------------------------------------------


@conditional_tool(canlii_mcp, requires_env=_CANLII_REQUIRED_ENV, annotations=READ_ONLY)
async def get_canlii_cited_cases(
    database_id: Annotated[str, "CanLII database code"],
    case_id: Annotated[str, "CanLII case identifier"],
) -> ListEnvelope[dict]:
    """List cases that ``case_id`` cites (CanLII citator, English-only).

    Returns each cited case as a lean reference (case_id, citation,
    title, database_id). Pass any returned ``case_id`` to
    ``get_canlii_case`` for full metadata. The CanLII citator endpoint
    is English-only — the response shape is the same regardless of the
    case's filing language.

    Related tools: get_canlii_case, get_canlii_citing_cases,
    get_canlii_cited_legislations, search_canlii_cases.
    """
    params = GetCitatorInput(database_id=database_id, case_id=case_id)
    async with CanLIIClient() as client:
        response = await client.get_cited_cases(**params.model_dump())

    dumped = _dump(response)
    raw = list(dumped.get("cited_cases") or [])
    items = [_stub_case_ref(c) for c in raw]
    return ListEnvelope[dict](
        summary=(
            f"CanLII citator: case `{case_id}` (database `{database_id}`) "
            f"cites {len(items)} case{'s' if len(items) != 1 else ''}."
        ),
        items=items,
        provenance=_canlii_provenance(f"/v1/caseCitator/en/{database_id}/{case_id}/citedCases"),
    )


@conditional_tool(canlii_mcp, requires_env=_CANLII_REQUIRED_ENV, annotations=READ_ONLY)
async def get_canlii_citing_cases(
    database_id: Annotated[str, "CanLII database code"],
    case_id: Annotated[str, "CanLII case identifier"],
) -> ListEnvelope[dict]:
    """List cases that cite ``case_id`` (CanLII citator, English-only).

    Returns each citing case as a lean reference. Pass any returned
    ``case_id`` to ``get_canlii_case`` for full metadata. The CanLII
    citator endpoint is English-only — the response shape is the same
    regardless of the case's filing language.

    Related tools: get_canlii_case, get_canlii_cited_cases,
    get_canlii_cited_legislations, search_canlii_cases.
    """
    params = GetCitatorInput(database_id=database_id, case_id=case_id)
    async with CanLIIClient() as client:
        response = await client.get_citing_cases(**params.model_dump())

    dumped = _dump(response)
    raw = list(dumped.get("citing_cases") or [])
    items = [_stub_case_ref(c) for c in raw]
    return ListEnvelope[dict](
        summary=(
            f"CanLII citator: {len(items)} case{'s' if len(items) != 1 else ''} "
            f"cite case `{case_id}` (database `{database_id}`)."
        ),
        items=items,
        provenance=_canlii_provenance(f"/v1/caseCitator/en/{database_id}/{case_id}/citingCases"),
    )


@conditional_tool(canlii_mcp, requires_env=_CANLII_REQUIRED_ENV, annotations=READ_ONLY)
async def get_canlii_cited_legislations(
    database_id: Annotated[str, "CanLII database code"],
    case_id: Annotated[str, "CanLII case identifier"],
) -> ListEnvelope[dict]:
    """List legislation that ``case_id`` cites (CanLII citator, English-only).

    Returns each cited statute or regulation as a lean reference
    (legislation_id, title, citation, type, database_id). Pass any
    returned ``legislation_id`` to ``get_canlii_legislation`` for full
    point-in-time metadata.

    Related tools: get_canlii_case, get_canlii_legislation,
    get_canlii_cited_cases, get_canlii_citing_cases.
    """
    params = GetCitatorInput(database_id=database_id, case_id=case_id)
    async with CanLIIClient() as client:
        response = await client.get_cited_legislations(**params.model_dump())

    dumped = _dump(response)
    raw = list(dumped.get("cited_legislations") or [])
    items = [_stub_legislation_ref(leg) for leg in raw]
    return ListEnvelope[dict](
        summary=(
            f"CanLII citator: case `{case_id}` (database `{database_id}`) "
            f"cites {len(items)} legislation reference"
            f"{'s' if len(items) != 1 else ''}."
        ),
        items=items,
        provenance=_canlii_provenance(
            f"/v1/caseCitator/en/{database_id}/{case_id}/citedLegislations"
        ),
    )


# ---------------------------------------------------------------------------
# Legislation
# ---------------------------------------------------------------------------


@conditional_tool(canlii_mcp, requires_env=_CANLII_REQUIRED_ENV, annotations=READ_ONLY)
async def search_canlii_legislation(
    database_id: Annotated[str, "Legislation database code (e.g. 'cas', 'car')"],
    language: Annotated[Language, "'en' or 'fr'"] = "en",
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: legislation_id, "
        "title, citation, type, database_id. When True, returns the upstream "
        "LegislationRef shape unchanged.",
    ] = False,
) -> ListEnvelope[dict]:
    """List statutes / regulations within a CanLII legislation database.

    Filter-driven listing — pass a ``database_id`` from
    ``list_canlii_legislation_databases`` (e.g. ``cas`` for federal
    statutes, including the Patent Act and Trademarks Act). Pass any
    hit's ``legislation_id`` to ``get_canlii_legislation`` for point-
    in-time metadata (start/end dates, repealed flag, parts).

    Related tools: get_canlii_legislation, list_canlii_legislation_databases,
    search_canlii_cases.
    """
    params = BrowseLegislationInput(database_id=database_id, language=language)
    async with CanLIIClient() as client:
        response = await client.browse_legislation(**params.model_dump())

    dumped = _dump(response)
    raw = list(dumped.get("legislations") or [])
    items = raw if full else [_stub_legislation_ref(leg) for leg in raw]
    return ListEnvelope[dict](
        summary=(
            f"CanLII legislation — database `{database_id}` ({language}): "
            f"{len(items)} entr{'ies' if len(items) != 1 else 'y'}."
        ),
        items=items,
        provenance=_canlii_provenance(f"/v1/legislationBrowse/{language}/{database_id}/"),
    )


@conditional_tool(canlii_mcp, requires_env=_CANLII_REQUIRED_ENV, annotations=READ_ONLY)
async def get_canlii_legislation(
    database_id: Annotated[str, "Legislation database code"],
    legislation_id: Annotated[
        str | list[str],
        "Legislation identifier (e.g. 'rsc-1985-c-p-4' for the Patent Act), "
        "or a list of identifiers for portfolio workflows. Each entry resolves "
        "against the same ``database_id`` (use separate calls if your portfolio "
        "spans multiple databases).",
    ],
    language: Annotated[Language, "'en' or 'fr'"] = "en",
) -> ListEnvelope[dict]:
    """Get CanLII (Canadian Legal Information Institute) statute or regulation metadata.

    Returns ``start_date`` / ``end_date`` and ``repealed`` flags for
    point-in-time interpretation, plus the list of parts / chapters
    and the canonical CanLII URL. Accepts either a single
    ``legislation_id`` or a list (§5.4); the response is always a
    ListEnvelope so the shape is stable. Bounded concurrent fan-out
    internally; order matches the input.

    Related tools: search_canlii_legislation, list_canlii_legislation_databases,
    get_canlii_cited_legislations.
    """
    ids = [legislation_id] if isinstance(legislation_id, str) else list(legislation_id)
    if not ids:
        raise ValidationError("get_canlii_legislation requires at least one legislation_id")

    semaphore = asyncio.Semaphore(_CANLII_FANOUT_CONCURRENCY)

    async def _fetch_one(client: CanLIIClient, lid: str) -> dict:
        async with semaphore:
            params = GetLegislationInput(
                database_id=database_id, legislation_id=lid, language=language
            )
            return _dump(await client.get_legislation(**params.model_dump()))  # type: ignore[return-value]

    async with CanLIIClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, lid) for lid in ids])

    if len(results) == 1:
        summary = _summarize_legislation(results[0])
        path = f"/v1/legislationBrowse/{language}/{database_id}/{ids[0]}/"
    else:
        summary = (
            f"Fetched {len(results)} CanLII legislation entries from "
            f"`{database_id}` ({language}): {', '.join(ids)}"
        )
        path = f"/v1/legislationBrowse/{language}/{database_id}/"

    return ListEnvelope[dict](
        summary=summary,
        items=results,
        provenance=_canlii_provenance(path),
    )


__all__ = ["canlii_mcp"]
