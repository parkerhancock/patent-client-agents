"""Async client for KIPO KIPRIS Plus REST API.

KIPRIS Plus is the Korean Intellectual Property Information Service Plus
data API operated by KIPI on behalf of KIPO (Korea). Auth is a single
per-user ``serviceKey`` (query parameter) issued at signup; ToS §11
forbids key sharing, hence BYOK only (no shared-key proxy on the hosted
deploy).

Responses are XML envelopes shaped::

    <response>
      <header>
        <successYN>Y</successYN>
        <resultCode>00</resultCode>
        <resultMsg>NORMAL SERVICE</resultMsg>
      </header>
      <body>
        <items>
          <item>...row fields...</item>
        </items>
        <numOfRows>10</numOfRows>
        <pageNo>1</pageNo>
        <totalCount>123</totalCount>
      </body>
    </response>

Usage::

    async with KiprisClient(service_key="...") as client:
        envelope = await client.search_patents_word(query="battery")
        for row in envelope.items:
            ...

Environment Variables:
    KIPO_KIPRIS_API_KEY: per-user KIPRIS Plus ``serviceKey`` issued at
        ``https://plus.kipris.or.kr/eng/main.do`` (ToS §11 BYOK).
"""

from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator
from typing import Any

import httpx

from law_tools_core.base_client import BaseAsyncClient
from law_tools_core.exceptions import (
    ApiError,
    ConfigurationError,
    RateLimitError,
)
from law_tools_core.resilience import default_retryer

from .models import DesignRow, PatentUtilityRow, TrademarkRow

logger = logging.getLogger(__name__)

# KIPRIS Plus docs cite this host (HTTP, not HTTPS in current docs). If
# HTTPS works once cassettes are recorded in chunk 4, update the scheme
# at that point — for now, document what the primary source says.
BASE_URL = "http://kipo-api.kipi.or.kr/openapi/service"

# Service prefixes (each prefix maps to a KIPRIS Plus service; operations
# hang off the prefix as ``/{operation}``).
PAT_UTL = "patUtliInfoSearchService"
TM = "trademarkInfoSearchService"
DESIGN = "designInfoSearchService"

# Default + max page sizes per KIPRIS Plus service docs.
DEFAULT_NUM_OF_ROWS = 10
MAX_NUM_OF_ROWS = 1000

# Cap list-accept fan-out per spec §6 to bound latency on serial fetches.
LIST_ACCEPT_CAP = 50

_SIGNUP_URL = "https://plus.kipris.or.kr/eng/main.do"


