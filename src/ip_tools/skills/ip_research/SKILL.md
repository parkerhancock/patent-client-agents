---
name: ip_research
description: |
  IP data research tools for patents, applications, and related USPTO/EPO/JPO records. Use when:
  - Looking up patents by number (US, EP, WO, JP, etc.)
  - Searching patent databases by keyword, assignee, inventor, or classification
  - Getting patent family, citation, or legal status information
  - Checking USPTO application status, file wrapper, PTAB proceedings, or petitions
  - Searching office action rejections and cited references
  - Looking up MPEP sections or CPC classifications
  - Finding patent assignments or ownership history
  - Fetching USPTO publication full-text data
---

# IP Research

Async Python clients for patent and IP data. All clients use `async with` context
managers. All shared scaffolding (HTTP, cache, retry, errors) lives in
`law_tools_core`, shipped in the same wheel.

## Routing

| Task | Client / Module | Reference |
|------|-----------------|-----------|
| Patent lookup / search by keywords | `google_patents.GooglePatentsClient` | [google_patents.md](references/google_patents.md) |
| USPTO application status + file wrapper | `uspto_odp.ApplicationsClient` | [uspto_odp.md](references/uspto_odp.md) |
| USPTO application high-level API | `ip_tools.uspto_applications` | [uspto_applications.md](references/uspto_applications.md) |
| USPTO PTAB (IPR/PGR/CBM, ex parte appeals, interferences) | `uspto_odp.PtabTrialsClient` / `PtabAppealsClient` / `PtabInterferencesClient` | [uspto_odp.md](references/uspto_odp.md) |
| USPTO petitions | `uspto_odp.PetitionsClient` or `ip_tools.uspto_petitions` | [uspto_petitions.md](references/uspto_petitions.md) |
| USPTO bulk data products | `uspto_odp.BulkDataClient` or `ip_tools.uspto_bulkdata` | [uspto_bulkdata.md](references/uspto_bulkdata.md) |
| USPTO assignments | `uspto_assignments.AssignmentCenterClient` | [uspto_assignments.md](references/uspto_assignments.md) |
| USPTO publications (PPUBS) full-text | `uspto_publications.PublicSearchClient` | [uspto_publications.md](references/uspto_publications.md) |
| USPTO office actions | `ip_tools.uspto_office_actions` | [uspto_office_actions.md](references/uspto_office_actions.md) |
| EPO bibliographic / family / legal events | `epo_ops.EpoOpsClient` | [epo_ops.md](references/epo_ops.md) |
| JPO application status | `jpo.JpoClient` | [jpo.md](references/jpo.md) |
| MPEP search + section lookup | `ip_tools.mpep` | [mpep.md](references/mpep.md) |
| CPC lookup / search / mapping | `ip_tools.cpc` | [cpc.md](references/cpc.md) |

## Quick Examples

### Lookup patent by number

```python
from ip_tools.google_patents import GooglePatentsClient

async with GooglePatentsClient() as client:
    patent = await client.get_patent_data("US10123456B2")
```

### Search USPTO applications

```python
from ip_tools.uspto_odp import ApplicationsClient

async with ApplicationsClient() as client:  # Requires USPTO_ODP_API_KEY
    results = await client.search(query="inventionTitle:laser", limit=25)
    for record in results.applicationBag:
        print(record.applicationNumberText, record.filingDate)
```

### Find PTAB proceedings

```python
from ip_tools.uspto_odp import PtabTrialsClient

async with PtabTrialsClient() as client:
    proceedings = await client.search_proceedings(query="patent:US10123456")
```

### Look up MPEP section

```python
from ip_tools.mpep import SearchInput, search

response = await search(SearchInput(query="obviousness rejection", per_page=10))
for hit in response.hits:
    print(hit.section_id, hit.title)
```

### Resolve a CPC symbol

```python
from ip_tools.cpc import retrieve_cpc

entry = await retrieve_cpc(symbol="H04L63/08", ancestors=True)
```

## Error Handling

All clients raise typed exceptions from `law_tools_core.exceptions`. `ApiError`
and its subclasses include a path to the log file in their string representation
so agents can inspect stacktraces without keeping them in context.

```python
from law_tools_core.exceptions import (
    LawToolsCoreError,
    NotFoundError,
    RateLimitError,
)

try:
    async with GooglePatentsClient() as client:
        patent = await client.get_patent_data("US99999999")
except NotFoundError as e:
    print(e)  # "... (HTTP 404, details: ~/.cache/ip_tools/ip_tools.log)"
except RateLimitError as e:
    if e.retry_after:
        await asyncio.sleep(e.retry_after)
except LawToolsCoreError as e:
    print(e)  # Fallback for any other typed error
```

**Exception hierarchy** (from `law_tools_core.exceptions`):

| Exception | When |
|-----------|------|
| `NotFoundError` | Resource not found (404) |
| `RateLimitError` | Rate limit exceeded (429); `retry_after` set if server supplied it |
| `AuthenticationError` | Bad or missing API credentials (401/403) |
| `ServerError` | Remote API 5xx |
| `ApiError` | Other HTTP errors (base for all HTTP-level errors; appends log path) |
| `ParseError` | Failed to parse response data |
| `ConfigurationError` | Missing API key / invalid config |
| `ValidationError` | Invalid input; also inherits `ValueError` |
| `LawToolsCoreError` | Base for all typed errors |

**Log file:** `~/.cache/ip_tools/ip_tools.log` — full tracebacks, request/response
details, debug info. Read this when concise error messages aren't enough.

## Environment Variables

| Variable | Required For |
|----------|--------------|
| `USPTO_ODP_API_KEY` | All USPTO ODP clients (Applications, PTAB, BulkData, Petitions, Office Actions) |
| `EPO_OPS_API_KEY` | EPO OPS, CPC (CPC uses EPO OPS under the hood) |
| `EPO_OPS_API_SECRET` | EPO OPS, CPC |
| `JPO_API_USERNAME` | JPO client |
| `JPO_API_PASSWORD` | JPO client |

USPTO Publications, USPTO Assignments, Google Patents, and MPEP require no API key.

## Cache Management

All clients cache HTTP responses to `~/.cache/ip_tools/` using `hishel` with a
SQLite backend and WAL pragmas. See [cache.md](references/cache.md) for TTL,
invalidation, and statistics APIs.

## Issue Reporting

**Source**: [parkerhancock/ip_tools](https://github.com/parkerhancock/ip_tools)

Report bugs with version, minimal reproduction code, and relevant API response
if applicable.

## References

- [google_patents.md](references/google_patents.md) — Full-text search, patent documents, citations
- [uspto_odp.md](references/uspto_odp.md) — Applications, PTAB, bulk data, petitions
- [uspto_applications.md](references/uspto_applications.md) — High-level applications API
- [uspto_petitions.md](references/uspto_petitions.md) — Petition decisions
- [uspto_bulkdata.md](references/uspto_bulkdata.md) — Bulk data product catalog
- [uspto_office_actions.md](references/uspto_office_actions.md) — Office action analytics
- [uspto_assignments.md](references/uspto_assignments.md) — Assignment/ownership lookup
- [uspto_publications.md](references/uspto_publications.md) — PPUBS full-text
- [epo_ops.md](references/epo_ops.md) — EPO bibliographic, family, legal status
- [jpo.md](references/jpo.md) — Japan Patent Office
- [mpep.md](references/mpep.md) — Manual of Patent Examining Procedure
- [cpc.md](references/cpc.md) — CPC classification lookup
- [cache.md](references/cache.md) — Cache management
