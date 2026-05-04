"""Auth wiring helpers for MCP servers built on ``law_tools_core``.

Two entry points:

- :func:`make_auth` builds the ``AuthProvider`` passed to
  ``FastMCP(auth=...)``, reading env vars to pick a shape:

  - ``GOOGLE_OAUTH_CLIENT_ID`` + ``GOOGLE_OAUTH_CLIENT_SECRET`` set
    (plus ``API_KEY``) → ``MultiAuth(GoogleProvider, [StaticTokenVerifier])``.
    Interactive MCP clients (CoWork) do the full OAuth 2.1 + PKCE + DCR
    dance via Google; cron/S2S callers keep using the static token.
  - Only ``API_KEY`` set → ``StaticTokenVerifier`` alone.
    Drop-in replacement for the legacy ``BearerTokenAuth`` middleware.
  - Neither set → ``None``. Stdio / local dev.

- :func:`make_domain_gate_middleware` rejects tool calls whose Google
  claims don't match an allowed email domain. Static-token callers bypass
  (no claims attached). Empty allowlist disables the gate.

Env var names are read via :mod:`law_tools_core.mcp._env`, so both
``LAW_TOOLS_CORE_*`` (canonical) and ``LAW_TOOLS_*`` (legacy) prefixes
work.
"""

from __future__ import annotations

from collections.abc import Sequence

from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AuthProvider, MultiAuth, TokenVerifier
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import Middleware, MiddlewareContext

from . import _env

_DEFAULT_MCP_REDIRECT_URIS: tuple[str, ...] = (
    "https://claude.ai/*",
    "https://*.anthropic.com/*",
    # Native OAuth clients (Claude Code CLI, gcloud-style helpers) follow
    # RFC 8252 §7.3 and bind a loopback listener on an ephemeral port,
    # registering ``http://localhost:<port>/callback`` as their redirect.
    # FastMCP rejects userinfo bypasses (``http://localhost@evil.com``)
    # before pattern matching, so widening the loopback port is safe.
    "http://localhost:*",
    "http://127.0.0.1:*",
)


def make_auth(
    *,
    base_url: str | None = None,
    issuer_url: str | None = None,
    allowed_email_domains: Sequence[str] = (),
    allowed_client_redirect_uris: Sequence[str] = _DEFAULT_MCP_REDIRECT_URIS,
) -> AuthProvider | None:
    """Build the MCP server's auth provider from env vars.

    Args:
        base_url: Public URL of this server including any mount path
            (e.g. ``https://mcp.bakerbotts.tools/law_tools``). Google's
            redirect lands at ``{base_url}/auth/callback``. When ``None``,
            falls back to ``LAW_TOOLS_CORE_PUBLIC_URL`` (or the legacy
            ``LAW_TOOLS_PUBLIC_URL``) via :mod:`._env`.
        issuer_url: Root-level URL used as the OAuth issuer
            (e.g. ``https://mcp.bakerbotts.tools``). MUST be the host
            root, not a mount path — MCP clients probe
            ``/.well-known/oauth-authorization-server`` at this URL.
            When ``None``, falls back to ``LAW_TOOLS_CORE_ISSUER_URL``,
            then to ``base_url`` (after env resolution). Cloud Run-style
            deployments where the FastMCP app mounts at root can leave
            both unset and let the env supply a single URL for both.
        allowed_email_domains: If non-empty and exactly one domain,
            injected as Google's ``hd`` hint to pre-filter the account
            picker. This is a soft UX hint — actual enforcement lives in
            :func:`make_domain_gate_middleware`.
        allowed_client_redirect_uris: URI patterns accepted from MCP
            clients during Dynamic Client Registration. Default covers
            Claude.ai / Anthropic apps.

    Returns:
        Configured ``AuthProvider`` or ``None`` if no auth env vars are
        set (stdio / local dev).

    Raises:
        ValueError: if Google OAuth credentials are configured but
            ``base_url`` is neither passed nor in env. Static-token-only
            and stdio modes don't need URLs and don't raise.
    """
    google_client_id = _env.get("GOOGLE_OAUTH_CLIENT_ID")
    google_client_secret = _env.get("GOOGLE_OAUTH_CLIENT_SECRET")
    api_key = _env.get("API_KEY")

    static = _build_static_verifier(api_key) if api_key else None

    if google_client_id and google_client_secret:
        resolved_base = base_url or _env.get("PUBLIC_URL")
        resolved_issuer = issuer_url or _env.get("ISSUER_URL") or resolved_base
        if not resolved_base:
            raise ValueError(
                "make_auth: Google OAuth requires base_url (pass arg or set "
                "LAW_TOOLS_CORE_PUBLIC_URL)"
            )
        google = GoogleProvider(
            client_id=google_client_id,
            client_secret=google_client_secret,
            base_url=resolved_base,
            issuer_url=resolved_issuer,
            required_scopes=["openid", "email", "profile"],
            allowed_client_redirect_uris=list(allowed_client_redirect_uris),
            extra_authorize_params=_google_hd_hint(allowed_email_domains),
            require_authorization_consent="external",
        )
        verifiers: list[TokenVerifier] = [static] if static is not None else []
        return MultiAuth(server=google, verifiers=verifiers)

    if static is not None:
        return static

    return None


