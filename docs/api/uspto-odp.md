# USPTO ODP

Low-level client for the USPTO Open Data Portal. Covers patent applications,
PTAB proceedings (trials, appeals, interferences), petitions, and bulk data
via one authenticated API surface. Higher-level wrapper modules
(`uspto_applications`, `uspto_petitions`, `uspto_bulkdata`) route through
the same underlying client.

## Quick Start

```python
from ip_tools.uspto_odp import UsptoOdpClient

async with UsptoOdpClient() as client:
    results = await client.search_applications(query="artificial intelligence")
    app = await client.get_application("16123456")
    trials = await client.search_trial_proceedings(query="patent owner")
```

Most work is routed through dedicated sub-clients:

```python
from ip_tools.uspto_odp import (
    ApplicationsClient,     # applications, IFW file history
    PtabTrialsClient,       # IPR/PGR/CBM trial data
    PtabAppealsClient,      # ex parte appeal decisions
    PtabInterferencesClient,
    PetitionsClient,        # petition decisions
    BulkDataClient,         # bulk data product catalog
)
```

## Configuration

Requires a USPTO ODP API key (free registration):

```bash
export USPTO_ODP_API_KEY="your-api-key"
```

Get a key at [developer.uspto.gov](https://developer.uspto.gov). Rate
limit: 60 requests/minute.

## Client classes

| Class | Purpose |
|---|---|
| `UsptoOdpClient` | Aggregate client exposing all endpoints |
| `ApplicationsClient` | Applications, file wrapper, family graph |
| `PtabTrialsClient` | PTAB trial proceedings (IPR, PGR, CBM, DER) |
| `PtabAppealsClient` | Ex parte appeals |
| `PtabInterferencesClient` | Interference decisions |
| `PetitionsClient` | Petition decisions |
| `BulkDataClient` | Bulk data product catalog |

All inherit from `law_tools_core.BaseAsyncClient` — built-in hishel cache,
tenacity retry (4 attempts, exponential jitter), structured error types,
log-first error messages.

## Key functions — Applications

| Function | Description |
|---|---|
| `search_applications(query, limit, offset)` | Lucene search over app metadata |
| `get_application(application_number)` | Application status, examiner, CPC |
| `get_documents(application_number)` | List file-history documents |
| `get_document_content(app, doc_id, format="auto")` | Parsed text / raw XML / PDF URL |
| `get_family(identifier, identifier_type)` | Continuation/divisional graph |
| `get_granted_claims(patent_number)` | Structured claims from grant XML |
| `get_assignment(application_number)` | Chain-of-title records |

## Key functions — PTAB

| Function | Description |
|---|---|
| `search_trial_proceedings(query)` | IPR / PGR / CBM search |
| `get_trial_proceeding(trial_number)` | IPR2024-00001 style lookup |
| `search_trial_decisions(query)` | Final / institution decisions |
| `search_trial_documents(query)` | Full-text petition search |
| `download_document_pdf(uri_path)` | Raw PDF bytes |
| `search_appeal_decisions(query)` | Ex parte BPAI / PTAB appeals |
| `search_interference_decisions(query)` | Pre-AIA interferences |

## Error handling

Typed exceptions inherit from `law_tools_core.exceptions.ApiError`:

- `NotFoundError` (404) — application or document not indexed
- `AuthenticationError` (401/403) — missing or revoked API key
- `RateLimitError` (429) — includes `retry_after` seconds

Every error message ends with a path to the log file
(`~/.cache/ip_tools/ip_tools.log`) for full response body inspection.

## Usage patterns

```python
from ip_tools.uspto_odp import ApplicationsClient

# Context manager (recommended)
async with ApplicationsClient() as client:
    docs = await client.get_documents("16123456")
    text = await client.get_document_content("16123456", docs.documents[0].documentIdentifier)
    print(text["content"][:1000])
```

## Higher-level wrappers

For most use cases, the wrapper modules are more ergonomic:

- `ip_tools.uspto_applications` — function-level API over applications
- `ip_tools.uspto_petitions` — petition search/get helpers
- `ip_tools.uspto_bulkdata` — bulk data product catalog
- `ip_tools.uspto_office_actions` — office-action analytics (separate endpoint)

See [uspto-applications.md](uspto-applications.md) and peer files.
