"""USPTO Patent Publications (PPUBS) MCP tools."""

from __future__ import annotations

import asyncio
import base64
from typing import Annotated, Any, cast

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, ResponseEnvelope, make_provenance
from law_tools_core.exceptions import ValidationError
from law_tools_core.filenames import publication_pdf as _publication_pdf_name
from law_tools_core.mcp.annotations import READ_ONLY
from law_tools_core.mcp.downloads import read_resource, register_source
from patent_client_agents.uspto_publications import (
    PublicSearchClient,
    resolve_and_download_pdf,
)

publications_mcp = FastMCP("Publications")


# ──────────────────────────────────────────────────────────────────────
# Envelope helpers — PPUBS source-specific wrappers around
# law_tools_core.envelope per CONNECTOR_STANDARDS.md §5.9. See
# ``uspto.py`` (USPTO Applications) for the canonical template.
# ──────────────────────────────────────────────────────────────────────

_PPUBS_BASE = "https://ppubs.uspto.gov"
_PPUBS_NAME = "USPTO Patent Public Search (PPUBS)"


def _ppubs_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{base}{path}`` for the PPUBS upstream."""
    return make_provenance(
        source_url=f"{_PPUBS_BASE}{path}",
        source_name=_PPUBS_NAME,
    )


def _dump(obj: object) -> dict[str, Any]:
    """Serialize a Pydantic model (JSON mode) to a dict (or pass through dicts).

    JSON mode coerces datetimes/Decimals/etc to strings — keeps the
    payload JSON-safe at the envelope boundary.
    """
    if hasattr(obj, "model_dump"):
        return cast("dict[str, Any]", obj.model_dump(mode="json"))  # type: ignore[union-attr]  # ty: ignore[call-non-callable]
    if isinstance(obj, dict):
        return cast("dict[str, Any]", obj)
    raise TypeError(f"_dump expected a Pydantic model or dict, got {type(obj).__name__}")


def _stub_publication(record: dict) -> dict:
    """Lean projection of one PPUBS biblio row (§5.5).

    Keeps the eight scalar fields an agent uses to triage a result set:
    canonical publication number, title, document type (US-PGPUB / USPAT /
    USOCR), publication and filing dates, lead applicant and assignee,
    and the headline classification code.
    """
    applicants = record.get("applicant_names") or []
    assignees = record.get("assignee_names") or []
    return {
        "publication_number": record.get("publication_number"),
        "patent_title": record.get("patent_title"),
        "type": record.get("type"),
        "publication_date": record.get("publication_date"),
        "app_filing_date": record.get("app_filing_date"),
        "applicant": applicants[0] if applicants else None,
        "assignee": assignees[0] if assignees else None,
        "main_classification_code": record.get("main_classification_code"),
    }


def _summarize_publication(record: dict) -> str:
    """One-line Markdown summary for a single PPUBS document record."""
    pub = record.get("publication_number") or "(no pub#)"
    title = record.get("patent_title") or "(no title)"
    kind = record.get("type") or "?"
    pub_date = record.get("publication_date") or "?"
    applicants = record.get("applicants") or []
    applicant = None
    if applicants and isinstance(applicants, list):
        first = applicants[0]
        if isinstance(first, dict):
            applicant = first.get("name")
    head = f"**US publication {pub}** — {title}"
    line = f"{kind}; published {pub_date}"
    if applicant:
        line += f"; applicant {applicant}"
    line += "."
    return f"{head}\n{line}"


# ---------------------------------------------------------------------------
# Download fetcher
# ---------------------------------------------------------------------------


async def _fetch_publication_pdf(path: str) -> tuple[bytes, str]:
    """Fetch a USPTO publication PDF. Path: ``{publication_number}``."""
    publication_number = path.strip("/")
    result = await resolve_and_download_pdf(publication_number)
    content = base64.b64decode(result.pdf_base64)
    pub_no = result.publication_number or publication_number
    return content, _publication_pdf_name(pub_no)


register_source("publications", _fetch_publication_pdf, "application/pdf")


@publications_mcp.resource(
    "pca://publications/{publication_number}",
    mime_type="application/pdf",
    name="Patent publication PDF (PPUBS)",
    description=(
        "US patent or publication PDF resolved through PPUBS. URI parameter is "
        "the publication number with country and kind code (e.g. 'US20230012345A1')."
    ),
)
async def _publication_pdf_resource(publication_number: str):
    return await read_resource(f"publications/{publication_number}")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


_PUB_FANOUT_CONCURRENCY = 5


@publications_mcp.tool(annotations=READ_ONLY)
async def search_patent_publications(
    query: Annotated[
        str,
        "Search query using USPTO Patent Public Search (PPUBS) syntax. "
        "Supports Boolean operators (AND/OR/NOT) and field codes: CLM (claims), "
        "SPEC (description), AB (abstract), TTL (title), IN (inventor), AS "
        "(assignee), CPC (classification). Example: "
        "'\"machine learning\" AND CLM/neural.CLM.' or 'blockchain.TTL.'",
    ],
    limit: Annotated[int, "Maximum number of results to return"] = 25,
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: publication "
        "number, title, document type, publication/filing dates, lead "
        "applicant and assignee, headline classification. When True, every "
        "hit carries the full PPUBS biblio record (all applicants/assignees, "
        "examiner, document structure, etc.) — large; prefer "
        "``get_patent_publication`` for one record.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search the full text of US patents and published applications.

    The only US patent search that hits claims, specification, and abstract
    text — use it for prior-art and keyword discovery. For metadata-only
    queries (filing date, status, examiner, CPC), use ``search_applications``
    instead. Returns lean stubs by default; pass ``full=True`` for the
    upstream-shaped biblio row.

    Related tools: get_patent_publication, get_patent, download_patent_pdf,
    search_applications.
    """
    async with PublicSearchClient() as client:
        page = await client.search_biblio(query=query, limit=limit)

    dumped = _dump(page)
    if not isinstance(dumped, dict):  # pragma: no cover - upstream always Pydantic
        dumped = {}
    rows = list(dumped.get("docs") or [])
    total = dumped.get("num_found")
    shown = len(rows)
    more = bool(total is not None and shown < int(total))
    items = rows if full else [_stub_publication(r) for r in rows]
    summary_total = f"{shown} of {total} hits" if total is not None else f"{shown} hits"
    return ListEnvelope[dict](
        summary=f"USPTO Patent Publications — `{query}`: {summary_total}.",
        items=items,
        more_available=more,
        next_cursor=None,
        provenance=_ppubs_provenance("/api/searches/searchWithBeFamily"),
    )


