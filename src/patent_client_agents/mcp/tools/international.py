"""International patent office MCP tools (EPO, JPO, CPC)."""

from __future__ import annotations

import asyncio
import base64
from typing import Annotated, Any, Literal, cast

import httpx
from fastmcp import FastMCP

from law_tools_core.envelope import (
    ListEnvelope,
    ResponseEnvelope,
    decode_cursor,
    encode_cursor,
    make_provenance,
)
from law_tools_core.exceptions import ValidationError
from law_tools_core.filenames import epo_pdf as _epo_pdf_name
from law_tools_core.mcp.annotations import READ_ONLY
from law_tools_core.mcp.conditional import (
    conditional_resource,
    conditional_tool,
    register_source_if_configured,
)
from law_tools_core.mcp.downloads import (
    build_download_url,
    download_response,
    read_resource,
    register_source,
)
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


@international_mcp.resource(
    "pca://epo/patents/{publication_number}",
    mime_type="application/pdf",
    name="EPO patent PDF",
    description=(
        "Patent PDF resolved through EPO Open Patent Services. URI parameter is "
        "the publication number with country and kind code (e.g. 'EP3456789A1')."
    ),
)
async def _epo_patent_pdf_resource(publication_number: str):
    return await read_resource(f"epo/patents/{publication_number}")


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


@conditional_resource(
    international_mcp,
    "pca://jpo/documents/{ip_type}/{application_number}/{doc_kind}",
    mime_type="application/zip",
    name="JPO document bundle",
    description=(
        "Zip archive of JPO documents for one application/kind combination. "
        "ip_type ∈ {patent, design, trademark}; doc_kind ∈ {application, mailed, refusal}."
    ),
    requires_env=_JPO_REQUIRED_ENV,
)
async def _jpo_document_bundle_resource(ip_type: str, application_number: str, doc_kind: str):
    return await read_resource(f"jpo/documents/{ip_type}/{application_number}/{doc_kind}")


# ---------------------------------------------------------------------------
# EPO Open Patent Services — envelope helpers
#
# Every EPO OPS tool returns ListEnvelope[dict] (search + list-accepting gets
# per §5.4) or ResponseEnvelope[dict] (CQL help, single-record number
# conversion). Provenance points at the upstream
# `https://ops.epo.org/3.2/rest-services` path so attorneys can verify any
# field against the source register.
# ---------------------------------------------------------------------------

_EPO_OPS_BASE = "https://ops.epo.org/3.2/rest-services"
_EPO_OPS_NAME = "European Patent Office Open Patent Services (EPO OPS)"
_EPO_FANOUT_CONCURRENCY = 5


