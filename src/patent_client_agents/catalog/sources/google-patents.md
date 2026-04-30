# Google Patents

Scrapes patent data from Google Patents, providing full-text patent documents, structured claims, figures, citations, and family information. Data is parsed from the Google Patents HTML pages and returned as structured Pydantic models.

## Source

| | |
|---|---|
| Module | `patent_client_agents.google_patents` |
| Client | `GooglePatentsClient` |
| Base URL | `https://patents.google.com` |
| Auth | None |
| Rate limits | Not published; aggressive scraping can trigger CAPTCHAs |
| Status | Active |

## Authentication

None required. Google Patents is a free public resource.

## Rate Limits

No documented limits, but aggressive scraping may trigger CAPTCHAs. The client uses exponential backoff with jitter via tenacity.

## API Endpoints

- `https://patents.google.com`

## Library API

```python
from patent_client_agents.google_patents import GooglePatentsClient

async with GooglePatentsClient() as client:
    patent = await client.get_patent_data("US10123456B2")
    print(patent.title)
    print(patent.abstract)
```

### Methods

| Method | Description |
|--------|-------------|
| `search_patents(keywords, cpc_codes, inventors, assignees, ...)` | Search patents by keyword, CPC code, inventor, assignee, date range, and country |
| `get_patent_data(patent_number)` | Get full patent data including title, abstract, claims, description, and citations |
| `get_patent_details(patent_number)` | Get structured metadata: filing date, grant date, priority date, assignee, inventors |
| `get_patent_claims(patent_number)` | Get structured claims with dependency information |
| `get_structured_claim_limitations(patent_number)` | Get claim limitations broken down by claim number as a dict of limitation lists |
| `get_patent_figures(patent_number)` | Get patent figure images with callout annotations |
| `download_patent_pdf(patent_number)` | Download the patent PDF as bytes |

### `expiration_date` fallback

Google Patents doesn't populate `expiration_date` for newly-granted patents
(typical for grants in the last ~6 months). When this happens,
`get_patent_data` falls back to `priority_date + 20 years` as a rough
estimate and sets `expiration_estimated=True` on the returned `PatentData`.

**The estimate is approximate** — refine via USPTO ODP
(`applicationFilingDate + 20y + patentTermAdjustmentData.adjustmentTotalQuantity`,
walking `parentContinuityBag`) before relying on the date for legally
significant work.

## MCP Tools

8 tools. `get_patent_claims` routes through USPTO ODP with a Google fallback — documented on [uspto-odp.md](uspto-odp.md).

| Tool | Description |
|------|-------------|
| `search_google_patents` | Search Google Patents by keyword, inventor, assignee, or CPC code |
| `get_patent` | Get full patent data including title, abstract, claims, description, and citations |
| `get_patent_details` | Get structured patent details: dates, assignee, inventors |
| `get_patent_figures` | Get patent figure images with callout annotations |
| `get_patent_claims(patent_number, view)` | Unified claims tool. Cascades USPTO ODP grant XML → Google Patents for full coverage. Returns canonical shape per claim: `{claim_number, limitations: [{text, depth}], claim_text, claim_type, depends_on}`. `view` = `full` (default), `independent_only`, or `limitations` (compact mapping for infringement charts). |
| `get_forward_citations` | Get patents that cite the given patent (publication_number, assignee, title, examiner_cited flag); optional family-level citations |
| `download_patent_pdf(patent_number)` | Unified PDF download. Cascades Google Patents → PPUBS → EPO OPS until one source returns bytes. Response includes a `source` field indicating which backend served the PDF. |
