# USPTO Petitions

Access USPTO petition decision data via the Open Data Portal.

## Quick Start

```python
from ip_tools.uspto_petitions import UsptoOdpClient

async with UsptoOdpClient() as client:
    # Search petition decisions
    results = await client.search_petitions(q="continuation")

    # Get specific petition
    petition = await client.get_petition("12345", include_documents=True)
```

## Configuration

Requires a USPTO ODP API key:

```bash
export USPTO_ODP_API_KEY="your-api-key"
```

## Functions

| Function | Description |
|----------|-------------|
| `search_petitions()` | Search petition decisions |
| `get_petition()` | Get a specific petition by identifier |
| `download_petitions()` | Download petition data |

## Usage Pattern

```python
from ip_tools.uspto_petitions import search_petitions, get_petition

# One-shot convenience functions
results = await search_petitions(q="revival")
petition = await get_petition("12345", include_documents=True)
```