def _epo_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{base}{path}`` on EPO OPS."""
    return make_provenance(source_url=f"{_EPO_OPS_BASE}{path}", source_name=_EPO_OPS_NAME)


def _stub_epo_search_hit(record: dict) -> dict:
    """Lean projection of an EPO publication search hit (§5.5).

    Returns scalar identifiers + the most-quotable metadata: publication number
    (country + doc_number + kind code, when present), application number,
    publication date, and family id. Mirrors the upstream ``SearchResult``
    shape but flattens the publication identity into a single string so an
    agent can paste it into ``get_epo_biblio`` or ``get_epo_family`` directly.
    """
    country = record.get("country")
    doc_number = record.get("doc_number")
    kind = record.get("kind")
    pub_parts = [p for p in (country, doc_number, kind) if p]
    publication_number = "".join(pub_parts) if pub_parts else record.get("docdb_number")
    return {
        "publication_number": publication_number,
        "application_number": record.get("application_number"),
        "publication_date": record.get("publication_date"),
        "country": country,
        "kind": kind,
        "family_id": record.get("family_id"),
    }


def _stub_epo_family_hit(record: dict) -> dict:
    """Lean projection of an EPO family search hit (one row per family)."""
    members = record.get("members") or []
    member_stubs = [_stub_epo_search_hit(m) for m in members if isinstance(m, dict)]
    return {
        "family_id": record.get("family_id"),
        "member_count": len(member_stubs),
        "members": member_stubs,
    }


def _summarize_epo_biblio(record: dict, *, fallback_number: str) -> str:
    """One-line Markdown summary for a single ``BiblioRecord`` dump."""
    documents = record.get("documents") or []
    first = documents[0] if documents and isinstance(documents[0], dict) else record
    pub = first.get("docdb_number") or fallback_number
    title = first.get("title") or "(no title)"
    applicants = first.get("applicants") or []
    head = f"**EPO {pub}** — {title}"
    if applicants:
        return f"{head}\nApplicant: {applicants[0]}."
    return f"{head}."


def _summarize_epo_fulltext(record: dict, *, fallback_number: str) -> str:
    pub = record.get("docdb_number") or fallback_number
    section = record.get("section") or "fulltext"
    claims = record.get("claims") or []
    if claims:
        return f"**EPO {pub}** — {section}: {len(claims)} claim(s)."
    has_desc = bool(record.get("description") or record.get("raw_text"))
    if has_desc:
        return f"**EPO {pub}** — {section} text returned."
    return f"**EPO {pub}** — no {section} content available."


def _summarize_epo_family(record: dict, *, fallback_number: str) -> str:
    pub = record.get("publication_number") or fallback_number
    num = record.get("num_records") or len(record.get("members") or [])
    return f"**EPO {pub}** — INPADOC family: {num} member(s)."


def _summarize_epo_legal_events(record: dict, *, fallback_number: str) -> str:
    events = record.get("events") or []
    ref = record.get("publication_reference") or {}
    pub = ref.get("doc_number") or fallback_number
    return f"**EPO {pub}** — {len(events)} legal event(s) on file."


def _summarize_epo_number_conversion(input_number: str, record: dict) -> str:
    out_doc = record.get("output_document") or {}
    country = out_doc.get("country") or ""
    number = out_doc.get("doc_number") or out_doc.get("number") or "(no output)"
    kind = out_doc.get("kind") or ""
    rendered = f"{country}{number}{kind}".strip() or number
    return f"**EPO number conversion `{input_number}`** → {rendered}."


# ---------------------------------------------------------------------------
# EPO Open Patent Services — MCP tools
# ---------------------------------------------------------------------------


@international_mcp.tool(annotations=READ_ONLY)
async def search_epo(
    cql_query: Annotated[
        str,
        "CQL (Common Query Language) query string. Common examples: "
        "'ta=CRISPR and pa=Broad Institute' (title/abstract + applicant), "
        "'in=Nakamura and ic=H01L' (inventor + IPC class), "
        "'pn=EP1234567' (publication number lookup). "
        "Call ``get_epo_cql_help`` for the full field reference.",
    ],
    group_by: Annotated[
        str,
        "Result grouping: 'publication' (one row per publication, default) or "
        "'family' (one row per patent family — de-duplicates across jurisdictions).",
    ] = "publication",
    range_begin: Annotated[int, "Start of result range (1-indexed)."] = 1,
    range_end: Annotated[int, "End of result range."] = 25,
    next_cursor: Annotated[
        str | None,
        "Opaque cursor from a previous response's ``next_cursor``. Overrides "
        "``range_begin``/``range_end`` when present.",
    ] = None,
    full: Annotated[
        bool,
        "When False (default), each hit is a lean stub: publication number, "
        "application number, publication date, country, kind, family id. "
        "When True, hits carry the full upstream ``SearchResult`` shape. "
        "For deep bibliographic data on one publication, prefer "
        "``get_epo_biblio``.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search worldwide patents (US, EP, WO, JP, CN, KR, and more) via EPO Open Patent Services.

    Returns a ListEnvelope of publication or family hits ranked by EPO's
    CQL search service. The lean default surfaces just the identifiers an
    agent needs to follow up with ``get_epo_biblio`` (bibliography),
    ``get_epo_fulltext`` (claims + description), ``get_epo_family``
    (INPADOC family), ``get_epo_legal_events`` (status timeline), or
    ``convert_epo_number`` (format conversion). Pass ``group_by='family'``
    to deduplicate across priority-linked publications.

    Pagination uses EPO's ``range_begin``/``range_end`` window (1-indexed,
    inclusive). When ``total > shown + (range_begin - 1)`` the envelope
    sets ``more_available=True`` and returns an opaque ``next_cursor`` —
    pass it back unchanged for the next page.

    Related tools: get_epo_cql_help, get_epo_biblio, get_epo_fulltext,
    get_epo_family, get_epo_legal_events, convert_epo_number.
    """
    group = group_by.strip().lower()
    if group not in ("publication", "family"):
        raise ValidationError(f"group_by must be 'publication' or 'family'; got {group_by!r}")

    if next_cursor:
        try:
            payload = decode_cursor(next_cursor)
        except ValueError as exc:
            raise ValidationError(f"invalid next_cursor: {exc}") from exc
        range_begin = int(payload.get("range_begin", range_begin))
        range_end = int(payload.get("range_end", range_end))

    async with client_from_env() as client:
        if group == "family":
            result = await client.search_families(
                query=cql_query, range_begin=range_begin, range_end=range_end
            )
        else:
            result = await client.search_published(
                query=cql_query, range_begin=range_begin, range_end=range_end
            )

    dumped = _dump(result)
    raw = dumped.get("families") if group == "family" else dumped.get("results")
    raw_rows: list[dict[str, Any]] = raw if isinstance(raw, list) else []
    items: list[dict[str, Any]]
    if full:
        items = raw_rows
    elif group == "family":
        items = [_stub_epo_family_hit(r) for r in raw_rows]
    else:
        items = [_stub_epo_search_hit(r) for r in raw_rows]

    total = dumped.get("total_results")
    shown = len(items)
    page_size = max(range_end - range_begin + 1, 1)
    more = bool(total and (range_begin - 1) + shown < int(total))
    cursor: str | None = None
    if more:
        next_begin = range_begin + page_size
        cursor = encode_cursor({"range_begin": next_begin, "range_end": next_begin + page_size - 1})

    summary_total = f"{shown} of {total} hits" if total else f"{shown} hits"
    return ListEnvelope[dict](
        summary=f"EPO OPS — `{cql_query}` ({group}): {summary_total}.",
        items=items,
        more_available=more,
        next_cursor=cursor,
        provenance=_epo_provenance(
            "/family/search" if group == "family" else "/published-data/search"
        ),
    )


