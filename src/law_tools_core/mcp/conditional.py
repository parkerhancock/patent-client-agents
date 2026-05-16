"""Env-gated MCP tool registration.

Helpers for registering MCP tools and download fetchers only when the
required environment variables are present. Used to suppress
credentialed connectors (e.g. JPO, TIPO) on deployments that don't carry
the keys, without forking the codebase or building per-deployment
sub-servers.

Both helpers are evaluated at module-import time. Env-var changes after
process startup will NOT retroactively register or unregister tools —
the process must be restarted to pick up env changes. This is by design:
callers that build a ``FastMCP`` instance and serve it should observe a
stable tool surface for the lifetime of the process.

Typical usage::

    from law_tools_core.mcp import conditional_tool, register_source_if_configured

    @conditional_tool(
        my_mcp,
        requires_env=["JPO_API_USERNAME", "JPO_API_PASSWORD"],
        annotations=READ_ONLY,
    )
    async def get_jpo_progress(application_number: str) -> dict:
        ...

    register_source_if_configured(
        "jpo/documents",
        _fetch_jpo_document_bundle,
        "application/zip",
        requires_env=["JPO_API_USERNAME", "JPO_API_PASSWORD"],
    )

TIPO (Taiwan) follows the same pattern with a single ``TIPO_API_KEY``
env var::

    @conditional_tool(
        tipo_opdata_mcp,
        requires_env=["TIPO_API_KEY"],
        annotations=READ_ONLY,
    )
    async def search_tipo_patents(...) -> ListEnvelope[dict]:
        ...

Tool modules live at ``patent_client_agents.mcp.tools.tipo_opdata``.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp import FastMCP

from .downloads import register_source


def _env_satisfied(requires_env: list[str]) -> bool:
    """Return True iff every name in ``requires_env`` is set AND non-empty."""
    return all(os.environ.get(name) for name in requires_env)


def conditional_tool(
    mcp: FastMCP,
    *,
    requires_env: list[str],
    **tool_kwargs: Any,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register an MCP tool only when all required env vars are set.

    The function itself is always defined (so direct Python imports keep
    working for skill/library callers). Only the FastMCP registration is
    gated. Tools that aren't registered don't appear in ``tool/list``,
    so agents never see them.

    Registration happens at module-import time — env-var changes after
    process startup will NOT retroactively register or unregister tools.
    Restart the process to pick up env changes.

    Args:
        mcp: The FastMCP instance to register on (or not).
        requires_env: All of these env vars must be set AND non-empty
            for registration to happen. Empty strings count as unset.
        **tool_kwargs: Forwarded to ``mcp.tool(...)`` when registering.

    Returns:
        A decorator. When env is satisfied, wraps the target function
        with ``mcp.tool(...)`` and returns the wrapped registration.
        When env is not satisfied, returns the function unchanged so
        direct Python callers still work.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if _env_satisfied(requires_env):
            return mcp.tool(**tool_kwargs)(func)
        return func

    return decorator


def register_source_if_configured(
    path_prefix: str,
    fetch: Callable[..., Awaitable[tuple[bytes, str]]],
    mime_type: str = "application/pdf",
    *,
    requires_env: list[str],
) -> None:
    """Register a download source only when all required env vars are set.

    Companion to :func:`conditional_tool`: if a connector's MCP tools
    are env-gated, its download fetcher must be too. Otherwise the
    ``/downloads/{path}`` route would still resolve a previously-minted
    signed URL and fan out to the fetcher (which would then fail
    deeper in the stack with auth errors). This is defense in depth —
    no MCP tool can mint a JPO download URL when JPO tools aren't
    registered, but if one ever leaks (e.g. cached in agent memory
    across a redeployment), the route should refuse cleanly.

    Args:
        path_prefix: Resource path prefix to register against.
        fetch: Async fetcher returning ``(content, filename)``.
        mime_type: MIME type of the fetched content.
        requires_env: All of these env vars must be set AND non-empty
            for the source to register. Empty strings count as unset.
    """
    if _env_satisfied(requires_env):
        register_source(path_prefix, fetch, mime_type)


def conditional_resource(
    mcp: FastMCP,
    uri_template: str,
    *,
    requires_env: list[str],
    **resource_kwargs: Any,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register an MCP resource only when all required env vars are set.

    Companion to :func:`conditional_tool` for the resource side. Same
    rationale: env-gated connectors should not expose their resource
    templates on deployments that lack the required credentials.

    Args:
        mcp: The FastMCP instance to register on (or not).
        uri_template: URI template (e.g. ``"pca://jpo/{ip_type}/..."``).
        requires_env: All of these env vars must be set AND non-empty
            for registration to happen.
        **resource_kwargs: Forwarded to ``mcp.resource(...)`` when
            registering (e.g. ``mime_type``, ``name``, ``description``).
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if _env_satisfied(requires_env):
            return mcp.resource(uri_template, **resource_kwargs)(func)
        return func

    return decorator
