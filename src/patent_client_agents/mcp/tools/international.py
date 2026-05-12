"""International patent office MCP tools (EPO, JPO, CPC)."""

from __future__ import annotations

import base64
from typing import Annotated, Literal

import httpx
from fastmcp import FastMCP

from law_tools_core.exceptions import ValidationError
from law_tools_core.filenames import epo_pdf as _epo_pdf_name
from law_tools_core.mcp.annotations import READ_ONLY
from law_tools_core.mcp.conditional import conditional_tool, register_source_if_configured
from law_tools_core.mcp.downloads import build_download_url, download_response, register_source
from patent_client_agents.cpc import map_classification
from patent_client_agents.epo_ops.client import client_from_env

# JPO tools are env-gated: they only appear in tool/list when JPO_API_USERNAME
# and JPO_API_PASSWORD are both set. The hosted public deploy at
# mcp.patentclient.com intentionally does not carry these keys per JPO TOS;
# private deploys flip them on by adding the secrets to their Cloud Run env.
# The download fetcher uses register_source_if_configured for the same
# reason — defense in depth.
_JPO_REQUIRED_ENV: list[str] = ["JPO_API_USERNAME", "JPO_API_PASSWORD"]

international_mcp = FastMCP("International")


def _dump(obj: object) -> object:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()  # type: ignore[union-attr]
    return obj


# ---------------------------------------------------------------------------
# Download fetcher — EPO
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
# Download fetcher — JPO document bundles
# ---------------------------------------------------------------------------

# IP type / doc kind aliases — re-used by the JPO MCP tools below.
_IP_TYPES: tuple[str, ...] = ("patent", "design", "trademark")
_DOC_KINDS: tuple[str, ...] = ("application", "mailed", "refusal")

# Map (ip_type, doc_kind) -> JpoClient method name.
_JPO_DOC_METHODS: dict[tuple[str, str], str] = {
    ("patent", "application"): "get_patent_application_documents",
    ("patent", "mailed"): "get_patent_mailed_documents",
    ("patent", "refusal"): "get_patent_refusal_notices",
    ("design", "application"): "get_design_application_documents",
    ("design", "mailed"): "get_design_mailed_documents",
    ("design", "refusal"): "get_design_refusal_notices",
    ("trademark", "application"): "get_trademark_application_documents",
    ("trademark", "mailed"): "get_trademark_mailed_documents",
    ("trademark", "refusal"): "get_trademark_refusal_notices",
}


def _validate_ip_type(value: str) -> str:
    """Normalize and validate the ``ip_type`` argument."""
    norm = value.strip().lower()
    if norm not in _IP_TYPES:
        raise ValidationError(f"ip_type must be one of {_IP_TYPES}; got {value!r}")
    return norm


def _validate_doc_kind(value: str) -> str:
    norm = value.strip().lower()
    if norm not in _DOC_KINDS:
        raise ValidationError(f"doc_kind must be one of {_DOC_KINDS}; got {value!r}")
    return norm


async def _fetch_jpo_document_bundle(path: str) -> tuple[bytes, str]:
    """Fetch a JPO document-bundle ZIP. Path: ``{ip_type}/{app_no}/{doc_kind}``.

    The fetcher dispatches to the right ``JpoClient`` method, then resolves
    the oversize-redirect case in-process so the caller always gets bytes.

    Empty bundles (no documents on file) raise ``ValueError`` rather than
    return zero-byte content — the agent should call
    :func:`get_jpo_documents` first to know whether a bundle exists at all.
    """
    parts = path.strip("/").split("/")
    if len(parts) != 3:
        raise ValueError(
            f"Expected JPO document bundle path {{ip_type}}/{{app_no}}/{{doc_kind}}, got: {path!r}"
        )
    ip_type, application_number, doc_kind = parts
    ip_type = _validate_ip_type(ip_type)
    doc_kind = _validate_doc_kind(doc_kind)
    method_name = _JPO_DOC_METHODS[(ip_type, doc_kind)]

    from patent_client_agents.jpo import JpoClient

    async with JpoClient() as client:
        method = getattr(client, method_name)
        bundle = await method(application_number)
        if bundle.zip_bytes:
            content = bundle.zip_bytes
        elif bundle.download_url:
            # Oversize redirect: JPO hosts the ZIP on their CDN. We fetch
            # in-process so the agent's signed URL always resolves to
            # bytes — we never hand off "go fetch this other URL".
            async with httpx.AsyncClient(timeout=120.0) as http:
                resp = await http.get(bundle.download_url)
                resp.raise_for_status()
                content = resp.content
        else:
            raise ValueError(
                f"JPO returned no documents for {ip_type}/{application_number}/{doc_kind}"
            )

    filename = f"jpo_{ip_type}_{application_number}_{doc_kind}.zip"
    return content, filename


