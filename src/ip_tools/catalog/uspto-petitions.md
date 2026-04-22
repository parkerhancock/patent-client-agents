# USPTO Petitions

Search and retrieval of USPTO petition decisions. Wraps
`uspto_odp.PetitionsClient` with convenience functions.

## Source

| | |
|---|---|
| Module | `ip_tools.uspto_petitions` |
| Client | Uses `ip_tools.uspto_odp.PetitionsClient` |
| Base URL | `https://api.uspto.gov` |
| Auth | `USPTO_ODP_API_KEY` |
| Rate limits | 60 req/min per key (shared with USPTO ODP) |
| Status | Active |

## Authentication

Same as [uspto-odp.md](uspto-odp.md).

## Library API

```python
from ip_tools.uspto_petitions import (
    search_petitions,
    get_petition,
    download_petitions,
)

result = await search_petitions(
    q="petitionDecision:granted",
    fields=["petitionIdentifier", "petitionDecisionDate", "petitionType"],
    limit=25,
)
petition = await get_petition("P20230001")
```

### Methods

| Method | Description |
|---|---|
| `search_petitions(q, fields, sort, limit, offset, ...)` | Search petition decisions |
| `get_petition(petition_identifier)` | Single petition decision record |
| `download_petitions(identifiers)` | Bulk-fetch petition decision documents |

All functions accept an optional `client=` parameter to reuse an existing
`PetitionsClient`.

## MCP Tools

Exposed via downstream MCP packaging.

| Tool | Description |
|---|---|
| `search_petitions` | Search USPTO petition decisions |
| `get_petition` | Get details for a specific petition decision |

## Related Docs

- [uspto-odp.md](uspto-odp.md) — underlying client + auth
