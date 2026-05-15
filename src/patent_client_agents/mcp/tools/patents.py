"""Google Patents and cross-source patent MCP tools.

The fused tools (``get_patent_claims``, ``download_patent_pdf``) delegate to
:mod:`patent_client_agents.unified` — the MCP wrappers handle annotations,
view shapes, and signed-URL packaging; fusion semantics live in the library.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, cast

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.exceptions import NotFoundError, RateLimitError, ValidationError
from law_tools_core.filenames import patent_pdf as _patent_pdf_name
from law_tools_core.mcp.annotations import READ_ONLY
from law_tools_core.mcp.downloads import (
    download_tool_result,
    read_resource,
    register_source,
)
from patent_client_agents import unified
from patent_client_agents.google_patents import GooglePatentsClient

_GET_PATENT_BUDGET_SECONDS = 60.0
_GP_FANOUT_CONCURRENCY = 5

patents_mcp = FastMCP("Patents")


# ──────────────────────────────────────────────────────────────────────
# Envelope helpers — Google Patents source-specific wrappers around
# law_tools_core.envelope. Google Patents is a worldwide aggregator that
# indexes >100 jurisdictions including offices unreachable via authoritative
# APIs; "Google Patents (worldwide aggregator)" is the canonical source name.
# ──────────────────────────────────────────────────────────────────────

_GOOGLE_PATENTS_BASE = "https://patents.google.com"
_GOOGLE_PATENTS_NAME = "Google Patents (worldwide aggregator)"


def _google_patents_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{base}{path}`` for the Google Patents upstream."""
    return make_provenance(
        source_url=f"{_GOOGLE_PATENTS_BASE}{path}",
        source_name=_GOOGLE_PATENTS_NAME,
    )


def _dump(obj: object) -> dict[str, Any]:
    """Serialize a Pydantic model to a dict (or pass through dicts)."""
    if hasattr(obj, "model_dump"):
        return cast("dict[str, Any]", obj.model_dump())  # type: ignore[union-attr]  # ty: ignore[call-non-callable]
    if isinstance(obj, dict):
        return cast("dict[str, Any]", obj)
    raise TypeError(f"_dump expected a Pydantic model or dict, got {type(obj).__name__}")


# Country code is the leading two-letter prefix of a publication_number
# like 'US10123456B2', 'EP3456789A1', 'WO2020123456A1'.
def _country_from_publication_number(pub_no: str | None) -> str | None:
    if not pub_no:
        return None
    head = pub_no[:2]
    if len(head) == 2 and head.isalpha() and head.isupper():
        return head
    return None


def _stub_search_hit(record: dict) -> dict:
    """Lean projection of one Google Patents search hit (§5.5).

    Keeps the ~8 scalar fields an agent needs to triage a worldwide
    result set. Skips the bulky family_country_status array, thumbnail
    URLs, and the upstream rank/result_type/id (the agent talks to the
    tool by ``publication_number``, not Google's internal id).
    """
    pub_no = record.get("publication_number")
    return {
        "publication_number": pub_no,
        "title": record.get("title"),
        "assignee": record.get("assignee"),
        "inventor": record.get("inventor"),
        "filing_date": record.get("filing_date"),
        "publication_date": record.get("publication_date"),
        "grant_date": record.get("grant_date"),
        "country": _country_from_publication_number(pub_no),
        "language": record.get("language"),
    }


def _summarize_patent(record: dict) -> str:
    """One-line Markdown summary for a single Google Patents patent record."""
    pub_no = record.get("patent_number") or record.get("publication_number") or "(no pub#)"
    title = record.get("title") or "(no title)"
    status = record.get("status") or "?"
    assignee = record.get("current_assignee") or record.get("assignee") or None
    filing = record.get("filing_date") or "?"
    grant = record.get("grant_date") or record.get("issue_date")
    head = f"**Patent {pub_no}** — {title}"
    line = f"Status: {status}. Filed {filing}"
    if grant:
        line += f"; granted {grant}"
    if assignee:
        line += f"; assignee {assignee}"
    line += "."
    return f"{head}\n{line}"


