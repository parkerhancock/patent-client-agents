"""Standalone patent-client-agents MCP server entry point.

Run via the ``patent-client-agents-mcp`` console script (installed by the ``[mcp]``
extra of the ``patent-client-agents`` distribution), or directly::

    python -m patent_client_agents.mcp.server
    fastmcp run patent_client_agents.mcp.server:mcp

Stdio is the default transport. Pass ``--transport http`` (or use
``fastmcp run``) for HTTP mode.

Hosted deployment lives at ``https://mcp.patentclient.com``. Auth is
env-driven via ``law_tools_core.mcp.auth.make_auth``: set
``LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_ID`` + ``_SECRET`` to enable
interactive OAuth (public, no email-domain restriction), and
``LAW_TOOLS_CORE_API_KEY`` for static bearer access alongside it. Leave
all three unset for stdio / local use.

Note on naming: the PyPI distribution is ``patent-client-agents``; the import module
stays ``patent_client_agents`` (PyYAML/yaml, scikit-learn/sklearn style decoupling).
"""

from __future__ import annotations

import argparse
import sys

from law_tools_core.mcp import make_auth
from law_tools_core.mcp.server_factory import build_server
from patent_client_agents import __version__

from . import ip_mcp

_HOSTED_BASE_URL = "https://mcp.patentclient.com"

mcp = build_server(
    name="patent-client-agents",
    instructions=(
        "Patent and IP data connectors: USPTO (ODP, PPUBS, Assignments, "
        "Office Actions, PTAB, Petitions, Bulk Data, TSDR, Trademark "
        "Assignments), EPO OPS, Google Patents, CPC, MPEP, and TMEP."
    ),
    auth=make_auth(
        base_url=_HOSTED_BASE_URL,
        issuer_url=_HOSTED_BASE_URL,
        # Public server — any verified Google account is welcome.
        allowed_email_domains=(),
    ),
)
mcp.mount(ip_mcp)


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``patent-client-agents-mcp`` console script.

    No args ⇒ run the MCP server on stdio (the default behavior MCP
    clients expect). ``--version`` and ``--help`` print and exit.
    """
    parser = argparse.ArgumentParser(
        prog="patent-client-agents-mcp",
        description=(
            "Run the patent-client-agents MCP server on stdio. Exposes ~40 patent/IP "
            "tools from USPTO, EPO, Google Patents, and MPEP to any MCP "
            "client. See docs/installation.md for client configuration."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"patent-client-agents {__version__}",
    )
    parser.parse_args(argv)
    try:
        mcp.run()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
