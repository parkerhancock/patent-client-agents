"""USPTO Trademark MCP tools (TESS search, TMEP, TSDR, trademark assignments).

Tools backed by:

- ``patent_client_agents.uspto_tmsearch`` — TESS Elasticsearch search.
  Needs an AWS WAF token (see token_manager docs); install with the
  ``[tmsearch]`` extra to enable in-process token minting via Playwright.
- ``patent_client_agents.tmep`` — TMEP corpus search/lookup. No auth.
- ``patent_client_agents.uspto_tsdr`` — TSDR status / documents.
  Requires ``USPTO_TSDR_API_KEY``.
- ``patent_client_agents.uspto_trademark_assignments`` — Assignment Center
  records. No auth.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, cast

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.exceptions import ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.tmep import TmepClient, get_corpus_status
from patent_client_agents.uspto_tmsearch import TmsearchClient
from patent_client_agents.uspto_trademark_assignments import TrademarkAssignmentClient
from patent_client_agents.uspto_tsdr import TsdrClient

trademarks_mcp = FastMCP("Trademarks")


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


def _dump_list(items: list) -> dict:
    return {"results": [_dump(i) for i in items]}


# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). See uspto.py for the
# canonical template; this file adds source-specific helpers for TM Search
# (TESS) and TSDR.
# ──────────────────────────────────────────────────────────────────────

_TMSEARCH_BASE = "https://tmsearch.uspto.gov"
_TMSEARCH_NAME = "USPTO Trademark Search (TESS)"
_TSDR_BASE = "https://tsdrapi.uspto.gov"
_TSDR_NAME = "USPTO TSDR"
_TMEP_BASE = "https://tmep.uspto.gov"
_TMEP_NAME = "USPTO TMEP (Trademark Manual of Examining Procedure)"

# Lean snippet cap (§5.5). FTS5 already returns short snippets, but the
# raw column can run long when the surrounding context is dense; truncate
# so a 25-hit page fits comfortably under the §5.5 token budget.
_TMEP_LEAN_SNIPPET_CHARS = 400

# Bounded fan-out for list-accepting get_tmep_section (§5.4). SQLite reads
# are fast so the concurrency budget is conservative — the cap exists so a
# 50-section portfolio doesn't open 50 connections at once.
_TMEP_FANOUT_CONCURRENCY = 5


def _tmsearch_provenance(path: str) -> Any:
    return make_provenance(source_url=f"{_TMSEARCH_BASE}{path}", source_name=_TMSEARCH_NAME)


def _tsdr_provenance(path: str) -> Any:
    return make_provenance(source_url=f"{_TSDR_BASE}{path}", source_name=_TSDR_NAME)


def _tmep_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{base}{path}`` with corpus metadata.

    Reads ``corpus_synced_at`` / ``corpus_version`` from
    :func:`patent_client_agents.tmep.get_corpus_status` so the values
    track the bundled corpus without per-call hardcoding. Mirrors the
    MPEP pattern (CONNECTOR_STANDARDS.md §4 / §5.9).
    """
    status = get_corpus_status()
    return make_provenance(
        source_url=f"{_TMEP_BASE}{path}",
        source_name=_TMEP_NAME,
        corpus_synced_at=status["corpus_synced_at"],
        corpus_version=status["corpus_version"],
    )


def _truncate(text: str, limit: int) -> str:
    """Cap a string at ``limit`` chars, appending an ellipsis on overflow."""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _stub_tmep_hit(hit: dict) -> dict:
    """Lean projection of a TMEP search hit (§5.5).

    Drops the per-row ``result_url`` (reconstructable from ``href``) and
    truncates the snippet to keep multi-hit pages cheap. Use
    ``get_tmep_section`` for the full content of any hit.
    """
    title = hit.get("title") or ""
    path_parts = hit.get("path") or []
    section_number: str | None = None
    title_only = title
    for part in path_parts:
        # path looks like ["Chapter 1200", "1207"]; the last entry that is
        # NOT a "Chapter ..." string is the section number.
        if isinstance(part, str) and not part.lower().startswith("chapter"):
            section_number = part
    if section_number and title.startswith(f"{section_number} - "):
        title_only = title[len(section_number) + 3 :]
    return {
        "section_number": section_number,
        "title": title_only,
        "snippet": _truncate(hit.get("snippet") or "", _TMEP_LEAN_SNIPPET_CHARS),
        "href": hit.get("href"),
    }