def _details_view(record: dict) -> dict:
    """Project a full PatentData dump down to the metadata subset that
    ``get_patent_details`` used to return.

    Carries the fields agents need for triage (dates, assignee, inventors,
    abstract, claim count) without the bulky claims/description/citation
    arrays. Mirrors :meth:`GooglePatentsClient.get_patent_details` so the
    ``view='details'`` opt-in is shape-compatible with the deleted tool.
    """
    claims = record.get("claims") or []
    return {
        "patent_number": record.get("patent_number"),
        "application_number": record.get("application_number"),
        "title": record.get("title"),
        "filing_date": record.get("filing_date"),
        "grant_date": record.get("grant_date"),
        "priority_date": record.get("priority_date"),
        "publication_date": record.get("publication_date"),
        "current_assignee": record.get("current_assignee"),
        "original_assignee": record.get("original_assignee"),
        "inventors": record.get("inventors") or [],
        "status": record.get("status"),
        "claim_count": len(claims) if isinstance(claims, list) else None,
        "abstract": record.get("abstract"),
        "kind_code": record.get("kind_code"),
    }


# ---------------------------------------------------------------------------
# Download fetcher: registered for signed-URL path `patents/{patent_number}`
# ---------------------------------------------------------------------------


async def _fetch_patent_pdf(path: str) -> tuple[bytes, str]:
    """Fetch a patent PDF from Google Patents. Path: ``{patent_number}``."""
    patent_number = path.strip("/")
    async with GooglePatentsClient() as client:
        pdf_bytes = await client.download_patent_pdf(patent_number)
        return pdf_bytes, _patent_pdf_name(patent_number)


register_source("patents", _fetch_patent_pdf, "application/pdf")


@patents_mcp.resource(
    "pca://patents/{publication_number}",
    mime_type="application/pdf",
    name="Patent PDF",
    description=(
        "Patent publication PDF resolved from Google Patents. URI parameter "
        "is the publication number with country and kind code (e.g. 'US10123456B2')."
    ),
)
async def _patent_pdf_resource(publication_number: str):
    return await read_resource(f"patents/{publication_number}")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@patents_mcp.tool(annotations=READ_ONLY)
