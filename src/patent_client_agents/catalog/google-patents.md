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

## MCP Tools

8 tools. `get_patent_claims` routes through USPTO ODP with a Google fallback — documented on [uspto-odp.md](uspto-odp.md).

| Tool | Description |
|------|-------------|
| `search_google_patents` | Search Google Patents by keyword, inventor, assignee, or CPC code |
| `get_patent` | Get full patent data including title, abstract, claims, description, and citations |
| `get_patent_details` | Get structured patent details: dates, assignee, inventors |
| `get_patent_figures` | Get patent figure images with callout annotations |
| `get_structured_claim_limitations` | Get structured claim limitations broken down by claim number |
| `get_independent_claims` | Get only independent claims for a patent (filters out dependent claims) |
| `get_forward_citations` | Get patents that cite the given patent (publication_number, assignee, title, examiner_cited flag); optional family-level citations |
| `download_patent_pdf` | Download a patent PDF and save to a temporary file |
