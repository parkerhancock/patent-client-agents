# USPTO Publications

Access USPTO Patent Public Search (PPUBS) for searching and retrieving published patents and applications.

## Quick Start

```python
from patent_client_agents.uspto_publications import PublicSearchClient

async with PublicSearchClient() as client:
    # Search publications
    results = await client.search_biblio(query="machine learning")

    # Get document details
    doc = await client.get_document(guid="...", source="US-PGPUB")

    # Download PDF
    pdf_bytes = await client.download_pdf(doc)
```

## Functions

| Function | Description |
|----------|-------------|
| `search()` | Search USPTO Patent Public Search |
| `get_document()` | Get document by GUID and source |
| `download_pdf()` | Download patent as PDF |
| `resolve_publication()` | Resolve publication number to document |
| `resolve_and_download_pdf()` | Resolve and download PDF in one call |

## Sources

The `source` parameter accepts:

| Source | Description |
|--------|-------------|
| `US-PGPUB` | Published applications |
| `USPAT` | Granted patents |
| `USOCR` | OCR'd historical patents |

## Usage Pattern

```python
from patent_client_agents.uspto_publications import (
    PublicSearchClient,
    search,
    download_pdf,
)

# Context manager (recommended)
async with PublicSearchClient() as client:
    results = await client.search_biblio(query="AI")

# One-shot convenience function
results = await search(query="AI")
pdf = await download_pdf(publication_number="US10000000B2")
```