@international_mcp.tool(annotations=READ_ONLY)
async def get_epo_cql_help() -> ResponseEnvelope[dict]:
    """Show the search syntax (CQL — Common Query Language) accepted by ``search_epo``.

    Returns example queries for each searchable field plus the operators,
    wildcards, and date-range forms that EPO OPS understands. Call this
    before constructing complex queries; pass the resulting field codes
    (``ta``, ``pa``, ``ic``, …) to ``search_epo``.

    Related tools: search_epo, get_epo_biblio, get_epo_family.
    """
    details = {
        "overview": (
            "EPO OPS uses CQL (Common Query Language). Queries are "
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
    return ResponseEnvelope[dict](
        summary="EPO OPS CQL reference — field codes, operators, wildcards, examples.",
        details=details,
        provenance=_epo_provenance("/published-data/search"),
    )


@international_mcp.tool(annotations=READ_ONLY)
async def get_epo_biblio(
    patent_number: Annotated[
        str | list[str],
        "Patent document number (e.g. 'EP1234567A1'), or a list of such "
        "numbers for portfolio workflows. Examples: 'EP1234567A1', "
        "['EP1234567A1', 'US10123456B2']. EPO OPS accepts country-prefixed "
        "publication numbers across all jurisdictions it indexes.",
    ],
) -> ListEnvelope[dict]:
    """Get bibliographic data (title, applicants, inventors, IPC/CPC, priority) for one or more patents from EPO OPS.

    Accepts a single number or a list (per §5.4); the response is always
    a ListEnvelope. Bounded concurrent fan-out internally. Each item
    carries the upstream ``BiblioResponse`` shape (``documents`` list with
    title, applicants, inventors, classifications, priority claims).
    For full text use ``get_epo_fulltext``; for the family graph use
    ``get_epo_family``; for status timeline use ``get_epo_legal_events``.

    Related tools: search_epo, get_epo_fulltext, get_epo_family,
    get_epo_legal_events, convert_epo_number, get_epo_cql_help.
    """
    numbers = [patent_number] if isinstance(patent_number, str) else list(patent_number)
    if not numbers:
        raise ValidationError("get_epo_biblio requires at least one patent number")

    semaphore = asyncio.Semaphore(_EPO_FANOUT_CONCURRENCY)

    async def _fetch_one(client: Any, n: str) -> dict:
        async with semaphore:
            return _dump(await client.fetch_biblio(number=n))  # type: ignore[return-value]

    async with client_from_env() as client:
        items = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    if len(numbers) == 1:
        summary = _summarize_epo_biblio(items[0], fallback_number=numbers[0])
        path = f"/published-data/publication/docdb/{numbers[0]}/biblio"
    else:
        summary = f"EPO OPS biblio — fetched {len(items)} record(s): " + ", ".join(numbers)
        path = "/published-data/publication"

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_epo_provenance(path),
    )


@international_mcp.tool(annotations=READ_ONLY)
async def get_epo_fulltext(
    patent_number: Annotated[
        str | list[str],
        "Patent document number (e.g. 'EP1234567A1'), or a list for portfolio "
        "workflows. Examples: 'EP1234567A1', ['EP1234567A1', 'EP9876543B1'].",
    ],
) -> ListEnvelope[dict]:
    """Get full text (claims + description) for one or more patents from EPO OPS.

    Accepts a single number or a list (per §5.4); the response is always
    a ListEnvelope. Each item carries the parsed ``FullTextResponse`` —
    claims list with dependency graph and (where indexed) the
    description text. Bounded concurrent fan-out internally. Note: EPO
    OPS only carries fulltext for jurisdictions that license it to EPO;
    coverage is denser for EP/WO than for national US/JP/CN
    publications.

    Related tools: search_epo, get_epo_biblio, get_epo_family,
    get_epo_legal_events, convert_epo_number.
    """
    numbers = [patent_number] if isinstance(patent_number, str) else list(patent_number)
    if not numbers:
        raise ValidationError("get_epo_fulltext requires at least one patent number")

    semaphore = asyncio.Semaphore(_EPO_FANOUT_CONCURRENCY)

    async def _fetch_one(client: Any, n: str) -> dict:
        async with semaphore:
            return _dump(await client.fetch_fulltext(number=n))  # type: ignore[return-value]

    async with client_from_env() as client:
        items = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    if len(numbers) == 1:
        summary = _summarize_epo_fulltext(items[0], fallback_number=numbers[0])
        path = f"/published-data/publication/docdb/{numbers[0]}/claims"
    else:
        summary = f"EPO OPS fulltext — fetched {len(items)} record(s): " + ", ".join(numbers)
        path = "/published-data/publication"

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_epo_provenance(path),
    )


@international_mcp.tool(annotations=READ_ONLY)
async def get_epo_family(
    patent_number: Annotated[
        str | list[str],
        "Patent document number, or a list for portfolio workflows. "
        "Examples: 'EP1234567A1', ['EP1234567A1', 'US10123456B2']. EPO uses "
        "INPADOC families (priority-linked publications across jurisdictions).",
    ],
) -> ListEnvelope[dict]:
    """Get INPADOC patent family members (priority-linked publications across jurisdictions) for one or more patents.

    Accepts a single number or a list (per §5.4); the response is always
    a ListEnvelope. Each item carries the parsed ``FamilyResponse`` —
    every family member with its publication number, application number,
    and priority claims. Bounded concurrent fan-out internally. INPADOC
    families group all publications that share at least one priority
    document, so the response covers continuation chains, national-phase
    entries from a PCT, and cross-jurisdiction equivalents.

    Related tools: search_epo, get_epo_biblio, get_epo_fulltext,
    get_epo_legal_events, convert_epo_number.
    """
    numbers = [patent_number] if isinstance(patent_number, str) else list(patent_number)
    if not numbers:
        raise ValidationError("get_epo_family requires at least one patent number")

    semaphore = asyncio.Semaphore(_EPO_FANOUT_CONCURRENCY)

    async def _fetch_one(client: Any, n: str) -> dict:
        async with semaphore:
            return _dump(await client.fetch_family(number=n))  # type: ignore[return-value]

    async with client_from_env() as client:
        items = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    if len(numbers) == 1:
        summary = _summarize_epo_family(items[0], fallback_number=numbers[0])
        path = f"/family/publication/docdb/{numbers[0]}"
    else:
        summary = f"EPO OPS family — fetched {len(items)} record(s): " + ", ".join(numbers)
        path = "/family/publication"

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_epo_provenance(path),
    )


