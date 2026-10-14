"""Starting the MCP server must not load libraries only some tools need.

markitdown pulls in magika, onnxruntime and numpy; pypdf, curl_cffi and
playwright are only needed by single connectors. Loading them at import
cost the server tens of MB and most of a second on every start.
"""

from __future__ import annotations

import json
import subprocess
import sys

DEFERRED = [
    "markitdown",
    "magika",
    "onnxruntime",
    "numpy",
    "pypdf",
    "curl_cffi",
    "playwright",
    "bs4",
    "markdownify",
]


def test_server_import_does_not_load_deferred_libraries() -> None:
    code = (
        "import json, sys\n"
        "import patent_client_agents.mcp.server\n"
        f"deferred = {DEFERRED!r}\n"
        "print(json.dumps(sorted({m.split('.')[0] for m in sys.modules} & set(deferred))))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, timeout=120
    )
    assert json.loads(out.stdout.strip().splitlines()[-1]) == []
