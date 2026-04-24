"""International patent office MCP tools (EPO, JPO, CPC)."""

from __future__ import annotations

import base64
from typing import Annotated

from fastmcp import FastMCP

from law_tools_core.filenames import epo_pdf as _epo_pdf_name
from law_tools_core.mcp.annotations import READ_ONLY
from law_tools_core.mcp.downloads import register_source
from patent_client_agents.cpc import map_classification
from patent_client_agents.epo_ops.client import client_from_env

international_mcp = FastMCP("International")


def _dump(obj: object) -> object:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()  # type: ignore[union-attr]
    return obj


# ---------------------------------------------------------------------------
# Download fetcher
# ---------------------------------------------------------------------------


async def _fetch_epo_pdf(path: str) -> tuple[bytes, str]:
    """Fetch a patent PDF from EPO OPS. Path: ``{publication_number}``."""
    publication_number = path.strip("/")
    async with client_from_env() as client:
        result = await client.download_pdf(number=publication_number)
        content = base64.b64decode(result.pdf_base64)
        return content, _epo_pdf_name(publication_number)


register_source("epo/patents", _fetch_epo_pdf, "application/pdf")


# ---------------------------------------------------------------------------
# EPO Open Patent Services
# ---------------------------------------------------------------------------


@international_mcp.tool(annotations=READ_ONLY)
async def search_epo(
    cql_query: Annotated[
        str,
        "CQL query string. Common examples: "
        "'ta=CRISPR and pa=Broad Institute' (title/abstract + applicant), "
        "'in=Nakamura and ic=H01L' (inventor + IPC class), "
        "'pn=EP1234567' (publication number lookup). "
        "For complex queries, call get_epo_cql_help first.",
    ],
    group_by: Annotated[
        str,
        "Result grouping: 'publication' (one row per publication, default) or "
        "'family' (one row per patent family — de-duplicates across jurisdictions).",
    ] = "publication",
    range_begin: Annotated[int, "Start of result range (1-indexed)"] = 1,
    range_end: Annotated[int, "End of result range"] = 25,
) -> dict:
    """Search patents via EPO Open Patent Services.

    Covers patents worldwide including US, EP, WO, JP, CN, KR, and
    many other jurisdictions. Use CQL query syntax — call
    get_epo_cql_help for the full field reference.

    Set ``group_by='family'`` to deduplicate across priority-linked
    publications (INPADOC families); the default returns one row per
    publication.

    Returns 404 when no results match (not an error).
    """
    group = group_by.strip().lower()
    if group not in ("publication", "family"):
        from law_tools_core.exceptions import ValidationError

        raise ValidationError(f"group_by must be 'publication' or 'family'; got {group_by!r}")
    async with client_from_env() as client:
        if group == "family":
            result = await client.search_families(
                query=cql_query, range_begin=range_begin, range_end=range_end
            )
        else:
            result = await client.search_published(
                query=cql_query, range_begin=range_begin, range_end=range_end
            )
        return _dump(result)  # type: ignore[return-value]


@international_mcp.tool(annotations=READ_ONLY)
async def get_epo_cql_help() -> dict:
    """Get the full CQL query syntax reference for EPO OPS search tools.

    Call this before constructing complex EPO search queries. Returns
    all searchable fields, operators, wildcards, and examples.
    """
    return {
        "overview": (
            "EPO OPS uses CQL (Contextual Query Language). Queries are "
            "field=value pairs combined with boolean operators."
        ),
        "fields": {
            "ta": "Title and abstract (combined search)",
            "ti": "Title only",
            "ab": "Abstract only",
            "pa": "Applicant name",
            "in": "Inventor name",
            "pn": "Publication number (e.g. 'EP1234567', 'WO2023001234')",
            "ap": "Application number",
            "pr": "Priority number",
            "pd": "Publication date (YYYYMMDD or range)",
            "ic": "IPC classification (e.g. 'H04L9/32')",
            "cl": "Claims text",
            "desc": "Description text",
            "ct": "Citation (cited document number)",
        },
        "operators": {
            "and": "Both conditions must match: 'ta=battery and pa=Tesla'",
            "or": "Either condition: 'ta=solar or ta=photovoltaic'",
            "not": "Exclude: 'ta=battery not pa=Samsung'",
            "proximity": "Words near each other: 'ta = electric NEAR5 vehicle'",
        },
        "wildcards": {
            "*": "Any characters: 'ta=batter*' matches battery, batteries",
            "?": "Single character: 'pa=Sm?th' matches Smith, Smyth",
        },
        "date_ranges": {
            "exact": "pd=20240115",
            "range": "pd within '20240101,20241231'",
            "year": "pd=2024",
        },
        "examples": [
            {
                "query": "ta=CRISPR and pa=Broad Institute",
                "description": "CRISPR patents filed by the Broad Institute",
            },
            {
                "query": "ti=autonomous vehicle and ic=B60W",
                "description": "Autonomous vehicle patents in IPC class B60W",
            },
            {
                "query": "in=Nakamura and pd within '20200101,20241231'",
                "description": "Patents by inventor Nakamura published 2020-2024",
            },
            {
                "query": "ta=mRNA vaccine not pa=Moderna",
                "description": "mRNA vaccine patents excluding Moderna",
            },
            {
                "query": "pn=EP3456789",
                "description": "Look up a specific EP publication number",
            },
            {
                "query": "ct=EP1234567",
                "description": "Find patents that cite EP1234567",
            },
        ],
        "coverage": (
            "EPO OPS covers patents worldwide including US, EP, WO, JP, CN, "
            "KR, and many other national offices. Use country-prefixed "
            "publication numbers (e.g. 'pn=US10123456', 'pn=EP1234567')."
        ),
    }


