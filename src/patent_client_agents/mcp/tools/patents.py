"""Google Patents MCP tools."""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP

from patent_client_agents.google_patents import GooglePatentsClient
from law_tools_core.filenames import patent_pdf as _patent_pdf_name
from law_tools_core.mcp.annotations import READ_ONLY
from law_tools_core.mcp.downloads import download_response, register_source

patents_mcp = FastMCP("Patents")


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


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@patents_mcp.tool(annotations=READ_ONLY)
async def search_google_patents(
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
) -> dict:
    """Search Google Patents by keyword, inventor, assignee, or CPC code.

    PREFER search_patent_publications (PPUBS) for US patent search — it is
    more reliable and supports full-text search within claims, specification,
    and abstract. Use this tool for non-US patents (EP, WO, JP, etc.) or
    when PPUBS does not support the query.

    Requests are rate-limited to avoid bot detection. If rate limited,
    wait and retry.

    Use download_patent_pdf to download a specific patent PDF.
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
        return {"results": [r.model_dump() for r in response.results]}


@patents_mcp.tool(annotations=READ_ONLY)
async def get_patent(
    patent_number: Annotated[
        str,
        "Patent publication number with country code and kind code. "
        "Examples: 'US10123456B2', 'US20230012345A1', 'EP3456789A1'. "
        "The 'US' prefix is added automatically if omitted for US patents.",
    ],
) -> dict:
    """Get full patent data from Google Patents: title, abstract, claims,
    description, and citations.

    For US patents, get_patent_publication (PPUBS) is more reliable.
    This tool is useful for non-US patents (EP, WO, JP, etc.).

    Use download_patent_pdf to download the patent PDF.
    """
    async with GooglePatentsClient() as client:
        result = await client.get_patent_data(patent_number)
        if result is None:
            raise ValueError(f"Patent {patent_number} not found")
        return result.model_dump()


@patents_mcp.tool(annotations=READ_ONLY)
async def get_patent_claims(
    patent_number: Annotated[
        str,
        "Patent publication number with country and kind code (e.g. 'US10123456B2'). "
        "For US patents, get_patent_publication (PPUBS) also returns structured claims.",
    ],
) -> dict:
    """Get structured patent claims with dependency information.

    For US patents, fetches claims from the USPTO patent grant XML (via ODP),
    which preserves hierarchical indentation of claim text. Falls back to
    Google Patents for non-US patents or when the grant XML is unavailable.
    """
    from patent_client_agents.uspto_odp.clients.applications import ApplicationsClient
    from law_tools_core.exceptions import LawToolsCoreError

    if patent_number.strip().upper().startswith("US"):
        try:
            async with ApplicationsClient() as odp:
                result = await odp.get_granted_claims(patent_number)
            if result:
                return {"results": result}
        except LawToolsCoreError:
            pass  # fall through to Google Patents

    async with GooglePatentsClient() as client:
        result = await client.get_patent_claims(patent_number)
        if result is None:
            raise ValueError(f"Claims not found for patent {patent_number}")
        return {"results": result}


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
async def get_structured_claim_limitations(
    patent_number: Annotated[
        str,
        "Patent publication number with country and kind code (e.g. 'US10123456B2').",
    ],
) -> dict:
    """Get claim limitations broken down by claim number from Google Patents.

    Returns a mapping of claim numbers to lists of limitation text strings.
    Useful for claim charting and infringement analysis.
    """
    async with GooglePatentsClient() as client:
        result = await client.get_structured_claim_limitations(patent_number)
        if result is None:
            raise ValueError(f"Claims not found for patent {patent_number}")
        return result


@patents_mcp.tool(annotations=READ_ONLY)
async def download_patent_pdf(
    patent_number: Annotated[
        str,
        "Patent publication number with country and kind code (e.g. 'US10123456B2'). "
        "For US patents, download_publication_pdf (PPUBS) may be more reliable.",
    ],
) -> dict:
    """Download a patent PDF from Google Patents.

    Returns a signed `download_url` (or `file_path` in local stdio mode) plus
    `filename`, `content_type`, `size_bytes`. Covers worldwide patents.
    For US patents, download_publication_pdf is a more reliable alternative.
    """
    async with GooglePatentsClient() as client:
        pdf_bytes = await client.download_patent_pdf(patent_number)
        return download_response(
            f"patents/{patent_number}",
            pdf_bytes,
            filename=_patent_pdf_name(patent_number),
            content_type="application/pdf",
            patent_number=patent_number,
        )


@patents_mcp.tool(annotations=READ_ONLY)
async def get_independent_claims(
    patent_number: Annotated[
        str,
        "Patent publication number with country and kind code (e.g. 'US10123456B2').",
    ],
) -> dict:
    """Get only the independent claims for a patent from Google Patents."""
    async with GooglePatentsClient() as client:
        claims = await client.get_patent_claims(patent_number)
        if claims is None:
            raise ValueError(f"Claims not found for patent {patent_number}")
        return {"results": [c for c in claims if not c.get("depends_on")]}


@patents_mcp.tool(annotations=READ_ONLY)
async def get_patent_details(
    patent_number: Annotated[
        str,
        "Patent publication number with country and kind code (e.g. 'US10123456B2'). "
        "For US patents, get_application (ODP) returns similar metadata more reliably.",
    ],
) -> dict:
    """Get structured patent details from Google Patents: dates, assignee, inventors.

    Returns filing date, grant date, priority date, assignee,
    and inventor names. For US patents, get_application provides
    more reliable and detailed metadata.
    """
    async with GooglePatentsClient() as client:
        result = await client.get_patent_details(patent_number)
        if result is None:
            raise ValueError(f"Patent {patent_number} not found")
        return result


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
    use search_oa_citations with citedDocumentIdentifier filter.
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