@international_mcp.tool(annotations=READ_ONLY)
async def get_epo_legal_events(
    patent_number: Annotated[
        str | list[str],
        "Patent document number, or a list for portfolio workflows. "
        "Examples: 'EP1234567A1', ['EP1234567A1', 'EP9876543B1'].",
    ],
) -> ListEnvelope[dict]:
    """Get the legal-status event timeline (filing, publication, grant, lapse) for one or more patents from EPO OPS.

    Accepts a single number or a list (per §5.4); the response is always
    a ListEnvelope. Each item carries the parsed ``LegalEventsResponse``
    — a chronological list of events with their date, country, EPO code,
    and human-readable description. Bounded concurrent fan-out
    internally. Useful for confirming grant date, lapse/withdrawal,
    opposition events, and renewal-fee history across the family.

    Related tools: search_epo, get_epo_biblio, get_epo_family,
    get_epo_fulltext, convert_epo_number, get_epo_unitary_patent_status.
    """
    numbers = [patent_number] if isinstance(patent_number, str) else list(patent_number)
    if not numbers:
        raise ValidationError("get_epo_legal_events requires at least one patent number")

    semaphore = asyncio.Semaphore(_EPO_FANOUT_CONCURRENCY)

    async def _fetch_one(client: Any, n: str) -> dict:
        async with semaphore:
            return _dump(await client.fetch_legal_events(number=n))  # type: ignore[return-value]

    async with client_from_env() as client:
        items = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    if len(numbers) == 1:
        summary = _summarize_epo_legal_events(items[0], fallback_number=numbers[0])
        path = f"/legal/publication/docdb/{numbers[0]}"
    else:
        summary = f"EPO OPS legal events — fetched {len(items)} record(s): " + ", ".join(numbers)
        path = "/legal/publication"

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_epo_provenance(path),
    )


@international_mcp.tool(annotations=READ_ONLY)
async def convert_epo_number(
    number: Annotated[
        str,
        "Patent number to convert. Examples: 'EP1234567A1' (original), "
        "'EP.1234567.A1' (docdb), 'EP1234567' (epodoc).",
    ],
    input_format: Annotated[str, "Input format: 'original', 'docdb', or 'epodoc'."] = "original",
    output_format: Annotated[str, "Output format: 'docdb' or 'epodoc'."] = "docdb",
) -> ResponseEnvelope[dict]:
    """Convert a patent number between EPO formats (original ↔ docdb ↔ epodoc).

    EPO OPS accepts three normalization formats. ``original`` is the
    publication number as printed on the document (e.g. ``EP1234567A1``);
    ``docdb`` is the dotted form used by INPADOC (``EP.1234567.A1``);
    ``epodoc`` is the country-prefixed bare form (``EP1234567``). Use
    this to translate between formats when an upstream tool wants a
    specific one. Returns a single conversion record in ``details``.

    Related tools: search_epo, get_epo_biblio, get_epo_family,
    get_epo_legal_events, get_epo_cql_help.
    """
    async with client_from_env() as client:
        result = await client.convert_number(
            number=number, input_format=input_format, output_format=output_format
        )

    details: dict = _dump(result)  # type: ignore[assignment]
    path = f"/number-service/publication/{input_format}/{number}/{output_format}"
    return ResponseEnvelope[dict](
        summary=_summarize_epo_number_conversion(number, details),
        details=details,
        provenance=_epo_provenance(path),
    )


# ---------------------------------------------------------------------------
# CPC (Cooperative Patent Classification) — envelope helpers
#
# CPC is the classification vocabulary used to index the patent register.
# Per coverage/sources.yaml it's `category: registered_ip`, served live via
# EPO OPS (the EPO and USPTO jointly maintain the scheme). Provenance points
# at `https://ops.epo.org/3.2/rest-services/classification/...` so an attorney
# can verify a title or mapping against the upstream OPS endpoint.
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


@international_mcp.tool(annotations=READ_ONLY)
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


@international_mcp.tool(annotations=READ_ONLY)
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


@international_mcp.tool(annotations=READ_ONLY)
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


# ---------------------------------------------------------------------------
# EPO Register — Unitary Patent (UP) status
#
# The Unitary Patent register is served live via the EPO Register service
# (the same OPS host as biblio / legal events / family). Provenance points at
# `https://ops.epo.org/3.2/rest-services/register/publication/epodoc/{n}/upp`
# so an attorney can verify a UP status timeline against the upstream
# register payload.
# ---------------------------------------------------------------------------

_EPO_REGISTER_BASE = "https://ops.epo.org/3.2"
_EPO_REGISTER_NAME = "EPO Register (Unitary Patent)"


