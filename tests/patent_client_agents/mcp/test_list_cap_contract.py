"""Every list-accepting get_* tool enforces the shared 50-ID cap before any request.

See ``patent_client_agents.shared.fanout``. Tools still on their own fan-out
are listed in ``PENDING``; migrate them to ``as_id_list``/``fetch_many`` and
remove them. The list must only shrink: the test fails if a tool outside it
breaks the rule, or if a tool in it already follows the rule.

The check runs in a fresh interpreter with every connector's credentials set,
because env-gated tools register only if their credentials exist at import.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PENDING: set[str] = {
    "get_canlii_case",
    "get_canlii_legislation",
    "get_dpma_design",
    "get_dpma_patent",
    "get_dpma_section",
    "get_dpma_trademark",
    "get_epc_section",
    "get_epo_biblio",
    "get_epo_case_law_section",
    "get_epo_citations",
    "get_epo_equivalents",
    "get_epo_family",
    "get_epo_fulltext",
    "get_epo_guidelines_section",
    "get_epo_legal_events",
    "get_epo_pct_guidelines_section",
    "get_epo_procedural_steps",
    "get_epo_register_biblio",
    "get_epo_register_events",
    "get_epo_up_guidelines_section",
    "get_euipo_design",
    "get_euipo_trademark",
    "get_ilpo_section",
    "get_inpi_br_section",
    "get_inpi_design",
    "get_inpi_trademark",
    "get_ipa_design",
    "get_ipa_patent",
    "get_ipa_trademark",
    "get_ipi_patent",
    "get_ipi_spc",
    "get_ipi_trademark",
    "get_ipo_in_mppp_section",
    "get_ipo_in_section",
    "get_iponz_design",
    "get_iponz_patent",
    "get_iponz_trademark",
    "get_ipos_manual_section",
    "get_ipos_section",
    "get_jpo_progress",
    "get_jpo_progress_simple",
    "get_jpo_registration_info",
    "get_kipo_design",
    "get_kipo_patent",
    "get_kipo_trademark",
    "get_legifrance_section",
    "get_mopp_section",
    "get_mpep_section",
    "get_oepm_design",
    "get_oepm_patent",
    "get_oepm_trademark",
    "get_thai_dip_copyright",
    "get_thai_dip_geographical_indication",
    "get_thai_dip_patent",
    "get_thai_dip_trademark",
    "get_tipo_patent",
    "get_tipo_patent_annuity",
    "get_tipo_patent_events",
    "get_tipo_patent_priority",
    "get_tipo_patent_publication",
    "get_tipo_patent_rights",
    "get_tipo_patent_twins",
    "get_tipo_trademark",
    "get_tipo_trademark_events",
    "get_tipo_trademark_image_urls",
    "get_tipo_trademark_priority",
    "get_tipo_trademark_rights",
    "get_tw_trade_secrets_section",
    "get_upc_decision",
    "get_upc_section",
}

_CHECK = """
import asyncio, json, os, sys
sys.path.insert(0, {scripts!r})
from validate_mcp_contracts import CONTRACT_ENV
os.environ.update(CONTRACT_ENV)
import httpx
from mcp_data_core.exceptions import ValidationError
from patent_client_agents.shared.fanout import LIST_CAP
import patent_client_agents.mcp.full as full

EXTRA = {{
    "get_canlii_case": {{"database_id": "fct"}},
    "get_canlii_legislation": {{"database_id": "cas"}},
    "get_ptab": {{"type": "trial"}},
}}

async def no_network(*args, **kwargs):
    raise AssertionError("request before validation")

httpx.AsyncClient.send = no_network

async def main():
    offenders = set()
    for name, server in vars(full).items():
        if not name.endswith("_mcp") or name == "ip_mcp":
            continue
        for tool in await server.list_tools():
            if not tool.name.startswith("get_"):
                continue
            for param, schema in tool.parameters.get("properties", {{}}).items():
                types = {{o.get("type") for o in schema.get("anyOf", [])}}
                if not {{"string", "array"}} <= types:
                    continue
                ids = [f"{{i:08d}}" for i in range(LIST_CAP + 1)]
                try:
                    await tool.fn(**{{param: ids}}, **EXTRA.get(tool.name, {{}}))
                except ValidationError as exc:
                    if f"limit {{LIST_CAP}}" in str(exc):
                        continue
                except BaseException:
                    pass
                offenders.add(tool.name)
    print(json.dumps(sorted(offenders)))

asyncio.run(main())
"""


def test_list_tools_reject_over_cap_lists_before_any_request() -> None:
    scripts = str(Path(__file__).resolve().parents[3] / "scripts")
    out = subprocess.run(
        [sys.executable, "-c", _CHECK.format(scripts=scripts)],
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )
    offenders = set(json.loads(out.stdout.strip().splitlines()[-1]))
    assert offenders - PENDING == set(), "these tools must use shared.fanout.as_id_list"
    assert PENDING - offenders == set(), "these tools now comply; remove them from PENDING"
