"""Tests for law_tools_core.mcp.auth."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import MultiAuth
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

from law_tools_core.mcp import auth as auth_module
from law_tools_core.mcp.auth import make_auth, make_domain_gate_middleware


@pytest.fixture(autouse=True)
def _clear_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scrub any real auth env vars so tests are hermetic."""
    for var in (
        "LAW_TOOLS_CORE_API_KEY",
        "LAW_TOOLS_API_KEY",
        "LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_ID",
        "LAW_TOOLS_GOOGLE_OAUTH_CLIENT_ID",
        "LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_SECRET",
        "LAW_TOOLS_GOOGLE_OAUTH_CLIENT_SECRET",
        "LAW_TOOLS_CORE_PUBLIC_URL",
        "LAW_TOOLS_PUBLIC_URL",
        "LAW_TOOLS_CORE_ISSUER_URL",
        "LAW_TOOLS_ISSUER_URL",
    ):
        monkeypatch.delenv(var, raising=False)


class TestMakeAuth:
    def test_returns_none_without_env(self) -> None:
        result = make_auth(
            base_url="https://example.com",
            issuer_url="https://example.com",
        )
        assert result is None

    def test_static_only_when_only_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LAW_TOOLS_CORE_API_KEY", "secret")
        result = make_auth(
            base_url="https://example.com",
            issuer_url="https://example.com",
        )
        assert isinstance(result, StaticTokenVerifier)

    def test_static_only_accepts_legacy_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LAW_TOOLS_API_KEY", "legacy")
        result = make_auth(
            base_url="https://example.com",
            issuer_url="https://example.com",
        )
        assert isinstance(result, StaticTokenVerifier)

    def test_multiauth_when_google_and_api_key_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LAW_TOOLS_CORE_API_KEY", "secret")
        monkeypatch.setenv("LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_ID", "gid")
        monkeypatch.setenv("LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_SECRET", "gsecret")
        result = make_auth(
            base_url="https://mcp.bakerbotts.tools/law_tools",
            issuer_url="https://mcp.bakerbotts.tools",
            allowed_email_domains=["bakerbotts.com"],
        )
        assert isinstance(result, MultiAuth)

    def test_multiauth_without_api_key_has_empty_verifiers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_ID", "gid")
        monkeypatch.setenv("LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_SECRET", "gsecret")
        result = make_auth(
            base_url="https://mcp.patentclient.com",
            issuer_url="https://mcp.patentclient.com",
        )
        assert isinstance(result, MultiAuth)

    def test_ignores_google_when_secret_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Half-configured Google creds should not produce a MultiAuth;
        # fall back to static if API key is present.
        monkeypatch.setenv("LAW_TOOLS_CORE_API_KEY", "secret")
        monkeypatch.setenv("LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_ID", "gid")
        result = make_auth(
            base_url="https://example.com",
            issuer_url="https://example.com",
        )
        assert isinstance(result, StaticTokenVerifier)

    def test_urls_from_env_when_args_omitted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Cloud Run-style: deployer sets URLs via env, server.py calls
        # make_auth() with no URL kwargs. issuer_url defaults to base_url
        # when the env doesn't set it separately.
        monkeypatch.setenv("LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_ID", "gid")
        monkeypatch.setenv("LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_SECRET", "gsecret")
        monkeypatch.setenv("LAW_TOOLS_CORE_PUBLIC_URL", "https://law-mcp-xyz.a.run.app")
        result = make_auth()
        assert isinstance(result, MultiAuth)

    def test_url_legacy_prefix_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # _env.get accepts the legacy LAW_TOOLS_* prefix as a fallback;
        # make_auth inherits that for URLs too.
        monkeypatch.setenv("LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_ID", "gid")
        monkeypatch.setenv("LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_SECRET", "gsecret")
        monkeypatch.setenv("LAW_TOOLS_PUBLIC_URL", "https://example.com")
        result = make_auth()
        assert isinstance(result, MultiAuth)

    def test_explicit_kwargs_override_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Belt-and-suspenders: when both env and kwarg are set, the kwarg
        # wins. Lets PCA-style deployers keep passing settings-derived
        # URLs without the env interfering.
        monkeypatch.setenv("LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_ID", "gid")
        monkeypatch.setenv("LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_SECRET", "gsecret")
        monkeypatch.setenv("LAW_TOOLS_CORE_PUBLIC_URL", "https://from-env.example.com")
        result = make_auth(base_url="https://from-arg.example.com")
        # Hard to assert which URL the GoogleProvider got without poking
        # internals, but the call must not raise — the explicit arg
        # short-circuits the env-fallback path.
        assert isinstance(result, MultiAuth)

    def test_raises_when_google_configured_without_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_ID", "gid")
        monkeypatch.setenv("LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_SECRET", "gsecret")
        with pytest.raises(ValueError, match="LAW_TOOLS_CORE_PUBLIC_URL"):
            make_auth()

    def test_static_only_does_not_need_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # No Google creds → no GoogleProvider built → URLs irrelevant.
        # Static-token-only deploys (e.g. cron callers) shouldn't be
        # forced to set a URL just to pass the check.
        monkeypatch.setenv("LAW_TOOLS_CORE_API_KEY", "secret")
        result = make_auth()
        assert isinstance(result, StaticTokenVerifier)

    def test_client_storage_passes_through_to_google_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Persistent client storage (Firestore/Redis-backed) must be
        # threaded into GoogleProvider — the default per-container
        # FileTreeStore silently breaks DCR across Cloud Run cold starts
        # and multi-instance routing. Asserts wiring, not behavior.
        monkeypatch.setenv("LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_ID", "gid")
        monkeypatch.setenv("LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_SECRET", "gsecret")
        monkeypatch.setenv("LAW_TOOLS_CORE_PUBLIC_URL", "https://example.com")
        sentinel = MagicMock(name="client_storage")
        result = make_auth(client_storage=sentinel)
        assert isinstance(result, MultiAuth)
        google_provider = result.server  # MultiAuth.server holds GoogleProvider
        assert google_provider._client_storage is sentinel

    def test_client_storage_default_keeps_fastmcp_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Without an explicit client_storage, GoogleProvider falls back
        # to its built-in FileTreeStore. Stdio / single-process dev rely
        # on this default, so we don't want make_auth() to silently
        # introduce a different one.
        monkeypatch.setenv("LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_ID", "gid")
        monkeypatch.setenv("LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_SECRET", "gsecret")
        monkeypatch.setenv("LAW_TOOLS_CORE_PUBLIC_URL", "https://example.com")
        result = make_auth()
        assert isinstance(result, MultiAuth)
        # FastMCP swaps None for a FileTreeStore in OAuthProxy.__init__,
        # so we just assert _something_ was wired in (proves the kwarg
        # path didn't accidentally swallow it).
        assert result.server._client_storage is not None

    def test_static_verifier_claims_google_scopes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Regression: when GoogleProvider AND static are both wired up
        # via MultiAuth, GoogleProvider's required_scopes are normalized
        # to the FULL Google URL form (e.g. "email" →
        # "https://www.googleapis.com/auth/userinfo.email") and the
        # subsequent issubset check is exact-string. So the static
        # verifier MUST claim the full URL form, or every cron call
        # gets `insufficient_scope`.
        monkeypatch.setenv("LAW_TOOLS_CORE_API_KEY", "cron-secret")
        verifier = make_auth()
        assert isinstance(verifier, StaticTokenVerifier)
        token_record = verifier.tokens["cron-secret"]
        assert "openid" in token_record["scopes"]
        assert "https://www.googleapis.com/auth/userinfo.email" in token_record["scopes"]
        assert "https://www.googleapis.com/auth/userinfo.profile" in token_record["scopes"]