def _epo_register_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{base}{path}`` on the EPO Register."""
    return make_provenance(source_url=f"{_EPO_REGISTER_BASE}{path}", source_name=_EPO_REGISTER_NAME)


def _summarize_unitary_patent(record: dict) -> str:
    """One-line Markdown summary for a Unitary Patent register record."""
    epo_number = record.get("epo_number") or "(unknown EP)"
    statuses = record.get("statuses") or []
    if not statuses:
        return (
            f"**Unitary Patent {epo_number}** — no unitary-effect record on file "
            f"(not elected, or registration not yet recorded)."
        )
    latest = statuses[0] if isinstance(statuses, list) else {}
    status_text = latest.get("text") or "(unknown status)"
    change_date = latest.get("change_date") or "?"
    registered = any(
        "registered" in (s.get("text") or "").lower() and "unitary" in (s.get("text") or "").lower()
        for s in statuses
        if isinstance(s, dict)
    )
    flag = "registered" if registered else "pending"
    return (
        f"**Unitary Patent {epo_number}** — status: {status_text} "
        f"({flag}); effective: {change_date}."
    )


@international_mcp.tool(annotations=READ_ONLY)
async def get_epo_unitary_patent_status(
    epo_number: Annotated[
        str,
        (
            "EP publication number (e.g. 'EP4108782' or 'EP4108782.B1'). "
            "Pass the granted B1 publication when known — UP register data "
            "is attached at grant."
        ),
    ],
) -> ResponseEnvelope[dict]:
    """Get the Unitary Patent (UP) Register record for a European patent application, with status, opt-out, license, and translation metadata.

    Calls the EPO Register's ``/upp`` sub-endpoint and returns the
    ``<reg:unitary-patent>`` block as structured data: the registration
    status timeline (e.g. "Request for unitary effect filed" →
    "Unitary effect registered") with the change date for each step.

    ``details`` is ``{}`` when the EP wasn't elected for unitary effect, or
    the registration hasn't been recorded yet. Note that UPC *opt-out*
    status is **not** exposed by the OPS Register — that requires the UPC
    CMS Public API (separate enrollment); the same caveat applies to
    license-of-right declarations and translation filings, which are
    surfaced through the register only after the unitary effect is
    registered.

    Related tools: get_epo_biblio, get_epo_legal_events, search_epo.
    """
    async with client_from_env() as client:
        result = await client.get_unitary_patent_package(epo_number)

    details: dict = result.model_dump() if result is not None else {}
    path = f"/rest-services/register/publication/epodoc/{epo_number}/upp"
    return ResponseEnvelope[dict](
        summary=_summarize_unitary_patent(details or {"epo_number": epo_number}),
        details=details,
        provenance=_epo_register_provenance(path),
    )


# ---------------------------------------------------------------------------
# JPO (Japan Patent Office) — Patent Information Retrieval API
#
# Each tool dispatches across patent / design / trademark via an
# ``ip_type`` argument so a single tool name covers all three IP types.
# Requires JPO_API_USERNAME / JPO_API_PASSWORD env vars (issued by JPO).
# Daily caps are enforced server-side per endpoint (handbook v14 Tables 1-3).
#
# Envelope helpers per CONNECTOR_STANDARDS.md §5.9 — every JPO tool returns
# a ``ResponseEnvelope`` (single-record facet) or ``ListEnvelope``
# (portfolio-shaped fan-outs per §5.4). Provenance points at the JPO
# Patent Information Retrieval API base.
# ---------------------------------------------------------------------------

_JPO_BASE = "https://ip-data.jpo.go.jp"
_JPO_NAME = "Japan Patent Office (JPO)"
_JPO_FANOUT_CONCURRENCY = 5


def _jpo_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{base}/api{path}`` on the JPO API."""
    return make_provenance(source_url=f"{_JPO_BASE}/api{path}", source_name=_JPO_NAME)


def _summarize_jpo_progress(application_number: str, record: dict) -> str:
    """One-line Markdown summary of a JPO progress record."""
    if not record:
        return f"**JPO application {application_number}** — no data on file."
    title = (
        record.get("title")
        or record.get("invention_title")
        or record.get("designArticleName")
        or record.get("design_article_name")
        or record.get("trademarkDisplayContent")
        or "(no title)"
    )
    filing = record.get("filing_date") or record.get("filingDate") or "?"
    status = (
        record.get("status")
        or record.get("application_status")
        or record.get("registrationStatus")
        or "(unknown status)"
    )
    head = f"**JPO application {application_number}** — {title}"
    return f"{head}\nFiled {filing}. Status: {status}."


def _summarize_jpo_registration(application_number: str, record: dict) -> str:
    """One-line Markdown summary of a JPO registration record."""
    if not record:
        return f"**JPO application {application_number}** — not registered."
    reg = record.get("registration_number") or record.get("registrationNumber") or "(no reg #)"
    reg_date = record.get("registration_date") or record.get("registrationDate") or "?"
    head = f"**JPO registration {reg}** (application {application_number})"
    return f"{head}\nRegistered {reg_date}."


def _summarize_jpo_priority(application_number: str, rows: list) -> str:
    return (
        f"**JPO application {application_number}** — "
        f"{len(rows)} priority claim{'s' if len(rows) != 1 else ''}."
    )


