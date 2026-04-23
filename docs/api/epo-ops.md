# EPO OPS

Access the European Patent Office Open Patent Services (OPS) API.

## Quick Start

```python
from patent_client_agents.epo_ops import EpoOpsClient

async with EpoOpsClient() as client:
    # Search published patents
    results = await client.search_published("ta=machine learning")

    # Get bibliographic data
    biblio = await client.fetch_biblio("EP1234567")

    # Get patent family
    family = await client.fetch_family("EP1234567")
```

## Configuration

Requires EPO OPS credentials:

```bash
export EPO_OPS_KEY="your-consumer-key"
export EPO_OPS_SECRET="your-consumer-secret"
```

Get credentials from [developers.epo.org](https://developers.epo.org).

## Functions

| Function | Description |
|----------|-------------|
| `search_published()` | Search published patents |
| `search_families()` | Search patent families |
| `fetch_biblio()` | Get bibliographic data |
| `fetch_fulltext()` | Get full text content |
| `fetch_family()` | Get family members |
| `fetch_family_details()` | Get detailed family info |
| `fetch_legal_events()` | Get legal status events |
| `convert_number()` | Convert patent number formats |
| `number_service()` | Number lookup service |
| `download_pdf()` | Download patent PDF |

## Usage Pattern

```python
from patent_client_agents.epo_ops import (
    EpoOpsClient,
    search_published,
    fetch_biblio,
)

# Context manager (recommended)
async with EpoOpsClient() as client:
    results = await client.search_published("ta=solar")

# One-shot convenience functions
results = await search_published(query="ta=solar")
biblio = await fetch_biblio(doc_number="EP1234567")
```
