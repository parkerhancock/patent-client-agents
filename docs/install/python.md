# Use the Python library

Use the base package when your application calls Patent Client Agents directly.
Add the MCP runtime when the same Python environment must also expose tools to
an MCP client.

## Install the base library

Use this when you're writing async Python that calls patent APIs
directly: no MCP, no Claude Code. The bare install pulls no
MCP-runtime dependencies (`fastmcp`, `starlette`), so it stays lean.

### Install

```bash
pip install patent-client-agents
```

Or with `uv`:

```bash
uv add patent-client-agents
```

### Configure source access

See [Configure local source access](local-runtime.md) for credentials, the
optional USPTO trademark-search browser runtime, and local corpus builders.

### Verify

```python
import asyncio
from patent_client_agents.google_patents import GooglePatentsClient

async def main():
    async with GooglePatentsClient() as client:
        patent = await client.get_patent_data("US10123456B2")
        print(patent.title)

asyncio.run(main())
```

Expected output: `Phase change material heat sink using additive manufacturing and method`.

---

## Add the MCP runtime

Use this when you want to run the stdio MCP server from the same venv
as other Python work: e.g. embedding `ip_mcp` in your own composed
FastMCP server, or running `patent-client-agents-mcp` as a subprocess from a
Python script.

### Install

```bash
pip install 'patent-client-agents[mcp]'
```

The `[mcp]` extra pulls `fastmcp>=3.2.3` and `starlette>=1.0.1` on top
of the base dependencies.

### What you get

Two new console scripts on your PATH:

- `patent-client-agents-mcp`: launches the stdio MCP server (136 patent + trademark + adjacent-IP tools by default; up to 234 when every env-gated family is configured)
- `patent-client-agents-skill-install`: symlinks the `ip_research` skill into `~/.claude/skills/` (see [Add the Claude Code library skill](#add-the-claude-code-library-skill))

Plus the Python-importable MCP surface:

```python
from patent_client_agents.mcp import ip_mcp                 # pre-composed FastMCP
from patent_client_agents.mcp.server import mcp as ip_server  # + middleware + routes
```

Mount `ip_mcp` inside your own FastMCP server:

```python
from fastmcp import FastMCP
from patent_client_agents.mcp import ip_mcp

my_server = FastMCP("my-server")
my_server.mount(ip_mcp)  # + your own tools alongside
```

This is exactly how `law-tools` consumes `patent-client-agents` in the monorepo.

---

## Add the Claude Code library skill

The [Claude Code agent plugin](agent-plugins.md) intentionally ships **only the
MCP server**: its tool descriptions carry the routing guidance a skill
would centralize. This section is for a different use case: you
installed `patent-client-agents` as a **Python library** through the base package or MCP runtime
and want the `ip_research` skill's reference docs available in
Claude Code for when you're *writing* Python code that uses the
library.

The skill covers:

- Client class to import-path routing
- Query-syntax cheat sheets (CQL for EPO, PPUBS field codes, Lucene
  for USPTO OA)
- Gotchas (patent number formats, JPO credentials, rate limits)
- Python usage examples

### Install

```bash
pip install 'patent-client-agents[mcp]'   # or without [mcp] if you don't need the MCP runtime
patent-client-agents-skill-install
```

Creates `~/.claude/skills/ip-research` as a symlink into the
pip-installed package. Idempotent: re-runs no-op when already linked.

### Point at a different target

```bash
patent-client-agents-skill-install --target=/path/to/other/skills/dir
```

### Replace an existing directory

```bash
patent-client-agents-skill-install --force
```

Backs up any existing `ip-research` dir to `ip-research.bak` and
replaces with the symlink.

### Plugin vs. standalone skill

|  | [Agent plugin](agent-plugins.md) | Standalone library skill |
|---|---|---|
| What it installs | MCP server only (136 default tools; up to 234 with all env-gated families configured) | Skill markdown for Python library usage |
| Command | `/plugin install patent-client-agents@patent-client-agents` | `patent-client-agents-skill-install` |
| Source | Cloned marketplace repo | pip-installed package (symlinked) |
| Updates | `/plugin marketplace update` + `/reload-plugins` | Reinstall `patent-client-agents` to pick up new skill content |
| Best for | Agents calling MCP tools | Humans writing Python that imports `patent_client_agents` |

The two paths can co-exist on the same machine: the plugin provides
the MCP tools to agents, the standalone skill provides reference docs
to humans working in the codebase.

---