class TestDefaultRedirectUris:
    """Pin the default redirect-URI allowlist used by ``make_auth``.

    The default must cover both the Claude.ai web client and Claude Code's
    native loopback callback (RFC 8252 §7.3). Regressing either forces
    callers to override ``allowed_client_redirect_uris`` and reproduces the
    "Redirect URI does not match allowed patterns" error during DCR.
    """

    def test_includes_claude_ai_web(self) -> None:
        assert "https://claude.ai/*" in auth_module._DEFAULT_MCP_REDIRECT_URIS
        assert "https://*.anthropic.com/*" in auth_module._DEFAULT_MCP_REDIRECT_URIS

    def test_includes_native_loopback_for_claude_code(self) -> None:
        # Claude Code (and other RFC 8252 native clients) bind a local HTTP
        # listener on an ephemeral port. The ``:*`` wildcard makes any port
        # match; userinfo bypass is rejected upstream by FastMCP.
        assert "http://localhost:*" in auth_module._DEFAULT_MCP_REDIRECT_URIS
        assert "http://127.0.0.1:*" in auth_module._DEFAULT_MCP_REDIRECT_URIS


class TestGoogleHdHint:
    def test_single_domain_sets_hd(self) -> None:
        hint = auth_module._google_hd_hint(["bakerbotts.com"])
        assert hint == {"hd": "bakerbotts.com"}

    def test_no_domain_returns_none(self) -> None:
        assert auth_module._google_hd_hint([]) is None

    def test_multiple_domains_returns_none(self) -> None:
        # hd only meaningfully filters one Workspace domain.
        assert auth_module._google_hd_hint(["a.com", "b.com"]) is None


