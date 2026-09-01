# Choose an installation path

Patent Client Agents supports direct Python use, local MCP clients, native
agent plugins, and remote MCP connections. Choose the page that matches where
the tools will run.

| You want to | Use this setup |
| --- | --- |
| Add the same local tool package to Claude Code, OpenAI Codex CLI, or Google Antigravity CLI | [Agent plugin](install/agent-plugins.md) |
| Import source-specific clients in Python | [Python library](install/python.md#install-the-base-library) |
| Run the MCP server from a Python environment | [Python library with MCP runtime](install/python.md#add-the-mcp-runtime) |
| Configure Claude Desktop, Gemini CLI, Cursor, Windsurf, Cline, Zed, Continue, VS Code, JetBrains, or another MCP client | [MCP client configurations](install/mcp-clients.md) |
| Connect ChatGPT, Replit, or another client to an HTTPS endpoint | [Remote MCP](install/remote-mcp.md) |
| Try the curated public service without a local install | [Hosted service](hosted-demo.md) |

The agent plugin is the shortest local setup for Claude Code, Codex, and
Antigravity. It installs the same Satchel-generated package in each host. Use a
direct MCP configuration when you need another client or want to control the
server command yourself.

## 1. Python library

Install the base package when Python code will call the clients directly. The
[Python library guide](install/python.md#install-the-base-library) covers the
package, credentials, the optional trademark-search extra, and a working
example.

## 2. Python library with MCP runtime

Add the `[mcp]` extra when one Python environment must provide both the client
library and the `patent-client-agents-mcp` command. Continue with the
[MCP runtime instructions](install/python.md#add-the-mcp-runtime).

## 3. Agent plugins

Claude Code, OpenAI Codex CLI, and Google Antigravity CLI are equal deployment
targets. The [agent plugin guide](install/agent-plugins.md) has the install,
update, removal, credential, corpus, verification, and troubleshooting steps
for all three.

## 4. Claude Code skill (standalone, library-user)

The standalone `ip_research` skill is for people writing Python code against
the library. It is separate from the agent plugin. See
[Add the Claude Code library skill](install/python.md#add-the-claude-code-library-skill).

## 5. Stdio MCP from any MCP client

Use the [MCP client configuration guide](install/mcp-clients.md) for exact
stdio and remote settings across supported clients. The
[local MCP server guide](mcp-stdio.md) explains the server command, tool
surface, downloads, and resource transport.

## 6. Remote MCP

Cloud clients cannot spawn a local subprocess. Point them at the public hosted
service or another HTTPS deployment by following the
[remote MCP guide](install/remote-mcp.md).

## MPEP / TMEP corpus setup

MPEP, TMEP, and UPC statutes use local SQLite/FTS5 snapshots. The canonical
build commands and deployment notes are under
[Build local corpora](install/local-runtime.md#build-local-corpora).

## Getting help

- Issues: [github.com/parkerhancock/patent-client-agents/issues](https://github.com/parkerhancock/patent-client-agents/issues)
- Full source: [github.com/parkerhancock/patent-client-agents](https://github.com/parkerhancock/patent-client-agents)
- Source inventory: [Patent Client Index](patent-client-index/index.md)
