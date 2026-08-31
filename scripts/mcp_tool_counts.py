#!/usr/bin/env python3
"""Compute and validate the patent-client-agents MCP tool counts.

Tool registration is partly environment-gated, so counts have to come
from the mounted FastMCP server at import time rather than from static
decorator scans. This script runs two fresh Python subprocesses:

* default: credential env vars removed
* all-configured: every env-gated family set to a placeholder value

Use ``--check-docs`` in CI to keep README, docs, plugin metadata, and
server help text from drifting.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CREDENTIAL_ENV_VARS = (
    "JPO_API_USERNAME",
    "JPO_API_PASSWORD",
    "CANLII_API_KEY",
    "EUIPO_CLIENT_ID",
    "EUIPO_CLIENT_SECRET",
    "IPAUSTRALIA_CLIENT_ID",
    "IPAUSTRALIA_CLIENT_SECRET",
    "KIPO_KIPRIS_API_KEY",
    "KIPO_KIPRIS_BASE_URL",
    "DPMA_CONNECTPLUS_USERNAME",
    "DPMA_CONNECTPLUS_PASSWORD",
    "IPI_DATA_USERNAME",
    "IPI_DATA_PASSWORD",
    "OEPM_CEO_USERNAME",
    "OEPM_CEO_PASSWORD",
    "IPONZ_SUBSCRIPTION_KEY",
    "DIP_DATA_EXCHANGE_TOKEN",
    "TIPO_API_KEY",
    "INPI_USERNAME",
    "INPI_PASSWORD",
    "USITC_EDIS_TOKEN",
)

COUNT_SNIPPET = """
import asyncio
from patent_client_agents.mcp import ip_mcp
print(len(asyncio.run(ip_mcp.list_tools())))
"""


def _project_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as fh:
        data = tomllib.load(fh)
    return data["project"]["version"]


def _count_tools(*, all_configured: bool) -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    for name in CREDENTIAL_ENV_VARS:
        if all_configured:
            env[name] = (
                "https://kipris.example.test/openapi/service"
                if name == "KIPO_KIPRIS_BASE_URL"
                else "test"
            )
        else:
            env.pop(name, None)

    result = subprocess.run(
        [sys.executable, "-W", "ignore", "-c", COUNT_SNIPPET],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    for line in reversed(result.stdout.splitlines()):
        line = line.strip()
        if line.isdigit():
            return int(line)
    raise RuntimeError(f"Could not parse tool count from subprocess output: {result.stdout!r}")


def _require(path: str, *needles: str) -> list[str]:
    text = (ROOT / path).read_text()
    normalized = " ".join(text.replace('"', "").replace("'", "").split())
    return [
        f"{path}: missing {needle!r}"
        for needle in needles
        if " ".join(needle.replace('"', "").replace("'", "").split()) not in normalized
    ]


def check_docs(default_count: int, full_count: int) -> list[str]:
    version = _project_version()
    return [
        *_require(
            "README.md",
            f"{default_count} patent + IP MCP tools are exposed by default",
            f"up to {full_count} tools",
        ),
        *_require(
            "docs/installation.md",
            f"Add {default_count} patent + trademark + adjacent-IP MCP tools",
            f"up to {full_count} tools",
            f"Expect **{default_count} tools** by default",
            f"patent-client-agents[mcp]=={version}",
        ),
        *_require(
            "docs/index.md",
            f"{default_count} tools by default",
            f"up to {full_count} when every gated family is configured",
        ),
        *_require(
            "docs/mcp-stdio.md",
            f"{default_count} patent + IP MCP tools are exposed by default",
            f"up to {full_count} tools",
            f"Expect {default_count} tools by default",
        ),
        *_require(
            ".claude-plugin/marketplace.json",
            f"{default_count} default MCP tools",
        ),
        *_require(
            "plugins/patent-client-agents/.claude-plugin/plugin.json",
            f"{default_count} default MCP tools",
        ),
        *_require(
            "plugins/patent-client-agents/.codex-plugin/plugin.json",
            f"{default_count} default MCP tools",
        ),
        *_require(
            "plugins/patent-client-agents/.mcp.json",
            f"patent-client-agents[mcp]=={version}",
        ),
        *_require(
            "plugins/patent-client-agents/plugin.json",
            f"{default_count} default MCP tools",
        ),
        *_require(
            "plugins/patent-client-agents/mcp_config.json",
            f"patent-client-agents[mcp]=={version}",
        ),
        *_require(
            "src/patent_client_agents/mcp/__init__.py",
            f"{default_count} default read-only tools",
            f"{full_count} tools",
        ),
        *_require(
            "src/patent_client_agents/mcp/server.py",
            f"Exposes {default_count} default patent/IP tools",
            f"up to {full_count} tools",
        ),
    ]


def _site_facts(default_count: int, full_count: int) -> dict[str, object]:
    coverage = json.loads((ROOT / "coverage" / "coverage.json").read_text())
    atlas = json.loads((ROOT / "coverage" / "atlas.json").read_text())
    profiles = json.loads((ROOT / "coverage" / "profiles-snapshot" / "index.json").read_text())
    coverage_summary = coverage["summary"]
    atlas_summary = atlas["summary"]
    catalog_records = len(list((ROOT / "catalog" / "sources").glob("**/*.md")))

    return {
        "schema_version": 1,
        "release_version": _project_version(),
        "mcp_tools": {
            "default": default_count,
            "all_configured": full_count,
            "environment_gated": full_count - default_count,
        },
        "catalog": {
            "canonical_records": catalog_records,
            "projected_products": coverage_summary["total"],
            "active_products": coverage_summary["by_status"]["active"],
            "beta_products": coverage_summary["by_status"]["beta"],
            "external_products": coverage_summary["by_status"]["external"],
            "rights": len(coverage_summary["rights_covered"]),
            "data_types": len(coverage_summary["data_types_covered"]),
        },
        "atlas": {
            "entities": atlas_summary["total_entities"],
            "shipped_entities": atlas_summary["by_connector_status"]["shipped"],
            "researched_synopses": atlas_summary["synopses_filled"],
        },
        "profiles": {
            "jurisdictions": profiles["total_profiles"],
        },
    }


def _site_facts_text(default_count: int, full_count: int) -> str:
    return json.dumps(_site_facts(default_count, full_count), indent=2, sort_keys=True) + "\n"


def _check_site_facts(default_count: int, full_count: int) -> list[str]:
    path = ROOT / "coverage" / "site-facts.json"
    expected = _site_facts_text(default_count, full_count)
    if not path.exists():
        return ["coverage/site-facts.json: missing; run with --write-site-facts"]
    if path.read_text() != expected:
        return ["coverage/site-facts.json: stale; run with --write-site-facts"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-docs", action="store_true", help="Fail if docs are stale.")
    parser.add_argument(
        "--write-site-facts",
        action="store_true",
        help="Write coverage/site-facts.json for patentclient.com.",
    )
    args = parser.parse_args()

    default_count = _count_tools(all_configured=False)
    full_count = _count_tools(all_configured=True)
    print(f"default={default_count}")
    print(f"all_configured={full_count}")
    print(f"env_gated={full_count - default_count}")

    if args.write_site_facts:
        path = ROOT / "coverage" / "site-facts.json"
        path.write_text(_site_facts_text(default_count, full_count))
        print(f"wrote={path.relative_to(ROOT)}")

    if args.check_docs:
        errors = [
            *check_docs(default_count, full_count),
            *_check_site_facts(default_count, full_count),
        ]
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
