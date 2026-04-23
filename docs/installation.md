# Installing `patent-client-agents`

`patent-client-agents` covers seven install modes. Pick the one that
matches how you're going to use it:

| Mode | You want to... | Section |
|---|---|---|
| Python library | Import `patent_client_agents` in your own async code | [§1](#1-python-library) |
| Python library + MCP runtime | Run an MCP server locally or in-process | [§2](#2-python-library-with-mcp-runtime) |
| Claude Code plugin (from GitHub marketplace) | Add 63 patent MCP tools to Claude Code with two slash commands | [§3](#3-claude-code-plugin-from-github) |
| Claude Code skill (standalone, library-user) | Install the `ip_research` skill into `~/.claude/skills/` for Python-library guidance | [§4](#4-claude-code-skill-standalone-library-user) |
| Stdio MCP (any MCP client) | Connect Claude Desktop / Cursor / Cline / CoWork-local / custom client | [§5](#5-stdio-mcp-from-any-mcp-client) |
| Remote MCP (hosted or self-hosted) | Point an MCP client at a deployed HTTPS endpoint | [§6](#6-remote-mcp) |

Skip to the section you need — they're independent.

**The Claude Code plugin** (§3) ships the MCP server only. The
`ip_research` skill is a separate artifact aimed at Python-library
users (§4); the plugin installs MCP tools whose in-schema descriptions
already cover the routing/usage guidance a skill would otherwise
centralize.

---

## 1. Python library

Use this when you're writing async Python that calls patent APIs
directly — no MCP, no Claude Code. The bare install pulls no
MCP-runtime dependencies (`fastmcp`, `starlette`), so it stays lean.

### Install

```bash
pip install patent-client-agents
```

Or with `uv`:

```bash
uv add patent-client-agents
```

### API keys

Set via environment variables. Most connectors work without keys but
these unlock the full surface:

| Variable | Source | How to get |
|---|---|---|
| `USPTO_ODP_API_KEY` | USPTO Open Data Portal | [developer.uspto.gov](https://developer.uspto.gov/) (free) |
| `EPO_OPS_API_KEY`, `EPO_OPS_API_SECRET` | EPO Open Patent Services | [developers.epo.org](https://developers.epo.org/) (free, 4 GB/week) |
| `JPO_API_USERNAME`, `JPO_API_PASSWORD` | JPO J-PlatPat | Contact JPO (restricted) |

Google Patents, USPTO Publications, USPTO Assignments, and MPEP need
no credentials.

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

## 2. Python library with MCP runtime

Use this when you want to run the stdio MCP server from the same venv
as other Python work — e.g. embedding `ip_mcp` in your own composed
FastMCP server, or running `patent-client-agents-mcp` as a subprocess from a
Python script.

### Install

```bash
pip install 'patent-client-agents[mcp]'
```

The `[mcp]` extra pulls `fastmcp>=3.2.3` and `starlette>=0.37` on top
of the base dependencies.

### What you get

Two new console scripts on your PATH:

- `patent-client-agents-mcp` — launches the stdio MCP server (63 patent tools)
- `patent-client-agents-skill-install` — symlinks the `ip_research` skill into `~/.claude/skills/` (see §4)

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

## 3. Claude Code plugin (from GitHub)

Use this when you use Claude Code and want the 63 patent MCP tools
dropped in with two slash commands.

The plugin ships **only the MCP server** — no skill, no agents, no
hooks. The MCP tools' in-schema descriptions already carry the
cross-tool routing guidance a skill would otherwise centralize (e.g.
`search_google_patents` tells the agent "PREFER search_patent_publications
for US patents"; `get_epo_cql_help` is itself a tool).

### Prereq

`uv` needs to be on `PATH`. The plugin's MCP server spawns via `uvx`,
which handles the Python runtime (`fastmcp` and friends) in a managed
environment so you don't have to `pip install` anything.

```bash
# install uv if you don't have it — one-liner from astral.sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install

Claude Code's plugin install goes through a **marketplace** — a small
catalog manifest that lists one or more plugins. This repo ships its
own single-plugin marketplace at `.claude-plugin/marketplace.json`,
with the plugin itself living in a subdirectory
(`plugins/patent-client-agents/`) that the schema requires.

Run these **inside a Claude Code session** (slash commands, not shell):

```
/plugin marketplace add parkerhancock/ip_tools
/plugin install patent-client-agents@patent-client-agents
/reload-plugins
```

What happens:

1. `/plugin marketplace add parkerhancock/ip_tools` clones this repo
   into `~/.claude/plugins/marketplaces/`, parses
   `.claude-plugin/marketplace.json`, and registers the marketplace
   under the name it declares (`patent-client-agents`).
2. `/plugin install patent-client-agents@patent-client-agents`
   resolves the `patent-client-agents` plugin from that marketplace
   (the redundant `@patent-client-agents` suffix is the marketplace
   name, not the plugin name), links it into `~/.claude/plugins/`,
   and registers the MCP server declared in
   `plugins/patent-client-agents/.claude-plugin/plugin.json`.
3. `/reload-plugins` tells Claude Code to pick up the newly-registered
   plugin in the current session.
4. On first MCP use, `uvx` fetches `patent-client-agents[mcp]` from
   **PyPI** (not from the cloned repo — the plugin manifest uses
   `uvx --from patent-client-agents[mcp] patent-client-agents-mcp`)
   into a managed environment and launches the server. The first run
   takes ~30 seconds while ~100 packages download; subsequent runs
   are fast because uv caches the resolved environment.

Expected output after install + reload:

```
Reloaded: 1 plugin · 0 skills · … agents · 0 hooks · 1 plugin MCP server · 0 plugin LSP servers
```

`0 skills` is the intended state — see the note at the top of this doc.

### Update

When a new plugin version lands on GitHub:

```
/plugin marketplace update patent-client-agents
/reload-plugins
```

The first command pulls the latest marketplace commit (which includes
any plugin-manifest changes). `/reload-plugins` then re-reads the
registered plugin's manifest. If the PyPI version referenced by
`uvx --from patent-client-agents[mcp]` changed, the next MCP call
rebuilds the uv-managed env.

If you need to force a clean reinstall:

```
/plugin uninstall patent-client-agents@patent-client-agents
/plugin install patent-client-agents@patent-client-agents
/reload-plugins
```

### Remove

```
/plugin uninstall patent-client-agents@patent-client-agents
/plugin marketplace remove patent-client-agents
```

### Configure API keys

API keys are read from environment. For a global Claude Code install,
export them in your shell profile:

```bash
export USPTO_ODP_API_KEY="…"
export EPO_OPS_API_KEY="…"
export EPO_OPS_API_SECRET="…"
```

Restart Claude Code so the new env reaches the MCP subprocess. Without
keys, Google Patents / PPUBS / MPEP / Assignments still work; USPTO
ODP and EPO tools will return auth errors.

### Verify

List MCP tools from within a Claude Code session:

```
/mcp
```

Expect `patent-client-agents` with 63 tools. Or call one directly by
asking something patent-research-ish:

> "What's in MPEP section 2106?"

Claude invokes `get_mpep_section` via the MCP server and returns the
text of MPEP 2106 — Patent Subject Matter Eligibility.

### Troubleshooting

**`uvx: command not found`** — install uv (see prereq).

**`/mcp` shows the server as "failed to start"** — open the logs pane
and look for stderr output. Common causes: offline during first
install (`uvx` can't reach PyPI), or an ancient macOS Python build
error (upgrade `uv` to latest).

**Cold start takes too long** — subsequent runs are ~1s. If every
session takes 30s, something is evicting uv's cache. Check that
`~/.cache/uv/` is persistent.

**Plugin shows 0 tools after install** — `/reload-plugins` didn't
pick it up. Fully exit Claude Code and restart the session.

---

## 4. Claude Code skill (standalone, library-user)

The Claude Code plugin (§3) intentionally ships **only the MCP
server** — its tool descriptions carry the routing guidance a skill
would centralize. This section is for a different use case: you
installed `patent-client-agents` as a **Python library** (§1 or §2)
and want the `ip_research` skill's reference docs available in
Claude Code for when you're *writing* Python code that uses the
library.

The skill covers:

- Client class → import path routing
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
pip-installed package. Idempotent — re-runs no-op when already linked.

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

|  | Plugin (§3) | Standalone skill (§4) |
|---|---|---|
| What it installs | MCP server only (63 tools) | Skill markdown for Python library usage |
| Command | `/plugin install patent-client-agents@patent-client-agents` | `patent-client-agents-skill-install` |
| Source | Cloned marketplace repo | pip-installed package (symlinked) |
| Updates | `/plugin marketplace update` + `/reload-plugins` | Reinstall `patent-client-agents` to pick up new skill content |
| Best for | Agents calling MCP tools | Humans writing Python that imports `patent_client_agents` |

The two paths can co-exist on the same machine — the plugin provides
the MCP tools to agents, the standalone skill provides reference docs
to humans working in the codebase.

---

## 5. Stdio MCP from any MCP client

Use this when you want every patent tool available as MCP tools to
your client (Claude Desktop, Cursor, Cline, CoWork-local, or a custom
fastmcp client). The server is a short-lived subprocess speaking
JSON-RPC over stdio.

### Install

```bash
pip install 'patent-client-agents[mcp]'
```

This gives you the `patent-client-agents-mcp` console script on PATH.

### Wire the MCP client

#### Claude Code

Add to `.mcp.json` at your project root (or `~/.claude.json` for
user-scope):

```json
{
  "mcpServers": {
    "patent-client-agents": {
      "command": "patent-client-agents-mcp"
    }
  }
}
```

Or add from the CLI:

```bash
claude mcp add patent-client-agents patent-client-agents-mcp
```

If you're using a venv, point at the absolute path so Claude Code
launches the right interpreter:

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

#### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "patent-client-agents": {
      "command": "patent-client-agents-mcp",
      "env": {
        "USPTO_ODP_API_KEY": "…"
      }
    }
  }
}
```

#### Cursor, Cline, and other stdio MCP clients

Same pattern — `command: "patent-client-agents-mcp"` plus any env vars. Consult
the client's own MCP config docs for the file location.

### Verify

```python
import asyncio
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

async def main():
    async with Client(StdioTransport(command="patent-client-agents-mcp", args=[])) as c:
        tools = await c.list_tools()
        print(f"{len(tools)} tools")
        result = await c.call_tool("get_mpep_section", {"section": "2106"})
        print(result.data.get("title"))

asyncio.run(main())
```

Expect **63 tools** and title starting `2106 ... Patent Subject Matter
Eligibility`.

### Troubleshooting

**`patent-client-agents-mcp: command not found`** — `[mcp]` extra wasn't
installed. Rerun `pip install 'patent-client-agents[mcp]'`.

**`ModuleNotFoundError: No module named 'fastmcp'` at startup** — same
root cause. Something is launching a Python that doesn't have fastmcp.

**Zero tools listed** — the MCP client is likely talking to the wrong
server. Check the JSON config points at the right binary.

---

## 6. Remote MCP

Use this when an MCP client (Claude Code, Claude Desktop, Cowork, Cursor,
custom agent) should point at a deployed HTTPS endpoint instead of spawning
a local subprocess.

The server side lives in a separate repo:
[**parkerhancock/patent-client-agents-deploy**](https://github.com/parkerhancock/patent-client-agents-deploy).
It packages this library with a FastAPI wrapper that adds Google-login
bearer tokens and Firestore-backed rate limits, and ships Terraform + Cloud
Build for a one-command GCP Cloud Run deployment. A public demo instance is
hosted at `https://patent-mcp-demo.example.com` (update this URL when the
demo lands).

### Using the hosted demo

1. Visit the demo URL, sign in with Google, and mint a bearer token at
   `/tokens`.
2. Add to `.mcp.json` / Claude Desktop config / Cowork connector:

   ```json
   {
     "mcpServers": {
       "patent-client-agents": {
         "url": "https://patent-mcp-demo.example.com/mcp/",
         "headers": { "Authorization": "Bearer <your token>" }
       }
     }
   }
   ```

3. Smoke-test:

   ```bash
   curl -s -X POST https://patent-mcp-demo.example.com/mcp/ \
     -H "Authorization: Bearer <your token>" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json, text/event-stream" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize",
          "params":{"protocolVersion":"2025-06-18","capabilities":{},
                    "clientInfo":{"name":"curl","version":"0"}}}'
   ```

   Expect `"serverInfo":{"name":"patent-client-agents",...}`.

### Running your own

If you need higher rate limits, private data sources, or control over
auth/domain allowlists, run your own deployment. See the
[deploy repo README](https://github.com/parkerhancock/patent-client-agents-deploy)
and `deploy/DEPLOYMENT.md` there — the short version:

```bash
git clone https://github.com/parkerhancock/patent-client-agents-deploy
cd patent-client-agents-deploy/deploy/terraform
cp terraform.tfvars.example terraform.tfvars   # edit project_id + public_url
terraform init && terraform apply
# populate secrets, then:
gcloud builds submit --config=cloudbuild.yaml
```

---

## Deciding which path

```
  Are you writing Python that uses the library directly?
  ├── yes → §1 (bare) or §2 (with MCP runtime)
  └── no ↓

  Are you a Claude Code user?
  ├── yes → §3 (plugin install from GitHub)
  │         plus §5 if you also want the tools as MCP locally
  └── no ↓

  Are you on Claude Desktop / Cursor / Cline / other MCP client?
  ├── local subprocess → §5 (stdio MCP)
  └── pointing at a deployed server → §6 (remote MCP)
```

## Getting help

- Issues: [github.com/parkerhancock/ip_tools/issues](https://github.com/parkerhancock/ip_tools/issues)
- Full source: [github.com/parkerhancock/ip_tools](https://github.com/parkerhancock/ip_tools)
- Remote MCP deployment: [github.com/parkerhancock/patent-client-agents-deploy](https://github.com/parkerhancock/patent-client-agents-deploy)
- Per-connector API notes: `src/patent_client_agents/catalog/*.md`
