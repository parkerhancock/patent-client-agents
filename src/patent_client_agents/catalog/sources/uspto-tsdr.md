# USPTO TSDR (Trademark Status & Document Retrieval)

Programmatic access to U.S. trademark status, prosecution documents, and mark images via the USPTO TSDR API. Status records are returned as Pydantic models parsed from ST.96 XML; documents come back as a list of metadata records with download paths; batch lookups accept up to several hundred serial numbers per call.

## Source

| | |
|---|---|
| Module | `patent_client_agents.uspto_tsdr` |
| Client | `TsdrClient` |
| Base URL | `https://tsdrapi.uspto.gov` |
| Auth | `USPTO_TSDR_API_KEY` (header `USPTO-API-KEY`) |
| Rate limits | Peak (5am–10pm ET): 60 req/min general, 4 req/min PDF/ZIP. Off-peak: 120 / 12. |
| Status | Active |

## Authentication

Sign in to the USPTO API Key Manager at
[account.uspto.gov/api-manager/](https://account.uspto.gov/api-manager/)
with a free MyUSPTO account, select the TSDR API product, and click
"Request API key". The key is emailed and stored under your account.
Lost keys are recoverable by signing back in. USPTO support:
APIhelp@uspto.gov.

Set `USPTO_TSDR_API_KEY` in the environment, or pass `api_key=` to the
client constructor. Missing key raises `ConfigurationError` at client
construction.

## Library API

```python
from patent_client_agents.uspto_tsdr import TsdrClient

async with TsdrClient() as client:
    status = await client.get_status("97123456")
    print(f"{status.mark_text}: {status.status_description}")

    docs = await client.get_documents("97123456")
    image_bytes = await client.get_image("97123456")
```

### Methods

| Method | Description |
|---|---|
| `get_status(serial_number)` | Full status (mark text, dates, owners, classes, prosecution history) |
| `get_status_json(serial_number)` | Lightweight JSON status payload |
| `get_last_update(serial_number)` | Last-modified timestamp (derived from most recent event) |
| `get_documents(serial_number)` | List `TsdrDocument` records with download paths |
| `download_documents_pdf(serial_number)` | Bundle all documents as a single PDF (PDF rate limit applies) |
| `download_documents_zip(serial_number)` | Bundle as a ZIP (PDF/ZIP rate limit applies) |
| `get_image(serial_number)` | Mark drawing JPG bytes |
| `get_status_html(serial_number)` | TSDR HTML status page |
| `batch_status(serial_numbers)` | Status for multiple serial numbers in one call |

## MCP Tools

| Tool | Description |
|---|---|
| `get_trademark_status` | Status, mark text, filing/registration dates for one serial |
| `get_trademark_documents` | List prosecution documents for one serial |
| `get_trademark_last_update` | Last-modified timestamp |
| `batch_trademark_status` | Status for a JSON array of serial numbers |
