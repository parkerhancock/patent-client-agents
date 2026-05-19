"""JPO (Japan Patent Office) Patent Information Retrieval API MCP tools.

Each tool dispatches across patent / design / trademark via an ``ip_type``
argument so a single tool name covers all three IP types. Requires
``JPO_API_USERNAME`` / ``JPO_API_PASSWORD`` env vars (issued by JPO).
Daily caps are enforced server-side per endpoint (handbook v14 Tables 1-3).

JPO tools are env-gated: they only appear in tool/list when both
credentials are set. The hosted public deploy at ``mcp.patentclient.com``
intentionally does not carry these keys per JPO TOS; private deploys flip
them on by adding the secrets to their Cloud Run env. The download fetcher
uses ``register_source_if_configured`` for the same reason — defense in
depth.

Envelope helpers follow ``CONNECTOR_STANDARDS.md`` §5.9 — every JPO tool
returns a ``ResponseEnvelope`` (single-record facet) or ``ListEnvelope``
(portfolio-shaped fan-outs per §5.4). Provenance points at the JPO Patent
Information Retrieval API base.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, Literal, cast

import httpx
from fastmcp import FastMCP

from law_tools_core.envelope import (
    ListEnvelope,
    ResponseEnvelope,
    make_provenance,
)
from law_tools_core.exceptions import ValidationError
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
)

_JPO_REQUIRED_ENV: list[str] = ["JPO_API_USERNAME", "JPO_API_PASSWORD"]

jpo_mcp = FastMCP("JPO")


def _dump(obj: object) -> dict[str, Any]:
    """Serialize a Pydantic model to a dict (or pass through dicts)."""
    if hasattr(obj, "model_dump"):
        return cast("dict[str, Any]", obj.model_dump())  # type: ignore[union-attr]  # ty: ignore[call-non-callable]
    if isinstance(obj, dict):
        return cast("dict[str, Any]", obj)
    raise TypeError(f"_dump expected a Pydantic model or dict, got {type(obj).__name__}")


# ---------------------------------------------------------------------------
# IP type / doc kind aliases — re-used by JPO tools below.
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Download fetcher — JPO document bundles
# ---------------------------------------------------------------------------


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
    jpo_mcp,
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
# JPO — envelope helpers
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


# ---------------------------------------------------------------------------
# JPO — MCP tools (env-gated)
# ---------------------------------------------------------------------------


@conditional_tool(jpo_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
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


@conditional_tool(jpo_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
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


@conditional_tool(jpo_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
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


@conditional_tool(jpo_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
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


@conditional_tool(jpo_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
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


@conditional_tool(jpo_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
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


@conditional_tool(jpo_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
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


@conditional_tool(jpo_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
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


@conditional_tool(jpo_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
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


@conditional_tool(jpo_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
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


@conditional_tool(jpo_mcp, requires_env=_JPO_REQUIRED_ENV, annotations=READ_ONLY)
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
