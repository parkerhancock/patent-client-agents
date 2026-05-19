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

from .tools.cafc import cafc_mcp
from .tools.canlii import canlii_mcp
from .tools.copyright import copyright_mcp
from .tools.dpma_statutes import dpma_statutes_mcp
from .tools.epc import epc_mcp
from .tools.epo_case_law import epo_case_law_mcp
from .tools.epo_guidelines import epo_guidelines_mcp
from .tools.epo_pct_guidelines import epo_pct_guidelines_mcp
from .tools.epo_up_guidelines import epo_up_guidelines_mcp
from .tools.euipo import euipo_mcp
from .tools.fees import fees_mcp
from .tools.inpi_pi import inpi_pi_mcp
from .tools.international import international_mcp
from .tools.ip_australia_bulk import ip_australia_bulk_mcp
from .tools.ip_australia_designs import ip_australia_designs_mcp
from .tools.ip_australia_patents import ip_australia_patents_mcp
from .tools.ip_australia_trademarks import ip_australia_trademarks_mcp
from .tools.ipo_in_mppp import ipo_in_mppp_mcp
from .tools.ipo_in_statutes import ipo_in_statutes_mcp
from .tools.kipo_kipris import kipo_kipris_mcp
from .tools.mpep import mpep_mcp
from .tools.office_actions import office_actions_mcp
from .tools.patent_assignments import patent_assignments_mcp
from .tools.patents import patents_mcp
from .tools.publications import publications_mcp
from .tools.tipo_opdata import tipo_opdata_mcp
from .tools.trademarks import trademarks_mcp
from .tools.tw_trade_secrets import tw_trade_secrets_mcp
from .tools.ukipo_mopp import ukipo_mopp_mcp
from .tools.upc import upc_mcp
from .tools.usitc import usitc_mcp
from .tools.uspto import uspto_mcp
from .tools.wipo_lex import wipo_lex_mcp

ip_mcp = FastMCP(
    "patent-client-agents",
    instructions=(
        "Patent and IP data connectors: USPTO (ODP, PPUBS, Assignments, "
        "Office Actions, PTAB, Petitions, Bulk Data, TSDR, TESS trademark "
        "search, Trademark Assignments), EPO OPS, Google Patents, CPC, "
        "MPEP, TMEP, US Copyright Office, Federal Circuit (CAFC) opinions, "
        "USITC (EDIS Section 337 + DataWeb + HTS + IDS), CanLII "
        "(Canadian courts, tribunals, and IP statutes — env-gated on "
        "CANLII_API_KEY), WIPO Lex (global IP statute / treaty / "
        "judgment database), EUIPO (EU Trade Marks + Registered "
        "Community Designs — env-gated on EUIPO_CLIENT_ID / EUIPO_CLIENT_SECRET), "
        "and UPC (Unified Patent Court decisions/orders feed + corpus-backed "
        "UPCA / RoP / Fees statutes). ~73 default read-only tools "
        "(+12 JPO / +9 CanLII / +4 EUIPO when credentials are set), grouped by intent."
    ),
)

ip_mcp.mount(patents_mcp)
ip_mcp.mount(uspto_mcp)
ip_mcp.mount(publications_mcp)
ip_mcp.mount(international_mcp)
ip_mcp.mount(office_actions_mcp)
ip_mcp.mount(patent_assignments_mcp)
ip_mcp.mount(trademarks_mcp)
ip_mcp.mount(mpep_mcp)
ip_mcp.mount(ukipo_mopp_mcp)
ip_mcp.mount(epo_guidelines_mcp)
ip_mcp.mount(epo_pct_guidelines_mcp)
ip_mcp.mount(epo_up_guidelines_mcp)
ip_mcp.mount(epc_mcp)
ip_mcp.mount(epo_case_law_mcp)
ip_mcp.mount(cafc_mcp)
ip_mcp.mount(canlii_mcp)
ip_mcp.mount(copyright_mcp)
ip_mcp.mount(usitc_mcp)
ip_mcp.mount(wipo_lex_mcp)
ip_mcp.mount(euipo_mcp)
ip_mcp.mount(ip_australia_patents_mcp)
ip_mcp.mount(ip_australia_trademarks_mcp)
ip_mcp.mount(ip_australia_designs_mcp)
ip_mcp.mount(ip_australia_bulk_mcp)
ip_mcp.mount(ipo_in_statutes_mcp)
ip_mcp.mount(ipo_in_mppp_mcp)
ip_mcp.mount(inpi_pi_mcp)
ip_mcp.mount(dpma_statutes_mcp)
ip_mcp.mount(tipo_opdata_mcp)
ip_mcp.mount(tw_trade_secrets_mcp)
ip_mcp.mount(kipo_kipris_mcp)
ip_mcp.mount(upc_mcp)
ip_mcp.mount(fees_mcp)

__all__ = ["ip_mcp"]
