# Installing `patent-client-agents`

`patent-client-agents` covers seven install modes. Pick the one that
matches how you're going to use it:

| Mode | You want to... | Section |
|---|---|---|
| Python library | Import `patent_client_agents` in your own async code | [§1](#1-python-library) |
| Python library + MCP runtime | Run an MCP server locally or in-process | [§2](#2-python-library-with-mcp-runtime) |
| Claude Code plugin (from GitHub marketplace) | Add 86 patent + trademark + adjacent-IP MCP tools to Claude Code with two slash commands (plus +12 JPO / +9 CanLII / +4 EUIPO when those credentials are set) | [§3](#3-claude-code-plugin-from-github) |
| Claude Code skill (standalone, library-user) | Install the `ip_research` skill into `~/.claude/skills/` for Python-library guidance | [§4](#4-claude-code-skill-standalone-library-user) |
| Stdio MCP (any MCP client) | Connect Claude Code / Claude Desktop / Codex CLI / Gemini CLI / Cursor / Windsurf / Cline / Zed / Continue / Copilot Chat / JetBrains / custom | [§5](#5-stdio-mcp-from-any-mcp-client) |
| Remote MCP (hosted or self-hosted) | Point an MCP client at a deployed HTTPS endpoint — including cloud-only clients like ChatGPT Apps and Replit Agent | [§6](#6-remote-mcp) |

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
| `USPTO_TSDR_API_KEY` | USPTO Trademark Status & Document Retrieval | [account.uspto.gov/api-manager/](https://account.uspto.gov/api-manager/) (free MyUSPTO account; pick the TSDR API product) |
| `EPO_OPS_API_KEY`, `EPO_OPS_API_SECRET` | EPO Open Patent Services | [developers.epo.org](https://developers.epo.org/) (free, 4 GB/week) |
| `JPO_API_USERNAME`, `JPO_API_PASSWORD` | JPO J-PlatPat | Contact JPO (restricted). **Python library only — JPO MCP tools are not available.** |
| `CANLII_API_KEY` | CanLII | [canlii.org/en/feedback/feedback.html](https://www.canlii.org/en/feedback/feedback.html) (free, by request) |
| `EUIPO_CLIENT_ID`, `EUIPO_CLIENT_SECRET` | EUIPO Trademark + Design Search | [dev.euipo.europa.eu](https://dev.euipo.europa.eu/) (sandbox auto-approves; production requires ID-document review). Set `EUIPO_ENV=sandbox` to point at the sandbox. |
| `USITC_EDIS_TOKEN` | USITC EDIS (Section 337) | [edis.usitc.gov](https://edis.usitc.gov) → API Token Generator (free Login.gov account). JWT, ~2 wk lifetime. Required for attachment downloads even on public documents. |
| `USITC_DATAWEB_TOKEN` | USITC DataWeb (US trade statistics) | [dataweb.usitc.gov](https://dataweb.usitc.gov) account page (free). Needed only for `run_dataweb_report`. |
| `PCA_WAF_TOKEN_PATH` *or* `PCA_WAF_TOKEN_JSON` | USPTO Trademark Search (TESS) | Bring-your-own AWS WAF token (~4 day lifetime), *or* install the `[tmsearch]` extra to mint via Playwright in-process. See [`tmsearch` extra below](#tmsearch-extra-playwright--curl_cffi). |

Google Patents, USPTO Publications, USPTO Assignments, USPTO Trademark
Assignments, MPEP, TMEP, WIPO Lex, Federal Circuit (CAFC), US Copyright
Office, USITC HTS, USITC IDS, and the UPC decisions feed need no
credentials.

### `tmsearch` extra (Playwright + curl_cffi)

USPTO TESS sits behind AWS WAF. To mint the WAF token in-process,
install the optional extra and bootstrap Chromium once:

```bash
pip install 'patent-client-agents[tmsearch]'
playwright install chromium
```

On headless server deployments where Playwright isn't installed, set
`PCA_WAF_TOKEN_JSON` to a token JSON payload (Secret Manager mount) or
`PCA_WAF_TOKEN_PATH` to a path on disk — the client will reuse the
cached token until it expires (~4 days). A typical pattern is to run a
Playwright job on a workstation, write the token JSON into a secret,
and mount it into the server container at runtime.

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

- `patent-client-agents-mcp` — launches the stdio MCP server (86 patent + trademark + adjacent-IP tools by default; +12 JPO / +9 CanLII / +4 EUIPO when those credentials are set)
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

Use this when you use Claude Code and want the 86 patent + trademark +
adjacent-IP MCP tools dropped in with two slash commands (plus +12 JPO /
+9 CanLII / +4 EUIPO when the corresponding credentials are in the
environment).

The plugin ships **only the MCP server** — no skill, no agents, no
hooks. The MCP tools' in-schema descriptions already carry the
cross-tool routing guidance a skill would otherwise centralize (e.g.
`search_patents_global` tells the agent "PREFER search_patent_publications
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
/plugin marketplace add parkerhancock/patent-client-agents
/plugin install patent-client-agents@patent-client-agents
/reload-plugins
```

What happens:

1. `/plugin marketplace add parkerhancock/patent-client-agents` clones this repo
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
export USPTO_TSDR_API_KEY="…"
export EPO_OPS_API_KEY="…"
export EPO_OPS_API_SECRET="…"
```

Restart Claude Code so the new env reaches the MCP subprocess. Without
keys, Google Patents / PPUBS / Assignments / Trademark Assignments
still work; USPTO ODP, USPTO TSDR, and EPO tools will return auth
errors. MPEP and TMEP no longer hit USPTO at runtime — see "MPEP /
TMEP corpus setup" below for the one-time build step.

### MPEP / TMEP / UPC-statutes corpus setup

`MpepClient`, `TmepClient`, and the UPC statutes tools read from local
SQLite/FTS5 snapshots instead of calling upstream sources. The wheel
ships the builders; build each corpus once into the default cache:

```bash
patent-client-agents-build-mpep-corpus \
    --output ~/.cache/patent_client_agents/mpep.db
patent-client-agents-build-tmep-corpus \
    --output ~/.cache/patent_client_agents/tmep.db
patent-client-agents-build-upc-statutes-corpus \
    --output ~/.cache/patent_client_agents/upc_statutes.db
```

MPEP is ~50MB and takes ~4 minutes; TMEP is ~16MB and takes ~2 minutes;
UPC statutes (UPCA + Rules of Procedure + Table of Fees, EN/FR/DE) is
~2MB and takes well under a minute. Re-run periodically to pick up
revisions.

For cloud deployments, build the corpora into the container image and
set `MPEP_CORPUS_PATH` / `TMEP_CORPUS_PATH` / `UPC_STATUTES_CORPUS_PATH`
in the runtime env to point at the output paths. The published wheel
stays small (no corpus bundled); refresh becomes "rebuild + redeploy."

If a call is made before the corpus exists, the client raises
`CorpusUnavailable` with the build command in the message — there is
no silent fallback to live HTTP.

### Verify

List MCP tools from within a Claude Code session:

```
/mcp
```

Expect `patent-client-agents` with 86 tools by default. Add +12 JPO
(`JPO_API_USERNAME` + `JPO_API_PASSWORD`), +9 CanLII (`CANLII_API_KEY`),
and +4 EUIPO (`EUIPO_CLIENT_ID` + `EUIPO_CLIENT_SECRET`) when the
corresponding env vars are set. Or call one directly by asking something
patent-research-ish:

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
| What it installs | MCP server only (86 default + env-gated families: +12 JPO, +9 CanLII, +4 EUIPO) | Skill markdown for Python library usage |
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
your client. The server is a short-lived subprocess speaking JSON-RPC
over stdio.

Confirmed-working clients: **Claude Code**, **Claude Desktop**, **OpenAI
Codex CLI**, **Google Gemini CLI**, **Cursor**, **Windsurf**, **Cline**,
**Zed**, **Continue.dev**, **VS Code Copilot Chat** (Agent mode), and
**JetBrains AI Assistant**. Snippets for each are below.

### Install

```bash
pip install 'patent-client-agents[mcp]'
```

This gives you the `patent-client-agents-mcp` console script on PATH.

### Quick reference — config-file shapes

| Client | Config file | Root key | Stdio field | Remote field |
|---|---|---|---|---|
| Claude Code | use `claude mcp add` (writes to `.mcp.json` / `~/.claude.json`) | `mcpServers` | `command` | `url` |
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) | `mcpServers` | `command` | UI only (Pro+) |
| Codex CLI | `~/.codex/config.toml` | `[mcp_servers.<name>]` | `command` | `url` |
| Gemini CLI | `~/.gemini/settings.json` | `mcpServers` | `command` | `httpUrl` |
| Cursor | `~/.cursor/mcp.json` (or `.cursor/mcp.json`) | `mcpServers` | `command` | `url` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` | `mcpServers` | `command` | `serverUrl` |
| Cline | extension UI → "Configure MCP Servers" | `mcpServers` | `command` | `url` + `type: "streamableHttp"` |
| Zed | `~/.config/zed/settings.json` | `context_servers` | `command` | `url` (or `mcp-remote` bridge) |
| Continue.dev | `~/.continue/config.yaml` | `mcpServers` (YAML list) | `command` | `type: streamable-http` + `url` |
| VS Code Copilot | `.vscode/mcp.json` (workspace) | `servers` | `type: "stdio"` + `command` | `type: "http"` + `url` |
| JetBrains AI | Settings → Tools → AI Assistant → MCP → Add | `mcpServers` (in pasted snippet) | `command` | `url` |

Three things differ across clients that look like they should be standardized but aren't:

1. **Root key:** `mcpServers` (most), `servers` (VS Code), `context_servers` (Zed), `[mcp_servers.<name>]` (Codex TOML).
2. **Remote URL field:** `url` (most), `httpUrl` (Gemini), `serverUrl` (Windsurf).
3. **Streamable-HTTP type field spelling:** `streamableHttp` (Cline), `streamable-http` (Continue), `http` (VS Code). Same protocol, three names.

### Wire the MCP client

#### Claude Code

Add via the CLI (writes to `.mcp.json` in the current dir, or `~/.claude.json` with `--scope user`):

```bash
claude mcp add --transport stdio patent-client-agents \
    --env USPTO_ODP_API_KEY=your-key \
    -- patent-client-agents-mcp
```

Or edit the JSON directly:

```json
{
  "mcpServers": {
    "patent-client-agents": {
      "command": "patent-client-agents-mcp",
      "env": {
        "USPTO_ODP_API_KEY": "…",
        "EPO_OPS_API_KEY": "…",
        "EPO_OPS_API_SECRET": "…"
      }
    }
  }
}
```

If you're using a venv, point at the absolute path so Claude Code
launches the right interpreter (`/path/to/.venv/bin/patent-client-agents-mcp`).

#### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS),
`%APPDATA%\Claude\claude_desktop_config.json` (Windows),
`~/.config/Claude/claude_desktop_config.json` (Linux):

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

GUI apps on macOS don't inherit shell `PATH`. If startup fails, replace
`"command": "patent-client-agents-mcp"` with the absolute path output by
`which patent-client-agents-mcp`. Remote MCP servers can be added via
Settings → Connectors on Pro/Team/Enterprise plans, but not through this
config file.

#### OpenAI Codex CLI

`~/.codex/config.toml` (global) or `.codex/config.toml` (per-project, trusted):

```toml
[mcp_servers.patent-client-agents]
command = "patent-client-agents-mcp"
args = []
env = { USPTO_ODP_API_KEY = "your-key" }
startup_timeout_sec = 10.0
```

To **forward** secrets from the parent shell instead of inlining them,
use `env_vars` instead of `env`:

```toml
[mcp_servers.patent-client-agents]
command = "patent-client-agents-mcp"
env_vars = ["USPTO_ODP_API_KEY", "EPO_OPS_API_KEY", "EPO_OPS_API_SECRET"]
```

Or use the CLI: `codex mcp add patent-client-agents --env USPTO_ODP_API_KEY=… -- patent-client-agents-mcp`.

Remote (Streamable HTTP) needs direct TOML editing — no CLI shortcut yet:

```toml
[mcp_servers.patent-client-agents]
url = "https://mcp.patentclient.com/mcp"
# bearer_token_env_var = "PATENT_CLIENT_AGENTS_TOKEN"  # optional
startup_timeout_sec = 30
tool_timeout_sec = 60
```

See the [Codex config reference](https://developers.openai.com/codex/config-reference).

#### Google Gemini CLI

`~/.gemini/settings.json` (global) or `.gemini/settings.json` (per-project):

```json
{
  "mcpServers": {
    "patent-client-agents": {
      "command": "patent-client-agents-mcp",
      "args": [],
      "env": {
        "USPTO_ODP_API_KEY": "$USPTO_ODP_API_KEY"
      }
    }
  }
}
```

Gemini CLI interpolates `$VAR` / `${VAR}` from the parent shell (cross-platform)
or `%VAR%` (Windows only). **Gotcha:** `.env` files placed in the project root
are *not* loaded into the `env` block — the variables must be in the actual
shell environment at launch time
([gemini-cli#2836](https://github.com/google-gemini/gemini-cli/issues/2836)).

Remote (Streamable HTTP) uses `httpUrl`, not `url`:

```json
{
  "mcpServers": {
    "patent-client-agents": {
      "httpUrl": "https://mcp.patentclient.com/mcp",
      "timeout": 30000
    }
  }
}
```

`timeout` is in milliseconds. See the [Gemini CLI MCP docs](https://geminicli.com/docs/tools/mcp-server/).

#### Cursor

`~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (per-project):

```json
{
  "mcpServers": {
    "patent-client-agents": {
      "command": "patent-client-agents-mcp",
      "env": {
        "USPTO_ODP_API_KEY": "${env:USPTO_ODP_API_KEY}"
      }
    }
  }
}
```

`${env:VAR}` reads from the parent environment. Cursor recommends
Streamable HTTP for remote-development setups — stdio with a remote
workspace tends to spawn the subprocess on the wrong side
([Cursor MCP docs](https://cursor.com/docs/mcp)).

#### Windsurf (Codeium)

`~/.codeium/windsurf/mcp_config.json` (macOS/Linux) or
`%USERPROFILE%\.codeium\windsurf\mcp_config.json` (Windows):

```json
{
  "mcpServers": {
    "patent-client-agents": {
      "command": "patent-client-agents-mcp",
      "env": {
        "USPTO_ODP_API_KEY": "${env:USPTO_ODP_API_KEY}"
      }
    }
  }
}
```

Remote uses `serverUrl` (Windsurf-specific, not `url`):

```json
{
  "mcpServers": {
    "patent-client-agents": {
      "serverUrl": "https://mcp.patentclient.com/mcp"
    }
  }
}
```

#### Cline (VS Code extension)

Open via the Cline panel → MCP Servers icon → Configure tab → "Configure
MCP Servers" (opens the JSON file in your editor).

```json
{
  "mcpServers": {
    "patent-client-agents": {
      "command": "patent-client-agents-mcp",
      "env": {
        "USPTO_ODP_API_KEY": "your-key"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

For remote, set `type: "streamableHttp"` (camelCase) — `"sse"` still
works but is deprecated:

```json
{
  "mcpServers": {
    "patent-client-agents": {
      "type": "streamableHttp",
      "url": "https://mcp.patentclient.com/mcp",
      "timeout": 60
    }
  }
}
```

`timeout` is in seconds, default 60. See the [Cline remote-server docs](https://docs.cline.bot/mcp/connecting-to-a-remote-server).

#### Zed

`~/.config/zed/settings.json` (macOS/Linux) or `%APPDATA%\Zed\settings.json` (Windows):

```json
{
  "context_servers": {
    "patent-client-agents": {
      "source": "custom",
      "command": "patent-client-agents-mcp",
      "env": {
        "USPTO_ODP_API_KEY": "your-key"
      }
    }
  }
}
```

Note the root key is `context_servers`, not `mcpServers`. Newer Zed
builds support remote URLs directly:

```json
{
  "context_servers": {
    "patent-client-agents": {
      "url": "https://mcp.patentclient.com/mcp"
    }
  }
}
```

If your Zed build doesn't support remote yet, bridge through `mcp-remote`:

```json
{
  "context_servers": {
    "patent-client-agents": {
      "source": "custom",
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://mcp.patentclient.com/mcp"]
    }
  }
}
```

#### Continue.dev

`~/.continue/config.yaml` or a per-server YAML file under
`.continue/mcpServers/<name>.yaml`:

```yaml
mcpServers:
  - name: patent-client-agents
    command: patent-client-agents-mcp
    args: []
    env:
      USPTO_ODP_API_KEY: ${{ secrets.USPTO_ODP_API_KEY }}
```

Continue uses `${{ secrets.NAME }}` for secret references (Continue
Hub-style), not `${env:...}`. For remote, note the kebab-case `type`:

```yaml
mcpServers:
  - name: patent-client-agents
    type: streamable-http
    url: https://mcp.patentclient.com/mcp
```

You can also paste a Claude Desktop / Cursor / Cline `mcpServers` JSON
block into `.continue/mcpServers/` — Continue auto-converts on next
launch.

#### VS Code Copilot Chat (Agent mode)

`.vscode/mcp.json` at the workspace root, or open user config via
Command Palette → "MCP: Open User Configuration". VS Code is the
exception — root key is `servers` (not `mcpServers`), and a `type`
field is required:

```json
{
  "servers": {
    "patent-client-agents": {
      "type": "stdio",
      "command": "patent-client-agents-mcp",
      "env": {
        "USPTO_ODP_API_KEY": "${input:uspto-odp-key}"
      }
    }
  },
  "inputs": [
    {
      "id": "uspto-odp-key",
      "type": "promptString",
      "description": "USPTO ODP API key",
      "password": true
    }
  ]
}
```

VS Code prompts for the input value on first use and caches it. For
remote, use `"type": "http"`:

```json
{
  "servers": {
    "patent-client-agents": {
      "type": "http",
      "url": "https://mcp.patentclient.com/mcp"
    }
  }
}
```

MCP tools only appear in Copilot's **Agent mode** — not in Ask or Edit
mode. See [Add and manage MCP servers in VS Code](https://code.visualstudio.com/docs/copilot/customization/mcp-servers).

#### JetBrains AI Assistant

Settings → Tools → AI Assistant → Model Context Protocol (MCP) → Add.
The dialog accepts a JSON snippet in the same shape as Claude Desktop:

```json
{
  "mcpServers": {
    "patent-client-agents": {
      "command": "patent-client-agents-mcp",
      "env": {
        "USPTO_ODP_API_KEY": "your-key"
      }
    }
  }
}
```

For HTTP, paste `https://mcp.patentclient.com/mcp` into the Streamable
HTTP option of the same dialog. JetBrains stores the config in IDE
settings — there's no canonical file path. See the [JetBrains AI Assistant MCP docs](https://www.jetbrains.com/help/ai-assistant/mcp.html).

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

Expect **86 tools** by default, with env-gated families adding
**+12 JPO** / **+9 CanLII** / **+4 EUIPO** when their credentials are
present. Title starts with `2106 ... Patent Subject Matter Eligibility`.

### Troubleshooting

**`patent-client-agents-mcp: command not found`** — `[mcp]` extra wasn't
installed. Rerun `pip install 'patent-client-agents[mcp]'`.

**`ModuleNotFoundError: No module named 'fastmcp'` at startup** — same
root cause. Something is launching a Python that doesn't have fastmcp.

**Zero tools listed** — the MCP client is likely talking to the wrong
server. Check the JSON config points at the right binary.

---

## 6. Remote MCP

Use this when an MCP client should point at a hosted HTTPS endpoint
instead of spawning a local subprocess. **Required** for cloud-hosted
clients that can't run subprocesses at all — ChatGPT Apps/Connectors
and Replit Agent. **Useful** for everyone else who'd rather avoid
managing a local Python install.

### Public demo

A hosted instance runs at **`https://mcp.patentclient.com`**. Add it to
any MCP client with just the URL — no tokens, no setup:

```json
{
  "mcpServers": {
    "patent-client-agents": {
      "url": "https://mcp.patentclient.com/mcp"
    }
  }
}
```

The first time you connect, you'll be sent to Google sign-in. Approve,
and you're done. Any verified Google account works. Usage is rate-limited
per account (100 MB/day, 20 MB/minute).

This is a public demo — don't send confidential material through it.
See the [Terms of Use](https://mcp.patentclient.com/terms).

### Cloud-only clients

These clients run in someone else's cloud and can't spawn local
subprocesses, so remote MCP is the only option:

#### ChatGPT (Apps / Connectors)

Plus or Pro subscription required. As of late 2025, ChatGPT renamed
"connectors" to "apps" (2025-12-17). HTTPS-only — no stdio.

1. Settings → Connectors → Advanced settings → enable **Developer mode**.
2. Settings → Connectors → **Create**.
3. Paste `https://mcp.patentclient.com/mcp` as the server URL.

If the connector flow rejects the modern Streamable-HTTP `/mcp` endpoint,
some older ChatGPT deep-research connectors required a URL ending in
`/sse/`. The modern Apps SDK accepts Streamable HTTP — try `/mcp` first.
See [Connect from ChatGPT — Apps SDK](https://developers.openai.com/apps-sdk/deploy/connect-chatgpt).

#### Replit Agent

Available since December 2025. UI-only:

1. Replit **Integrations** page → scroll to **MCP Servers for Replit Agent**.
2. **Add MCP server**.
3. Name (`patent-client-agents`) + URL (`https://mcp.patentclient.com/mcp`).

All MCP traffic passes through Replit's security scanner, which can
block tools it considers unsafe. See the [Replit MCP overview](https://docs.replit.com/replitai/mcp/overview).

### Bridge a stdio server to ChatGPT / Replit via `mcp-remote`

If you want to use the local `patent-client-agents-mcp` (e.g. so your own
API keys are honored) from a cloud-only client, run `mcp-remote` on a
public HTTPS host that wraps the stdio process and exposes it as
Streamable HTTP. Point ChatGPT or Replit at that wrapper's URL.

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

  Cloud-only client (ChatGPT Apps, Replit Agent)?
  ├── yes → §6 (remote MCP — point at hosted demo or your HTTPS deploy)
  └── no ↓

  Any other MCP client (Codex CLI, Gemini CLI, Cursor, Windsurf, Cline,
  Zed, Continue.dev, VS Code Copilot Chat, JetBrains AI, Claude Desktop)?
  ├── local subprocess → §5 (stdio MCP)
  └── pointing at a deployed server → §6 (remote MCP)
```

## Getting help

- Issues: [github.com/parkerhancock/patent-client-agents/issues](https://github.com/parkerhancock/patent-client-agents/issues)
- Full source: [github.com/parkerhancock/patent-client-agents](https://github.com/parkerhancock/patent-client-agents)
- Per-source API notes: `src/patent_client_agents/catalog/sources/`
- MCP tool reference (by intent): `src/patent_client_agents/catalog/intents/`
