"""PatentsView API client for USPTO patent data.

PatentsView provides pre-aggregated patent statistics including citation counts,
examiner data, claim text, and entity disambiguation.

Usage::

    from ip_tools.patentsview import PatentsViewClient, PatentsViewQuery

    async with PatentsViewClient() as client:
        # Search patents
        query = PatentsViewQuery().cpc("H04L63").since("2020-01-01").build()
        results = await client.search_patents(query)

        # Get a specific patent
        patent = await client.get_patent("US10123456B2")
        print(f"Forward citations: {patent.patent_num_cited_by_us_patents}")

One-shot functions are also available::

    from ip_tools.patentsview import get_patent, get_forward_citation_count

    patent = await get_patent("US10123456B2")
    count = await get_forward_citation_count("US10123456B2")
"""

from .api import (  # noqa: F401
    DEFAULT_CITATION_FIELDS,
    DEFAULT_CLAIM_FIELDS,
    DEFAULT_PATENT_DETAIL_FIELDS,
    DEFAULT_PATENT_FIELDS,
    Assignee,
    Citation,
    CitationsResponse,
    Claim,
    ClaimsResponse,
    CpcClassification,
    Examiner,
    Inventor,
    Patent,
    PatentsResponse,
    PatentsSearchInput,
    PatentsViewClient,
    PatentsViewQuery,
    PatentWithDetails,
    get_citations,
    get_claims,
    get_client,
    get_forward_citation_count,
    get_independent_claims,
    get_patent,
    get_shortest_independent_claim_length,
    search_patents,
)

__all__ = [
    # Client
    "PatentsViewClient",
    # Query builder
    "PatentsViewQuery",
    # Models
    "Patent",
    "PatentWithDetails",
    "Inventor",
    "Assignee",
    "Examiner",
    "CpcClassification",
    "Citation",
    "Claim",
    # Response models
    "PatentsResponse",
    "CitationsResponse",
    "ClaimsResponse",
    # Input models
    "PatentsSearchInput",
    # Functions
    "get_client",
    "search_patents",
    "get_patent",
    "get_citations",
    "get_claims",
    "get_forward_citation_count",
    "get_independent_claims",
    "get_shortest_independent_claim_length",
    # Field defaults
    "DEFAULT_PATENT_FIELDS",
    "DEFAULT_PATENT_DETAIL_FIELDS",
    "DEFAULT_CITATION_FIELDS",
    "DEFAULT_CLAIM_FIELDS",
]