async def search_patents_global(
    query: Annotated[str, "Keyword search query"],
    cpc_codes: Annotated[list[str] | None, "CPC classification codes (e.g. ['H04L9/32'])"] = None,
    inventors: Annotated[list[str] | None, "Inventor names to filter on"] = None,
    assignees: Annotated[list[str] | None, "Assignee or applicant names"] = None,
    country_codes: Annotated[
        list[str] | None, "Country codes to restrict results (e.g. ['US', 'EP'])"
    ] = None,
    filed_after: Annotated[str | None, "ISO date (YYYY-MM-DD) for earliest filing date"] = None,
    filed_before: Annotated[str | None, "ISO date (YYYY-MM-DD) for latest filing date"] = None,
    sort: Annotated[str | None, "Sort order: 'new' (newest first) or 'old' (oldest first)"] = None,
    page: Annotated[int | None, "Page number (1-indexed)"] = None,
    page_size: Annotated[int | None, "Results per page (max 100)"] = None,
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: publication "
        "number, title, assignee, inventor, filing/publication/grant dates, "
        "country, language. When True, every hit carries the full upstream "
        "search row (family_country_status array, rank, thumbnail URLs, "
        "etc.) — larger; prefer ``get_patent`` for one record.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search patent publications worldwide via Google Patents (covers >100 jurisdictions including non-US offices).

    The most jurisdiction-portable patent search this server exposes —
    pull EP, WO, JP, CN, KR, AU, CA, BR, IN, and many others from one
    query. For US-only full-text search (which can match claims and
    specification text), ``search_patent_publications`` (PPUBS) is more
    reliable and supports field codes.

    Returns lean stubs by default; pass ``full=True`` for the upstream
    search row shape. Requests are rate-limited to avoid bot detection;
    if rate limited, wait and retry.

    Related tools: get_patent, search_patent_publications, search_applications, download_patent_pdf.
    """
    async with GooglePatentsClient() as client:
        response = await client.search_patents(
            keywords=[query] if query else [],
            cpc_codes=cpc_codes or [],
            inventors=inventors or [],
            assignees=assignees or [],
            countries=country_codes or [],
            filed_after=filed_after,
            filed_before=filed_before,
            sort=sort,
            page=page,
            page_size=page_size,
        )

    rows = [r.model_dump() for r in response.results]
    total = response.total_results
    shown = len(rows)
    more = bool(total and shown < int(total))
    items = rows if full else [_stub_search_hit(r) for r in rows]
    summary_total = f"{shown} of {total} hits" if total else f"{shown} hits"
    return ListEnvelope[dict](
        summary=f"Google Patents — `{query}`: {summary_total}.",
        items=items,
        more_available=more,
        next_cursor=None,
        provenance=_google_patents_provenance("/xhr/query"),
    )


@patents_mcp.tool(annotations=READ_ONLY)
async def get_patent(
    patent_number: Annotated[
        str | list[str],
        "Patent number with country and kind code (or a list for portfolio "
        "workflows). Accepts patent numbers AND publication numbers from any "
        "jurisdiction — the upstream client cascades publication → grant. "
        "Examples: 'US10123456B2', 'US20230012345A1', 'EP3456789A1', "
        "['US10123456B2', 'EP3456789A1']. The 'US' prefix is added "
        "automatically when omitted for US patents.",
    ],
    view: Annotated[
        str,
        "Response detail level. 'full' (default): full Google Patents record "
        "— title, abstract, claims, description, citations, family, legal "
        "events, etc. 'details': metadata subset — patent_number, "
        "application_number, title, dates (filing/grant/priority/publication), "
        "assignee, inventors, status, claim_count, abstract. Use 'details' "
        "for triage; 'full' when you need the claims/description/citations.",
    ] = "full",
) -> ListEnvelope[dict]:
    """Get worldwide patent data from Google Patents (the worldwide patent search aggregator): title, abstract, claims, description, and citations.

    Accepts a single patent number or a list (§5.4) and always returns a
    ListEnvelope so the response shape stays stable. Bounded concurrent
    fan-out internally. For US patents, ``get_patent_publication`` (PPUBS)
    is more reliable; this tool is the only path for non-US patents
    (EP, WO, JP, CN, KR, etc.).

    The ``view`` parameter swaps in a metadata-only projection on the same
    upstream record — see the parameter docs. Use ``download_patent_pdf``
    for PDF bytes.

    Related tools: search_patents_global, get_patent_publication, get_patent_family, download_patent_pdf.
    """
    view_key = view.strip().lower()
    if view_key not in ("full", "details"):
        raise ValidationError(f"view must be 'full' or 'details'; got {view!r}")

    numbers = [patent_number] if isinstance(patent_number, str) else list(patent_number)
    if not numbers:
        raise ValidationError("get_patent requires at least one patent number")

    semaphore = asyncio.Semaphore(_GP_FANOUT_CONCURRENCY)

    async def _fetch_one(client: GooglePatentsClient, pat_no: str) -> dict:
        async with semaphore:
            try:
                async with asyncio.timeout(_GET_PATENT_BUDGET_SECONDS):
                    record = await client.get_patent_data(pat_no)
            except FileNotFoundError as exc:
                raise NotFoundError(f"Patent {pat_no} not found on Google Patents") from exc
            except TimeoutError as exc:
                raise RateLimitError(
                    f"Google Patents did not return {pat_no} within "
                    f"{int(_GET_PATENT_BUDGET_SECONDS)}s — usually upstream rate limiting. "
                    "Retry shortly."
                ) from exc
        return _dump(record)  # type: ignore[return-value]

    async with GooglePatentsClient() as client:
        full_records = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    items = full_records if view_key == "full" else [_details_view(r) for r in full_records]

    if len(numbers) == 1:
        # _summarize_patent reads the same scalar fields from either view.
        summary = _summarize_patent(items[0])
        path = f"/patent/{numbers[0]}"
    else:
        summary = f"Fetched {len(items)} patents: " + ", ".join(numbers)
        path = "/patent"

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_google_patents_provenance(path),
    )


@patents_mcp.tool(annotations=READ_ONLY)
async def get_patent_claims(
    patent_number: Annotated[
        str,
        "Patent publication number with country and kind code. "
        "Examples: 'US10123456B2', 'US20230012345A1', 'EP3456789A1'.",
    ],
    view: Annotated[
        str,
        "Which claims to return. 'full' (default): all claims with full nested "
        "limitation structure. 'independent_only': only independent claims "
        "(those with no claim-ref). 'limitations': compact mapping "
        "{claim_number: [{text, depth}]} for infringement claim charts.",
    ] = "full",
) -> dict:
    """Get structured patent claims with nested limitation depth.

    Cascades two sources for full coverage:

    1. USPTO ODP grant XML (authoritative for US patents post-~2000)
    2. Google Patents (worldwide fallback, including pre-2000 US patents)

    Both paths produce the **same canonical shape** per claim:

    ```
    {
        "claim_number": int,
        "limitations": [{"text": str, "depth": int}, ...],
        "claim_text": str,   # rebuilt from limitations with 4-space-per-depth indent
        "claim_type": "independent" | "dependent",
        "depends_on": int | None,
    }
    ```

    ``depth=0`` is the claim preamble (e.g. "A method comprising:"); ``depth=1``
    are the top-level requirements; ``depth=2+`` are sub-requirements nested
    within a parent limitation. Use the depth structure for infringement
    claim-charting — sub-limitations only apply within their parent.
    """
    view_key = view.strip().lower()
    if view_key not in ("full", "independent_only", "limitations"):
        raise ValidationError(
            f"view must be 'full', 'independent_only', or 'limitations'; got {view!r}"
        )

    claims = await unified.get_patent_claims(patent_number)

    if view_key == "independent_only":
        claims = [c for c in claims if c["depends_on"] is None]
    if view_key == "limitations":
        return {
            "patent_number": patent_number,
            "limitations_by_claim": {c["claim_number"]: c["limitations"] for c in claims},
        }
    return {"patent_number": patent_number, "claims": claims}


@patents_mcp.tool(annotations=READ_ONLY)
async def get_patent_figures(
    patent_number: Annotated[
        str,
        "Patent publication number with country and kind code (e.g. 'US10123456B2').",
    ],
) -> dict:
    """Get patent figure images with callout annotations from Google Patents."""
    async with GooglePatentsClient() as client:
        result = await client.get_patent_figures(patent_number)
        if result is None:
            raise ValueError(f"Figures not found for patent {patent_number}")
        return {"results": result}


@patents_mcp.tool(annotations=READ_ONLY)
async def download_patent_pdf(
    patent_number: Annotated[
        str,
        "Patent or publication number. Accepts 'US10123456B2', 'US20230012345A1', "
        "'EP3456789A1', etc. The 'US' prefix is added automatically when omitted.",
    ],
):
    """Download a patent or publication PDF.

    Cascades three sources until one returns bytes:

    1. Google Patents (preferred — PDFs are already OCR'ed for text extraction)
    2. USPTO PPUBS (US patents; clean 404s on non-US numbers, fall through)
    3. EPO OPS (worldwide fallback)

    Returns a ResourceLink pointing at ``pca://patent/{publication_number}``
    (or the matching publication / EPO scheme) alongside `download_url`,
    `filename`, `content_type`, `size_bytes`, `resource_uri`, and `source`.
    Resource-aware MCP clients (e.g. Claude CoWork) can fetch the bytes
    via ``resources/read`` over the MCP session; clients without that
    affordance fetch ``download_url`` directly. Non-not-found errors
    (auth, transient HTTP failures) surface immediately rather than
    being masked by silent fallback.

    Related tools: search_patents_global, get_patent, get_patent_publication.
    """
    pdf = await unified.download_patent_pdf(patent_number)
    signed_path_prefix = {
        "google_patents": "patents",
        "ppubs": "publications",
        "epo": "epo/patents",
    }[pdf.source]
    # Dynamic metadata kwargs forwarded to download_tool_result. ty can't
    # statically verify dict-spread kwargs against the function signature, so
    # the suppression is targeted to the spread site only.
    extra: dict[str, str] = {"patent_number": pdf.patent_number, "source": pdf.source}
    if pdf.patent_title is not None:
        extra["patent_title"] = pdf.patent_title
    return await download_tool_result(
        f"{signed_path_prefix}/{pdf.patent_number}",
        pdf.pdf_bytes,
        filename=pdf.filename,
        content_type="application/pdf",
        description=pdf.patent_title,
        **extra,  # ty: ignore[invalid-argument-type]
    )


@patents_mcp.tool(annotations=READ_ONLY)
async def get_forward_citations(
    patent_number: Annotated[
        str,
        "Patent publication number with country and kind code (e.g. 'US10123456B2').",
    ],
    include_family: Annotated[
        bool,
        "Also include citations at the family level (other publications in the "
        "cited patent's family that were cited). Default False.",
    ] = False,
    limit: Annotated[
        int,
        "Maximum citations to return. Google Patents lists up to ~1000; default 500.",
    ] = 500,
) -> dict:
    """Get patents that cite the given patent (forward citations, from Google Patents).

    Each citation includes publication_number, publication_date, assignee, title,
    and examiner_cited (True if cited by the examiner during prosecution of the
    citing application, vs. cited by the applicant).

    For USPTO-official citations-against this patent in later office actions,
    use search_office_actions(result_type='citations', criteria=...) with a
    citedDocumentIdentifier filter.
    """
    async with GooglePatentsClient() as client:
        patent = await client._get_patent_data(patent_number)
    if patent is None:
        raise ValueError(f"Patent {patent_number} not found")
    result: dict[str, object] = {
        "patent_number": patent_number,
        "total_count": len(patent.citing_patents),
        "citing_patents": [c.model_dump() for c in patent.citing_patents[:limit]],
    }
    if include_family:
        result["citing_patents_family_count"] = len(patent.citing_patents_family)
        result["citing_patents_family"] = [
            c.model_dump() for c in patent.citing_patents_family[:limit]
        ]
    return result