def _summarize_tmep_section(record: dict, corpus_version: str) -> str:
    """One-line Markdown summary of a single TMEP section record.

    Leads with the corpus version so the agent can quote it directly
    when warning about staleness (§4 + §5.13).
    """
    section_number = record.get("section_number") or "(no §)"
    title = record.get("title") or "(no title)"
    href = record.get("href") or ""
    head = f"**TMEP {corpus_version} — §{section_number}: {title}**"
    if href:
        return f"{head}\nSource: {_TMEP_BASE}/RDMS/TMEP/result?href={href}"
    return head


def _tmep_section_to_dict(section: Any, *, section_number: str | None) -> dict:
    """Dump a TmepSection model and re-attach the section_number we resolved.

    The model carries href + html + text + title + version, but not the
    practitioner-facing section_number (the corpus row carries it but
    the TmepSection model drops it). We surface it on the returned dict
    so agents can quote it without round-tripping.
    """
    data = section.model_dump() if hasattr(section, "model_dump") else dict(section)
    data["section_number"] = section_number
    return data


def _stub_trademark(record: dict) -> dict:
    """Lean projection of a TESS trademark search row (§5.5)."""
    return {
        "serial_number": record.get("serialNumber"),
        "registration_number": record.get("registrationNumber"),
        "wordmark": record.get("wordmark") or record.get("markIdentification"),
        "owner_name": record.get("ownerName"),
        "filing_date": record.get("filingDate"),
        "registration_date": record.get("registrationDate"),
        "status_code": record.get("statusCode"),
        "status_text": record.get("statusText") or record.get("status"),
    }


def _summarize_trademark(record: dict) -> str:
    """One-line Markdown summary of a single trademark record."""
    serial = record.get("serialNumber") or "(no serial)"
    mark = record.get("wordmark") or record.get("markIdentification") or "(no mark)"
    owner = record.get("ownerName") or "(no owner)"
    status = record.get("statusText") or record.get("status") or "(unknown status)"
    reg = record.get("registrationNumber")
    head = f"**US trademark {serial}** — {mark} (owner: {owner})"
    line = f"Status: {status}."
    if reg:
        line = f"Registration {reg}. {line}"
    return f"{head}\n{line}"


def _classify_tm_identifier(value: str) -> str:
    """Return 'serial' or 'registration' from a numeric trademark identifier.

    USPTO serial numbers are 8 digits; registration numbers are typically
    7. Anything else raises ``ValidationError`` — auto-detection should be
    a help, not a guess.
    """
    raw = value.strip()
    if not raw.isdigit():
        raise ValidationError(
            f"trademark identifier must be all digits; got {value!r}. "
            f"Accepts 8-digit serial numbers (e.g. '97123456') or 7-digit "
            f"registration numbers (e.g. '1234567')."
        )
    if len(raw) == 8:
        return "serial"
    if len(raw) in (6, 7):
        return "registration"
    raise ValidationError(
        f"trademark identifier {value!r} has {len(raw)} digits; expected 8 (serial) "
        f"or 6-7 (registration)."
    )


_TM_FANOUT_CONCURRENCY = 5


# ---------------------------------------------------------------
# Trademark Search (TESS)
# ---------------------------------------------------------------


