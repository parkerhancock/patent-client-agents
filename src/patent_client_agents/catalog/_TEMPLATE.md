<!--
Catalog file template. Copy and fill in for a new data connector.

Required sections (enforced by scripts/lint_catalog.py):
  ## Source
  ## Library API          — omit for skill-only / disabled connectors
  ## MCP Tools            — omit for skill-only / disabled connectors

Optional sections (use as needed, in this order between Source and Library API):
  ## Authentication
  ## Rate Limits
  ## API Endpoints
  ## <connector-specific>  e.g. "FTP Structure", "Rule Sets", "Pages Scraped",
                           "Budget", "Archive", "Supported Sources", "Clients"

End with:
  ## Related Docs          — optional; link to docs/*.md pages that expand on this

The Source meta-table must have rows for: Module, Client, Base URL, Auth,
Rate limits, Status. Values may be "None" or "Not published" — the row
must be present.
-->

# Connector Name

One-paragraph description of what this connector exposes: scope, data types, how the data is sourced (API vs scraped vs FTP), and what the typical agent use case looks like.

## Source

| | |
|---|---|
| Module | `patent_client_agents.connector_name` |
| Client | `ConnectorClient` |
| Base URL | `https://api.example.com` |
| Auth | None / `ENV_VAR` / credentials |
| Rate limits | e.g. `60 req/min` or `Not published` |
| Status | Active / Deprecated / Disabled / Skill-only |

## Authentication

Prose explaining how to obtain credentials, which env vars the client accepts (with priority order if multiple), and how to configure the auth. Omit this section entirely when Auth = None.

## Rate Limits

Prose explaining the documented limits, any auto-throttling in the client, and how to request higher quotas if applicable. Omit when Rate limits = Not published or trivially summarized in the Source table.

## Library API

```python
from patent_client_agents.connector_name import ConnectorClient

async with ConnectorClient() as client:
    result = await client.some_method(arg="value")
```

### Methods

| Method | Description |
|---|---|
| `some_method(arg)` | One-line description |
| `other_method(arg1, arg2)` | One-line description |

Group methods by category with h4 subsections if the connector exposes more than ~8 methods.

## MCP Tools

| Tool | Description |
|---|---|
| `search_connector` | One-line description |
| `get_connector_item` | One-line description |
| `download_connector_pdf` | One-line description (if applicable) |

## Related Docs

- [docs/SOME_ARCHITECTURE.md](../docs/SOME_ARCHITECTURE.md) — when applicable
