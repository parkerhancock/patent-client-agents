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
    "get_canada_federal_court_case",
    "get_canlii_case",
    "get_canlii_legislation",
    "get_china_spc_ip_hearing_notice",
    "get_copyright_record",
    "get_dpma_design",
    "get_dpma_patent",
    "get_dpma_trademark",
    "get_euipo_design",
    "get_euipo_trademark",
    "get_inpi_design",
    "get_inpi_trademark",
    "get_ipa_design",
    "get_ipa_patent",
    "get_ipa_trademark",
    "get_ipi_patent",
    "get_ipi_spc",
    "get_ipi_trademark",
    "get_iponz_design",
    "get_iponz_patent",
    "get_iponz_trademark",
    "get_japan_ip_high_court_case",
    "get_kipo_design",
    "get_kipo_patent",
    "get_kipo_trademark",
    "get_oepm_design",
    "get_oepm_patent",
    "get_oepm_trademark",
    "get_office_action",
    "get_patent",
    "get_patent_assignment",
    "get_patent_publication",
    "get_petition",
    "get_prh_patent",
    "get_prv_patent",
    "get_ptab",
    "get_thai_dip_copyright",
    "get_thai_dip_geographical_indication",
    "get_thai_dip_patent",
    "get_thai_dip_trademark",
    "get_tmep_section",
    "get_trademark_last_update",
    "get_trademark_status",
    "get_usitc_investigation",
    "get_wipo_lex_legislation",
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
