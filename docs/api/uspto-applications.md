# USPTO Applications

Access patent application data and PTAB proceedings via the USPTO Open Data Portal (ODP).

## Quick Start

```python
from patent_client_agents.uspto_applications import UsptoOdpClient

async with UsptoOdpClient() as client:
    # Search applications
    results = await client.search_applications(query="artificial intelligence")

    # Get application details
    app = await client.get_application("16123456")

    # Search PTAB trials
    trials = await client.search_trial_proceedings(query="patent owner")
```

## Configuration

Requires a USPTO ODP API key:

```bash
export USPTO_ODP_API_KEY="your-api-key"
```

Get your API key from [developer.uspto.gov](https://developer.uspto.gov).

## Client

The `UsptoOdpClient` is re-exported from `uspto_odp_mcp.client`. See the source for full method documentation.

## Application Functions

| Function | Description |
|----------|-------------|
| `search_applications()` | Search USPTO patent applications |
| `get_application()` | Get application by number |
| `list_documents()` | List documents for an application |
| `get_family()` | Get patent family data |

## PTAB Trial Functions

| Function | Description |
|----------|-------------|
| `search_trial_proceedings()` | Search PTAB trials (IPR, PGR, CBM, DER) |
| `get_trial_proceeding()` | Get trial by number |
| `search_trial_decisions()` | Search trial decisions |
| `get_trial_decisions_by_trial()` | Get decisions for a trial |
| `search_trial_documents()` | Search trial documents |
| `get_trial_documents_by_trial()` | Get documents for a trial |

## PTAB Appeal Functions

| Function | Description |
|----------|-------------|
| `search_appeal_decisions()` | Search ex parte appeal decisions |
| `get_appeal_decisions_by_number()` | Get decisions by appeal number |

## PTAB Interference Functions

| Function | Description |
|----------|-------------|
| `search_interference_decisions()` | Search interference decisions |
| `get_interference_decisions_by_number()` | Get decisions by interference number |

## Usage Pattern

All functions support the standard async context manager pattern:

```python
from patent_client_agents.uspto_applications import (
    UsptoOdpClient,
    search_applications,
    get_application,
)

# Context manager (recommended)
async with UsptoOdpClient() as client:
    results = await client.search_applications(query="AI")

# One-shot convenience function
results = await search_applications(q="AI")
```