def _summarize_jpo_number_reference(number: str, kind: str, record: dict) -> str:
    if not record:
        return f"**JPO {kind} {number}** — no cross-reference found."
    return f"**JPO {kind} {number}** — cross-reference resolved."


def _summarize_jpo_jplatpat(application_number: str, url: str | None) -> str:
    if not url:
        return f"**JPO application {application_number}** — no J-PlatPat URL available."
    return f"**JPO application {application_number}** — J-PlatPat permalink: {url}"


def _classify_jpo_applicant(value: str) -> str:
    """Return 'code' for a 9-digit numeric string, 'name' otherwise.

    JPO applicant/attorney codes are exactly 9 digits. Names are any
    other (non-purely-numeric) text — typically Japanese registered
    entity names.
    """
    raw = value.strip()
    if raw.isdigit() and len(raw) == 9:
        return "code"
    return "name"


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
        str | list[str],
        "10-digit JP application number (Gregorian year 4 digits + 6-digit "
        "serial, e.g. '2020123456'), or a list for portfolio workflows. "
        "Format is the same for patent, design, and trademark applications.",
    ],
    ip_type: Annotated[
        Literal["patent", "design", "trademark"],
        "Which JPO register to query. The same tool works for all three.",
    ] = "patent",
) -> ListEnvelope[dict]:
    """Get full prosecution status for a JPO patent, design, or trademark filing.

    Returns title, applicants, filing/publication/registration dates,
    priority claims (Paris Convention or domestic), parent + divisional
    family info (patents and designs), expiration, erasure status, and
    the file-wrapper inventory.

    Per §5.4 accepts a single number or a list; the response is always a
    ListEnvelope. Each item is the per-application record, or ``{}`` for
    an unknown number (status 107 / 111). Bounded concurrent fan-out
    internally.

    Related tools: get_jpo_progress_simple, get_jpo_priority_info,
    get_jpo_registration_info, get_jpo_documents, get_jpo_jplatpat_url.
    """
    ip = _validate_ip_type(ip_type)
    numbers = (
        [application_number] if isinstance(application_number, str) else list(application_number)
    )
    if not numbers:
        raise ValidationError("get_jpo_progress requires at least one application number")

    semaphore = asyncio.Semaphore(_JPO_FANOUT_CONCURRENCY)
    from patent_client_agents.jpo import JpoClient

    async def _fetch_one(client: Any, appl: str) -> dict:
        async with semaphore:
            method = getattr(client, _JPO_PROGRESS_METHODS[ip])
            result = await method(appl)
            return _dump(result) if result else {}  # type: ignore[return-value]

    async with JpoClient() as client:
        items = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    if len(numbers) == 1:
        summary = _summarize_jpo_progress(numbers[0], items[0])
        path = f"/{ip}/v1/app_progress/{numbers[0]}"
    else:
        summary = f"Fetched {len(items)} JPO {ip} progress records: " + ", ".join(numbers)
        path = f"/{ip}/v1/app_progress"

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_jpo_provenance(path),
    )


@conditional_tool(international_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_jpo_progress_simple(
    application_number: Annotated[
        str | list[str],
        "10-digit JP application number, or a list for portfolio workflows.",
    ],
    ip_type: Annotated[
        Literal["patent", "design", "trademark"],
        "Which JPO register to query. The same tool works for all three.",
    ] = "patent",
) -> ListEnvelope[dict]:
    """Get a simplified JPO status (no priority or family detail).

    Works for patent, design, or trademark applications. Cheaper than
    ``get_jpo_progress`` for bulk status checks — same daily quota tier
    (400/day) but skips the priority and divisional sections. Per §5.4
    accepts a single number or a list; the response is always a
    ListEnvelope.

    Related tools: get_jpo_progress, get_jpo_priority_info,
    get_jpo_registration_info, get_jpo_documents.
    """
    ip = _validate_ip_type(ip_type)
    numbers = (
        [application_number] if isinstance(application_number, str) else list(application_number)
    )
    if not numbers:
        raise ValidationError("get_jpo_progress_simple requires at least one application number")

    semaphore = asyncio.Semaphore(_JPO_FANOUT_CONCURRENCY)
    from patent_client_agents.jpo import JpoClient

    async def _fetch_one(client: Any, appl: str) -> dict:
        async with semaphore:
            method = getattr(client, _JPO_PROGRESS_SIMPLE_METHODS[ip])
            result = await method(appl)
            return _dump(result) if result else {}  # type: ignore[return-value]

    async with JpoClient() as client:
        items = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    if len(numbers) == 1:
        summary = _summarize_jpo_progress(numbers[0], items[0])
        path = f"/{ip}/v1/app_progress_simple/{numbers[0]}"
    else:
        summary = f"Fetched {len(items)} JPO {ip} simplified status records."
        path = f"/{ip}/v1/app_progress_simple"

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_jpo_provenance(path),
    )


