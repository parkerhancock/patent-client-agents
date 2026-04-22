# EPO Open Patent Services

Provides access to the European Patent Office Open Patent Services (OPS) API for searching published patents, retrieving bibliographic data, full text (claims and descriptions), patent family information, legal events, CPC classification data, and downloading patent PDFs.

## Source

| | |
|---|---|
| Module | `ip_tools.epo_ops` |
| Client | `EpoOpsClient` |
| Base URL | `https://ops.epo.org/3.2` |
| Auth | `EPO_OPS_API_KEY` + `EPO_OPS_API_SECRET` (aliases: `EPO_API_KEY`, `EPO_API_SECRET`) |
| Rate limits | Hourly + weekly quotas; ~4 GB/week on the free tier |
| Status | Active |

## Authentication

Requires `EPO_OPS_API_KEY` and `EPO_OPS_API_SECRET` environment variables. Register for free credentials at [developers.epo.org](https://developers.epo.org).

## Rate Limits

EPO enforces hourly and weekly quotas. The client reports quota usage in error headers (X-IndividualQuotaPerHour-Used, X-RegisteredQuotaPerWeek-Used). 403 responses indicate rate limiting or quota exceeded.

## API Endpoints

- `https://ops.epo.org/3.2`

## Library API

```python
from ip_tools.epo_ops import EpoOpsClient

client = EpoOpsClient(api_key="...", api_secret="...")
async with client:
    results = await client.search_published(query="ta=machine learning")
    biblio = await client.fetch_biblio(number="EP1234567A1")
```

### Methods

| Method | Description |
|--------|-------------|
| `search_published(query, range_begin, range_end)` | Search published patents using CQL query syntax |
| `search_families(query, range_begin, range_end)` | Search patent families, grouping results by family ID |
| `fetch_biblio(number, doc_type, fmt)` | Get bibliographic data for a patent document |
| `fetch_fulltext(number, section, doc_type, fmt)` | Get full text (claims or description) for a patent |
| `fetch_family(number, doc_type, fmt, constituents)` | Get INPADOC patent family members |
| `fetch_legal_events(number, doc_type, fmt)` | Get legal status events for a patent |
| `convert_number(number, input_format, output_format)` | Convert patent numbers between formats (original, docdb, epodoc) |
| `retrieve_cpc(symbol, depth, ancestors, navigation)` | Look up a CPC classification symbol with hierarchy |
| `search_cpc(query, range_begin, range_end)` | Search CPC classifications by keyword |
| `map_classification(input_schema, symbol, output_schema)` | Map classifications between CPC, IPC, and USCLS |
| `fetch_cpc_media(media_id, accept)` | Fetch CPC media resources (images, etc.) |
| `fetch_cpci_biblio(number, doc_type, fmt, condensed)` | Get CPC classification from bibliographic data |
| `download_pdf(number, doc_type, fmt)` | Download a patent PDF assembled from page images |

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_epo_patents` | Search published patents via EPO OPS using CQL syntax |
| `get_epo_cql_help` | CQL field reference for building complex `search_epo_patents` queries |
| `get_epo_biblio` | Get bibliographic data for a patent from EPO OPS |
| `get_epo_fulltext` | Get full text (description and claims) of a patent |
| `get_epo_family` | Get patent family members (INPADOC family) |
| `get_epo_legal_events` | Get legal status events for a patent |
| `search_epo_families` | Search patent families via EPO OPS using CQL syntax |
| `convert_epo_number` | Convert a patent number between EPO formats |
| `download_epo_pdf` | Download a patent PDF from EPO OPS |
| `lookup_cpc` | Look up a CPC classification symbol to get its title and hierarchy |
| `map_cpc_classification` | Map a patent classification between CPC, IPC, and USCLS |
| `search_cpc` | Search CPC classifications by keyword |