register_source_if_configured(
    "jpo/documents",
    _fetch_jpo_document_bundle,
    "application/zip",
    requires_env=_JPO_REQUIRED_ENV,
)


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
# JPO (Japan Patent Office) — Patent Information Retrieval API
#
# Each tool dispatches across patent / design / trademark via an
# ``ip_type`` argument so a single tool name covers all three IP types.
# Requires JPO_API_USERNAME / JPO_API_PASSWORD env vars (issued by JPO).
# Daily caps are enforced server-side per endpoint (handbook v14 Tables 1-3).
# ---------------------------------------------------------------------------


# Map (ip_type, use_case) -> JpoClient method name. Lookups for the
# small number of "core" cross-IP-type tools below.
_JPO_PROGRESS_METHODS: dict[str, str] = {
    "patent": "get_patent_progress",
    "design": "get_design_progress",
    "trademark": "get_trademark_progress",
}
_JPO_PROGRESS_SIMPLE_METHODS: dict[str, str] = {
    "patent": "get_patent_progress_simple",
    "design": "get_design_progress_simple",
    "trademark": "get_trademark_progress_simple",
}
_JPO_PRIORITY_METHODS: dict[str, str] = {
    "patent": "get_patent_priority_info",
    "design": "get_design_priority_info",
    "trademark": "get_trademark_priority_info",
}
_JPO_REGISTRATION_METHODS: dict[str, str] = {
    "patent": "get_patent_registration_info",
    "design": "get_design_registration_info",
    "trademark": "get_trademark_registration_info",
}
_JPO_NUMBER_REF_METHODS: dict[str, str] = {
    "patent": "get_patent_number_reference",
    "design": "get_design_number_reference",
    "trademark": "get_trademark_number_reference",
}
_JPO_JPLATPAT_METHODS: dict[str, str] = {
    "patent": "get_patent_jplatpat_url",
    "design": "get_design_jplatpat_url",
    "trademark": "get_trademark_jplatpat_url",
}
_JPO_APPLICANT_BY_CODE_METHODS: dict[str, str] = {
    "patent": "get_patent_applicant_by_code",
    "design": "get_design_applicant_by_code",
    "trademark": "get_trademark_applicant_by_code",
}
_JPO_APPLICANT_BY_NAME_METHODS: dict[str, str] = {
    "patent": "get_patent_applicant_by_name",
    "design": "get_design_applicant_by_name",
    "trademark": "get_trademark_applicant_by_name",
}