def make_domain_gate_middleware(allowed_domains: Sequence[str]) -> Middleware:
    """Middleware that restricts Google-authenticated callers by email domain.

    Static-token callers (no email claim) always pass through — they are
    service accounts. Google-authenticated callers must have
    ``email_verified == True`` and an email ending in one of
    ``allowed_domains``.

    Args:
        allowed_domains: Bare domains (e.g. ``["bakerbotts.com"]``). An
            empty list disables the gate entirely; the middleware
            becomes a no-op.

    Note:
        Google's ``hd`` parameter is a UX hint, not a security
        boundary — attackers can manipulate it. Always pair
        ``allowed_email_domains`` in :func:`make_auth` with this
        middleware when you need enforcement.
    """
    normalized = tuple(d.lower().lstrip("@") for d in allowed_domains)
    return _DomainGate(normalized)


class _DomainGate(Middleware):
    """Reject tool calls whose Google claims don't match the domain allowlist."""

    def __init__(self, allowed_domains: tuple[str, ...]) -> None:
        self._allowed_domains = allowed_domains

    async def on_call_tool(self, context: MiddlewareContext, call_next):  # noqa: ANN001
        if not self._allowed_domains:
            return await call_next(context)

        token = get_access_token()
        claims = getattr(token, "claims", None) or {}

        # Static-token callers have no email claim; pass through.
        email = claims.get("email")
        if not email:
            return await call_next(context)

        if not claims.get("email_verified"):
            raise ToolError("Unauthorized: Google email not verified")

        domain = email.rsplit("@", 1)[-1].lower()
        if domain not in self._allowed_domains:
            raise ToolError(
                f"Unauthorized: only {', '.join(self._allowed_domains)} accounts may call this server"
            )

        return await call_next(context)


def _build_static_verifier(api_key: str) -> StaticTokenVerifier:
    """Wrap the shared API key as a StaticTokenVerifier entry.

    Claim shape matches what FastMCP expects: a dict keyed by raw token
    string, each value a dict with at minimum ``client_id`` and
    ``scopes``.

    Scopes match the set GoogleProvider requires
    (``["openid", "email", "profile"]``) so static-token callers
    satisfy MultiAuth's scope check when GoogleProvider is also wired
    up. Without this, cron / S2S callers using the static bearer would
    get ``insufficient_scope`` 403s on every tool call in any
    deployment that enables Google OAuth.
    """
    return StaticTokenVerifier(
        tokens={
            api_key: {
                "client_id": "law-tools-core-service",
                "scopes": ["openid", "email", "profile"],
            }
        }
    )


def _google_hd_hint(allowed_email_domains: Sequence[str]) -> dict[str, str] | None:
    """Return an ``hd`` hint dict if exactly one Workspace domain is allowed.

    Google's ``hd`` parameter filters the account picker to a single
    Workspace domain. With more than one allowed domain it's meaningless;
    with zero it's not relevant. GoogleProvider's defaults
    (``access_type=offline``, ``prompt=consent``) are preserved because
    FastMCP merges our dict on top of its own.
    """
    if len(allowed_email_domains) == 1:
        return {"hd": allowed_email_domains[0]}
    return None
