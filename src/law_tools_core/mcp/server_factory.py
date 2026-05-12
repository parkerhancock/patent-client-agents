"""FastMCP server factory.

``build_server()`` returns a ``FastMCP`` instance with standard
middleware wired (friendly errors, tool-call logging) and standard
custom routes mounted (``/downloads/{path}``). Consumers then
``mcp.mount(sub_mcp)`` their domain-specific tool servers and call
``mcp.run()``.

Both ``patent-client-agents`` and ``law-tools`` MCP servers sit on top of this.

Auth selection:

- If the caller passes ``auth=`` (typically from
  :func:`law_tools_core.mcp.auth.make_auth`), FastMCP handles
  bearer/OAuth validation and the legacy ``/oauth/token`` route and
  ``BearerTokenAuth`` middleware are NOT wired. This is the HTTP
  deployment path.
- If ``auth=None`` (default), the server keeps the legacy behavior:
  ``BearerTokenAuth`` middleware enforces ``LAW_TOOLS_CORE_API_KEY``
  when set, and a ``/oauth/token`` ``client_credentials`` endpoint is
  exposed for OAuth-only clients. This is the stdio / local-dev path
  and a safe fallback for servers not yet migrated to the new helpers.
"""

from __future__ import annotations

import mcp.types
from fastmcp import FastMCP
from fastmcp.server.auth import AuthProvider
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import _env
from .downloads import handle_download
from .middleware import BearerTokenAuth, FriendlyErrors, ToolCallLogger


def build_server(
    name: str,
    instructions: str,
    *,
    auth: AuthProvider | None = None,
    icons: list[mcp.types.Icon] | None = None,
    website_url: str | None = None,
) -> FastMCP:
    """Build a FastMCP server with all standard middleware and routes.

    Args:
        name: Server name (shows up in MCP client UI).
        instructions: One-paragraph description passed to ``FastMCP(...)``.
        auth: Optional FastMCP auth provider. Pass the result of
            :func:`law_tools_core.mcp.auth.make_auth` to opt into the
            new auth stack (Google OAuth + static token). Leave ``None``
            for stdio / legacy static-bearer behavior.
        icons: Optional icons surfaced in ``serverInfo.icons`` on the
            MCP ``initialize`` response (MCP spec 2025-11-25). Hosted
            UIs like Claude.ai's connector panel display these on the
            server card; absent, they fall back to a generic placeholder.
            Prefer absolute HTTPS URLs over data URIs so the asset can
            be updated without bumping the wire payload.
        website_url: Optional public site URL surfaced in
            ``serverInfo.websiteUrl`` (same spec revision). Used by
            client UIs to deep-link from the server card.
    """
    mcp = FastMCP(
        name,
        instructions=instructions,
        auth=auth,
        icons=icons,
        website_url=website_url,
    )

    # Outer-to-inner: FriendlyErrors wraps ToolCallLogger so the JSONL
    # log sees the raw exception type, not the remapped ToolError.
    if auth is None:
        mcp.add_middleware(BearerTokenAuth())
    mcp.add_middleware(FriendlyErrors())
    mcp.add_middleware(ToolCallLogger())

    @mcp.custom_route("/downloads/{path:path}", methods=["GET"])
    async def _downloads_route(request: Request):  # noqa: ANN202
        """Serve HMAC-signed document downloads."""
        return await handle_download(request)

    if auth is None:

        @mcp.custom_route("/oauth/token", methods=["POST"])
        async def _oauth_token(request: Request) -> JSONResponse:
            """OAuth2 client-credentials grant (legacy path).

            Validates ``client_secret`` against ``LAW_TOOLS_CORE_API_KEY``
            and returns it as an access token. Preserved for servers
            that haven't migrated to the new auth stack yet.
            """
            token = _env.get("API_KEY", "")
            if not token:
                return JSONResponse({"error": "server_error"}, status_code=500)

            content_type = request.headers.get("content-type", "")
            if "application/x-www-form-urlencoded" in content_type:
                data = dict(await request.form())
            else:
                data = await request.json()

            if data.get("grant_type") != "client_credentials":
                return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

            if data.get("client_secret") != token:
                return JSONResponse({"error": "invalid_client"}, status_code=401)

            return JSONResponse({"access_token": token, "token_type": "bearer"})

    return mcp
