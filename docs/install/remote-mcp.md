# Connect to remote MCP

Use this when an MCP client should point at a hosted HTTPS endpoint
instead of spawning a local subprocess. **Required** for cloud-hosted
clients that can't run subprocesses at all: ChatGPT Apps/Connectors
and Replit Agent. **Useful** for everyone else who'd rather avoid
managing a local Python install.

## Use the public hosted service

The public endpoint is `https://mcp.patentclient.com/mcp`. Read the [hosted service guide](../hosted-demo.md) before using it for limits, tool availability, and confidentiality guidance.

## Connect cloud-only clients

These clients run in someone else's cloud and can't spawn local
subprocesses, so remote MCP is the only option:

### ChatGPT (Apps / Connectors)

Plus or Pro subscription required. As of late 2025, ChatGPT renamed
"connectors" to "apps" (2025-12-17). HTTPS-only: no stdio.

1. Settings > Connectors > Advanced settings > enable **Developer mode**.
2. Settings > Connectors > **Create**.
3. Paste `https://mcp.patentclient.com/mcp` as the server URL.

If the connector flow rejects the modern Streamable-HTTP `/mcp` endpoint,
some older ChatGPT deep-research connectors required a URL ending in
`/sse/`. The modern Apps SDK accepts Streamable HTTP: try `/mcp` first.
See [Connect from ChatGPT: Apps SDK](https://developers.openai.com/apps-sdk/deploy/connect-chatgpt).

### Replit Agent

Available since December 2025. UI-only:

1. Open the Replit **Integrations** page and scroll to **MCP Servers for Replit Agent**.
2. Select **Add MCP server**.
3. Enter the name `patent-client-agents` and the URL (`https://mcp.patentclient.com/mcp`).

All MCP traffic passes through Replit's security scanner, which can
block tools it considers unsafe. See the [Replit MCP overview](https://docs.replit.com/replitai/mcp/overview).

## Bridge a stdio server to ChatGPT / Replit via `mcp-remote`

If you want to use the local `patent-client-agents-mcp` (e.g. so your own
API keys are honored) from a cloud-only client, run `mcp-remote` on a
public HTTPS host that wraps the stdio process and exposes it as
Streamable HTTP. Point ChatGPT or Replit at that wrapper's URL.

---