@conditional_tool(international_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_jpo_progress(
    application_number: Annotated[
        str,
        "10-digit JP application number (Gregorian year 4 digits + 6-digit "
        "serial, e.g. '2020123456'). Format is the same for patent, design, "
        "and trademark applications.",
    ],
    ip_type: Annotated[
        Literal["patent", "design", "trademark"],
        "Which JPO register to query. The same tool works for all three.",
    ] = "patent",
) -> dict:
    """Get full prosecution status from JPO — works for patent, design, or trademark.

    Returns title (invention / design article / trademark display),
    applicants, filing/publication/registration dates, priority claims
    (Paris Convention or domestic), parent + divisional family info
    (patents and designs), expiration, erasure status, and the
    ``bibliographyInformation`` file-wrapper inventory.

    Returns ``{}`` when the application number is unknown or out of
    scope (status 107 / 111).
    """
    ip = _validate_ip_type(ip_type)
    from patent_client_agents.jpo import JpoClient

    async with JpoClient() as client:
        method = getattr(client, _JPO_PROGRESS_METHODS[ip])
        result = await method(application_number)
        return _dump(result) if result else {}  # type: ignore[return-value]


@conditional_tool(international_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_jpo_progress_simple(
    application_number: Annotated[str, "10-digit JP application number"],
    ip_type: Annotated[
        Literal["patent", "design", "trademark"],
        "Which JPO register to query. The same tool works for all three.",
    ] = "patent",
) -> dict:
    """Get a simplified JPO status (no priority/family detail).

    Works for patent, design, or trademark applications. Cheaper than
    ``get_jpo_progress`` for bulk status checks — same daily quota tier
    (400/day) but skips the priority and divisional sections.
    """
    ip = _validate_ip_type(ip_type)
    from patent_client_agents.jpo import JpoClient

    async with JpoClient() as client:
        method = getattr(client, _JPO_PROGRESS_SIMPLE_METHODS[ip])
        result = await method(application_number)
        return _dump(result) if result else {}  # type: ignore[return-value]


@conditional_tool(international_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_jpo_priority_info(
    application_number: Annotated[str, "10-digit JP application number"],
    ip_type: Annotated[
        Literal["patent", "design", "trademark"],
        "Which JPO register to query. The same tool works for all three.",
    ] = "patent",
) -> dict:
    """List priority basis applications (Paris + domestic) for a JPO filing.

    Works for patent, design, or trademark applications. Returns
    ``{"results": [...]}`` — each row carries either a Paris Convention
    foreign priority (``parisPriorityApplicationNumber`` + country code +
    date) or a domestic JP priority
    (``nationalPriorityApplicationNumber`` + four-law code + date).
    """
    ip = _validate_ip_type(ip_type)
    from patent_client_agents.jpo import JpoClient

    async with JpoClient() as client:
        method = getattr(client, _JPO_PRIORITY_METHODS[ip])
        priorities = await method(application_number)
        return {"results": [_dump(p) for p in priorities]}


@conditional_tool(international_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_jpo_registration_info(
    application_number: Annotated[str, "10-digit JP application number"],
    ip_type: Annotated[
        Literal["patent", "design", "trademark"],
        "Which JPO register to query. The same tool works for all three.",
    ] = "patent",
) -> dict:
    """Get the registration record for a JPO filing.

    Works for patent, design, or trademark applications. Includes
    registration number/date, decision date, current rights holders,
    claim count (patents) / design article (designs) / trademark display
    (trademarks), expiration, next pension payment due date, last paid
    year, erasure flag/date, and last update date. Returns ``{}`` when
    the application is not registered.
    """
    ip = _validate_ip_type(ip_type)
    from patent_client_agents.jpo import JpoClient

    async with JpoClient() as client:
        method = getattr(client, _JPO_REGISTRATION_METHODS[ip])
        result = await method(application_number)
        return _dump(result) if result else {}  # type: ignore[return-value]


@conditional_tool(international_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_jpo_number_reference(
    number: Annotated[
        str,
        "The number to look up. Application number = 10 digits "
        "(YYYY+6 digits), publication = 10 digits (Gregorian), "
        "registration = 7 digits.",
    ],
    kind: Annotated[
        Literal["application", "publication", "registration"],
        "Number type — descriptive strings, NOT the numeric NumberType "
        "codes used in bibliographyInformation.",
    ] = "application",
    ip_type: Annotated[
        Literal["patent", "design", "trademark"],
        "Which JPO register to query. The same tool works for all three.",
    ] = "patent",
) -> dict:
    """Cross-reference a JPO number to other forms.

    Works for patent, design, or trademark applications. Given an
    application/publication/registration number, returns the other
    associated numbers for the same JPO record.
    """
    ip = _validate_ip_type(ip_type)
    from patent_client_agents.jpo import JpoClient

    async with JpoClient() as client:
        method = getattr(client, _JPO_NUMBER_REF_METHODS[ip])
        result = await method(kind, number)
        return _dump(result) if result else {}  # type: ignore[return-value]


@conditional_tool(international_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_jpo_jplatpat_url(
    application_number: Annotated[str, "10-digit JP application number"],
    ip_type: Annotated[
        Literal["patent", "design", "trademark"],
        "Which JPO register to query. The same tool works for all three.",
    ] = "patent",
) -> dict:
    """Get the J-PlatPat fixed-address URL for a JPO filing.

    Works for patent, design, or trademark applications. J-PlatPat is
    JPO's free public search portal — the returned URL is a stable
    permalink that opens directly to this filing's bibliographic page
    (in Japanese).
    """
    ip = _validate_ip_type(ip_type)
    from patent_client_agents.jpo import JpoClient

    async with JpoClient() as client:
        method = getattr(client, _JPO_JPLATPAT_METHODS[ip])
        url = await method(application_number)
        return {"url": url} if url else {}


@conditional_tool(international_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_jpo_applicant_by_code(
    applicant_code: Annotated[str, "9-digit JPO applicant/attorney code"],
    ip_type: Annotated[
        Literal["patent", "design", "trademark"],
        "Which JPO register to query. The same tool works for all three.",
    ] = "patent",
) -> dict:
    """Get an applicant or attorney name from a JPO 9-digit code.

    Works for patent, design, or trademark registers. Returns the
    applicant or attorney name (a single string). Returns an empty
    object when the code is unknown.
    """
    ip = _validate_ip_type(ip_type)
    from patent_client_agents.jpo import JpoClient

    async with JpoClient() as client:
        method = getattr(client, _JPO_APPLICANT_BY_CODE_METHODS[ip])
        name = await method(applicant_code)
        return {"name": name} if name else {}


@conditional_tool(international_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_jpo_applicant_by_name(
    applicant_name: Annotated[
        str,
        "EXACT applicant or attorney name to look up (the API requires an "
        "exact match — partial / fuzzy queries return no data).",
    ],
    ip_type: Annotated[
        Literal["patent", "design", "trademark"],
        "Which JPO register to query. The same tool works for all three.",
    ] = "patent",
) -> dict:
    """Get JPO applicant/attorney code(s) by exact name.

    Works for patent, design, or trademark registers. Note: the
    endpoint requires an exact match. Searching for "トヨタ" won't
    return Toyota; you need the full registered name e.g.
    "トヨタ自動車株式会社".
    """
    ip = _validate_ip_type(ip_type)
    from patent_client_agents.jpo import JpoClient

    async with JpoClient() as client:
        method = getattr(client, _JPO_APPLICANT_BY_NAME_METHODS[ip])
        applicants = await method(applicant_name)
        return {"results": [_dump(a) for a in applicants]}


# ---------------------------------------------------------------------------
# JPO patent-only endpoints (no design / trademark equivalent)
# ---------------------------------------------------------------------------


@conditional_tool(international_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_jpo_patent_divisional_info(
    application_number: Annotated[str, "10-digit JP patent application number"],
) -> dict:
    """Get divisional family (parent + descendants) for a JP patent.

    Patent-only endpoint (no design/trademark equivalent). Returns the
    parent application info (if any) and a list of divisional descendants
    with their generation, publication/registration numbers, erasure
    status, and expiration.
    """
    from patent_client_agents.jpo import JpoClient

    async with JpoClient() as client:
        result = await client.get_patent_divisional_info(application_number)
        return _dump(result) if result else {}  # type: ignore[return-value]


@conditional_tool(international_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_jpo_patent_cited_documents(
    application_number: Annotated[str, "10-digit JP patent application number"],
) -> dict:
    """Get patent and non-patent citations for a JP patent application.

    Patent-only endpoint. Returns ``patentDoc`` (cited patent documents
    with type/order) and ``nonPatentDoc`` (NPL with author, title,
    publication, etc.). Citation types follow JPO code-table 07010.
    """
    from patent_client_agents.jpo import JpoClient

    async with JpoClient() as client:
        result = await client.get_patent_cited_documents(application_number)
        return _dump(result) if result else {}  # type: ignore[return-value]


@conditional_tool(international_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_jpo_pct_national_phase_number(
    number: Annotated[
        str,
        "PCT international application number (e.g. 'JP2019011858') or "
        "international publication number (e.g. 'WO2019123456').",
    ],
    kind: Annotated[
        Literal["international_application", "international_publication"],
        "Either 'international_application' (use with PCT/JP-style number) "
        "or 'international_publication' (use with WO-style number).",
    ] = "international_application",
) -> dict:
    """Look up the JP national-phase application number for a PCT filing.

    Patent-only endpoint. Useful for following PCT applications that
    have entered Japan's national phase.
    """
    from patent_client_agents.jpo import JpoClient

    async with JpoClient() as client:
        result = await client.get_patent_pct_national_number(kind, number)
        return _dump(result) if result else {}  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# JPO document download (parsed contents + signed URL for raw ZIP)
# ---------------------------------------------------------------------------


@conditional_tool(international_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_jpo_documents(
    application_number: Annotated[
        str,
        "10-digit JP application number (Gregorian year + 6-digit serial). "
        "Format is the same for patent, design, and trademark applications.",
    ],
    doc_kind: Annotated[
        Literal["application", "mailed", "refusal"],
        "Which document set to fetch: 'application' (applicant-filed "
        "opinions / amendments), 'mailed' (JPO-mailed notices including "
        "rejections AND decisions of grant), or 'refusal' (rejection "
        "notices only — strict subset of 'mailed').",
    ] = "mailed",
    ip_type: Annotated[
        Literal["patent", "design", "trademark"],
        "Which JPO register to query. The same tool works for all three.",
    ] = "patent",
    parse: Annotated[
        bool,
        "If True (default), parse the bundle ZIP and return file-history "
        "entries with body text inline. If False, skip parsing and return "
        "just the bundle metadata + signed download_url — useful when the "
        "agent only needs to hand the URL to a human or to a separate "
        "processing pipeline.",
    ] = True,
) -> dict:
    """Download (and optionally parse) a JPO document bundle.

    Works for patent, design, or trademark applications across all
    three doc-kinds. Patent bundles ship Shift-JIS XML; design and
    trademark bundles ship Shift-JIS HTM. The parser decodes both.

    With ``parse=True`` (default) returns the parsed file-history
    entries (one per index inside the JPO ZIP) plus a signed
    ``download_url`` for the raw archive — agents that need binary
    attachments or supplementary files we don't surface inline can
    fetch the raw bundle from that URL. Each entry includes (where
    applicable): JPO document code, document name (Japanese),
    document variant (root XML element / ``htm`` for HTM), application
    number, drafting/filing date, examiner / drafting person (mailed
    docs), statute references (refusal notices), and body text.
    ``binary_attachments`` lists the filenames of any other files in
    the archive (their bytes are still in the raw ZIP).

    With ``parse=False`` skips parsing entirely and returns just the
    bundle metadata (``application_number``, ``ip_type``, ``doc_kind``,
    empty ``entries``/``binary_attachments`` lists) plus the standard
    download response (``download_url``, ``filename``,
    ``content_type``, ``size_bytes``, ``expires_at``). Useful when
    handing the URL to a human reviewer or a separate processing
    pipeline.

    Returns ``{}`` when JPO has no documents on file (status 107 /
    108) — no entries, no download URL — regardless of the ``parse``
    value.
    """
    ip = _validate_ip_type(ip_type)
    kind = _validate_doc_kind(doc_kind)
    method_name = _JPO_DOC_METHODS[(ip, kind)]

    from patent_client_agents.jpo import JpoClient, parse_document_bundle

    async with JpoClient() as client:
        method = getattr(client, method_name)
        bundle_result = await method(application_number)

        if bundle_result.is_empty:
            return {}

        # Resolve oversize redirect to inline bytes so we have a real
        # ZIP for both the parser and the download cache.
        zip_bytes: bytes | None = bundle_result.zip_bytes
        if zip_bytes is None and bundle_result.download_url:
            async with httpx.AsyncClient(timeout=120.0) as http:
                resp = await http.get(bundle_result.download_url)
                resp.raise_for_status()
                zip_bytes = resp.content

        resource_path = f"jpo/documents/{ip}/{application_number}/{kind}"
        filename = f"jpo_{ip}_{application_number}_{kind}.zip"

        if not parse:
            # Skip the parser — return metadata + the standard download
            # response so the caller can fetch the raw ZIP themselves.
            payload: dict = {
                "application_number": application_number,
                "ip_type": ip,
                "doc_kind": kind,
                "entries": [],
                "binary_attachments": [],
            }
            if zip_bytes is not None:
                payload.update(
                    download_response(
                        resource_path,
                        zip_bytes,
                        filename=filename,
                        content_type="application/zip",
                    )
                )
            else:
                # Fall back to a bare signed URL when we don't have the
                # bytes to cache (shouldn't happen in practice given the
                # oversize-redirect resolution above, but kept for
                # safety so we never silently 500).
                payload["download_url"] = build_download_url(resource_path)
                payload["filename"] = filename
                payload["content_type"] = "application/zip"
            return payload

        bundle = parse_document_bundle(
            zip_bytes,
            kind,  # type: ignore[arg-type]
            ip,  # type: ignore[arg-type]
            application_number=application_number,
        )

        download_url = build_download_url(resource_path)

        payload = bundle.model_dump()
        payload["download_url"] = download_url
        payload["filename"] = filename
        payload["content_type"] = "application/zip"
        return payload