@international_mcp.tool(annotations=READ_ONLY)
async def get_epo_biblio(
    patent_number: Annotated[str, "Patent document number (e.g. 'EP1234567A1')"],
) -> dict:
    """Get bibliographic data for a patent from EPO OPS.

    Use download_patent_pdf to download the patent PDF.
    """
    async with client_from_env() as client:
        result = await client.fetch_biblio(number=patent_number)
        return _dump(result)  # type: ignore[return-value]


@international_mcp.tool(annotations=READ_ONLY)
async def get_epo_fulltext(
    patent_number: Annotated[str, "Patent document number (e.g. 'EP1234567A1')"],
) -> dict:
    """Get full text (description and claims) of a patent from EPO OPS."""
    async with client_from_env() as client:
        result = await client.fetch_fulltext(number=patent_number)
        return _dump(result)  # type: ignore[return-value]


@international_mcp.tool(annotations=READ_ONLY)
async def get_epo_family(
    patent_number: Annotated[str, "Patent document number"],
) -> dict:
    """Get patent family members from EPO OPS (INPADOC family)."""
    async with client_from_env() as client:
        result = await client.fetch_family(number=patent_number)
        return _dump(result)  # type: ignore[return-value]


@international_mcp.tool(annotations=READ_ONLY)
async def get_epo_legal_events(
    patent_number: Annotated[str, "Patent document number"],
) -> dict:
    """Get legal status events for a patent from EPO OPS."""
    async with client_from_env() as client:
        result = await client.fetch_legal_events(number=patent_number)
        return _dump(result)  # type: ignore[return-value]


@international_mcp.tool(annotations=READ_ONLY)
async def convert_epo_number(
    number: Annotated[str, "Patent document number to convert"],
    input_format: Annotated[str, "Input format: 'original', 'docdb', or 'epodoc'"] = "original",
    output_format: Annotated[str, "Output format: 'docdb' or 'epodoc'"] = "docdb",
) -> dict:
    """Convert a patent number between EPO formats (original, docdb, epodoc)."""
    async with client_from_env() as client:
        result = await client.convert_number(
            number=number, input_format=input_format, output_format=output_format
        )
        return _dump(result)  # type: ignore[return-value]


@international_mcp.tool(annotations=READ_ONLY)
async def lookup_cpc(
    symbol: Annotated[str, "CPC classification symbol (e.g. 'H04L9/32')"],
) -> dict:
    """Look up a CPC classification symbol to get its title and hierarchy."""
    async with client_from_env() as client:
        result = await client.retrieve_cpc(symbol=symbol)
        return _dump(result)  # type: ignore[return-value]


@international_mcp.tool(annotations=READ_ONLY)
async def map_cpc_classification(
    symbol: Annotated[str, "Classification symbol to map (e.g. 'H04L9/32')"],
    from_scheme: Annotated[str, "Source scheme: 'cpc', 'ipc', or 'uscls'"],
    to_scheme: Annotated[str, "Target scheme: 'cpc', 'ipc', or 'uscls'"],
) -> dict:
    """Map a patent classification between CPC, IPC, and USCLS.

    Converts a classification symbol from one scheme to
    another using EPO OPS concordance data.
    """
    result = await map_classification(
        input_schema=from_scheme,
        symbol=symbol,
        output_schema=to_scheme,
    )
    return _dump(result)  # type: ignore[return-value]


@international_mcp.tool(annotations=READ_ONLY)
async def search_cpc(
    query: Annotated[str, "Text query to search CPC classifications"],
) -> dict:
    """Search CPC classifications by keyword."""
    async with client_from_env() as client:
        result = await client.search_cpc(query=query)
        return _dump(result)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# JPO (Japan Patent Office) — disabled pending API key approval
# Re-enable by uncommenting when JPO_API_USERNAME/JPO_API_PASSWORD are set.
# ---------------------------------------------------------------------------
