# CPC Classification

Cooperative Patent Classification (CPC) lookups, keyword search, and
cross-scheme mapping (CPC ↔ IPC / ECLA). Accessed through the EPO OPS
classification endpoints, so the module shares EPO OPS credentials but
exposes a distinct CPC-centric API.

## Source

| | |
|---|---|
| Module | `patent_client_agents.cpc` |
| Client | Uses `patent_client_agents.epo_ops.EpoOpsClient` under the hood |
| Base URL | `https://ops.epo.org/3.2/rest-services/classification/cpc` |
| Auth | `EPO_OPS_API_KEY` + `EPO_OPS_API_SECRET` (shared with EPO OPS) |
| Rate limits | 4 GB/week free tier (shared with EPO OPS) |
| Status | Active |

## Authentication

Uses the same EPO OPS OAuth2 credentials as [epo-ops.md](epo-ops.md). See that
page for registration, quota management, and throttling details. The CPC
endpoints count against the same EPO OPS weekly quota.

## Library API

```python
from patent_client_agents.cpc import retrieve_cpc, search_cpc, map_classification

entry = await retrieve_cpc(symbol="H04L63/08", ancestors=True)
results = await search_cpc(query="neural network", limit=10)
mapping = await map_classification(symbol="H04L63/08", to="IPC")
```

### Methods

| Method | Description |
|---|---|
| `retrieve_cpc(symbol, depth=None, ancestors=False, navigation=False)` | Look up a CPC entry; optionally include ancestors and descendants |
| `search_cpc(query, limit=25)` | Free-text search across CPC titles |
| `map_classification(symbol, to="IPC")` | Map CPC ↔ IPC or ECLA |
| `fetch_media(media_id, accept="image/png")` | Download figures/diagrams referenced from CPC entries |
| `fetch_biblio_cpci(...)` | Fetch biblio data indexed by CPC classification |

All functions accept an optional `client=` parameter so an existing
`EpoOpsClient` context can be reused across calls.

## MCP Tools

Exposed via downstream MCP packaging (part of the
EPO OPS block since they share an endpoint).

| Tool | Description |
|---|---|
| `lookup_cpc` | Resolve a CPC symbol to its title, ancestors, and descendants |
| `search_cpc` | Full-text search across CPC titles |
| `map_cpc_classification` | Map a CPC symbol to IPC or ECLA equivalents |

## Related Docs

- [epo-ops.md](epo-ops.md) — underlying OAuth flow and quota behavior
