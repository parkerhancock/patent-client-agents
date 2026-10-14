"""Server middleware for the patent-client-agents MCP server."""

from __future__ import annotations

from fastmcp.server.middleware import Middleware, MiddlewareContext

from patent_client_agents.shared.provenance import track_fetches


class FetchTracking(Middleware):
    """Record each tool call's HTTP responses so provenance can report cache hits."""

    async def on_call_tool(self, context: MiddlewareContext, call_next):  # noqa: ANN001, ANN201
        with track_fetches():
            return await call_next(context)