class KiprisClient(BaseAsyncClient):
    """Async client over the three KIPRIS Plus information-search services.

    One client instance covers ``patUtliInfoSearchService`` (patents +
    utility models), ``trademarkInfoSearchService``, and
    ``designInfoSearchService``. The ``serviceKey`` is appended to every
    request as a query parameter; per-service convenience methods cover
    word-search, advanced-search, and number-fetch operations.
    """

    DEFAULT_BASE_URL = BASE_URL
    CACHE_NAME = "kipo_kipris"
    DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        service_key: str | None = None,
        *,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize the KIPRIS Plus client.

        Args:
            service_key: Per-user KIPRIS Plus ``serviceKey``. Falls back
                to ``KIPO_KIPRIS_API_KEY``.
            base_url: Override the default API base URL.
            client: Existing httpx.AsyncClient (for testing).

        Raises:
            ConfigurationError: If no ``serviceKey`` is resolvable.
        """
        resolved_key = service_key or os.getenv("KIPO_KIPRIS_API_KEY")
        if not resolved_key:
            raise ConfigurationError(
                "KIPRIS Plus API key required. Set KIPO_KIPRIS_API_KEY "
                "environment variable or pass service_key parameter. "
                f"Sign up at {_SIGNUP_URL} (KIPRIS Plus ToS §11: "
                "per-user keys only — no shared keys)."
            )
        self._service_key = resolved_key

        super().__init__(
            base_url=base_url,
            client=client,
            use_cache=True,
            headers={"Accept": "application/xml"},
            timeout=self.DEFAULT_TIMEOUT,
        )

    # ------------------------------------------------------------------
    # Low-level transport
    # ------------------------------------------------------------------

    async def _get(self, service: str, operation: str, **params: Any) -> bytes:
        """Issue a GET against ``{BASE_URL}/{service}/{operation}``.

        Always appends ``serviceKey``; drops ``None`` values so callers
        can pass optional filters without conditional dict-building.

        Returns the raw response body bytes (XML) — parsing is the
        caller's responsibility via :func:`_parse_kipris_response`.
        """
        query: dict[str, Any] = {"serviceKey": self._service_key}
        for key, value in params.items():
            if value is None:
                continue
            query[key] = value

        url = f"{self.base_url}/{service}/{operation}"

        async for attempt in default_retryer(max_attempts=3, max_wait=10.0):
            with attempt:
                response = await self._client.get(url, params=query)
                if response.status_code == 429:
                    raise RateLimitError(
                        "KIPRIS Plus rate limit exceeded",
                        response.status_code,
                        response.text[:500],
                    )
                if not response.is_success:
                    raise ApiError(
                        f"KIPRIS Plus API error: {response.status_code}",
                        response.status_code,
                        response.text[:500],
                    )
                return response.content

        # Unreachable — default_retryer either yields or raises.
        raise ApiError("KIPRIS Plus API: retry loop exited unexpectedly", -1, "")

    # ------------------------------------------------------------------
    # XML parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_kipris_response(xml_bytes: bytes) -> tuple[list[dict], dict]:
        """Parse a KIPRIS Plus XML response into (items, pagination).

        Returns:
            A tuple ``(items, pagination)`` where ``items`` is the list
            of ``<item>`` dicts and ``pagination`` carries ``numOfRows``,
            ``pageNo``, ``totalCount``, ``resultCode``, ``resultMsg``.

        Raises:
            ApiError: When the response carries a non-success ``resultCode``
                or is structurally malformed.
        """
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as exc:
            raise ApiError(
                f"KIPRIS Plus returned non-XML response: {exc}",
                -1,
                xml_bytes[:500].decode("utf-8", errors="replace"),
            ) from exc

        # Header — every KIPRIS response includes a result code.
        header = root.find("header")
        result_code: str | None = None
        result_msg: str | None = None
        if header is not None:
            rc_el = header.find("resultCode")
            rm_el = header.find("resultMsg")
            if rc_el is not None and rc_el.text is not None:
                result_code = rc_el.text.strip()
            if rm_el is not None and rm_el.text is not None:
                result_msg = rm_el.text.strip()

        # Per KIPRIS docs, "00" means NORMAL SERVICE. Some operations
        # use empty/missing for success when no body is returned.
        if result_code not in (None, "", "00"):
            raise ApiError(
                f"KIPRIS Plus result {result_code}: {result_msg or 'unknown error'}",
                -1,
                "",
            )

        # Body — items + pagination.
        body = root.find("body")
        items: list[dict] = []
        pagination: dict[str, Any] = {
            "resultCode": result_code,
            "resultMsg": result_msg,
            "numOfRows": None,
            "pageNo": None,
            "totalCount": None,
        }
        if body is None:
            return items, pagination

        items_el = body.find("items")
        if items_el is not None:
            for item_el in items_el.findall("item"):
                items.append(_element_to_dict(item_el))

        for key in ("numOfRows", "pageNo", "totalCount"):
            el = body.find(key)
            if el is not None and el.text is not None:
                try:
                    pagination[key] = int(el.text.strip())
                except ValueError:
                    pagination[key] = el.text.strip()

        return items, pagination

    # ------------------------------------------------------------------
    # Pagination helper
    # ------------------------------------------------------------------

    async def paginate(
        self,
        method: Any,
        *,
        num_of_rows: int = DEFAULT_NUM_OF_ROWS,
        max_pages: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict]:
        """Walk pages of a KIPRIS Plus search method until exhausted.

        KIPRIS Plus uses 1-indexed ``pageNo`` + ``numOfRows`` (default
        10, max 1000). This helper invokes ``method`` repeatedly bumping
        ``pageNo`` and yields each row dict until a partial page is
        returned or ``max_pages`` is hit.

        Args:
            method: Bound search method (e.g. ``self.search_patents_word``).
                Must accept ``num_of_rows`` and ``page_no`` kwargs and
                return ``(items, pagination)``.
            num_of_rows: Rows per page (capped at ``MAX_NUM_OF_ROWS``).
            max_pages: Stop after this many pages even if more exist.
            **kwargs: Forwarded verbatim to ``method``.

        Yields:
            Each row dict in order across all pages.
        """
        rows_per_page = min(num_of_rows, MAX_NUM_OF_ROWS)
        page_no = 1
        while True:
            items, _ = await method(num_of_rows=rows_per_page, page_no=page_no, **kwargs)
            for item in items:
                yield item
            if len(items) < rows_per_page:
                return
            if max_pages is not None and page_no >= max_pages:
                return
            page_no += 1

    # ------------------------------------------------------------------
    # Patents + Utility Models (patUtliInfoSearchService)
    # ------------------------------------------------------------------

    async def search_patents_word(
        self,
        word: str,
        *,
        patent: bool = True,
        utility: bool = True,
        num_of_rows: int = DEFAULT_NUM_OF_ROWS,
        page_no: int = 1,
        **extra: Any,
    ) -> tuple[list[dict], dict]:
        """Free-text search across patent + utility-model bibliographies.

        Maps to ``patUtliInfoSearchService/getWordSearch``. The
        ``patent`` and ``utility`` flags toggle the two subsets KIPRIS
        bundles into one service. ``extra`` is forwarded verbatim for
        less-common filters (e.g. ``applicant``, date ranges, ``ipc``).
        """
        xml_bytes = await self._get(
            PAT_UTL,
            "getWordSearch",
            word=word,
            patent="Y" if patent else "N",
            utility="Y" if utility else "N",
            numOfRows=min(num_of_rows, MAX_NUM_OF_ROWS),
            pageNo=page_no,
            **extra,
        )
        return self._parse_kipris_response(xml_bytes)

    async def search_patents_advanced(
        self,
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
        num_of_rows: int = DEFAULT_NUM_OF_ROWS,
        page_no: int = 1,
        **extra: Any,
    ) -> tuple[list[dict], dict]:
        """Structured-field search over patents + utility models.

        Maps to ``patUtliInfoSearchService/getAdvancedSearch``. Every
        field is optional — KIPRIS ANDs whatever is provided.
        """
        xml_bytes = await self._get(
            PAT_UTL,
            "getAdvancedSearch",
            inventionTitle=invention_title,
            astrtCont=astrt_cont,
            claimScope=claim_scope,
            applicant=applicant,
            inventors=inventor,
            ipcNumber=ipc,
            applicationDate=application_date,
            publicationDate=publication_date,
            patent="Y" if patent else "N",
            utility="Y" if utility else "N",
            numOfRows=min(num_of_rows, MAX_NUM_OF_ROWS),
            pageNo=page_no,
            **extra,
        )
        return self._parse_kipris_response(xml_bytes)

    async def get_patent(self, number: str, **extra: Any) -> tuple[list[dict], dict]:
        """Fetch a single patent / UM by application or publication number.

        KIPRIS has no dedicated by-number fetch endpoint; we use the
        advanced-search service with the application-number field set,
        which returns the exact row(s) for that number.
        """
        # Use the advanced-search service with ``applicationNumber`` set;
        # KIPRIS returns the matching row directly.
        xml_bytes = await self._get(
            PAT_UTL,
            "getAdvancedSearch",
            applicationNumber=number,
            patent="Y",
            utility="Y",
            numOfRows=DEFAULT_NUM_OF_ROWS,
            pageNo=1,
            **extra,
        )
        return self._parse_kipris_response(xml_bytes)

    # ------------------------------------------------------------------
    # Trademarks (trademarkInfoSearchService)
    # ------------------------------------------------------------------

    async def search_trademarks_word(
        self,
        word: str,
        *,
        num_of_rows: int = DEFAULT_NUM_OF_ROWS,
        page_no: int = 1,
        **extra: Any,
    ) -> tuple[list[dict], dict]:
        """Free-text search across trademark bibliographies.

        Maps to ``trademarkInfoSearchService/getWordSearch``.
        """
        xml_bytes = await self._get(
            TM,
            "getWordSearch",
            word=word,
            numOfRows=min(num_of_rows, MAX_NUM_OF_ROWS),
            pageNo=page_no,
            **extra,
        )
        return self._parse_kipris_response(xml_bytes)

    async def search_trademarks_advanced(
        self,
        *,
        title: str | None = None,
        applicant: str | None = None,
        classification: str | None = None,
        vienna_code: str | None = None,
        application_date: str | None = None,
        registration_date: str | None = None,
        num_of_rows: int = DEFAULT_NUM_OF_ROWS,
        page_no: int = 1,
        **extra: Any,
    ) -> tuple[list[dict], dict]:
        """Structured-field search over trademarks.

        Maps to ``trademarkInfoSearchService/getAdvancedSearch``.
        """
        xml_bytes = await self._get(
            TM,
            "getAdvancedSearch",
            title=title,
            applicantName=applicant,
            classification=classification,
            viennaCode=vienna_code,
            applicationDate=application_date,
            registrationDate=registration_date,
            numOfRows=min(num_of_rows, MAX_NUM_OF_ROWS),
            pageNo=page_no,
            **extra,
        )
        return self._parse_kipris_response(xml_bytes)

    async def get_trademark(self, number: str, **extra: Any) -> tuple[list[dict], dict]:
        """Fetch a single trademark by application or registration number."""
        xml_bytes = await self._get(
            TM,
            "getAdvancedSearch",
            applicationNumber=number,
            numOfRows=DEFAULT_NUM_OF_ROWS,
            pageNo=1,
            **extra,
        )
        return self._parse_kipris_response(xml_bytes)

    # ------------------------------------------------------------------
    # Designs (designInfoSearchService)
    # ------------------------------------------------------------------

    async def search_designs_word(
        self,
        word: str,
        *,
        num_of_rows: int = DEFAULT_NUM_OF_ROWS,
        page_no: int = 1,
        **extra: Any,
    ) -> tuple[list[dict], dict]:
        """Free-text search across design bibliographies.

        Maps to ``designInfoSearchService/getWordSearch``.
        """
        xml_bytes = await self._get(
            DESIGN,
            "getWordSearch",
            word=word,
            numOfRows=min(num_of_rows, MAX_NUM_OF_ROWS),
            pageNo=page_no,
            **extra,
        )
        return self._parse_kipris_response(xml_bytes)

    async def search_designs_advanced(
        self,
        *,
        article_name: str | None = None,
        applicant: str | None = None,
        loc_code: str | None = None,
        application_date: str | None = None,
        registration_date: str | None = None,
        num_of_rows: int = DEFAULT_NUM_OF_ROWS,
        page_no: int = 1,
        **extra: Any,
    ) -> tuple[list[dict], dict]:
        """Structured-field search over designs.

        Maps to ``designInfoSearchService/getAdvancedSearch``.
        """
        xml_bytes = await self._get(
            DESIGN,
            "getAdvancedSearch",
            articleName=article_name,
            applicantName=applicant,
            locCode=loc_code,
            applicationDate=application_date,
            registrationDate=registration_date,
            numOfRows=min(num_of_rows, MAX_NUM_OF_ROWS),
            pageNo=page_no,
            **extra,
        )
        return self._parse_kipris_response(xml_bytes)

    async def get_design(self, number: str, **extra: Any) -> tuple[list[dict], dict]:
        """Fetch a single design by application or registration number."""
        xml_bytes = await self._get(
            DESIGN,
            "getAdvancedSearch",
            applicationNumber=number,
            numOfRows=DEFAULT_NUM_OF_ROWS,
            pageNo=1,
            **extra,
        )
        return self._parse_kipris_response(xml_bytes)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _element_to_dict(element: ET.Element) -> dict[str, Any]:
    """Flatten a KIPRIS ``<item>`` element into a ``{tag: text}`` dict.

    KIPRIS item elements are flat — every child is a leaf element with
    text content (or empty). We collect tag → text mappings; if KIPRIS
    ever introduces nested elements, the inner-element text is dropped
    here (Pydantic's ``extra="ignore"`` then absorbs the unmodeled
    parent silently).
    """
    out: dict[str, Any] = {}
    for child in element:
        text = (child.text or "").strip()
        out[child.tag] = text or None
    return out


__all__ = [
    "BASE_URL",
    "DEFAULT_NUM_OF_ROWS",
    "DESIGN",
    "DesignRow",
    "KiprisClient",
    "LIST_ACCEPT_CAP",
    "MAX_NUM_OF_ROWS",
    "PAT_UTL",
    "PatentUtilityRow",
    "TM",
    "TrademarkRow",
]
