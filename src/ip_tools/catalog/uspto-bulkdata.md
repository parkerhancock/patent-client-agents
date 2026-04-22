# USPTO Bulk Data

Programmatic access to USPTO's bulk data product catalog (weekly patent
grants, weekly applications, assignments, etc.). Wraps the
`uspto_odp.BulkDataClient` with convenience functions; for multi-call
workflows use the client directly.

## Source

| | |
|---|---|
| Module | `ip_tools.uspto_bulkdata` |
| Client | Uses `ip_tools.uspto_odp.BulkDataClient` |
| Base URL | `https://api.uspto.gov` |
| Auth | `USPTO_ODP_API_KEY` |
| Rate limits | 60 req/min per key (shared with USPTO ODP) |
| Status | Active |

## Authentication

Same as [uspto-odp.md](uspto-odp.md). The product download URIs themselves
require the API key attached to each download request — use `BulkDataClient`
directly to retrieve content, not the bare URI from the manifest.

## Library API

```python
from ip_tools.uspto_bulkdata import search_products, get_product

response = await search_products(query="grant")
for product in response.bulkDataBag:
    print(product.productIdentifier, product.productTitle)

product = await get_product("PTGRXML")
for f in product.productFiles:
    print(f.fileName, f.fileDownloadURI)
```

### Methods

| Method | Description |
|---|---|
| `search_products(query, ...)` | Enumerate available bulk data products |
| `get_product(product_identifier)` | Product metadata + download manifest |

Bundled reference data at `src/ip_tools/uspto_bulkdata/data/`:

- `2025_bulkdata_product_guide.md` — current product catalog
- `bulkdata-response-schema.json`, `patent-data-schema.json`,
  `petition-decision-schema.json` — JSON schemas for common products

## MCP Tools

Exposed via downstream MCP packaging.

| Tool | Description |
|---|---|
| `search_bulk_datasets` | Search available USPTO bulk data products |
| `get_bulk_dataset` | Get a product's file listing and metadata |

## Related Docs

- [uspto-odp.md](uspto-odp.md) — underlying client + auth
