# USPTO Patent Publications

Patent Public Search (PPUBS) for searching and downloading US patent publications, patent grants, and OCR-scanned patents.

## Source

| | |
|---|---|
| Module | `patent_client_agents.uspto_publications` |
| Client | `PublicSearchClient` |
| Base URL | `https://ppubs.uspto.gov` |
| Auth | None (session auto-managed) |
| Rate limits | Dynamic; 429 responses include `x-rate-limit-retry-after-seconds` header |
| Status | Active |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/users/me/session` | Acquire session and access token |
| POST | `/api/searches/counts` | Get result counts for a query |
| POST | `/api/searches/searchWithBeFamily` | Execute search with family grouping |
| GET | `/api/patents/highlight/{guid}` | Get full document by GUID |
| POST | `/api/print/imageviewer` | Request PDF generation |
| POST | `/api/print/print-process` | Poll print job status |
| GET | `/api/print/save/{pdfName}` | Download generated PDF |

## Library API

```python
from patent_client_agents.uspto_publications import PublicSearchClient

async with PublicSearchClient() as client:
    page = await client.search_biblio(query="machine learning", limit=25)
    doc = await client.get_document(guid, source="US-PGPUB")
    pdf = await client.download_pdf(doc)
```

| Method | Returns | Description |
|--------|---------|-------------|
| `search_biblio(query, start=0, limit=500, sort="date_publ desc", sources=["US-PGPUB","USPAT","USOCR"])` | `PublicSearchBiblioPage` | Search patents by keyword with Boolean support |
| `get_document(guid, source=)` | `PublicSearchDocument` | Get full document metadata by GUID and source |
| `download_pdf(document)` | `bytes` | Download document as PDF bytes |
| `download_pdf_base64(document)` | `str` | Download document as base64-encoded PDF |
| `resolve_document_by_publication_number(publication_number)` | `PublicSearchDocument` | Resolve a publication number to its full document |

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_patent_publications` | Search USPTO patent publications by keyword |
| `get_patent_publication` | Get bibliographic data for a publication number |
| `download_publication_pdf` | Download a patent publication as PDF |
| `resolve_publication_number` | Resolve a partial publication number to full metadata |
