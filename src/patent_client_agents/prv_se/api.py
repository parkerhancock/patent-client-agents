"""Module-level helpers for the PRV (Sweden) connector.

Each helper opens a context-managed :class:`PrvClient`, calls the
matching client method, and returns the parsed model. Use these
helpers from library callers; the MCP tools in
:mod:`patent_client_agents.mcp.tools.prv_se` wrap the same surface
behind ``ResponseEnvelope`` / ``ListEnvelope`` packaging.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .client import PrvClient
from .models import (
    DesignSearchResponse,
    PatentGetRecord,
    PatentSearchResponse,
    SpcSearchResponse,
    TrademarkSearchResponse,
)


async def search_prv_patents(
    *,
    text: str | None = None,
    page: int = 0,
    page_size: int = 10,
    sort_column: str | None = "filingDate",
    sort_order: str | None = "DESC",
    extra: dict[str, Any] | None = None,
) -> PatentSearchResponse:
    async with PrvClient() as client:
        return await client.search_patents(
            text=text,
            page=page,
            page_size=page_size,
            sort_column=sort_column,
            sort_order=sort_order,
            extra=extra,
        )


async def get_prv_patent(
    application_number: str,
    *,
    application_type: str = "NAT",
) -> PatentGetRecord:
    async with PrvClient() as client:
        return await client.get_patent(
            application_number,
            application_type=application_type,
        )


async def get_prv_patents(
    application_numbers: Iterable[str],
    *,
    application_type: str = "NAT",
) -> list[PatentGetRecord]:
    async with PrvClient() as client:
        return await client.get_patents(
            application_numbers,
            application_type=application_type,
        )


async def search_prv_trademarks(
    *,
    text: str | None = None,
    page: int = 0,
    page_size: int = 10,
    sort_column: str | None = "filingDate",
    sort_order: str | None = "DESC",
    extra: dict[str, Any] | None = None,
) -> TrademarkSearchResponse:
    async with PrvClient() as client:
        return await client.search_trademarks(
            text=text,
            page=page,
            page_size=page_size,
            sort_column=sort_column,
            sort_order=sort_order,
            extra=extra,
        )


async def search_prv_designs(
    *,
    text: str | None = None,
    page: int = 0,
    page_size: int = 10,
    sort_column: str | None = "filingDate",
    sort_order: str | None = "DESC",
    extra: dict[str, Any] | None = None,
) -> DesignSearchResponse:
    async with PrvClient() as client:
        return await client.search_designs(
            text=text,
            page=page,
            page_size=page_size,
            sort_column=sort_column,
            sort_order=sort_order,
            extra=extra,
        )


async def search_prv_spcs(
    *,
    substance_product: str | None = None,
    applicants: str | None = None,
    application_number_spc: str | None = None,
    base_patent_number: str | None = None,
    marketing_authorization_number: str | None = None,
    announcement: str | None = None,
    match_type: str = "CONTAINS",
    page: int = 0,
    page_size: int = 10,
) -> SpcSearchResponse:
    async with PrvClient() as client:
        return await client.search_spcs(
            substance_product=substance_product,
            applicants=applicants,
            application_number_spc=application_number_spc,
            base_patent_number=base_patent_number,
            marketing_authorization_number=marketing_authorization_number,
            announcement=announcement,
            match_type=match_type,
            page=page,
            page_size=page_size,
        )


__all__ = [
    "search_prv_patents",
    "get_prv_patent",
    "get_prv_patents",
    "search_prv_trademarks",
    "search_prv_designs",
    "search_prv_spcs",
]
