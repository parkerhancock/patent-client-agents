"""Consolidated public MCP facade — the curated Directory tool surface.

Servers mount ``facade_mcp`` in place of the full ``ip_mcp`` surface (see
:mod:`patent_client_agents.mcp`). Each domain facade is a thin
dispatcher over existing per-source tool functions; no business logic lives
here, and the §5.9 envelope / §5.15 per-module helpers are untouched.

Domain facades (one module each):

- ``uspto``            — search_uspto, get_uspto, get_file_history (+ standalone
                          search_office_actions, search_patent_assignments)
- ``patents``          — search_patents, get_patent, resolve_patent_number,
                          patent_client_status
- ``epo``              — search_epo, get_epo
- ``trademarks``       — search_trademarks, get_trademark (+ standalone
                          search_trademark_assignments)
- ``litigation``       — search_litigation, get_litigation (+ standalone
                          forum-specific searches / vocab enumerators)
- ``legal_reference``  — search_legal_reference, get_legal_reference (+ standalone
                          upc / wipo_lex pairs)
- ``reference``        — classify_cpc, get_fees, copyright
- ``documents``        — search_bulk_data, download_document
"""

from __future__ import annotations

from fastmcp import FastMCP

from .documents import documents_facade_mcp
from .epo import epo_facade_mcp
from .legal_reference import legal_reference_facade_mcp
from .litigation import litigation_facade_mcp
from .patents import patents_facade_mcp
from .reference import reference_facade_mcp
from .trademarks import trademarks_facade_mcp
from .uspto import uspto_facade_mcp

facade_mcp = FastMCP("patent-client-agents")
facade_mcp.mount(uspto_facade_mcp)
facade_mcp.mount(patents_facade_mcp)
facade_mcp.mount(epo_facade_mcp)
facade_mcp.mount(trademarks_facade_mcp)
facade_mcp.mount(litigation_facade_mcp)
facade_mcp.mount(legal_reference_facade_mcp)
facade_mcp.mount(reference_facade_mcp)
facade_mcp.mount(documents_facade_mcp)

__all__ = ["facade_mcp"]