class TestDomainGate:
    @pytest.fixture
    def call_next(self) -> AsyncMock:
        next_mock = AsyncMock()
        next_mock.return_value = "tool-result"
        return next_mock

    @pytest.fixture
    def context(self) -> MagicMock:
        return MagicMock()

    async def test_empty_allowlist_is_noop(
        self, call_next: AsyncMock, context: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Even with a "bad" caller, empty list should pass through.
        monkeypatch.setattr(
            auth_module,
            "get_access_token",
            lambda: MagicMock(claims={"email": "attacker@evil.com"}),
        )
        gate = make_domain_gate_middleware([])
        result = await gate.on_call_tool(context, call_next)
        assert result == "tool-result"
        call_next.assert_awaited_once_with(context)

    async def test_no_access_token_passes_through(
        self, call_next: AsyncMock, context: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(auth_module, "get_access_token", lambda: None)
        gate = make_domain_gate_middleware(["bakerbotts.com"])
        result = await gate.on_call_tool(context, call_next)
        assert result == "tool-result"

    async def test_static_token_caller_passes_through(
        self, call_next: AsyncMock, context: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # StaticTokenVerifier tokens have no email claim.
        monkeypatch.setattr(
            auth_module,
            "get_access_token",
            lambda: MagicMock(claims={}),
        )
        gate = make_domain_gate_middleware(["bakerbotts.com"])
        result = await gate.on_call_tool(context, call_next)
        assert result == "tool-result"

    async def test_rejects_unverified_email(
        self, call_next: AsyncMock, context: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            auth_module,
            "get_access_token",
            lambda: MagicMock(claims={"email": "user@bakerbotts.com", "email_verified": False}),
        )
        gate = make_domain_gate_middleware(["bakerbotts.com"])
        with pytest.raises(ToolError, match="not verified"):
            await gate.on_call_tool(context, call_next)
        call_next.assert_not_awaited()

    async def test_rejects_wrong_domain(
        self, call_next: AsyncMock, context: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            auth_module,
            "get_access_token",
            lambda: MagicMock(claims={"email": "user@gmail.com", "email_verified": True}),
        )
        gate = make_domain_gate_middleware(["bakerbotts.com"])
        with pytest.raises(ToolError, match="bakerbotts.com"):
            await gate.on_call_tool(context, call_next)

    async def test_accepts_allowed_domain(
        self, call_next: AsyncMock, context: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            auth_module,
            "get_access_token",
            lambda: MagicMock(claims={"email": "user@bakerbotts.com", "email_verified": True}),
        )
        gate = make_domain_gate_middleware(["bakerbotts.com"])
        result = await gate.on_call_tool(context, call_next)
        assert result == "tool-result"

    async def test_case_insensitive_domain(
        self, call_next: AsyncMock, context: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            auth_module,
            "get_access_token",
            lambda: MagicMock(claims={"email": "User@BakerBotts.COM", "email_verified": True}),
        )
        gate = make_domain_gate_middleware(["bakerbotts.com"])
        result = await gate.on_call_tool(context, call_next)
        assert result == "tool-result"


class TestBuildServerAuthParam:
    def test_default_none_keeps_legacy_oauth_route(self) -> None:
        from law_tools_core.mcp.server_factory import build_server

        mcp = build_server(name="test", instructions="test server")
        route_paths = _custom_route_paths(mcp)
        assert "/oauth/token" in route_paths
        assert "/downloads/{path:path}" in route_paths

    def test_with_auth_skips_legacy_oauth_route(self) -> None:
        from law_tools_core.mcp.server_factory import build_server

        verifier = StaticTokenVerifier(tokens={"t": {"client_id": "c", "scopes": ["openid"]}})
        mcp = build_server(name="test", instructions="test server", auth=verifier)
        route_paths = _custom_route_paths(mcp)
        assert "/oauth/token" not in route_paths
        # Downloads route remains regardless of auth mode.
        assert "/downloads/{path:path}" in route_paths


def _custom_route_paths(mcp: object) -> list[str]:
    """Extract the registered Starlette route paths from a FastMCP server.

    FastMCP stores ``mcp.custom_route(...)`` registrations on the
    underlying ``_additional_http_routes`` list. The attribute name is
    internal; this helper isolates that coupling.
    """
    routes = getattr(mcp, "_additional_http_routes", None)
    if routes is None:
        # Fallback: some FastMCP versions expose via `_custom_starlette_routes`.
        routes = getattr(mcp, "_custom_starlette_routes", [])
    return [getattr(r, "path", "") for r in routes]
