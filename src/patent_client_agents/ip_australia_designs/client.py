"""Async client for the Australian Designs Search API.

Endpoint surface (verified 2026-05-16 against
``descriptions.api.gov.au/ipaustralia/design-search/``):

* ``POST /search/quick`` — quick-search by query string + filters
  (``classificationFilter`` for Locarno codes, ``statusFilter``,
  ``changedSinceDate``).
* ``GET /design/{ipRightIdentifier}`` — full record for one Australian
  design by design number.

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

from .models import Design, DesignSearchResult

_API_PATH = "/public/australian-design-search-api/v1"


class IpAustraliaDesignsClient(BaseAsyncClient):
    """Async client for the Australian Designs Search API."""

    CACHE_NAME: str = "ip_australia_designs"
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
        classification: list[str] | None = None,
        status: list[str] | None = None,
        changed_since: str | None = None,
        sort_field: str | None = None,
        sort_direction: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> DesignSearchResult:
        """Quick-search Australian designs by ``query`` + optional filters.

        Args:
            query: Free-text search string.
            classification: Filter by Locarno classification codes
                (e.g. ``["0202c"]`` — clothing accessories).
            status: Filter by lifecycle status (e.g. ``["REGISTERED"]``).
            changed_since: ISO date (``YYYY-MM-DD``); only designs
                updated on or after this date are returned.
            sort_field: Optional sort field (e.g. ``"NUMBER"``).
            sort_direction: ``"ASCENDING"`` or ``"DESCENDING"``.
            extra: Additional payload fields to merge in.
        """
        filters: dict[str, Any] = {}
        if classification:
            filters["classificationFilter"] = list(classification)
        if status:
            filters["statusFilter"] = list(status)

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
            context="ip_australia_designs.search",
        )
        return DesignSearchResult.model_validate(data)

    # ------------------------------------------------------------------
    # Detail
    # ------------------------------------------------------------------

    async def get_design(self, design_number: str) -> Design:
        """Fetch the full record for one Australian design by design number."""
        data = await self._request_json(
            "GET",
            f"/design/{design_number}",
            context=f"ip_australia_designs.get_design[{design_number}]",
        )
        return Design.model_validate(data)


__all__ = ["IpAustraliaDesignsClient"]
