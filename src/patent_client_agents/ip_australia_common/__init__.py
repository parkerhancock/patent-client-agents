"""Shared scaffolding for IP Australia OAuth 2.0 connectors.

The three live IP Australia search APIs (patents, trade marks, designs)
share the same OAuth 2.0 client_credentials handshake against the same
External Token API, the same ``production.api.ipaustralia.gov.au`` /
``test.api.ipaustralia.gov.au`` hosts, and the same B2B partner scope.
This module pulls the boilerplate (env resolution, base URL selection,
token-endpoint selection, ``OAuth2ClientCredentialsAuth`` wiring) into
one place so each per-rights client only declares its own API path
prefix and ``CACHE_NAME``.

Auth env vars:
    * ``IPAUSTRALIA_CLIENT_ID``
    * ``IPAUSTRALIA_CLIENT_SECRET``
    * ``IPAUSTRALIA_ENV`` — ``"production"`` (default) or ``"sandbox"``.

The token endpoint expects ``client_id`` + ``client_secret`` in the
form body (RFC 6749 §4.4 "credentials in body" variant), not HTTP
Basic. ``OAuth2ClientCredentialsAuth`` supports both via the
``credentials_in_body=True`` flag.

Verified 2026-05-16 against ``descriptions.api.gov.au/ipaustralia``
and the live ``production.api.ipaustralia.gov.au`` hosts.
"""

from __future__ import annotations

import os
from typing import Literal, cast

from mcp_data_core.exceptions import ConfigurationError
from mcp_data_core.oauth2 import OAuth2ClientCredentialsAuth

IpAustraliaEnvironment = Literal["production", "sandbox"]

_PROD_HOST = "https://production.api.ipaustralia.gov.au"
_SANDBOX_HOST = "https://test.api.ipaustralia.gov.au"
_TOKEN_PATH = "/public/external-token-api/v1/access_token"


def resolve_environment(environment: IpAustraliaEnvironment | None) -> IpAustraliaEnvironment:
    """Resolve the environment from ``environment`` arg or ``IPAUSTRALIA_ENV`` env."""
    env_raw: str = environment or os.getenv("IPAUSTRALIA_ENV", "production")
    if env_raw not in ("production", "sandbox"):
        raise ConfigurationError(
            f"IPAUSTRALIA_ENV must be 'production' or 'sandbox', got {env_raw!r}"
        )
    return cast("IpAustraliaEnvironment", env_raw)


def host_for(environment: IpAustraliaEnvironment) -> str:
    """Return the host (sans path) for ``environment``."""
    return _SANDBOX_HOST if environment == "sandbox" else _PROD_HOST


def token_url_for(environment: IpAustraliaEnvironment) -> str:
    """Return the full External Token API URL for ``environment``."""
    return f"{host_for(environment)}{_TOKEN_PATH}"


def build_auth(
    *,
    client_id: str | None,
    client_secret: str | None,
    environment: IpAustraliaEnvironment,
) -> OAuth2ClientCredentialsAuth:
    """Build an ``OAuth2ClientCredentialsAuth`` from env or args.

    Raises:
        ConfigurationError: when ``client_id`` / ``client_secret`` are
            neither passed nor present in the environment.
    """
    resolved_id = client_id or os.getenv("IPAUSTRALIA_CLIENT_ID")
    if not resolved_id:
        raise ConfigurationError(
            "IP Australia client_id not provided. Set IPAUSTRALIA_CLIENT_ID or pass client_id=..."
        )
    resolved_secret = client_secret or os.getenv("IPAUSTRALIA_CLIENT_SECRET")
    if not resolved_secret:
        raise ConfigurationError(
            "IP Australia client_secret not provided. Set IPAUSTRALIA_CLIENT_SECRET "
            "or pass client_secret=..."
        )
    return OAuth2ClientCredentialsAuth(
        token_url=token_url_for(environment),
        client_id=resolved_id,
        client_secret=resolved_secret,
        credentials_in_body=True,
    )


__all__ = [
    "IpAustraliaEnvironment",
    "build_auth",
    "host_for",
    "resolve_environment",
    "token_url_for",
]
