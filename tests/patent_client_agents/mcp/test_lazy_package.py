"""Import boundaries for the patent MCP package."""

from __future__ import annotations

import subprocess
import sys


def _run(source: str) -> None:
    subprocess.run([sys.executable, "-c", source], check=True)


def test_package_import_does_not_construct_complete_surface() -> None:
    _run(
        "import sys; import patent_client_agents.mcp; "
        "assert 'patent_client_agents.mcp.full' not in sys.modules"
    )


def test_tool_submodule_import_does_not_construct_complete_surface() -> None:
    _run(
        "import sys; import patent_client_agents.mcp.tools.cpc; "
        "assert 'patent_client_agents.mcp.full' not in sys.modules"
    )


def test_public_ip_mcp_import_remains_compatible() -> None:
    from patent_client_agents.mcp import ip_mcp

    assert ip_mcp.name == "patent-client-agents"
