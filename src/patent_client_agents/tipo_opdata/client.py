"""Async client for the TIPO OpenData REST API.

SCAFFOLD STUB (chunk 1 of 4). This file currently retains the IP
Australia Patents client body purely so the package imports cleanly;
chunk 3 will rewrite this against the TIPO OAS (``tk`` query-string
auth, ``cloud.tipo.gov.tw/S220/opdataapi/api`` host, 15 endpoints with
``top``/``skip`` pagination and 6,000-row cap).

Final auth contract: ``TIPO_API_KEY`` env var carries the ``tk`` token
provisioned by emailing the docx form to ``ipoid@tipo.gov.tw``. See
``research/national/tw-tipo.md`` §3 + §5 and
``research/specs/tw-tipo-connector-spec.md``.
"""

from __future__ import annotations

from typing import Any

import httpx

from law_tools_core import BaseAsyncClient
from patent_client_agents.ip_australia_common import (
    IpAustraliaEnvironment,
    build_auth,
    host_for,
    resolve_environment,
)

from .models import Patent, PatentSearchResult

_API_PATH = "/public/australian-patent-search-api/v1"


class TipoClient(BaseAsyncClient):
    """Async client for the TIPO OpenData REST API.

    SCAFFOLD STUB — body retained from the IP Australia Patents template
    so the package is importable. Chunk 3 rewrites this against the
    TIPO OAS.
    """

    CACHE_NAME: str = "tipo_opdata"
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
                "User-Agent": "patent-client-agents-tipo-opdata/0.1",
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
        """Stub — chunk 3 will rewrite against TIPO ``/PatentAppl`` etc."""
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
            context="tipo_opdata.search",
        )
        return PatentSearchResult.model_validate(data)

    # ------------------------------------------------------------------
    # Detail
    # ------------------------------------------------------------------

    async def get_patent(self, application_number: str) -> Patent:
        """Stub — chunk 3 will rewrite against TIPO per-record FTPS pointer."""
        data = await self._request_json(
            "GET",
            f"/patent/{application_number}",
            context=f"tipo_opdata.get_patent[{application_number}]",
        )
        return Patent.model_validate(data)


__all__ = ["TipoClient"]
