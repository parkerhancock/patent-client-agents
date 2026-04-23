"""USPTO Office Action MCP tools.

Search office action rejections, citations, full text, and enriched citation
metadata via the USPTO ODP office action endpoints (X-API-KEY auth).
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP

from patent_client_agents.uspto_office_actions import OfficeActionClient
from law_tools_core.mcp.annotations import READ_ONLY

office_actions_mcp = FastMCP("Office Actions")


@office_actions_mcp.tool(annotations=READ_ONLY)
async def search_oa_rejections(
    criteria: Annotated[
        str,
        "Lucene query for office action rejections "
        "(e.g. 'patentApplicationNumber:16123456', 'hasRej103:1 AND nationalClass:438')",
    ],
    start: Annotated[int, "Result offset for pagination"] = 0,
    rows: Annotated[int, "Maximum results to return (max 100)"] = 25,
) -> dict:
    """Search structured office action rejection data.

    Returns per-claim rejection records with indicators for 35 USC 101, 102,
    103, 112, and double-patenting rejections. Includes Alice/Bilski/Mayo/Myriad
    subject-matter eligibility indicators.

    Searchable fields include: patentApplicationNumber, hasRej101, hasRej102,
    hasRej103, hasRej112, hasRejDP, legalSectionCode, nationalClass,
    groupArtUnitNumber, submissionDate, aliceIndicator, allowedClaimIndicator.
    """
    async with OfficeActionClient() as client:
        result = await client.search_rejections(criteria, start=start, rows=rows)
        return result.model_dump()


@office_actions_mcp.tool(annotations=READ_ONLY)
async def search_oa_citations(
    criteria: Annotated[
        str,
        "Lucene query for office action citations "
        "(e.g. 'patentApplicationNumber:16123456', 'examinerCitedReferenceIndicator:true')",
    ],
    start: Annotated[int, "Result offset for pagination"] = 0,
    rows: Annotated[int, "Maximum results to return (max 100)"] = 25,
) -> dict:
    """Search prior art references cited in office actions.

    Returns citation records linking applications to cited references, with
    indicators for whether the examiner or applicant cited the reference.

    Searchable fields include: patentApplicationNumber, referenceIdentifier,
    parsedReferenceIdentifier, legalSectionCode, examinerCitedReferenceIndicator,
    applicantCitedExaminerReferenceIndicator, groupArtUnitNumber, techCenter.
    """
    async with OfficeActionClient() as client:
        result = await client.search_citations(criteria, start=start, rows=rows)
        return result.model_dump()


@office_actions_mcp.tool(annotations=READ_ONLY)
async def search_oa_text(
    criteria: Annotated[
        str,
        "Lucene query for office action full text (e.g. 'patentApplicationNumber:16123456')",
    ],
    start: Annotated[int, "Result offset for pagination"] = 0,
    rows: Annotated[int, "Maximum results to return (max 100)"] = 25,
) -> dict:
    """Retrieve full text of office actions for a patent application.

    Returns the complete text of office actions (bodyText field) along with
    structured sections for 101/102/103/112 rejections, citations, and more.

    Searchable fields include: patentApplicationNumber, inventionTitle,
    submissionDate, legacyDocumentCodeIdentifier (CTNF, CTFR, NOA, etc.),
    groupArtUnitNumber, patentNumber, applicationTypeCategory.
    """
    async with OfficeActionClient() as client:
        result = await client.search_office_action_text(criteria, start=start, rows=rows)
        return result.model_dump()


@office_actions_mcp.tool(annotations=READ_ONLY)
async def search_enriched_citations(
    criteria: Annotated[
        str,
        "Lucene query for enriched citation metadata "
        "(e.g. 'patentApplicationNumber:16123456', 'countryCode:US AND kindCode:A1')",
    ],
    start: Annotated[int, "Result offset for pagination"] = 0,
    rows: Annotated[int, "Maximum results to return (max 100)"] = 25,
) -> dict:
    """Search enriched patent citation metadata with inventor names and passage locations.

    Returns enhanced citation records with inventor names, country codes, kind
    codes, passage locations, and quality summaries. More detailed than
    search_oa_citations.

    Searchable fields include: patentApplicationNumber, citedDocumentIdentifier,
    publicationNumber, inventorNameText, countryCode, kindCode,
    officeActionCategory, citationCategoryCode, officeActionDate,
    examinerCitedReferenceIndicator, nplIndicator, groupArtUnitNumber.
    """
    async with OfficeActionClient() as client:
        result = await client.search_enriched_citations(criteria, start=start, rows=rows)
        return result.model_dump()
