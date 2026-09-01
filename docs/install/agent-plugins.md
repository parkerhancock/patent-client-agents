# Install an agent plugin

Claude Code, OpenAI Codex CLI, and Google Antigravity CLI are equal
deployment targets. Each native plugin launches the same pinned PyPI
release. Add 136 patent + trademark + adjacent-IP MCP tools to any of
the three clients by default. Private/local deployments expose up to 234
tools when the corresponding credentials are in the environment.

The package metadata is maintained once in `satchel.yaml` and generated
for all three hosts with Satchel. Do not edit the generated marketplace or
plugin manifests directly. Contributors can regenerate and verify them with:

```bash
uvx --from git+https://github.com/parkerhancock/satchel@9c9117a3be6810ad847f3b27f4ab658465f77b2f satchel generate .
uvx --from git+https://github.com/parkerhancock/satchel@9c9117a3be6810ad847f3b27f4ab658465f77b2f satchel check . --release --host
```

The plugin ships **only the MCP server**: no skill, no agents, no
hooks. The MCP tools' in-schema descriptions already carry the
cross-tool routing guidance a skill would otherwise centralize (e.g.
`search_patents_global` tells the agent "PREFER search_patent_publications
for US patents"; `get_epo_cql_help` is itself a tool).

## Install uv

`uv` needs to be on `PATH`. Each plugin's MCP server spawns via `uvx`,
which handles the Python runtime (`fastmcp` and friends) in a managed
environment so you don't have to `pip install` anything.

```bash
# install uv if you don't have it: one-liner from astral.sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Install in Claude Code

Claude Code's plugin install goes through a **marketplace**: a small
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

## Install in OpenAI Codex CLI

Run these in your shell:

```bash
codex plugin marketplace add parkerhancock/patent-client-agents
codex plugin add patent-client-agents@patent-client-agents
```

The repository marketplace at `.agents/plugins/marketplace.json`
points Codex at `plugins/patent-client-agents/`. That package declares
the server in `.codex-plugin/plugin.json` and `.mcp.json`. Start a new
Codex session after installation.

## Install in Google Antigravity CLI

Antigravity installs a plugin from a local or remote directory. Clone
the repository, then install its shared plugin package:

```bash
git clone --depth 1 https://github.com/parkerhancock/patent-client-agents.git
agy plugin install ./patent-client-agents/plugins/patent-client-agents
```

Antigravity reads `plugin.json` and `mcp_config.json` from that package.
Start a new `agy` session after installation.

## What the packages do

For Claude Code specifically:

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
   **PyPI** (not from the cloned repo: the plugin manifest pins
   `uvx --from patent-client-agents[mcp]==0.27.1 patent-client-agents-mcp`)
   into a managed environment and launches the server. The first run
   takes ~30 seconds while ~100 packages download; subsequent runs
   are fast because uv caches the resolved environment.

Expected output after install + reload:

```
Reloaded: 1 plugin · 0 skills · … agents · 0 hooks · 1 plugin MCP server · 0 plugin LSP servers
```

`0 skills` is the intended state: see the package model above.

## Update

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

For Codex, refresh and reinstall from the configured marketplace:

```bash
codex plugin marketplace upgrade patent-client-agents
codex plugin remove patent-client-agents
codex plugin add patent-client-agents@patent-client-agents
```

For Antigravity, update the clone and reinstall the directory:

```bash
git -C ./patent-client-agents pull --ff-only
agy plugin uninstall patent-client-agents
agy plugin install ./patent-client-agents/plugins/patent-client-agents
```

## Remove

```
/plugin uninstall patent-client-agents@patent-client-agents
/plugin marketplace remove patent-client-agents
```

## Configure local sources

Follow [Configure local source access](local-runtime.md) for credentials and
local corpus builders. Restart the agent client afterward so its MCP subprocess
receives the updated environment.

## Verify

List MCP tools from within the installed agent client:

```
Claude Code: /mcp
Codex CLI:   /mcp
Antigravity: /mcp
```

Expect `patent-client-agents` with 136 tools by default. Local/private
servers expose up to 234 tools when all env-gated families are configured
with their corresponding credentials. Then complete
[your first research task](../first-research-task.md), a live patent lookup
that works without an API key or local corpus.

## Troubleshooting

**`uvx: command not found`**: [install uv](#install-uv).

**`/mcp` shows the server as "failed to start"**: open the logs pane
and look for stderr output. Common causes: offline during first
install (`uvx` can't reach PyPI), or an ancient macOS Python build
error (upgrade `uv` to latest).

**Cold start takes too long**: subsequent runs are ~1s. If every
session takes 30s, something is evicting uv's cache. Check that
`~/.cache/uv/` is persistent.

**Plugin shows 0 tools after install**: In Claude Code, try
`/reload-plugins`. In Codex or Antigravity, start a new session.

---
