# USPTO Office Actions

Structured office action data from the USPTO Open Data Portal — rejections, citations, full text, and enriched citation metadata. Covers office actions mailed from October 2017 to 30 days prior to current date.

## Source

| | |
|---|---|
| Module | `ip_tools.uspto_office_actions` |
| Client | `OfficeActionClient` |
| Base URL | `https://api.uspto.gov` |
| Auth | `USPTO_ODP_API_KEY` (X-API-KEY header) |
| Query syntax | Solr/Lucene via form-urlencoded POST |
| Rate limits | Shared with other ODP endpoints |
| Status | Active |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/patent/oa/oa_rejections/v2/records` | Search rejection data (101/102/103/112/DP) |
| POST | `/api/v1/patent/oa/oa_citations/v2/records` | Search prior art cited in office actions |
| POST | `/api/v1/patent/oa/oa_actions/v1/records` | Search full office action text |
| POST | `/api/v1/patent/oa/enriched_cited_reference_metadata/v3/records` | Search enriched citation metadata |

All endpoints accept `criteria` (Lucene query), `start` (offset), and `rows` (limit) as form-urlencoded parameters.

## Library API

```python
from ip_tools.uspto_office_actions import OfficeActionClient

async with OfficeActionClient() as client:
    rejections = await client.search_rejections("patentApplicationNumber:16123456")
    citations = await client.search_citations("examinerCitedReferenceIndicator:true")
    oa_text = await client.search_office_action_text("patentApplicationNumber:16123456")
    enriched = await client.search_enriched_citations("countryCode:US AND kindCode:A1")
```

| Method | Returns | Description |
|--------|---------|-------------|
| `search_rejections(criteria, start=, rows=)` | `RejectionSearchResponse` | Per-claim rejection records with 101/102/103/112/DP indicators |
| `search_citations(criteria, start=, rows=)` | `CitationSearchResponse` | Prior art references cited in office actions |
| `search_office_action_text(criteria, start=, rows=)` | `OfficeActionTextSearchResponse` | Full office action text with structured sections |
| `search_enriched_citations(criteria, start=, rows=)` | `EnrichedCitationSearchResponse` | Enhanced citations with inventor names, passage locations |

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_oa_rejections` | Search structured rejection data with eligibility indicators |
| `search_oa_citations` | Search prior art references cited in office actions |
| `search_oa_text` | Retrieve full office action text |
| `search_enriched_citations` | Search enriched citation metadata with inventor names and passages |

## Common Query Patterns

```
patentApplicationNumber:16123456
hasRej103:1 AND nationalClass:438
submissionDate:[2023-01-01T00:00:00 TO 2024-12-31T23:59:59]
examinerCitedReferenceIndicator:true
countryCode:US AND kindCode:A1
```