@conditional_tool(international_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_jpo_priority_info(
    application_number: Annotated[str, "10-digit JP application number"],
    ip_type: Annotated[
        Literal["patent", "design", "trademark"],
        "Which JPO register to query. The same tool works for all three.",
    ] = "patent",
) -> ListEnvelope[dict]:
    """List priority basis applications (Paris + domestic) for a JPO filing.

    Each row carries either a Paris Convention foreign priority
    (``parisPriorityApplicationNumber`` + country code + date) or a
    domestic JP priority (``nationalPriorityApplicationNumber`` +
    four-law code + date). Works for patent, design, or trademark
    applications.

    Related tools: get_jpo_progress, get_jpo_registration_info,
    get_jpo_number_reference.
    """
    ip = _validate_ip_type(ip_type)
    from patent_client_agents.jpo import JpoClient

    async with JpoClient() as client:
        method = getattr(client, _JPO_PRIORITY_METHODS[ip])
        priorities = await method(application_number)

    items = [_dump(p) for p in priorities]
    return ListEnvelope[dict](
        summary=_summarize_jpo_priority(application_number, items),
        items=items,
        provenance=_jpo_provenance(f"/{ip}/v1/priority_right_app_info/{application_number}"),
    )


@conditional_tool(international_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_jpo_registration_info(
    application_number: Annotated[
        str | list[str],
        "10-digit JP application number, or a list for portfolio workflows.",
    ],
    ip_type: Annotated[
        Literal["patent", "design", "trademark"],
        "Which JPO register to query. The same tool works for all three.",
    ] = "patent",
) -> ListEnvelope[dict]:
    """Get the JPO granted-rights record for a patent, design, or trademark filing.

    Includes registration number/date, decision date, current rights
    holders, claim count (patents) / design article (designs) /
    trademark display (trademarks), expiration, next pension payment
    due date, last paid year, erasure flag/date, and last update date.
    Per §5.4 accepts a single number or a list. Each item is ``{}`` when
    the application is not registered.

    Related tools: get_jpo_progress, get_jpo_priority_info,
    get_jpo_number_reference.
    """
    ip = _validate_ip_type(ip_type)
    numbers = (
        [application_number] if isinstance(application_number, str) else list(application_number)
    )
    if not numbers:
        raise ValidationError("get_jpo_registration_info requires at least one application number")

    semaphore = asyncio.Semaphore(_JPO_FANOUT_CONCURRENCY)
    from patent_client_agents.jpo import JpoClient

    async def _fetch_one(client: Any, appl: str) -> dict:
        async with semaphore:
            method = getattr(client, _JPO_REGISTRATION_METHODS[ip])
            result = await method(appl)
            return _dump(result) if result else {}  # type: ignore[return-value]

    async with JpoClient() as client:
        items = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    if len(numbers) == 1:
        summary = _summarize_jpo_registration(numbers[0], items[0])
        path = f"/{ip}/v1/registration_info/{numbers[0]}"
    else:
        summary = f"Fetched {len(items)} JPO {ip} registration records."
        path = f"/{ip}/v1/registration_info"

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_jpo_provenance(path),
    )


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
) -> ResponseEnvelope[dict]:
    """Convert a JPO number between application, publication, and registration forms.

    Given any one of the three identifiers for a JPO record (application
    number, publication number, or registration number), returns the
    other associated numbers for the same record. Works for patent,
    design, or trademark applications. ``details`` is ``{}`` when no
    cross-reference exists.

    Related tools: get_jpo_progress, get_jpo_registration_info,
    get_jpo_jplatpat_url.
    """
    ip = _validate_ip_type(ip_type)
    from patent_client_agents.jpo import JpoClient

    async with JpoClient() as client:
        method = getattr(client, _JPO_NUMBER_REF_METHODS[ip])
        result = await method(kind, number)

    details: dict = _dump(result) if result else {}  # type: ignore[assignment]
    return ResponseEnvelope[dict](
        summary=_summarize_jpo_number_reference(number, kind, details),
        details=details,
        provenance=_jpo_provenance(f"/{ip}/v1/case_number_reference/{kind}/{number}"),
    )


