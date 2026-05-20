"""Async client for the PRV (Sweden) public JSON APIs.

Three hosts, one client. All endpoints are unauthenticated; PRV's
parallel bulk feeds on ``data.prv.se`` are CC0 1.0 / CC BY 4.0 and
Sweden's Open Data Act (SFS 2022:818) provides statutory cover for
register-data reuse. Production callers should still send a courtesy
registration to ``data@prv.se`` so PRV can warn us before schema
changes.

The schema is reverse-engineered from the ``search.prv.se`` React
bundle — every model uses ``extra="allow"`` so a new upstream field
surfaces as a passthrough dict entry rather than a validation failure.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import httpx

from law_tools_core import BaseAsyncClient

from .models import (
    DesignSearchResponse,
    PatentGetRecord,
    PatentSearchResponse,
    SpcSearchResponse,
    TrademarkSearchResponse,
)

PATENTS_HOST: str = "https://patents-search-api.prv.se"
DV_HOST: str = "https://dv-search-api.prv.se"
API_HOST: str = "https://api.prv.se"

DEFAULT_USER_AGENT: str = "patent-client-agents/0 (+https://patentclient.com; contact data@prv.se)"
"""Identifies our calls to PRV so they can warn us about breakage."""

MAX_PAGE_SIZE: int = 100
"""Conservative cap. PRV's SPA defaults to 10–20; the upstream
ceiling is undocumented."""


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_simple_search_body(
    *,
    text: str | None,
    page: int,
    page_size: int,
    sort_column: str | None,
    sort_order: str | None,
    extra: dict[str, Any] | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "page": int(page),
        "pageSize": max(1, min(int(page_size), MAX_PAGE_SIZE)),
    }
    if sort_column:
        body["sortColumn"] = sort_column
    if sort_order:
        body["sortOrder"] = sort_order
    if text:
        body["simpleSearchText"] = text
    if extra:
        for key, value in extra.items():
            if value is None:
                continue
            body[key] = value
    return body


SpcSearchType = str
"""Match-type discriminator on advanced-search fields. PRV vocabulary:
``CONTAINS`` (default), ``STARTS_WITH``, ``EXACT``."""


def _build_advanced_search_body(
    *,
    page: int,
    page_size: int,
    sort_column: str,
    sort_order: str,
    filters: dict[str, str | tuple[str, SpcSearchType]],
) -> dict[str, Any]:
    """Build the PRV advanced-search request body.

    Each filter wraps as ``{value: ..., searchType: ...}``. Filter
    values that are bare strings get ``searchType="CONTAINS"`` by
    default; tuples ``(value, searchType)`` override the match type.
    Empty values are dropped — only fields the caller cares about
    appear in the body.
    """
    body: dict[str, Any] = {
        "page": int(page),
        "pageSize": max(1, min(int(page_size), MAX_PAGE_SIZE)),
        "sortColumn": sort_column,
        "sortOrder": sort_order,
    }
    for key, raw in filters.items():
        if raw is None:
            continue
        if isinstance(raw, tuple):
            value, match = raw
        else:
            value, match = raw, "CONTAINS"
        if not value:
            continue
        body[key] = {"value": value, "searchType": match}
    return body


class PrvClient(BaseAsyncClient):
    """Async client for PRV's three public JSON APIs.

    All methods are read-only. The client shares one cache database
    and one httpx connection pool across the three hosts; per-method
    helpers pass absolute URLs so the base-URL machinery on
    :class:`BaseAsyncClient` stays out of the way.

    Example::

        async with PrvClient() as client:
            page = await client.search_patents(text="Volvo", page_size=5)
            for row in page.search_patent_dtos:
                print(row.application_number_formatted, row.title)
    """

    CACHE_NAME: str = "prv_se"
    DEFAULT_TIMEOUT: float = 30.0
    DEFAULT_BASE_URL: str = ""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        merged_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }
        if headers:
            merged_headers.update(headers)
        super().__init__(
            client=client,
            headers=merged_headers,
            **kwargs,
        )

    def _build_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.base_url}{path}"

    # ------------------------------------------------------------------
    # Patent simple search
    # ------------------------------------------------------------------

    async def search_patents(
        self,
        *,
        text: str | None = None,
        page: int = 0,
        page_size: int = 10,
        sort_column: str | None = "filingDate",
        sort_order: str | None = "DESC",
        extra: dict[str, Any] | None = None,
    ) -> PatentSearchResponse:
        """``POST patents-search-api.prv.se/searchpatent/patentsimplesearch/``."""
        body = _build_simple_search_body(
            text=text,
            page=page,
            page_size=page_size,
            sort_column=sort_column,
            sort_order=sort_order,
            extra=extra,
        )
        payload = await self._request_json(
            "POST",
            f"{PATENTS_HOST}/searchpatent/patentsimplesearch/",
            json=body,
            context="prv_se.search_patents",
        )
        return PatentSearchResponse.model_validate(payload)

    # ------------------------------------------------------------------
    # Patent per-record fetch
    # ------------------------------------------------------------------

    async def get_patent(
        self,
        application_number: str,
        *,
        application_type: str = "NAT",
    ) -> PatentGetRecord:
        """``GET api.prv.se/patents/applications/{application_number}``.

        ``application_number`` accepts either the formatted form
        (``SE2615555-6``) or the compact form (``26155556``).
        ``application_type`` defaults to ``NAT`` (national); other
        enum values are accepted upstream for EP / PCT routes.
        """
        appno = (application_number or "").strip()
        if not appno:
            raise ValueError("application_number must be a non-empty string")
        payload = await self._request_json(
            "GET",
            f"{API_HOST}/patents/applications/{appno}",
            params={"applicationType": application_type},
            context=f"prv_se.get_patent[{appno}]",
        )
        return PatentGetRecord.model_validate(payload)

    async def get_patents(
        self,
        application_numbers: Iterable[str],
        *,
        application_type: str = "NAT",
    ) -> list[PatentGetRecord]:
        """Sequential portfolio fetch by application number.

        The MCP wrapper layers bounded concurrency on top; the library
        helper stays simple.
        """
        results: list[PatentGetRecord] = []
        for appno in application_numbers:
            results.append(await self.get_patent(appno, application_type=application_type))
        return results

    # ------------------------------------------------------------------
    # Trademark simple search
    # ------------------------------------------------------------------

    async def search_trademarks(
        self,
        *,
        text: str | None = None,
        page: int = 0,
        page_size: int = 10,
        sort_column: str | None = "filingDate",
        sort_order: str | None = "DESC",
        extra: dict[str, Any] | None = None,
    ) -> TrademarkSearchResponse:
        """``POST dv-search-api.prv.se/searchtrademark/tmsimplesearch/``."""
        body = _build_simple_search_body(
            text=text,
            page=page,
            page_size=page_size,
            sort_column=sort_column,
            sort_order=sort_order,
            extra=extra,
        )
        payload = await self._request_json(
            "POST",
            f"{DV_HOST}/searchtrademark/tmsimplesearch/",
            json=body,
            context="prv_se.search_trademarks",
        )
        return TrademarkSearchResponse.model_validate(payload)

    # ------------------------------------------------------------------
    # Design simple search
    # ------------------------------------------------------------------

    async def search_designs(
        self,
        *,
        text: str | None = None,
        page: int = 0,
        page_size: int = 10,
        sort_column: str | None = "filingDate",
        sort_order: str | None = "DESC",
        extra: dict[str, Any] | None = None,
    ) -> DesignSearchResponse:
        """``POST dv-search-api.prv.se/searchdesign/dssimplesearch/``."""
        body = _build_simple_search_body(
            text=text,
            page=page,
            page_size=page_size,
            sort_column=sort_column,
            sort_order=sort_order,
            extra=extra,
        )
        payload = await self._request_json(
            "POST",
            f"{DV_HOST}/searchdesign/dssimplesearch/",
            json=body,
            context="prv_se.search_designs",
        )
        return DesignSearchResponse.model_validate(payload)

    # ------------------------------------------------------------------
    # SPC search (advanced-shape body)
    # ------------------------------------------------------------------

    async def search_spcs(
        self,
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
        sort_column: str = "",
        sort_order: str = "DESC",
    ) -> SpcSearchResponse:
        """``POST patents-search-api.prv.se/searchpatentspc/patentsearchspc/``.

        Swedish supplementary protection certificates (SPCs) — the
        patent-term extension for pharmaceuticals and plant-protection
        products under EU Regulation 469/2009 / 1610/96.

        The SPC endpoint takes an advanced-search body (each filter
        wraps as ``{value, searchType}``); at least one filter is
        required (an empty body returns HTTP 500). ``match_type``
        applies to every populated filter and accepts ``CONTAINS``
        (default), ``STARTS_WITH``, or ``EXACT``.
        """
        if not any(
            (
                substance_product,
                applicants,
                application_number_spc,
                base_patent_number,
                marketing_authorization_number,
                announcement,
            )
        ):
            raise ValueError(
                "search_spcs requires at least one filter "
                "(substance_product / applicants / "
                "application_number_spc / base_patent_number / "
                "marketing_authorization_number / announcement)"
            )

        body = _build_advanced_search_body(
            page=page,
            page_size=page_size,
            sort_column=sort_column,
            sort_order=sort_order,
            filters={
                "substanceProduct": (substance_product, match_type) if substance_product else "",
                "applicants": (applicants, match_type) if applicants else "",
                "applicationNumberSPC": (application_number_spc, match_type)
                if application_number_spc
                else "",
                "basePatentNumber": (base_patent_number, match_type) if base_patent_number else "",
                "marketingAuthorizationNumber": (
                    marketing_authorization_number,
                    match_type,
                )
                if marketing_authorization_number
                else "",
                "announcement": (announcement, match_type) if announcement else "",
            },
        )
        payload = await self._request_json(
            "POST",
            f"{PATENTS_HOST}/searchpatentspc/patentsearchspc/",
            json=body,
            context="prv_se.search_spcs",
        )
        return SpcSearchResponse.model_validate(payload)


__all__ = [
    "PrvClient",
    "PATENTS_HOST",
    "DV_HOST",
    "API_HOST",
    "DEFAULT_USER_AGENT",
    "MAX_PAGE_SIZE",
]
