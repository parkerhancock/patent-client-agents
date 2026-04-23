"""Patent & IP MCP tool surface.

``ip_mcp`` is a :class:`fastmcp.FastMCP` composed from per-domain
sub-servers. Downstream consumers either:

* Mount ``ip_mcp`` inside their own server (e.g. law-tools does
  ``mcp.mount(ip_mcp)`` to expose the patent tools alongside its own
  non-patent tools), or
* Run the standalone patent-client-agents MCP server via ``patent-client-agents-mcp`` (defined
  in :mod:`patent_client_agents.mcp.server`).

Importing this module triggers each tool file's ``register_source()``
call for download fetchers, so the shared ``/downloads/{path}`` route
is populated whenever the patent tools are mounted.
"""

from __future__ import annotations

from fastmcp import FastMCP

from .tools.international import international_mcp
from .tools.mpep import mpep_mcp
from .tools.office_actions import office_actions_mcp
from .tools.patent_assignments import patent_assignments_mcp
from .tools.patents import patents_mcp
from .tools.publications import publications_mcp
from .tools.uspto import uspto_mcp

ip_mcp = FastMCP(
    "patent-client-agents",
    instructions=(
        "Patent and IP data connectors: USPTO (ODP, PPUBS, Assignments, "
        "Office Actions, PTAB, Petitions, Bulk Data), EPO OPS, Google "
        "Patents, CPC, and the MPEP. ~100 read-only tools."
    ),
)

ip_mcp.mount(patents_mcp)
ip_mcp.mount(uspto_mcp)
ip_mcp.mount(publications_mcp)
ip_mcp.mount(international_mcp)
ip_mcp.mount(office_actions_mcp)
ip_mcp.mount(patent_assignments_mcp)
ip_mcp.mount(mpep_mcp)

__all__ = ["ip_mcp"]
