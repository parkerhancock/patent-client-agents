"""Async client for the Australian Trade Mark Search API.

Endpoint surface (verified 2026-05-16 against
``descriptions.api.gov.au/ipaustralia/trademark-search/``):

* ``POST /search/quick`` — quick-search by query string + filters
  (``quickSearchType``, ``status``, ``changedSinceDate``).
* ``GET /trade-mark/{ipRightIdentifier}`` — full record for one
  Australian trade mark by serial number.

Auth: OAuth 2.0 client_credentials. See
:mod:`patent_client_agents.ip_australia_common` for the shared
handshake.
"""

from __future__ import annotations

from typing import Any

import httpx

from mcp_data_core import BaseAsyncClient
from patent_client_agents.ip_australia_common import (
    IpAustraliaEnvironment,
    build_auth,
    host_for,
    resolve_environment,
)

from .models import Trademark, TrademarkSearchResult

_API_PATH = "/public/australian-trade-mark-search-api/v1"


class IpAustraliaTrademarksClient(BaseAsyncClient):
    """Async client for the Australian Trade Mark Search API."""

    CACHE_NAME: str = "ip_australia_trademarks"
    DEFAULT_TIMEOUT: float = 30.0

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        environment: IpAustraliaEnvironment | None = None,
        base_url: str | None = None,
        auth: httpx.Auth | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_env = resolve_environment(environment)
        resolved_base = base_url or f"{host_for(resolved_env)}{_API_PATH}"
        if auth is None:
            auth = build_auth(
                client_id=client_id,
                client_secret=client_secret,
                environment=resolved_env,
            )

        self.environment: IpAustraliaEnvironment = resolved_env

        super().__init__(
            base_url=resolved_base,
            headers={
                "Accept": "application/json",
                "User-Agent": "patent-client-agents-ip-australia/0.1",
            },
            auth=auth,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        *,
        query: str,
        quick_search_type: list[str] | None = None,
        status: list[str] | None = None,
        changed_since: str | None = None,
        sort_field: str | None = None,
        sort_direction: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> TrademarkSearchResult:
        """Quick-search Australian trade marks by ``query`` + optional filters.

        Args:
            query: Free-text search string (e.g. ``"VEGEMITE"``).
            quick_search_type: Filter by mark type
                (e.g. ``["WORD"]`` or ``["IMAGE"]``).
            status: Filter by lifecycle status
                (e.g. ``["REGISTERED"]``).
            changed_since: ISO date (``YYYY-MM-DD``); only marks updated
                on or after this date are returned. Useful for
                incremental syncs.
            sort_field: Optional sort field (e.g. ``"NUMBER"``).
            sort_direction: ``"ASCENDING"`` or ``"DESCENDING"``.
            extra: Additional payload fields to merge in.
        """
        filters: dict[str, Any] = {}
        if quick_search_type:
            filters["quickSearchType"] = list(quick_search_type)
        if status:
            filters["status"] = list(status)

        payload: dict[str, Any] = {"query": query}
        if filters:
            payload["filters"] = filters
        if changed_since is not None:
            payload["changedSinceDate"] = changed_since
        if sort_field is not None:
            payload["sort"] = {
                "field": sort_field,
                "direction": sort_direction or "ASCENDING",
            }
        if extra:
            payload.update(extra)

        data = await self._request_json(
            "POST",
            "/search/quick",
            json=payload,
            context="ip_australia_trademarks.search",
        )
        return TrademarkSearchResult.model_validate(data)

    # ------------------------------------------------------------------
    # Detail
    # ------------------------------------------------------------------

    async def get_trademark(self, serial_number: str) -> Trademark:
        """Fetch the full record for one Australian trade mark by serial number.

        Serial numbers are the Australian trade mark numbers
        (e.g. ``"1234567"``).
        """
        data = await self._request_json(
            "GET",
            f"/trade-mark/{serial_number}",
            context=f"ip_australia_trademarks.get_trademark[{serial_number}]",
        )
        return Trademark.model_validate(data)


__all__ = ["IpAustraliaTrademarksClient"]
