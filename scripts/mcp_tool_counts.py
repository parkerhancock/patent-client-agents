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
    "TIPO_API_KEY",
    "INPI_USERNAME",
    "INPI_PASSWORD",
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
            env[name] = "test"
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-docs", action="store_true", help="Fail if docs are stale.")
    args = parser.parse_args()

    default_count = _count_tools(all_configured=False)
    full_count = _count_tools(all_configured=True)
    print(f"default={default_count}")
    print(f"all_configured={full_count}")
    print(f"env_gated={full_count - default_count}")

    if args.check_docs:
        errors = check_docs(default_count, full_count)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
