"""PRV (Sweden) — MCP tools.

Read-only access to the Swedish Patent and Registration Office's three
undocumented but unauthenticated JSON APIs:
``patents-search-api.prv.se`` (patents), ``dv-search-api.prv.se``
(trademarks + designs), and ``api.prv.se`` (per-record patent fetch).
No env vars required; production callers should send a courtesy
registration to ``data@prv.se`` so PRV can warn us about schema
changes.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, cast

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.exceptions import ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.prv_se import PrvClient
from patent_client_agents.prv_se.client import API_HOST, DV_HOST, PATENTS_HOST

prv_se_mcp = FastMCP("PRV Sweden")

_PRV_SOURCE_NAME = "Patent- och registreringsverket (PRV, Sweden)"
_PRV_FANOUT_CONCURRENCY = 5

# ----------------------------------------------------------------------
# Projection helpers (§5.5 lean defaults)
# ----------------------------------------------------------------------

_LEAN_PATENT_GET_DROP = {"first_drawing"}


def _provenance(source_url: str) -> Any:
    return make_provenance(source_url=source_url, source_name=_PRV_SOURCE_NAME)


def _dump(model: Any) -> dict[str, Any]:
    return cast("dict[str, Any]", model.model_dump(by_alias=True, exclude_none=False))


def _project_search_row(row: Any, *, full: bool) -> dict[str, Any]:
    """Dump a search-row model; lean view leaves it alone (already lean)."""
    return _dump(row)


def _project_patent_get(record: Any, *, full: bool) -> dict[str, Any]:
    """Dump a PatentGetRecord; lean view drops the ~32KB drawing payload."""
    data = _dump(record)
    if full:
        return data
    drawing = data.get("firstDrawing")
    if isinstance(drawing, dict) and "data" in drawing:
        drawing = {k: v for k, v in drawing.items() if k != "data"}
        data["firstDrawing"] = drawing
    return data


def _coerce_list(value: str | list[str], *, tool: str) -> list[str]:
    items = [value] if isinstance(value, str) else list(value)
    items = [s.strip() for s in items if isinstance(s, str) and s.strip()]
    if not items:
        raise ValidationError(f"{tool} requires at least one application number")
    return items


def _summarize_search(label: str, total: int, returned: int, text: str | None) -> str:
    if text:
        return f"PRV {label} — {total:,} total hits for `{text}`, returned {returned}."
    return f"PRV {label} — {total:,} total hits, returned {returned}."


# ----------------------------------------------------------------------
# search_prv_patents
# ----------------------------------------------------------------------


@prv_se_mcp.tool(annotations=READ_ONLY)
async def search_prv_patents(
    text: Annotated[
        str | None,
        "Free-text query — matches applicant, inventor, title, and "
        "application number. Example: 'Volvo'.",
    ] = None,
    page: Annotated[int, "Zero-indexed page number."] = 0,
    page_size: Annotated[int, "Hits per page (capped at 100)."] = 25,
    sort_column: Annotated[
        str,
        "Sort key: 'filingDate' (default), 'publicationDate', 'grantDate', 'title'.",
    ] = "filingDate",
    sort_order: Annotated[str, "'DESC' (default) or 'ASC'."] = "DESC",
    full: Annotated[
        bool,
        "When False (default), rows match upstream lean shape; "
        "when True, identical (PRV search rows are already minimal).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search Sweden national patent applications and grants at PRV.

    Wraps ``POST patents-search-api.prv.se/searchpatent/patentsimplesearch/``.
    Covers SE-national filings (``applicationType=NAT``); EP-route
    validations also appear with ``applicationType=EP``. Status codes
    are numeric on this surface — full text resolves on ``get_prv_patent``.

    Related tools: ``get_prv_patent`` for the full register record with
    multilingual status text and gazette announcements;
    ``search_epo_patents`` for SE-validated EP patents at INPADOC fidelity.
    """
    async with PrvClient() as client:
        result = await client.search_patents(
            text=text,
            page=page,
            page_size=page_size,
            sort_column=sort_column,
            sort_order=sort_order,
        )
    rows = [_project_search_row(r, full=full) for r in result.search_patent_dtos]
    return ListEnvelope[dict](
        summary=_summarize_search("patents", result.total_hits, len(rows), text),
        items=rows,
        more_available=(result.page + 1) < result.total_pages,
        next_cursor=None,
        provenance=_provenance(f"{PATENTS_HOST}/searchpatent/patentsimplesearch/"),
    )


# ----------------------------------------------------------------------
# get_prv_patent
# ----------------------------------------------------------------------