@trademarks_mcp.tool(annotations=READ_ONLY)
async def search_trademarks(
    query: Annotated[
        str,
        "Search query — a wordmark, owner name, or goods/services description.",
    ],
    search_by: Annotated[
        str,
        "Which field to search. 'wordmark' (default) — trademark text; 'owner' — registrant name; "
        "'goods_services' — goods/services description. The legacy 'general' alias is "
        "equivalent to 'wordmark'.",
    ] = "wordmark",
    paginate_all: Annotated[
        bool,
        "When true, auto-paginates through all matching results (wordmark/owner only). "
        "Ignored for goods_services.",
    ] = False,
    max_results: Annotated[
        int,
        "Cap on total results when paginate_all=True.",
    ] = 500,
    full: Annotated[
        bool,
        "When False (default), each hit is a lean stub: serial, wordmark, owner, "
        "status, filing/registration dates, registration number. When True, returns "
        "the full TESS record per hit (large; prefer ``get_trademark`` for one).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search USPTO trademarks by wordmark, owner, or goods/services (TESS).

    Returns lean stubs by default. Use ``get_trademark`` for a full record by
    serial or registration number, and ``get_trademark_status`` for current
    TSDR status on one or many marks.

    Related tools: get_trademark, get_trademark_status, get_trademark_documents,
    search_trademark_assignments.
    """
    field = search_by.strip().lower()
    if field == "general":
        field = "wordmark"
    if field not in ("wordmark", "owner", "goods_services"):
        raise ValidationError(
            f"search_by must be 'wordmark', 'owner', or 'goods_services'; got {search_by!r}"
        )

    async with TmsearchClient() as client:
        if paginate_all:
            if field == "goods_services":
                raise ValidationError(
                    "paginate_all is not supported for search_by='goods_services'"
                )
            kwargs: dict = {"max_results": max_results}
            if field == "owner":
                kwargs["owner"] = query
            else:
                kwargs["wordmark"] = query
            raw_results = await client.search_all(**kwargs)
            results = [_dump(r) for r in raw_results]
        else:
            if field == "wordmark":
                response = await client.search(wordmark=query)
            elif field == "owner":
                response = await client.search_owner(query)
            else:  # goods_services
                response = await client.search(goods_services=query)
            results = [_dump(r) for r in (response.results or [])]

    items = results if full else [_stub_trademark(r) for r in results]
    return ListEnvelope[dict](
        summary=f"USPTO trademarks (by {field}) — `{query}`: {len(items)} hits.",
        items=items,
        provenance=_tmsearch_provenance("/prod-stage-v1-0-0/tmsearch"),
    )


@trademarks_mcp.tool(annotations=READ_ONLY)
async def get_trademark(
    serial_number: Annotated[
        str | list[str],
        "USPTO trademark serial number (8 digits, e.g. '97123456') OR registration "
        "number (typically 7 digits, e.g. '1234567'). Auto-detected by digit count. "
        "Pass a list for portfolio workflows; the response shape stays a ListEnvelope.",
    ],
) -> ListEnvelope[dict]:
    """Get one or more USPTO trademark records (TESS) by serial or registration number.

    Auto-detects serial vs. registration by digit count (8 → serial, 6-7 →
    registration). Accepts either a single string or a list (§5.4); the
    response is always a ListEnvelope so the shape is stable.

    Returns full trademark details: wordmark, owner, goods/services, filing
    and registration dates, status. For current status only (no full record),
    use ``get_trademark_status`` (TSDR).

    Related tools: search_trademarks, get_trademark_status, get_trademark_documents.
    """
    numbers = [serial_number] if isinstance(serial_number, str) else list(serial_number)
    if not numbers:
        raise ValidationError("get_trademark requires at least one identifier")

    semaphore = asyncio.Semaphore(_TM_FANOUT_CONCURRENCY)

    async def _fetch_one(client: TmsearchClient, ident: str) -> dict | None:
        kind = _classify_tm_identifier(ident)
        async with semaphore:
            if kind == "serial":
                record = await client.get_by_serial(ident)
            else:
                record = await client.get_by_registration(ident)
        return _dump(record) if record is not None else None  # type: ignore[return-value]

    async with TmsearchClient() as client:
        fetched = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    items: list[dict] = [r for r in fetched if r is not None]
    not_found = [n for n, r in zip(numbers, fetched, strict=True) if r is None]

    if len(numbers) == 1 and items:
        summary = _summarize_trademark(items[0])
    elif len(numbers) == 1:
        summary = f"USPTO trademark {numbers[0]} — not found."
    else:
        head = f"Fetched {len(items)} of {len(numbers)} USPTO trademarks."
        summary = head + (f" Not found: {', '.join(not_found)}." if not_found else "")

    # Provenance: per-record path for single ID, base path for multi.
    if len(numbers) == 1:
        kind = _classify_tm_identifier(numbers[0])
        path = f"/prod-stage-v1-0-0/tmsearch?{kind}={numbers[0]}"
    else:
        path = "/prod-stage-v1-0-0/tmsearch"

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_tmsearch_provenance(path),
    )


# ---------------------------------------------------------------
# TSDR (Trademark Status & Document Retrieval)
# ---------------------------------------------------------------


@trademarks_mcp.tool(annotations=READ_ONLY)
async def get_trademark_status(
    serial_number: Annotated[
        str | list[str],
        "USPTO trademark serial number, or a list for portfolio status checks. "
        "Examples: '97123456', ['97123456', '97654321'].",
    ],
) -> ListEnvelope[dict]:
    """Get current trademark status from TSDR for one or many marks.

    Accepts a single serial number or a list (§5.4) and returns a
    ListEnvelope of TSDR status records: filing date, registration date,
    mark text, status code and description. Bounded concurrent fan-out
    internally. Requires ``USPTO_TSDR_API_KEY``.

    Replaces the deleted ``batch_trademark_status`` — pass a list here
    instead.

    Related tools: get_trademark, get_trademark_documents, get_trademark_last_update.
    """
    numbers = [serial_number] if isinstance(serial_number, str) else list(serial_number)
    if not numbers:
        raise ValidationError("get_trademark_status requires at least one serial number")

    semaphore = asyncio.Semaphore(_TM_FANOUT_CONCURRENCY)

    async def _fetch_one(client: TsdrClient, n: str) -> dict:
        async with semaphore:
            return _dump(await client.get_status(n))  # type: ignore[return-value]

    async with TsdrClient() as client:
        items = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    if len(numbers) == 1:
        summary = f"TSDR status for USPTO trademark {numbers[0]}."
        path = f"/ts/cd/casestatus/sn{numbers[0]}/info.xml"
    else:
        summary = f"TSDR status for {len(numbers)} USPTO trademarks: {', '.join(numbers)}."
        path = "/ts/cd/casestatus"

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_tsdr_provenance(path),
    )


@trademarks_mcp.tool(annotations=READ_ONLY)
async def get_trademark_documents(
    serial_number: Annotated[str, "USPTO trademark serial number (8 digits)."],
) -> ListEnvelope[dict]:
    """List prosecution documents (office actions, responses, registration certs) from TSDR.

    Returns a ListEnvelope of document records for one trademark application.
    Requires ``USPTO_TSDR_API_KEY``.

    Related tools: get_trademark_status, get_trademark, search_trademarks.
    """
    async with TsdrClient() as client:
        docs = await client.get_documents(serial_number)

    items = [_dump(d) for d in docs]
    return ListEnvelope[dict](
        summary=(
            f"TSDR prosecution documents for USPTO trademark {serial_number} "
            f"— {len(items)} documents."
        ),
        items=items,
        provenance=_tsdr_provenance(f"/ts/cd/casedocs/sn{serial_number}/index.xml"),
    )


@trademarks_mcp.tool(annotations=READ_ONLY)
async def get_trademark_last_update(
    serial_number: Annotated[
        str | list[str],
        "USPTO trademark serial number, or a list for portfolio checks. "
        "Examples: '97123456', ['97123456', '97654321'].",
    ],
) -> ListEnvelope[dict]:
    """Get last-update timestamps for one or many trademark cases (TSDR).

    Returns a ListEnvelope of records reporting when each trademark case was
    last modified at the USPTO. Useful for change-detection sweeps across a
    portfolio. Requires ``USPTO_TSDR_API_KEY``.

    Related tools: get_trademark_status, get_trademark_documents.
    """
    numbers = [serial_number] if isinstance(serial_number, str) else list(serial_number)
    if not numbers:
        raise ValidationError("get_trademark_last_update requires at least one serial number")

    semaphore = asyncio.Semaphore(_TM_FANOUT_CONCURRENCY)

    async def _fetch_one(client: TsdrClient, n: str) -> dict:
        async with semaphore:
            return _dump(await client.get_last_update(n))  # type: ignore[return-value]

    async with TsdrClient() as client:
        items = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    if len(numbers) == 1:
        summary = f"TSDR last-update for USPTO trademark {numbers[0]}."
        path = f"/ts/cd/caselastupdate/sn{numbers[0]}"
    else:
        summary = f"TSDR last-update for {len(numbers)} trademarks: {', '.join(numbers)}."
        path = "/ts/cd/caselastupdate"

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_tsdr_provenance(path),
    )


# ---------------------------------------------------------------
# TMEP (Trademark Manual of Examining Procedure)
# ---------------------------------------------------------------


@trademarks_mcp.tool(annotations=READ_ONLY)
async def search_tmep(
    query: Annotated[
        str,
        "Search query. Examples: 'likelihood of confusion', 'specimen of use', "
        "'identification of goods'. By default treated as an adjacent-word phrase; "
        "set ``syntax='or'`` to widen.",
    ],
    limit: Annotated[int, "Maximum hits to return (1-100)."] = 25,
    offset: Annotated[int, "Result offset for pagination."] = 0,
    syntax: Annotated[
        str,
        "Query syntax. 'adj' (default) — adjacent-word phrase match. "
        "'and' — all terms must match. 'or' — any term matches. 'exact' — same as 'adj'.",
    ] = "adj",
    sort: Annotated[
        str,
        "'relevance' (BM25, default) or 'outline' (section_number ascending).",
    ] = "relevance",
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: section_number, "
        "title, snippet (truncated to ~400 chars), href. When True, returns "
        "the upstream TmepSearchHit shape (title prefixed with section_number, "
        "the full result_url, and the path breadcrumb).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search the Trademark Manual of Examining Procedure (TMEP) for relevant sections.

    The TMEP is the USPTO examiner's manual for trademark registration
    practice — controlling distinctiveness, likelihood-of-confusion,
    specimen, and identification-of-goods analysis. Returns relevance-
    ranked hits with truncated snippets by default; use ``get_tmep_section``
    for the full section text by section number or href. Pass ``full=True``
    to get the upstream-shaped row.

    Examples:
      * §2(d) refusals: query='likelihood of confusion'
      * Distinctiveness analysis: query='acquired distinctiveness'
      * Specimen practice: query='specimen of use'

    Related tools: get_tmep_section.
    """
    if limit < 1 or limit > 100:
        raise ValidationError(f"limit must be between 1 and 100; got {limit}")

    # Translate the offset/limit pair into the underlying client's page/per_page.
    page = (offset // limit) + 1 if offset >= 0 else 1
    async with TmepClient() as client:
        response = await client.search(
            query=query,
            syntax=syntax,
            sort=sort,
            per_page=limit,
            page=page,
        )

    hits = [h.model_dump() for h in response.hits]
    items = hits if full else [_stub_tmep_hit(h) for h in hits]

    status = get_corpus_status()
    corpus_label = status["corpus_version"]
    summary = f"TMEP ({corpus_label}) — `{query}`: {len(items)} hit{'s' if len(items) != 1 else ''}"
    if response.has_more:
        summary += " (more available)."
    else:
        summary += "."

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        more_available=response.has_more,
        next_cursor=None,
        provenance=_tmep_provenance("/RDMS/TMEP/search"),
    )


@trademarks_mcp.tool(annotations=READ_ONLY)
async def get_tmep_section(
    section: Annotated[
        str | list[str],
        "TMEP section number (e.g. '1207', '1207.01(a)', '1209.03(u)'), an "
        "eTMEP href ('TMEP-1200d1e8145.html'), or a list of either for "
        "portfolio workflows. Examples: '1207', ['1207', '1209.03(u)', '1402'].",
    ],
) -> ListEnvelope[dict]:
    """Get one or more TMEP sections by number (or eTMEP href).

    Returns each section's title, full HTML, plaintext, and the resolved
    href. Accepts either a single section reference or a list (§5.4); the
    response is always a ListEnvelope so the shape is stable. Bounded
    concurrent fan-out internally; order matches the input.

    The TMEP is the Trademark Manual of Examining Procedure — the USPTO
    examiner's manual controlling trademark registration practice. The
    bundled corpus version is surfaced in ``provenance.corpus_version``
    so agents can quote freshness.

    Related tools: search_tmep.
    """
    refs = [section] if isinstance(section, str) else list(section)
    if not refs:
        raise ValidationError("get_tmep_section requires at least one section reference")

    semaphore = asyncio.Semaphore(_TMEP_FANOUT_CONCURRENCY)

    async def _fetch_one(client: TmepClient, ref: str) -> dict:
        async with semaphore:
            record = await client.get_section(ref)
            # When the caller passes a section number, ``ref`` already is
            # the section number. When they pass an href, the corpus row
            # carries the section_number but the TmepSection model drops
            # it. Resolve via SECTION_NUMBER_PATTERN so the returned dict
            # carries section_number when we know it.
            from patent_client_agents.tmep.client import SECTION_NUMBER_PATTERN

            section_number = ref if SECTION_NUMBER_PATTERN.match(ref) else None
            return _tmep_section_to_dict(record, section_number=section_number)

    async with TmepClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, ref) for ref in refs])

    status = get_corpus_status()
    corpus_label = status["corpus_version"]
    if len(results) == 1:
        summary = _summarize_tmep_section(results[0], corpus_label)
        ref = refs[0]
        if ref.endswith(".html") or "/" in ref:
            path = f"/RDMS/TMEP/result?href={ref.lstrip('/')}"
        else:
            path = f"/RDMS/TMEP/result?section={ref}"
    else:
        joined = ", ".join(refs)
        summary = f"Fetched {len(results)} TMEP sections ({corpus_label}): {joined}"
        path = "/RDMS/TMEP/result"

    return ListEnvelope[dict](
        summary=summary,
        items=results,
        provenance=_tmep_provenance(path),
    )


