# Hosted demo

The public MCP demo runs at `https://mcp.patentclient.com/mcp`. It is a
curated service for exploratory research. It is not the complete local tool
surface.

## Access

Add the MCP URL to a client that supports remote MCP. The service uses Google
sign-in. Any verified Google account can request access.

```json
{
  "mcpServers": {
    "patent-client-agents": {
      "url": "https://mcp.patentclient.com/mcp"
    }
  }
}
```

## Usage limits

The service applies byte limits to each authenticated account:

- 20 MB per minute.
- 100 MB per day.
- A minimum 1 KB charge for each tool call.

These limits support interactive research, not bulk extraction. A rate-limit
response states which bucket was exhausted. Retry after that bucket resets.

## Tool surface

The public demo exposes a curated subset of the library. The MCP `tools/list`
response is the authoritative current list. The deployment repository owns
the exact public contract and checks it after deployments.

Credential-gated connectors stay absent when their upstream terms require a
user-specific key. This includes JPO, KIPO, TIPO, INPI France, IP Australia,
CanLII, and EUIPO. Install the library locally and provide your own credentials
to use those connectors.

The demo can also hide tools that need deployment-specific state. Current
examples include MPEP corpus tools, USPTO trademark search, UPC decisions, and
USITC EDIS tools. The USPTO trademark search depends on an AWS WAF token. A
self-hosted deployment can supply `PCA_WAF_TOKEN_JSON` or
`PCA_WAF_TOKEN_PATH`, but the public demo does not advertise the tools unless
its refresh path is reliable.

## Data and confidentiality

The demo is a shared public service. Do not send confidential client material,
unpublished invention details, credentials, or privileged work product.
Authentication, aggregate usage, tool names, outcomes, and rate-limit data may
be processed to operate and protect the service. Review the live
[Terms of Use](https://mcp.patentclient.com/terms) and
[Privacy Policy](https://mcp.patentclient.com/privacy) before use.

Upstream offices remain the systems of record. Sources can change, fail, or
return stale data. Check each response's provenance before relying on it.

## Reliability checks

The library repository checks public health, OAuth metadata, and MCP ingress
each hour. The deployment repository owns authenticated checks for the curated
tool contract, required tools, and deliberately hidden tools.

Use a local or private deployment when you need the full connector set,
private credentials, larger workloads, or confidential handling.