@prv_se_mcp.tool(annotations=READ_ONLY)
async def get_prv_patent(
    application_number: Annotated[
        str | list[str],
        "PRV application number, formatted ('SE2615555-6') or compact "
        "('26155556'). Pass a list for portfolio fan-outs.",
    ],
    application_type: Annotated[
        str,
        "Application route: 'NAT' (default, national), 'EP', 'PCT'.",
    ] = "NAT",
    full: Annotated[
        bool,
        "When False (default), drops ~32 KB of base64-encoded first-"
        "drawing image bytes. When True, returns the upstream-shaped record.",
    ] = False,
) -> ListEnvelope[dict]:
    """Fetch one or more Sweden patent register records from PRV.

    Wraps ``GET api.prv.se/patents/applications/{number}``. Returns the
    full register entry — multilingual status text (Sv/En), prosecution
    timeline (``registryEntries{Sv,En}``), gazette announcements, and
    a downloadable publication URL. The first-drawing image is dropped
    by default to keep responses under context budget.

    Related tools: ``search_prv_patents`` to find candidate application
    numbers; ``get_epo_biblio`` for SE-validated EP patents at INPADOC
    fidelity.
    """
    numbers = _coerce_list(application_number, tool="get_prv_patent")
    semaphore = asyncio.Semaphore(_PRV_FANOUT_CONCURRENCY)

    async def _fetch_one(client: PrvClient, num: str) -> Any:
        async with semaphore:
            return await client.get_patent(num, application_type=application_type)

    async with PrvClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    rows = [_project_patent_get(r, full=full) for r in results]
    summary = (
        f"PRV patent records — {len(rows)} record{'s' if len(rows) != 1 else ''} "
        f"for {', '.join(numbers[:5])}{' …' if len(numbers) > 5 else ''}."
    )
    return ListEnvelope[dict](
        summary=summary,
        items=rows,
        more_available=False,
        next_cursor=None,
        provenance=_provenance(f"{API_HOST}/patents/applications/"),
    )


# ----------------------------------------------------------------------
# search_prv_trademarks
# ----------------------------------------------------------------------


@prv_se_mcp.tool(annotations=READ_ONLY)
async def search_prv_trademarks(
    text: Annotated[
        str | None,
        "Free-text query — matches mark text, applicant, and representative. Example: 'IKEA'.",
    ] = None,
    page: Annotated[int, "Zero-indexed page number."] = 0,
    page_size: Annotated[int, "Hits per page (capped at 100)."] = 25,
    sort_column: Annotated[
        str,
        "Sort key: 'filingDate' (default), 'expiryDate', 'markSpecification'.",
    ] = "filingDate",
    sort_order: Annotated[str, "'DESC' (default) or 'ASC'."] = "DESC",
    full: Annotated[bool, "Lean (default) vs upstream-shaped rows."] = False,
) -> ListEnvelope[dict]:
    """Search Sweden national trademarks at PRV.

    Wraps ``POST dv-search-api.prv.se/searchtrademark/tmsimplesearch/``.
    Returns biblio rows with Nice classes, mark feature (Word /
    Figurative / etc.), and bilingual status. ``dossierTypeEn`` /
    ``dossierTypeSv`` discriminates national filings from Madrid IRs
    designating Sweden.

    Related tools: ``search_euipo_trademarks`` for EU-wide trademarks
    covering Sweden; Madrid IR coverage requires WIPO Madrid Monitor.
    """
    async with PrvClient() as client:
        result = await client.search_trademarks(
            text=text,
            page=page,
            page_size=page_size,
            sort_column=sort_column,
            sort_order=sort_order,
        )
    rows = [_project_search_row(r, full=full) for r in result.trademarks]
    return ListEnvelope[dict](
        summary=_summarize_search("trademarks", result.total_hits, len(rows), text),
        items=rows,
        more_available=(result.page + 1) < result.total_pages,
        next_cursor=None,
        provenance=_provenance(f"{DV_HOST}/searchtrademark/tmsimplesearch/"),
    )


# ----------------------------------------------------------------------
# search_prv_designs
# ----------------------------------------------------------------------