# ---------------------------------------------------------------
# Trademark Assignment Center
# ---------------------------------------------------------------


_TM_ASSIGNMENT_AXES = (
    "assignee",
    "assignor",
    "serial_number",
    "registration_number",
    "reel_frame",
)

_TM_ASSIGNMENT_BASE = "https://assignment-api.uspto.gov"
_TM_ASSIGNMENT_NAME = "USPTO Trademark Assignment Center"


def _tm_assignment_provenance(path: str) -> Any:
    return make_provenance(
        source_url=f"{_TM_ASSIGNMENT_BASE}{path}",
        source_name=_TM_ASSIGNMENT_NAME,
    )


def _stub_trademark_assignment(record: Any) -> dict:
    """Lean projection (§5.5) of a trademark assignment recordation."""
    data = record.model_dump() if hasattr(record, "model_dump") else dict(record)
    assignors = data.get("assignors") or []
    assignees = data.get("assignees") or []
    properties = data.get("properties") or []
    first_assignor = (
        assignors[0].get("assignor_name") if assignors and isinstance(assignors[0], dict) else None
    )
    first_assignee = assignees[0] if assignees else None
    first_property = properties[0] if properties and isinstance(properties[0], dict) else {}
    reel_frame = (
        f"{data.get('reel_number')}/{data.get('frame_number')}"
        if data.get("reel_number") is not None and data.get("frame_number") is not None
        else None
    )
    return {
        "reel_frame": reel_frame,
        "assignor": first_assignor,
        "assignee": first_assignee,
        "assignor_execution_date": data.get("assignor_execution_date"),
        "number_of_properties": data.get("number_of_properties"),
        "serial_number": first_property.get("serial_number"),
        "registration_number": first_property.get("registration_number"),
        "mark": first_property.get("mark"),
    }


