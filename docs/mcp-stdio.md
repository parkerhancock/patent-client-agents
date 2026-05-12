# Running `patent-client-agents` as a stdio MCP server

The `[mcp]` extra ships a ready-to-run stdio MCP server that exposes
all patent and IP tools to any MCP-speaking client — Claude Code,
Claude Desktop, Cursor, Cline, CoWork, or a homegrown fastmcp Client.

## Install

```bash
pip install 'patent-client-agents[mcp]'
```

This installs the runtime (`fastmcp`, `starlette`) and adds the
`patent-client-agents-mcp` console script.

## Run

```bash
patent-client-agents-mcp                  # default: stdio transport, no auth
```

`patent-client-agents-mcp` is a thin wrapper around `patent_client_agents.mcp.server:mcp` that
runs via fastmcp. You can also invoke it directly:

```bash
python -m patent_client_agents.mcp.server
fastmcp run patent_client_agents.mcp.server:mcp
```

## Claude Code configuration

Add one of the following blocks to your MCP config (`.mcp.json` at the
project root or `~/.claude.json` for user-scope):

```json
{
  "mcpServers": {
    "patent-client-agents": {
      "command": "patent-client-agents-mcp"
    }
  }
}
```

If you prefer to invoke a specific venv or Python interpreter:

```json
{
  "mcpServers": {
    "patent-client-agents": {
      "command": "/path/to/.venv/bin/patent-client-agents-mcp",
      "env": {
        "USPTO_ODP_API_KEY": "…",
        "EPO_OPS_API_KEY": "…",
        "EPO_OPS_API_SECRET": "…"
      }
    }
  }
}
```

The server starts with no authentication in stdio mode. Any env vars
set in the `env` block are available to the connectors — USPTO ODP,
EPO OPS, and JPO all consume credentials from env (see each connector's
`CATALOG.md` entry).

## Tools exposed

The server mounts `ip_mcp`, which composes 8 sub-servers:

| Sub-server | Tools | Prefixes on signed-URL downloads |
|---|---:|---|
| `Patents` (Google Patents) | 7 | `patents/` |
| `USPTO` (ODP — applications, PTAB, petitions, bulk) | 18 | `uspto/applications/`, `ptab/documents/` |
| `Publications` (PPUBS) | 3 | `publications/` |
| `International` (EPO OPS, CPC; + 12 JPO when `JPO_API_USERNAME` and `JPO_API_PASSWORD` are set) | 10 / 22 | `epo/patents/`, `jpo/documents/` |
| `OfficeActions` (USPTO OA rejections/citations/text) | 1 | — |
| `PatentAssignments` (USPTO Assignment Center) | 1 | — |
| `Trademarks` (TSDR — needs `USPTO_TSDR_API_KEY`; TMEP; Trademark Assignments) | 7 | — |
| `MPEP` | 2 | — |
| **Total** | **49 / 61** | |

Downloadable artifacts mint HMAC-signed URLs when
`LAW_TOOLS_CORE_PUBLIC_URL` is set (remote HTTP deployment). In stdio
mode the tools write the bytes to a tempfile and return `file_path`.

## Verifying

A one-off smoke test against the running server:

```python
import asyncio
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

async def main():
    async with Client(StdioTransport(command="patent-client-agents-mcp", args=[])) as c:
        tools = await c.list_tools()
        print(len(tools), "tools")
        result = await c.call_tool("get_mpep_section", {"section": "2106"})
        print(result.data.get("title") if result.data else None)

asyncio.run(main())
```

Expect 49 tools (61 with `JPO_API_USERNAME`/`JPO_API_PASSWORD` set) and
the title `2106 … Patent Subject Matter Eligibility`.

## Not installed?

If `patent-client-agents-mcp` is on PATH but startup fails with
`ModuleNotFoundError: No module named 'fastmcp'`, you installed
`patent-client-agents` without the `[mcp]` extra. Re-install with
`pip install 'patent-client-agents[mcp]'`.
