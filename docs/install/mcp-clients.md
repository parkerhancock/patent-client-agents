# Configure another MCP client

Use this page for MCP clients that do not use the shared agent plugin. Claude
Code, Codex, and Antigravity users can also use these settings when they need a
hand-managed server command or a remote endpoint.

Use this when you want every patent tool available as MCP tools to
your client. The server is a short-lived subprocess speaking JSON-RPC
over stdio.

Confirmed-working clients: **Claude Code**, **Claude Desktop**, **OpenAI
Codex CLI**, **Google Antigravity CLI**, **Google Gemini CLI**, **Cursor**, **Windsurf**, **Cline**,
**Zed**, **Continue.dev**, **VS Code Copilot Chat** (Agent mode), and
**JetBrains AI Assistant**. Snippets for each are below.

## Install the local server

Install and verify the `patent-client-agents-mcp` command with the
[local MCP server guide](../mcp-stdio.md#install). Return here for the
configuration shape your client expects.

## Quick reference: config-file shapes

| Client | Config file | Root key | Stdio field | Remote field |
|---|---|---|---|---|
| Claude Code | use `claude mcp add` (writes to `.mcp.json` / `~/.claude.json`) | `mcpServers` | `command` | `url` |
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) | `mcpServers` | `command` | UI only (Pro+) |
| Codex CLI | `~/.codex/config.toml` | `[mcp_servers.<name>]` | `command` | `url` |
| Antigravity CLI | `~/.gemini/antigravity-cli/mcp_config.json` (or `.agents/mcp_config.json`) | `mcpServers` | `command` | `serverUrl` |
| Gemini CLI | `~/.gemini/settings.json` | `mcpServers` | `command` | `httpUrl` |
| Cursor | `~/.cursor/mcp.json` (or `.cursor/mcp.json`) | `mcpServers` | `command` | `url` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` | `mcpServers` | `command` | `serverUrl` |
| Cline | extension UI > "Configure MCP Servers" | `mcpServers` | `command` | `url` + `type: "streamableHttp"` |
| Zed | `~/.config/zed/settings.json` | `context_servers` | `command` | `url` (or `mcp-remote` bridge) |
| Continue.dev | `~/.continue/config.yaml` | `mcpServers` (YAML list) | `command` | `type: streamable-http` + `url` |
| VS Code Copilot | `.vscode/mcp.json` (workspace) | `servers` | `type: "stdio"` + `command` | `type: "http"` + `url` |
| JetBrains AI | Settings > Tools > AI Assistant > MCP > Add | `mcpServers` (in pasted snippet) | `command` | `url` |

Three things differ across clients that look like they should be standardized but aren't:

1. **Root key:** `mcpServers` (most), `servers` (VS Code), `context_servers` (Zed), `[mcp_servers.<name>]` (Codex TOML).
2. **Remote URL field:** `url` (most), `httpUrl` (Gemini), `serverUrl` (Antigravity and Windsurf).
3. **Streamable-HTTP type field spelling:** `streamableHttp` (Cline), `streamable-http` (Continue), `http` (VS Code). Same protocol, three names.

## Wire the MCP client

### Claude Code

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

### Claude Desktop

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
Settings > Connectors on Pro/Team/Enterprise plans, but not through this
config file.

### OpenAI Codex CLI

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

Remote (Streamable HTTP) needs direct TOML editing: no CLI shortcut yet:

```toml
[mcp_servers.patent-client-agents]
url = "https://mcp.patentclient.com/mcp"
# bearer_token_env_var = "PATENT_CLIENT_AGENTS_TOKEN"  # optional
startup_timeout_sec = 30
tool_timeout_sec = 60
```

See the [Codex config reference](https://developers.openai.com/codex/config-reference).

### Google Antigravity CLI

`~/.gemini/antigravity-cli/mcp_config.json` (global) or
`.agents/mcp_config.json` (workspace):

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

Remote connections use `serverUrl`:

```json
{
  "mcpServers": {
    "patent-client-agents": {
      "serverUrl": "https://mcp.patentclient.com/mcp"
    }
  }
}
```

Use `/mcp` inside Antigravity to inspect status and connection logs. See
the [official Antigravity MCP guide](https://antigravity.google/docs/cli/mcp/).

### Google Gemini CLI

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
are *not* loaded into the `env` block: the variables must be in the actual
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

### Cursor

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
Streamable HTTP for remote-development setups: stdio with a remote
workspace tends to spawn the subprocess on the wrong side
([Cursor MCP docs](https://cursor.com/docs/mcp)).

### Windsurf (Codeium)

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

### Cline (VS Code extension)

Open via the Cline panel > MCP Servers icon > Configure tab > "Configure
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

For remote, set `type: "streamableHttp"` (camelCase): `"sse"` still
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

### Zed

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

### Continue.dev

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
block into `.continue/mcpServers/`: Continue auto-converts on next
launch.

### VS Code Copilot Chat (Agent mode)

`.vscode/mcp.json` at the workspace root, or open user config via
Command Palette > "MCP: Open User Configuration". VS Code is the
exception: root key is `servers` (not `mcpServers`), and a `type`
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

MCP tools only appear in Copilot's **Agent mode**: not in Ask or Edit
mode. See [Add and manage MCP servers in VS Code](https://code.visualstudio.com/docs/copilot/customization/mcp-servers).

### JetBrains AI Assistant

Settings > Tools > AI Assistant > Model Context Protocol (MCP) > Add.
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
settings: there's no canonical file path. See the [JetBrains AI Assistant MCP docs](https://www.jetbrains.com/help/ai-assistant/mcp.html).

## Verify

```python
import asyncio
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

async def main():
    async with Client(StdioTransport(command="patent-client-agents-mcp", args=[])) as c:
        tools = await c.list_tools()
        print(f"{len(tools)} tools")
        result = await c.call_tool(
            "get_patent",
            {"patent_number": "US10000000B2", "view": "details"},
        )
        print(result.data.items[0]["title"])

asyncio.run(main())
```

Expect **136 tools** by default. Local/private servers expose up to
**234 tools** when every env-gated family is configured. The expected title is
`Coherent LADAR using intra-pixel quadrature detection`. Agent users can run
the equivalent [first research task](../first-research-task.md) as a prompt.

## Troubleshooting

**`patent-client-agents-mcp: command not found`**: `[mcp]` extra wasn't
installed. Rerun `pip install 'patent-client-agents[mcp]'`.

**`ModuleNotFoundError: No module named 'fastmcp'` at startup**: same
root cause. Something is launching a Python that doesn't have fastmcp.

**Zero tools listed**: the MCP client is likely talking to the wrong
server. Check the JSON config points at the right binary.

---
