"""USPTO Patent Publications MCP tools."""

from __future__ import annotations

import base64
from typing import Annotated

from fastmcp import FastMCP

from patent_client_agents.uspto_publications import (
    resolve_and_download_pdf,
    resolve_publication,
    search,
)
from law_tools_core.filenames import publication_pdf as _publication_pdf_name
from law_tools_core.mcp.annotations import READ_ONLY
from law_tools_core.mcp.downloads import download_response, register_source

publications_mcp = FastMCP("Publications")


def _dump(obj: object) -> object:
    """Serialize a Pydantic model or pass through."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()  # type: ignore[union-attr]
    return obj


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


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@publications_mcp.tool(annotations=READ_ONLY)
async def search_patent_publications(
    query: Annotated[
        str,
        "Search query using PPUBS syntax. Supports Boolean operators (AND/OR/NOT) "
        "and field codes: CLM (claims), SPEC (description), AB (abstract), "
        "TTL (title), IN (inventor), AS (assignee), CPC (classification). "
        "Example: '\"machine learning\" AND CLM/neural.CLM.' or 'blockchain.TTL.'",
    ],
    limit: Annotated[int, "Maximum number of results to return"] = 25,
) -> dict:
    """Search the full text of US patents and published applications (PPUBS).

    This is the ONLY patent search tool that searches within claims,
    specification, and abstract text. Use this for prior art searches
    and keyword-based patent discovery. For metadata-only searches
    (by filing date, status, examiner, CPC), use search_applications instead.

    Use download_publication_pdf to download a specific publication PDF.
    """
    result = await search(query=query, limit=limit)
    return _dump(result)  # type: ignore[return-value]


@publications_mcp.tool(annotations=READ_ONLY)
async def get_patent_publication(
    publication_number: Annotated[
        str,
        "Patent publication number. Accepts formats: 'US-20230012345-A1', "
        "'US20230012345A1', 'US-10123456-B2', or 'US10123456B2'. "
        "The 'US' prefix and dashes are optional.",
    ],
) -> dict:
    """Get full document content for a patent publication from PPUBS.

    Returns title, abstract, claims (structured with dependency info),
    description/specification text, references, and classification.
    This is the best tool for reading the actual text of a patent.

    Use download_publication_pdf to download the publication PDF.
    """
    result = await resolve_publication(publication_number)
    return _dump(result)  # type: ignore[return-value]


@publications_mcp.tool(annotations=READ_ONLY)
async def download_publication_pdf(
    publication_number: Annotated[
        str,
        "Patent publication number. Accepts formats: 'US-20230012345-A1', "
        "'US20230012345A1', 'US-10123456-B2', or 'US10123456B2'. "
        "The 'US' prefix and dashes are optional.",
    ],
) -> dict:
    """Download a patent publication PDF from PPUBS.

    Returns a signed `download_url` (or `file_path` in local stdio mode) plus
    `filename`, `content_type`, `size_bytes`. Works for both granted patents
    and pre-grant publications.
    """
    result = await resolve_and_download_pdf(publication_number)
    pdf_bytes = base64.b64decode(result.pdf_base64)
    pub_no = result.publication_number or publication_number
    return download_response(
        f"publications/{pub_no}",
        pdf_bytes,
        filename=_publication_pdf_name(pub_no),
        content_type="application/pdf",
        publication_number=pub_no,
        patent_title=result.patent_title,
    )


@publications_mcp.tool(annotations=READ_ONLY)
async def resolve_publication_number(
    publication_number: Annotated[
        str,
        "Partial or full publication number to resolve. Accepts formats: "
        "'US-20230012345-A1', 'US20230012345A1', 'US-10123456-B2', "
        "'US10123456B2', or just '10123456'. The 'US' prefix and dashes are optional.",
    ],
) -> dict:
    """Resolve a publication number to its canonical form and metadata.

    Useful for normalizing publication numbers before passing them
    to other tools, and for confirming that a publication exists in PPUBS.
    """
    result = await resolve_publication(publication_number)
    return _dump(result)  # type: ignore[return-value]
