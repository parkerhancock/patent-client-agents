"""Async client for the EUIPO Trademark Search API.

Spec: ``research/openapi/euipo_trademark_search.json`` (v1.0.0 prod) +
``research/openapi/euipo_trademark_search_v110_sandbox.json`` (v1.1.0 sandbox).
Operation signatures are identical across versions.

Auth: OAuth 2.0 client_credentials (RFC 6749 §4.4) with scope ``uid``.
Every request carries BOTH ``Authorization: Bearer ...`` AND
``X-IBM-Client-Id`` (the apiKey scheme). Configure via constructor args
or ``EUIPO_CLIENT_ID`` / ``EUIPO_CLIENT_SECRET`` env vars.

Environment toggle: ``environment="production"`` (default) uses
``api.euipo.europa.eu`` + the cas-server-webapp token endpoint;
``"sandbox"`` uses the matching ``api-sandbox`` host. Override per-host
with ``base_url=`` and ``token_url=`` if needed. ``EUIPO_ENV`` env var
applies if the constructor doesn't pass ``environment``.

Production access requires identity-document review by EUIPO; sandbox
auto-approves on subscription. Sandbox data is a frozen historical
snapshot plus synthetic test rows — fine for shape testing, not fresh
register data. See ``research/euipo_api_authoritative.md`` for details.

Query language is RSQL — for example
``applicationDate>=2024-01-01 and (markFeature==WORD and niceClasses=all=(25,40))``.
"""

from __future__ import annotations

import os
from typing import Any, Literal

import httpx

from law_tools_core import BaseAsyncClient
from law_tools_core.exceptions import ConfigurationError
from law_tools_core.oauth2 import OAuth2ClientCredentialsAuth

from .models import Trademark, TrademarkSearchResult

EuipoEnvironment = Literal["production", "sandbox"]

_PROD_BASE_URL = "https://api.euipo.europa.eu/trademark-search"
_SANDBOX_BASE_URL = "https://api-sandbox.euipo.europa.eu/trademark-search"
_PROD_TOKEN_URL = "https://euipo.europa.eu/cas-server-webapp/oidc/accessToken"
_SANDBOX_TOKEN_URL = "https://auth-sandbox.euipo.europa.eu/oidc/accessToken"

_DEFAULT_SCOPE = "uid"
_MAX_PAGE_SIZE = 100
_MIN_PAGE_SIZE = 10


class EuipoTrademarksClient(BaseAsyncClient):
    """Async client for ``api(-sandbox).euipo.europa.eu/trademark-search``.

    See module docstring for the auth + environment contract.
    """

    CACHE_NAME: str = "euipo_trademarks"
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
    ) -> TrademarkSearchResult:
        """Search EUTMs with an RSQL ``query`` expression.

        Args:
            query: RSQL filter, e.g.
                ``wordMarkSpecification.verbalElement==*Apple* and status==REGISTERED``.
                Omit for an unfiltered listing (you'll get the whole register).
            page: 0-indexed page number.
            size: Page size, 10..100. EUIPO rejects size<10 with HTTP 400.
            sort: ``field:asc`` or ``field:desc``, e.g. ``applicationDate:desc``.
            fields: EBNF field selector to trim the payload, e.g.
                ``!(goodsAndServices)`` to omit a heavy field.

        Returns:
            :class:`TrademarkSearchResult` envelope. Use ``.trademarks`` for
            rows and ``.total_elements`` for the match count.
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

        data = await self._request_json(
            "GET", "/trademarks", params=params, context="search_trademarks"
        )
        return TrademarkSearchResult.model_validate(data)

    # ------------------------------------------------------------------
    # Detail
    # ------------------------------------------------------------------

    async def get_trademark(self, application_number: str) -> Trademark:
        """Fetch the full record for a single EUTM by application number.

        EUTM application numbers are 9-digit zero-padded strings
        (e.g. ``000274084``) or ``W########[A]`` for international
        registrations designating the EU.
        """
        data = await self._request_json(
            "GET",
            f"/trademarks/{application_number}",
            context=f"get_trademark[{application_number}]",
        )
        return Trademark.model_validate(data)

    # ------------------------------------------------------------------
    # Media — return raw bytes
    # ------------------------------------------------------------------

    async def get_image(self, application_number: str) -> bytes:
        """Mark image (figurative / 3D shape / colour / position / pattern)."""
        response = await self._request(
            "GET",
            f"/trademarks/{application_number}/image",
            context=f"get_image[{application_number}]",
        )
        return response.content

    async def get_image_thumbnail(self, application_number: str) -> bytes:
        """Thumbnail of the mark image."""
        response = await self._request(
            "GET",
            f"/trademarks/{application_number}/image/thumbnail",
            context=f"get_image_thumbnail[{application_number}]",
        )
        return response.content

    async def get_sound(self, application_number: str) -> bytes:
        """Sound mark audio bytes."""
        response = await self._request(
            "GET",
            f"/trademarks/{application_number}/sound",
            context=f"get_sound[{application_number}]",
        )
        return response.content

    async def get_video(self, application_number: str) -> bytes:
        """Multimedia / motion mark video bytes."""
        response = await self._request(
            "GET",
            f"/trademarks/{application_number}/video",
            context=f"get_video[{application_number}]",
        )
        return response.content

    async def get_model(self, application_number: str) -> bytes:
        """3D shape mark model bytes."""
        response = await self._request(
            "GET",
            f"/trademarks/{application_number}/model",
            context=f"get_model[{application_number}]",
        )
        return response.content


__all__ = ["EuipoEnvironment", "EuipoTrademarksClient"]
