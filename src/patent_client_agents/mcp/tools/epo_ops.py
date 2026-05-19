"""EPO Open Patent Services (OPS) MCP tools — search, biblio, fulltext, family, legal events, number conversion, and the EPO Register Unitary Patent status endpoint."""

from __future__ import annotations

import asyncio
import base64
from typing import Annotated, Any, cast

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
from law_tools_core.mcp.downloads import (
    read_resource,
    register_source,
)
from patent_client_agents.epo_ops.client import client_from_env

epo_ops_mcp = FastMCP("EPO OPS")


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


@epo_ops_mcp.resource(
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


@epo_ops_mcp.tool(annotations=READ_ONLY)
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


@epo_ops_mcp.tool(annotations=READ_ONLY)
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


@epo_ops_mcp.tool(annotations=READ_ONLY)
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


@epo_ops_mcp.tool(annotations=READ_ONLY)
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


@epo_ops_mcp.tool(annotations=READ_ONLY)
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


@epo_ops_mcp.tool(annotations=READ_ONLY)
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


@epo_ops_mcp.tool(annotations=READ_ONLY)
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


@epo_ops_mcp.tool(annotations=READ_ONLY)
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
