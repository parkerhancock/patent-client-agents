"""Unit tests for ``law_tools_core.mcp.server_factory.build_server``.

Focused on the ``serverInfo`` plumbing that surfaces in MCP clients
(spec 2025-11-25): ``icons`` and ``websiteUrl``. Hosted UIs like
Claude.ai's connector card read these from the ``initialize`` response;
without them the card shows a generic placeholder.
"""

from __future__ import annotations

import mcp.types

from law_tools_core.mcp.server_factory import build_server


def test_build_server_without_icons_leaves_serverinfo_empty() -> None:
    mcp = build_server(name="t", instructions="x")
    assert mcp._mcp_server.icons is None
    assert mcp._mcp_server.website_url is None


def test_build_server_forwards_icons_and_website_url() -> None:
    icons = [
        mcp.types.Icon(
            src="https://example.com/icon.svg",
            mimeType="image/svg+xml",
            sizes=["any"],
        ),
        mcp.types.Icon(
            src="https://example.com/icon.png",
            mimeType="image/png",
            sizes=["512x512"],
        ),
    ]
    mcp_server = build_server(
        name="t",
        instructions="x",
        icons=icons,
        website_url="https://example.com/",
    )
    assert mcp_server._mcp_server.icons == icons
    assert mcp_server._mcp_server.website_url == "https://example.com/"
