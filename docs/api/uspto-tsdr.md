# USPTO TSDR

Access trademark status, prosecution documents, and mark images via the
USPTO TSDR (Trademark Status & Document Retrieval) API.

## Quick Start

```python
from patent_client_agents.uspto_tsdr import TsdrClient

async with TsdrClient() as client:
    # Current status
    status = await client.get_status("97123456")
    print(f"{status.mark_text}: {status.status_description}")

    # Document list
    docs = await client.get_documents("97123456")
    for d in docs:
        print(d.document_type, d.scan_date, d.url)

    # Mark drawing image
    image_bytes = await client.get_image("97123456")
```

## Configuration

Requires `USPTO_TSDR_API_KEY`. Get one from the USPTO API Key Manager at
[account.uspto.gov/api-manager/](https://account.uspto.gov/api-manager/)
with a free MyUSPTO account — request the TSDR API product.

```bash
export USPTO_TSDR_API_KEY="…"
```

Or pass `api_key=` to the constructor:

```python
async with TsdrClient(api_key="…") as client:
    ...
```

Missing key raises `ConfigurationError` at construction.

## Rate limits

Per key, enforced by USPTO:

| Window | General | PDF / ZIP |
|---|---|---|
| Peak (5am–10pm ET) | 60 req/min | 4 req/min |
| Off-peak (10pm–5am ET) | 120 req/min | 12 req/min |

## Functions

| Function | Description |
|---|---|
| `get_status(serial_number)` | Mark text, status, dates, owners, classes, prosecution history |
| `get_status_json(serial_number)` | Lightweight JSON status payload |
| `get_last_update(serial_number)` | Last-modified timestamp |
| `get_documents(serial_number)` | List of `TsdrDocument` records |
| `download_documents_pdf(serial_number)` | All documents bundled as one PDF |
| `download_documents_zip(serial_number)` | All documents bundled as a ZIP |
| `get_image(serial_number)` | Mark drawing JPG bytes |
| `get_status_html(serial_number)` | TSDR HTML status page |
| `batch_status(serial_numbers)` | Status for a list of serial numbers in one call |

## Result shape

```python
class TrademarkStatus(BaseModel):
    serial_number: str
    registration_number: str | None
    mark_text: str | None
    mark_type: str | None
    status_code: str | None
    status_description: str | None
    status_date: str | None
    filing_date: str | None
    registration_date: str | None
    owners: list[Owner]
    goods_services: list[GoodsServices]
    prosecution_history: list[ProsecutionEvent]
```

## Usage patterns

```python
from patent_client_agents.uspto_tsdr import TsdrClient

# Batch status — single call, many serials
async with TsdrClient() as client:
    multi = await client.batch_status(["97123456", "97654321", "98000001"])
    for serial, status in multi.cases.items():
        print(serial, status.status_description)
```

## Error handling

Inherits typed exceptions from `law_tools_core`:
`NotFoundError`, `RateLimitError` (TSDR sets `retry_after`),
`AuthenticationError` (bad/missing key), `ApiError`.
