# USPTO Bulk Data

Access USPTO bulk data products for downloading large datasets.

## Quick Start

```python
from patent_client_agents.uspto_bulkdata import UsptoOdpClient

async with UsptoOdpClient() as client:
    # Search available products
    results = await client.search_bulk_datasets(query="grant")

    # Get product details with files
    product = await client.get_bulk_dataset_product(
        "grantTar",
        include_files=True,
        latest_only=True
    )
```

## Configuration

Requires a USPTO ODP API key:

```bash
export USPTO_ODP_API_KEY="your-api-key"
```

## Functions

| Function | Description |
|----------|-------------|
| `search_products()` | Search available bulk data products |
| `get_product()` | Get details for a specific product |

## Usage Pattern

```python
from patent_client_agents.uspto_bulkdata import search_products, get_product

# One-shot convenience functions
results = await search_products(q="grant")
product = await get_product("grantTar", include_files=True)
```
