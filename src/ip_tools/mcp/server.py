"""Standalone ip-tools MCP server entry point.

Run via the ``ip-tools-mcp`` console script (installed by the
``[mcp]`` extra), or directly::

    python -m ip_tools.mcp.server
    fastmcp run ip_tools.mcp.server:mcp

Stdio is the default transport. Pass ``--transport http`` (or use
``fastmcp run``) for HTTP mode.
"""

from __future__ import annotations

import argparse
import sys

from ip_tools import __version__
from law_tools_core.mcp.server_factory import build_server

from . import ip_mcp

mcp = build_server(
    name="ip-tools",
    instructions=(
        "Patent and IP data connectors: USPTO (ODP, PPUBS, Assignments, "
        "Office Actions, PTAB, Petitions, Bulk Data), EPO OPS, Google "
        "Patents, CPC, and the MPEP."
    ),
)
mcp.mount(ip_mcp)


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``ip-tools-mcp`` console script.

    No args ⇒ run the MCP server on stdio (the default behavior MCP
    clients expect). ``--version`` and ``--help`` print and exit.
    """
    parser = argparse.ArgumentParser(
        prog="ip-tools-mcp",
        description=(
            "Run the ip-tools MCP server on stdio. Exposes 63 patent/IP "
            "tools from USPTO, EPO, Google Patents, and MPEP to any MCP "
            "client. See docs/installation.md for client configuration."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ip-tools {__version__}",
    )
    parser.parse_args(argv)
    try:
        mcp.run()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
