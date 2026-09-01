"""Patent & IP MCP package.

The complete ``ip_mcp`` surface is expensive to construct because it imports
every connector module. Keep ordinary package and tool-submodule imports light,
while preserving ``from patent_client_agents.mcp import ip_mcp`` through a lazy
module attribute.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .full import ip_mcp


def __getattr__(name: str) -> Any:
    if name == "ip_mcp":
        from .full import ip_mcp

        globals()[name] = ip_mcp
        return ip_mcp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["ip_mcp"]
