"""Async client for the EUIPO Design (RCD) Search API.

Spec: ``research/openapi/euipo_design_search.json`` (v1.0.0 production).

Auth: OAuth 2.0 client_credentials with scope ``uid`` and the
``X-IBM-Client-Id`` apiKey header. Same dev-portal App + credentials
work for both Trademark Search and Design Search — see
:mod:`patent_client_agents.euipo_trademarks.client` for the contract.

Production access requires identity-document review; sandbox auto-
approves on subscription. Sandbox data has same-day-registered designs
that aren't realistic of production cadence — useful for shape tests
only. See ``research/euipo_api_authoritative.md``.

Design numbers are ``NNNNNNNNN-NNNN`` (9 digits + dash + 4 digits, e.g.
``099037115-0001``); a multi-design application produces one entry per
indexed design.
"""

from __future__ import annotations

import os
from typing import Any, Literal

import httpx

from law_tools_core import BaseAsyncClient
from law_tools_core.exceptions import ConfigurationError
from law_tools_core.oauth2 import OAuth2ClientCredentialsAuth

from .models import Design, DesignSearchResult

EuipoEnvironment = Literal["production", "sandbox"]

_PROD_BASE_URL = "https://api.euipo.europa.eu/design-search"
_SANDBOX_BASE_URL = "https://api-sandbox.euipo.europa.eu/design-search"
_PROD_TOKEN_URL = "https://euipo.europa.eu/cas-server-webapp/oidc/accessToken"
_SANDBOX_TOKEN_URL = "https://auth-sandbox.euipo.europa.eu/oidc/accessToken"

_DEFAULT_SCOPE = "uid"
_MAX_PAGE_SIZE = 100
_MIN_PAGE_SIZE = 10


class EuipoDesignsClient(BaseAsyncClient):
    """Async client for ``api(-sandbox).euipo.europa.eu/design-search``."""

    CACHE_NAME: str = "euipo_designs"
    DEFAULT_TIMEOUT: float = 30.0

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        environment: EuipoEnvironment | None = None,
        scope: str = _DEFAULT_SCOPE,
        base_url: str | None = None,
        token_url: str | None = None,
        auth: httpx.Auth | None = None,
        **kwargs: Any,
    ) -> None:
        env_raw: str = environment or os.getenv("EUIPO_ENV", "production")
        if env_raw not in ("production", "sandbox"):
            raise ConfigurationError(
                f"EUIPO environment must be 'production' or 'sandbox', got {env_raw!r}"
            )
        resolved_env: EuipoEnvironment = env_raw  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

        resolved_base_url = base_url or (
            _SANDBOX_BASE_URL if resolved_env == "sandbox" else _PROD_BASE_URL
        )
        resolved_token_url = token_url or (
            _SANDBOX_TOKEN_URL if resolved_env == "sandbox" else _PROD_TOKEN_URL
        )

        resolved_client_id = client_id or os.getenv("EUIPO_CLIENT_ID")
        if not resolved_client_id:
            raise ConfigurationError(
                "EUIPO client_id not provided. Set EUIPO_CLIENT_ID or pass client_id=..."
            )

        if auth is None:
            resolved_secret = client_secret or os.getenv("EUIPO_CLIENT_SECRET")
            if not resolved_secret:
                raise ConfigurationError(
                    "EUIPO client_secret not provided. "
                    "Set EUIPO_CLIENT_SECRET or pass client_secret=..., "
                    "or supply a pre-built auth handler via auth=..."
                )
            auth = OAuth2ClientCredentialsAuth(
                token_url=resolved_token_url,
                client_id=resolved_client_id,
                client_secret=resolved_secret,
                scope=scope,
                credentials_in_body=True,
            )

        self._client_id = resolved_client_id
        self.environment: EuipoEnvironment = resolved_env

        super().__init__(
            base_url=resolved_base_url,
            headers={
                "Accept": "application/json",
                "X-IBM-Client-Id": resolved_client_id,
                "User-Agent": "patent-client-agents-euipo/0.1",
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
        query: str | None = None,
        page: int = 0,
        size: int = 25,
        sort: str | None = None,
        fields: str | None = None,
    ) -> DesignSearchResult:
        """Search RCDs with an RSQL ``query`` expression.

        Example queries:
            ``status==REGISTERED_AND_FULLY_PUBLISHED``
            ``applicants.name==*Apple* and locarnoClasses=in=(14.03,14.04)``
            ``applicationDate>=2024-01-01``
        """
        if not _MIN_PAGE_SIZE <= size <= _MAX_PAGE_SIZE:
            raise ValueError(f"size must be {_MIN_PAGE_SIZE}..{_MAX_PAGE_SIZE}, got {size}")
        if page < 0:
            raise ValueError(f"page must be >= 0, got {page}")

        params: dict[str, Any] = {"page": page, "size": size}
        if query is not None:
            params["query"] = query
        if sort is not None:
            params["sort"] = sort
        if fields is not None:
            params["fields"] = fields

        data = await self._request_json("GET", "/designs", params=params, context="search_designs")
        return DesignSearchResult.model_validate(data)

    # ------------------------------------------------------------------
    # Detail
    # ------------------------------------------------------------------

    async def get_design(self, design_number: str) -> Design:
        """Fetch the full record for a single RCD by design number.

        Design numbers are ``NNNNNNNNN-NNNN`` (e.g. ``099037115-0001``).
        """
        data = await self._request_json(
            "GET",
            f"/designs/{design_number}",
            context=f"get_design[{design_number}]",
        )
        return Design.model_validate(data)

    # ------------------------------------------------------------------
    # Media — return raw bytes
    # ------------------------------------------------------------------

    async def get_view(self, design_number: str, order: int) -> bytes:
        """Image bytes for a single view (angle) of the design.

        ``order`` is 1-indexed and matches :class:`View.order`.
        """
        response = await self._request(
            "GET",
            f"/designs/{design_number}/views/{order}",
            context=f"get_view[{design_number}/{order}]",
        )
        return response.content

    async def get_view_thumbnail(self, design_number: str, order: int) -> bytes:
        """Thumbnail of a single view."""
        response = await self._request(
            "GET",
            f"/designs/{design_number}/views/{order}/thumbnail",
            context=f"get_view_thumbnail[{design_number}/{order}]",
        )
        return response.content

    async def get_model(self, design_number: str) -> bytes:
        """3D model bytes (when the design has an attached 3D model)."""
        response = await self._request(
            "GET",
            f"/designs/{design_number}/model",
            context=f"get_model[{design_number}]",
        )
        return response.content


__all__ = ["EuipoDesignsClient", "EuipoEnvironment"]
