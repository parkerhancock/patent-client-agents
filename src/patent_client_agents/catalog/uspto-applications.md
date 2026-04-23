# USPTO Applications (high-level API)

Function-level wrappers over `uspto_odp.ApplicationsClient` covering patent
application search, file-wrapper documents, family graphs, and PTAB trial
proceedings. Exists so callers can do one-shot lookups without managing a
client context; for long-running sessions use `ApplicationsClient` directly
(see [uspto-odp.md](uspto-odp.md)).

## Source

| | |
|---|---|
| Module | `patent_client_agents.uspto_applications` |
| Client | Uses `patent_client_agents.uspto_odp.ApplicationsClient` |
| Base URL | `https://api.uspto.gov` |
| Auth | `USPTO_ODP_API_KEY` |
| Rate limits | 60 req/min per key (shared with USPTO ODP) |
| Status | Active |

## Authentication

Same as [uspto-odp.md](uspto-odp.md).

## Library API

```python
from patent_client_agents.uspto_applications import (
    search_applications,
    get_application,
    list_documents,
    get_family,
)

result = await search_applications(q="inventionTitle:laser", limit=25)
app = await get_application("16123456")
docs = await list_documents("16123456")
family = await get_family("16123456")
```

### Methods

| Method | Description |
|---|---|
| `search_applications(q, fields, sort, limit, offset, ...)` | Search applications via Lucene-style queries |
| `get_application(application_number)` | Full bibliographic + status record |
| `list_documents(application_number)` | File-wrapper documents (prosecution history) |
| `get_family(application_number)` | Parent/child continuity + foreign priority as a graph |
| `search_trial_proceedings(...)` | PTAB trial proceeding search |
| `get_trial_proceeding(proceeding_identifier)` | Single PTAB trial proceeding |
| `search_trial_decisions(...)` | PTAB trial decisions |
| `get_trial_decisions_by_trial(proceeding_identifier)` | All decisions for a specific trial |
| `search_trial_documents(...)` | PTAB trial document search |
| `get_trial_documents_by_trial(proceeding_identifier)` | All documents filed in a trial |

All functions accept an optional `client=` parameter to reuse an existing
`ApplicationsClient` across calls.

## MCP Tools

Exposed via downstream MCP packaging. These are the
same tools documented under [uspto-odp.md](uspto-odp.md); the wrapper module
is a Python-API convenience, not a separate MCP surface.

| Tool | Description |
|---|---|
| `search_applications` | Search USPTO patent applications |
| `get_application` | Get a single application by number |
| `list_file_history` | List prosecution history documents |
| `get_file_history_item` | Fetch a single file-wrapper document |
| `get_patent_family` | Continuity and foreign priority graph |

## Related Docs

- [uspto-odp.md](uspto-odp.md) — underlying client, auth, release tracking
