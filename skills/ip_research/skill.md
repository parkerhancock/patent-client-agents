---
name: ip_research
description: |
  IP data research tools for patents, trademarks, and applications. Use when:
  - Looking up patents by number (US, EP, WO, JP, etc.)
  - Searching patent databases by keyword, assignee, inventor, or classification
  - Getting patent family, citation, or legal status information
  - Checking USPTO application status, file wrapper, or PTAB proceedings
  - Downloading bulk USPTO data products
  - Finding patent assignments or ownership history
---

# IP Research

Async Python clients for patent data. All clients use `async with` context managers.

## Routing

| Task | Client | Reference |
|------|--------|-----------|
| Patent lookup/search | `GooglePatentsClient` | [google_patents.md](references/google_patents.md) |
| USPTO application status | `ApplicationsClient` | [uspto_odp.md](references/uspto_odp.md) |
| USPTO PTAB (IPR/PGR) | `PtabTrialsClient` | [uspto_odp.md](references/uspto_odp.md) |
| USPTO bulk data | `BulkDataClient` | [uspto_odp.md](references/uspto_odp.md) |
| USPTO assignments | `UsptoAssignmentsClient` | [uspto_assignments.md](references/uspto_assignments.md) |
| EPO bibliographic/family | `EpoOpsClient` | [epo_ops.md](references/epo_ops.md) |
| JPO application status | `JpoClient` | [jpo.md](references/jpo.md) |

## Quick Examples

### Lookup patent by number

```python
from ip_tools.google_patents import GooglePatentsClient

async with GooglePatentsClient() as client:
    patent = await client.get_patent_data("US10123456B2")
```

### Search patents

```python
from ip_tools.google_patents import GooglePatentsClient

async with GooglePatentsClient() as client:
    results = await client.search_patents(
        keywords="machine learning",
        assignee="Google",
        limit=25
    )
```

### Check application status

```python
from ip_tools.uspto_odp import ApplicationsClient

async with ApplicationsClient() as client:  # Requires USPTO_ODP_API_KEY
    app = await client.get("16123456")
    docs = await client.get_documents("16123456")
```

### Find PTAB proceedings

```python
from ip_tools.uspto_odp import PtabTrialsClient

async with PtabTrialsClient() as client:
    results = await client.search_proceedings(query="patent:US10123456")
```

## Environment Variables

| Variable | Required For |
|----------|--------------|
| `USPTO_ODP_API_KEY` | All ODP clients (Applications, PTAB, BulkData, Petitions) |
| `EPO_OPS_API_KEY` | EPO OPS client |
| `EPO_OPS_API_SECRET` | EPO OPS client |
| `JPO_API_USERNAME` | JPO client |
| `JPO_API_PASSWORD` | JPO client |

## Cache Management

All clients cache to `~/.cache/ip_tools/`. See [cache.md](references/cache.md) for TTL, invalidation, and statistics APIs.

## Issue Reporting

**Source**: [parkerhancock/ip_tools](https://github.com/parkerhancock/ip_tools)

Report bugs with: version, minimal reproduction code, and API response if applicable.

## References

- [google_patents.md](references/google_patents.md) - Full-text search, patent documents, citations
- [uspto_odp.md](references/uspto_odp.md) - Applications, PTAB, bulk data, petitions
- [uspto_assignments.md](references/uspto_assignments.md) - Assignment/ownership lookup
- [epo_ops.md](references/epo_ops.md) - EPO bibliographic, family, legal status
- [jpo.md](references/jpo.md) - Japan Patent Office APIs
- [cache.md](references/cache.md) - Cache management APIs
