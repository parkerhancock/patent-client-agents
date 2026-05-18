"""High-level async API for the KIPO KIPRIS Plus services.

Each helper opens a :class:`KiprisClient` via ``async with`` and
delegates to the corresponding instance method. All helpers require
``KIPO_KIPRIS_API_KEY`` to be set (ToS §11 BYOK); they raise
``ConfigurationError`` otherwise.

Returns are kept as ``(items, pagination)`` tuples shaped like the
client methods — the MCP tool layer maps them onto :class:`ListEnvelope`.
"""

from __future__ import annotations

from typing import Any

from .client import KiprisClient

# ----------------------------------------------------------------------
# Patents + Utility Models
# ----------------------------------------------------------------------


async def search_kipo_patents(
    query: str,
    *,
    patent: bool = True,
    utility: bool = True,
    num_of_rows: int = 10,
    page_no: int = 1,
    **extra: Any,
) -> tuple[list[dict], dict]:
    """Free-text search across patent + utility-model bibliographies."""
    async with KiprisClient() as client:
        return await client.search_patents_word(
            word=query,
            patent=patent,
            utility=utility,
            num_of_rows=num_of_rows,
            page_no=page_no,
            **extra,
        )


async def search_kipo_patents_advanced(
    *,
    invention_title: str | None = None,
    astrt_cont: str | None = None,
    claim_scope: str | None = None,
    applicant: str | None = None,
    inventor: str | None = None,
    ipc: str | None = None,
    application_date: str | None = None,
    publication_date: str | None = None,
    patent: bool = True,
    utility: bool = True,
    num_of_rows: int = 10,
    page_no: int = 1,
    **extra: Any,
) -> tuple[list[dict], dict]:
    """Structured-field advanced search over patents + utility models."""
    async with KiprisClient() as client:
        return await client.search_patents_advanced(
            invention_title=invention_title,
            astrt_cont=astrt_cont,
            claim_scope=claim_scope,
            applicant=applicant,
            inventor=inventor,
            ipc=ipc,
            application_date=application_date,
            publication_date=publication_date,
            patent=patent,
            utility=utility,
            num_of_rows=num_of_rows,
            page_no=page_no,
            **extra,
        )


async def get_kipo_patent(number: str, **extra: Any) -> tuple[list[dict], dict]:
    """Fetch a single patent / UM by application or publication number."""
    async with KiprisClient() as client:
        return await client.get_patent(number, **extra)


# ----------------------------------------------------------------------
# Trademarks
# ----------------------------------------------------------------------


async def search_kipo_trademarks(
    query: str,
    *,
    num_of_rows: int = 10,
    page_no: int = 1,
    **extra: Any,
) -> tuple[list[dict], dict]:
    """Free-text search across trademark bibliographies."""
    async with KiprisClient() as client:
        return await client.search_trademarks_word(
            word=query,
            num_of_rows=num_of_rows,
            page_no=page_no,
            **extra,
        )


async def search_kipo_trademarks_advanced(
    *,
    title: str | None = None,
    applicant: str | None = None,
    classification: str | None = None,
    vienna_code: str | None = None,
    application_date: str | None = None,
    registration_date: str | None = None,
    num_of_rows: int = 10,
    page_no: int = 1,
    **extra: Any,
) -> tuple[list[dict], dict]:
    """Structured-field advanced search over trademarks."""
    async with KiprisClient() as client:
        return await client.search_trademarks_advanced(
            title=title,
            applicant=applicant,
            classification=classification,
            vienna_code=vienna_code,
            application_date=application_date,
            registration_date=registration_date,
            num_of_rows=num_of_rows,
            page_no=page_no,
            **extra,
        )


async def get_kipo_trademark(number: str, **extra: Any) -> tuple[list[dict], dict]:
    """Fetch a single trademark by application or registration number."""
    async with KiprisClient() as client:
        return await client.get_trademark(number, **extra)


# ----------------------------------------------------------------------
# Designs
# ----------------------------------------------------------------------


async def search_kipo_designs(
    query: str,
    *,
    num_of_rows: int = 10,
    page_no: int = 1,
    **extra: Any,
) -> tuple[list[dict], dict]:
    """Free-text search across design bibliographies."""
    async with KiprisClient() as client:
        return await client.search_designs_word(
            word=query,
            num_of_rows=num_of_rows,
            page_no=page_no,
            **extra,
        )


async def search_kipo_designs_advanced(
    *,
    article_name: str | None = None,
    applicant: str | None = None,
    loc_code: str | None = None,
    application_date: str | None = None,
    registration_date: str | None = None,
    num_of_rows: int = 10,
    page_no: int = 1,
    **extra: Any,
) -> tuple[list[dict], dict]:
    """Structured-field advanced search over designs."""
    async with KiprisClient() as client:
        return await client.search_designs_advanced(
            article_name=article_name,
            applicant=applicant,
            loc_code=loc_code,
            application_date=application_date,
            registration_date=registration_date,
            num_of_rows=num_of_rows,
            page_no=page_no,
            **extra,
        )


async def get_kipo_design(number: str, **extra: Any) -> tuple[list[dict], dict]:
    """Fetch a single design by application or registration number."""
    async with KiprisClient() as client:
        return await client.get_design(number, **extra)


__all__ = [
    "get_kipo_design",
    "get_kipo_patent",
    "get_kipo_trademark",
    "search_kipo_designs",
    "search_kipo_designs_advanced",
    "search_kipo_patents",
    "search_kipo_patents_advanced",
    "search_kipo_trademarks",
    "search_kipo_trademarks_advanced",
]