@trademarks_mcp.tool(annotations=READ_ONLY)
async def search_trademark_assignments(
    query: Annotated[
        str,
        "Value to search for (e.g. 'Apple Inc', '97123456', '9006/0093').",
    ],
    by: Annotated[
        str,
        "What kind of value `query` is. One of: assignee, assignor, "
        "serial_number, registration_number, reel_frame.",
    ],
    limit: Annotated[
        int,
        "Maximum records to return per request (max 1000).",
    ] = 100,
    start_row: Annotated[
        int,
        "1-based starting row for pagination.",
    ] = 1,
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: reel/frame, "
        "first assignor, first assignee, execution date, number of "
        "properties, plus the lead property's serial/registration number "
        "and mark text. When True, every hit is the full Trademark "
        "Assignment Center record (all properties, all assignors, "
        "correspondent, domestic representative, etc.).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search USPTO trademark assignment recordations by assignee, assignor, or mark identifier.

    Returns recordations with reel/frame, assignors, assignees, and
    affected trademark properties. Lean by default (§5.5); use
    ``full=True`` for the upstream record per hit. No auth required.
    For the underlying register data, use ``get_trademark`` (full record)
    or ``get_trademark_status`` (current TSDR status).

    Related tools: get_trademark, get_trademark_status, search_trademarks.
    """
    axis = by.strip().lower()
    if axis not in _TM_ASSIGNMENT_AXES:
        raise ValidationError(f"`by` must be one of {_TM_ASSIGNMENT_AXES}; got {by!r}")

    async with TrademarkAssignmentClient() as client:
        if axis == "assignee":
            records = await client.search_by_assignee(query, start_row=start_row, limit=limit)
        elif axis == "assignor":
            records = await client.search_by_assignor(query, start_row=start_row, limit=limit)
        elif axis == "serial_number":
            records = await client.search_by_serial(query, limit=limit)
        elif axis == "registration_number":
            records = await client.search_by_registration(query, limit=limit)
        else:  # reel_frame
            records = await client.search_by_reel_frame(query)

    items = (
        [_dump(r) for r in records] if full else [_stub_trademark_assignment(r) for r in records]
    )
    shown = len(items)
    summary = (
        f"USPTO trademark assignments (by {axis}) — `{query}`: {shown} hit"
        f"{'s' if shown != 1 else ''}."
    )
    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_tm_assignment_provenance(
            "/ipas/search/api/v2/public/trademark/exportTradeMarkData"
        ),
    )
