"""Async client for the Australian Patent Search API.

Endpoint surface (verified 2026-05-16 against ``descriptions.api.gov.au``
and the live ``production.api.ipaustralia.gov.au`` host):

* ``POST /search/quick`` — quick-search by query string + filters.
* ``GET /patent/{ipRightIdentifier}`` — full record for one patent /
  application number.

Auth: OAuth 2.0 client_credentials against the IP Australia External
Token API. Credentials are sent in the form body
(``credentials_in_body=True``) — IP Australia's documentation specifies
``grant_type``, ``client_id``, ``client_secret`` as form params, not
HTTP Basic.

Environment toggle: ``environment="production"`` (default) targets the
``production.api.ipaustralia.gov.au`` host; ``"sandbox"`` targets
``test.api.ipaustralia.gov.au``. The ``IPAUSTRALIA_ENV`` env var applies
when ``environment`` isn't passed.
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

from .models import Patent, PatentSearchResult

_API_PATH = "/public/australian-patent-search-api/v1"


class IpAustraliaPatentsClient(BaseAsyncClient):
    """Async client for the Australian Patent Search API."""

    CACHE_NAME: str = "ip_australia_patents"
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
        status: list[str] | None = None,
        changed_since: str | None = None,
        sort_field: str | None = None,
        sort_direction: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> PatentSearchResult:
        """Quick-search Australian patents by ``query`` + optional filters.

        Args:
            query: Free-text search string (title / abstract / number).
            status: Filter by patent status (e.g. ``["GRANTED"]``).
            changed_since: ISO date (``YYYY-MM-DD``); only patents updated
                on or after this date are returned. Useful for incremental
                syncs.
            sort_field: Optional sort field (e.g. ``"NUMBER"``).
            sort_direction: ``"ASCENDING"`` or ``"DESCENDING"``.
            extra: Additional payload fields to merge in — escape hatch
                for filters the schema may grow without us re-shipping.
        """
        filters: dict[str, Any] = {}
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
            context="ip_australia_patents.search",
        )
        return PatentSearchResult.model_validate(data)

    # ------------------------------------------------------------------
    # Detail
    # ------------------------------------------------------------------

    async def get_patent(self, application_number: str) -> Patent:
        """Fetch the full record for a single Australian patent.

        ``application_number`` is the Australian patent / application
        number (digits-only, e.g. ``"2019204205"`` or AusPat-style
        ``"AU2019204205"``).
        """
        data = await self._request_json(
            "GET",
            f"/patent/{application_number}",
            context=f"ip_australia_patents.get_patent[{application_number}]",
        )
        return Patent.model_validate(data)


__all__ = ["IpAustraliaPatentsClient"]