@conditional_tool(international_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_jpo_jplatpat_url(
    application_number: Annotated[str, "10-digit JP application number"],
    ip_type: Annotated[
        Literal["patent", "design", "trademark"],
        "Which JPO register to query. The same tool works for all three.",
    ] = "patent",
) -> ResponseEnvelope[dict]:
    """Get the J-PlatPat (JPO public search portal) permalink for a JPO filing.

    J-PlatPat is JPO's free public search portal — the returned URL is a
    stable permalink that opens directly to this filing's bibliographic
    page (in Japanese). Works for patent, design, or trademark
    applications. ``details["url"]`` is the permalink, or absent when no
    URL is available.

    Related tools: get_jpo_progress, get_jpo_number_reference.
    """
    ip = _validate_ip_type(ip_type)
    from patent_client_agents.jpo import JpoClient

    async with JpoClient() as client:
        method = getattr(client, _JPO_JPLATPAT_METHODS[ip])
        url = await method(application_number)

    details: dict = {"url": url} if url else {}
    return ResponseEnvelope[dict](
        summary=_summarize_jpo_jplatpat(application_number, url),
        details=details,
        provenance=_jpo_provenance(f"/{ip}/v1/jpp_fixed_address/{application_number}"),
    )


@conditional_tool(international_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_jpo_applicant(
    applicant: Annotated[
        str,
        "JPO applicant/attorney identifier. Either a 9-digit code "
        "(e.g. '000003207') or the EXACT registered name "
        "(e.g. 'トヨタ自動車株式会社'). Auto-detected: 9 digits → "
        "code lookup; anything else → name lookup. Name search "
        "requires an exact match — partial / fuzzy queries return no data.",
    ],
    ip_type: Annotated[
        Literal["patent", "design", "trademark"],
        "Which JPO register to query. The same tool works for all three.",
    ] = "patent",
) -> ResponseEnvelope[dict]:
    """Look up a JPO applicant/attorney by 9-digit code or by exact registered name.

    Auto-detects which lookup to run from the input shape: 9-digit
    numeric → code-to-name; anything else → exact-name-to-code(s).
    ``details["name"]`` carries the resolved name for a code lookup;
    ``details["results"]`` carries the matching code rows for a name
    lookup. Empty when nothing matches. Works for patent, design, or
    trademark registers.

    Related tools: get_jpo_progress, get_jpo_registration_info.
    """
    ip = _validate_ip_type(ip_type)
    kind = _classify_jpo_applicant(applicant)
    from patent_client_agents.jpo import JpoClient

    async with JpoClient() as client:
        if kind == "code":
            method = getattr(client, _JPO_APPLICANT_BY_CODE_METHODS[ip])
            name = await method(applicant)
            details: dict = {"name": name} if name else {}
            path = f"/{ip}/v1/applicant_attorney_cd/{applicant}"
            summary = (
                f"**JPO applicant code {applicant}** — {name}"
                if name
                else f"**JPO applicant code {applicant}** — not found."
            )
        else:
            method = getattr(client, _JPO_APPLICANT_BY_NAME_METHODS[ip])
            applicants = await method(applicant)
            rows = [_dump(a) for a in applicants]
            details = {"results": rows}
            path = f"/{ip}/v1/applicant_attorney/{applicant}"
            summary = (
                f"**JPO applicant `{applicant}`** — {len(rows)} matching code(s)."
                if rows
                else f"**JPO applicant `{applicant}`** — not found (exact match required)."
            )

    return ResponseEnvelope[dict](
        summary=summary,
        details=details,
        provenance=_jpo_provenance(path),
    )


# ---------------------------------------------------------------------------
# JPO patent-only endpoints (no design / trademark equivalent)
# ---------------------------------------------------------------------------


@conditional_tool(international_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_jpo_patent_divisional_info(
    application_number: Annotated[str, "10-digit JP patent application number"],
) -> ResponseEnvelope[dict]:
    """Get the divisional family (parent + descendants) for a JP patent.

    Patent-only endpoint (no design or trademark equivalent). Returns
    the parent application info (if any) and a list of divisional
    descendants with their generation, publication/registration numbers,
    erasure status, and expiration. ``details`` is ``{}`` when the
    application has no divisional history.

    Related tools: get_jpo_progress, get_jpo_patent_cited_documents,
    get_jpo_pct_national_phase_number.
    """
    from patent_client_agents.jpo import JpoClient

    async with JpoClient() as client:
        result = await client.get_patent_divisional_info(application_number)

    details: dict = _dump(result) if result else {}  # type: ignore[assignment]
    summary = (
        f"**JPO patent {application_number}** — divisional family resolved."
        if details
        else f"**JPO patent {application_number}** — no divisional history."
    )
    return ResponseEnvelope[dict](
        summary=summary,
        details=details,
        provenance=_jpo_provenance(f"/patent/v1/divisional_app_info/{application_number}"),
    )


@conditional_tool(international_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_jpo_patent_cited_documents(
    application_number: Annotated[str, "10-digit JP patent application number"],
) -> ResponseEnvelope[dict]:
    """Get patent and non-patent literature citations for a JP patent application.

    Patent-only endpoint. Returns ``patentDoc`` (cited patent documents
    with type/order) and ``nonPatentDoc`` (non-patent literature with
    author, title, publication, etc.). Citation types follow JPO
    code-table 07010. ``details`` is ``{}`` when no citations exist.

    Related tools: get_jpo_progress, get_jpo_patent_divisional_info.
    """
    from patent_client_agents.jpo import JpoClient

    async with JpoClient() as client:
        result = await client.get_patent_cited_documents(application_number)

    details: dict = _dump(result) if result else {}  # type: ignore[assignment]
    summary = (
        f"**JPO patent {application_number}** — citation record resolved."
        if details
        else f"**JPO patent {application_number}** — no citations on file."
    )
    return ResponseEnvelope[dict](
        summary=summary,
        details=details,
        provenance=_jpo_provenance(f"/patent/v1/cite_doc_info/{application_number}"),
    )


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
) -> ResponseEnvelope[dict]:
    """Look up the JP national-phase application number for a PCT filing.

    Patent-only endpoint. Useful for following PCT applications that
    have entered Japan's national phase. ``details`` is ``{}`` when the
    PCT filing has no JP national-phase record.

    Related tools: get_jpo_progress, get_jpo_patent_divisional_info.
    """
    from patent_client_agents.jpo import JpoClient

    async with JpoClient() as client:
        result = await client.get_patent_pct_national_number(kind, number)

    details: dict = _dump(result) if result else {}  # type: ignore[assignment]
    summary = (
        f"**PCT {number}** — JP national phase resolved."
        if details
        else f"**PCT {number}** — no JP national-phase record."
    )
    return ResponseEnvelope[dict](
        summary=summary,
        details=details,
        provenance=_jpo_provenance(
            f"/patent/v1/pct_national_phase_application_number/{kind}/{number}"
        ),
    )


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
                    await download_response(
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
            kind,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
            ip,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
            application_number=application_number,
        )

        download_url = build_download_url(resource_path)

        payload = bundle.model_dump()
        payload["download_url"] = download_url
        payload["filename"] = filename
        payload["content_type"] = "application/zip"
        return payload