@publications_mcp.tool(annotations=READ_ONLY)
async def get_patent_publication(
    publication_number: Annotated[
        str | list[str],
        "Patent publication number, or a list for portfolio workflows. "
        "Accepts: 'US-20230012345-A1', 'US20230012345A1', 'US-10123456-B2', "
        "or 'US10123456B2'. The 'US' prefix and dashes are optional. "
        "Examples: 'US20230012345A1', ['US20230012345A1', 'US10123456B2'].",
    ],
) -> ListEnvelope[dict]:
    """Get the full text of a US patent or published application (title, abstract, claims, spec).

    Accepts either a single publication number or a list (§5.4) and always
    returns a ListEnvelope so the response shape stays stable. Bounded
    concurrent fan-out internally.

    Returns title, abstract, structured claims (with dependency info),
    description/specification text, references, and classification. For
    the PDF instead of structured text, use ``download_patent_pdf``.

    Related tools: search_patent_publications, get_patent, download_patent_pdf.
    """
    numbers = (
        [publication_number] if isinstance(publication_number, str) else list(publication_number)
    )
    if not numbers:
        raise ValidationError("get_patent_publication requires at least one publication number")

    semaphore = asyncio.Semaphore(_PUB_FANOUT_CONCURRENCY)

    async def _fetch_one(client: PublicSearchClient, pub_no: str) -> dict:
        async with semaphore:
            record = await client.resolve_document_by_publication_number(pub_no)
        return _dump(record)  # type: ignore[return-value]

    async with PublicSearchClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    if len(numbers) == 1:
        summary = _summarize_publication(results[0])
        path = f"/api/patents/highlight?publicationNumber={numbers[0]}"
    else:
        summary = f"Fetched {len(results)} US patent publications: " + ", ".join(numbers)
        path = "/api/patents/highlight"

    return ListEnvelope[dict](
        summary=summary,
        items=results,
        provenance=_ppubs_provenance(path),
    )


@publications_mcp.tool(annotations=READ_ONLY)
async def resolve_publication_number(
    publication_number: Annotated[
        str,
        "Partial or full publication number to resolve. Accepts formats: "
        "'US-20230012345-A1', 'US20230012345A1', 'US-10123456-B2', "
        "'US10123456B2', or just '10123456'. The 'US' prefix and dashes are optional.",
    ],
) -> ResponseEnvelope[dict]:
    """Resolve a publication number to its canonical form and confirm it exists in PPUBS.

    Useful for normalizing publication numbers before passing them to other
    tools, and for confirming that a publication exists in the USPTO Patent
    Public Search corpus.

    Related tools: get_patent_publication, search_patent_publications.
    """
    async with PublicSearchClient() as client:
        record = await client.resolve_document_by_publication_number(publication_number)

    dumped = _dump(record)
    if not isinstance(dumped, dict):  # pragma: no cover - upstream always Pydantic
        dumped = {}
    return ResponseEnvelope[dict](
        summary=_summarize_publication(dumped),
        details=dumped,
        provenance=_ppubs_provenance(
            f"/api/patents/highlight?publicationNumber={publication_number}"
        ),
    )