@prv_se_mcp.tool(annotations=READ_ONLY)
async def search_prv_designs(
    text: Annotated[
        str | None,
        "Free-text query — matches product title, applicant, and "
        "representative. Example: 'stol' (Swedish for 'chair').",
    ] = None,
    page: Annotated[int, "Zero-indexed page number."] = 0,
    page_size: Annotated[int, "Hits per page (capped at 100)."] = 25,
    sort_column: Annotated[
        str,
        "Sort key: 'filingDate' (default), 'expiryDate', 'productTitle'.",
    ] = "filingDate",
    sort_order: Annotated[str, "'DESC' (default) or 'ASC'."] = "DESC",
    full: Annotated[bool, "Lean (default) vs upstream-shaped rows."] = False,
) -> ListEnvelope[dict]:
    """Search Sweden national design (mönster) registrations at PRV.

    Wraps ``POST dv-search-api.prv.se/searchdesign/dssimplesearch/``.
    Each row represents one embodiment within a multi-design
    application — ``designNumber`` and ``designsTotal`` indicate
    position. Locarno classes appear in ``classes``.

    Related tools: EUIPO Registered Community Designs (covers SE
    transitively); WIPO Hague IR coverage via Hague Monitor (not yet
    in this catalog).
    """
    async with PrvClient() as client:
        result = await client.search_designs(
            text=text,
            page=page,
            page_size=page_size,
            sort_column=sort_column,
            sort_order=sort_order,
        )
    rows = [_project_search_row(r, full=full) for r in result.designs]
    return ListEnvelope[dict](
        summary=_summarize_search("designs", result.total_hits, len(rows), text),
        items=rows,
        more_available=(result.page + 1) < result.total_pages,
        next_cursor=None,
        provenance=_provenance(f"{DV_HOST}/searchdesign/dssimplesearch/"),
    )


# ----------------------------------------------------------------------
# search_prv_spcs
# ----------------------------------------------------------------------


@prv_se_mcp.tool(annotations=READ_ONLY)
async def search_prv_spcs(
    substance_product: Annotated[
        str | None,
        "Substance or product name (active pharmaceutical ingredient / "
        "agrochemical). Example: 'rosuvastatin'.",
    ] = None,
    applicants: Annotated[
        str | None,
        "SPC applicant name. Example: 'AstraZeneca'.",
    ] = None,
    application_number_spc: Annotated[
        str | None,
        "SPC's own application number (e.g. '2490037-5').",
    ] = None,
    base_patent_number: Annotated[
        str | None,
        "Base patent application number (the patent the SPC extends, "
        "typically EP-route, e.g. 'EP08806741.8').",
    ] = None,
    marketing_authorization_number: Annotated[
        str | None,
        "EMA / national marketing authorization (MA) number.",
    ] = None,
    announcement: Annotated[
        str | None,
        "Free-text match on the gazette announcement entry.",
    ] = None,
    match_type: Annotated[
        str,
        "Match strategy applied to every populated filter: "
        "'CONTAINS' (default), 'STARTS_WITH', or 'EXACT'.",
    ] = "CONTAINS",
    page: Annotated[int, "Zero-indexed page number."] = 0,
    page_size: Annotated[int, "Hits per page (capped at 100)."] = 25,
    full: Annotated[bool, "Lean (default) vs upstream-shaped rows."] = False,
) -> ListEnvelope[dict]:
    """Search Sweden Supplementary Protection Certificates (SPCs) at PRV.

    Wraps ``POST patents-search-api.prv.se/searchpatentspc/patentsearchspc/``.
    SPCs are patent-term extensions for pharmaceuticals and
    plant-protection products under EU Regulation 469/2009 (medicines)
    and 1610/96 (plant protection). At least one filter is required —
    the endpoint returns HTTP 500 for an empty query.

    Each row carries the base patent application number, the SPC's
    own application + publication numbers, the substance name, and
    the SPC term (``valid_from_date`` / ``valid_until_date``).

    Related tools: ``search_prv_patents`` for the base patents the
    SPCs extend; ``get_prv_patent`` for the full base-patent register
    record.
    """
    async with PrvClient() as client:
        result = await client.search_spcs(
            substance_product=substance_product,
            applicants=applicants,
            application_number_spc=application_number_spc,
            base_patent_number=base_patent_number,
            marketing_authorization_number=marketing_authorization_number,
            announcement=announcement,
            match_type=match_type,
            page=page,
            page_size=page_size,
        )
    rows = [_project_search_row(r, full=full) for r in result.search_spc_dtos]
    hint = (
        substance_product
        or applicants
        or application_number_spc
        or base_patent_number
        or marketing_authorization_number
        or announcement
    )
    return ListEnvelope[dict](
        summary=_summarize_search("SPCs", result.total_hits, len(rows), hint),
        items=rows,
        more_available=(result.page + 1) < result.total_pages,
        next_cursor=None,
        provenance=_provenance(f"{PATENTS_HOST}/searchpatentspc/patentsearchspc/"),
    )


__all__ = ["prv_se_mcp"]
