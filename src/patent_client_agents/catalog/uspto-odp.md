# USPTO Open Data Portal

Provides access to USPTO patent application data, prosecution documents, patent families, assignments, PTAB trial proceedings (IPR/PGR/CBM), PTAB appeals, PTAB interferences, petition decisions, and bulk data products via the USPTO Open Data Portal REST API.

## Source

| | |
|---|---|
| Module | `patent_client_agents.uspto_odp` (plus `uspto_applications`, `uspto_bulkdata`, `uspto_petitions`, `uspto_office_actions` — all share the ODP base client) |
| Client | `UsptoOdpClient` |
| Base URL | `https://api.uspto.gov` |
| Auth | `USPTO_ODP_API_KEY` |
| Rate limits | 60 req/min per key (USPTO-enforced) |
| Status | Active |

## ODP version tracking

| Field | Value |
|---|---|
| ODP release tracked | **3.6** (2026-04-10) |
| Last verified against release notes | 2026-04-14 |
| Release notes | https://data.uspto.gov/support/release |

When checking for updates: compare the current USPTO release number against the **tracked** version above. Changes most likely to affect us: field renames on `applicationMetaData`/`assignmentBag`/`correspondenceAddressBag`, new required request fields, base URL or auth changes, and PTAB/OA endpoint path changes.

## Authentication

Requires `USPTO_ODP_API_KEY` environment variable. Get a free API key at [developer.uspto.gov](https://developer.uspto.gov).

## Rate Limits

USPTO enforces per-key rate limits. The client uses automatic retry with backoff.

## API Endpoints

- `https://api.uspto.gov`

## Library API

```python
from patent_client_agents.uspto_odp import UsptoOdpClient

async with UsptoOdpClient() as client:
    result = await client.search_applications(query="machine learning")
    app = await client.get_application("16123456")
```

### Methods

| Method | Description |
|--------|-------------|
| `search_applications(query, fields, filters, sort, limit, offset, ...)` | Search patent applications by keyword or structured filters |
| `get_application(application_number)` | Get full metadata for a patent application |
| `get_documents(application_number)` | List file-wrapper documents (office actions, responses, etc.) |
| `download_document(application_number, document_identifier)` | Download a prosecution document PDF |
| `download_documents(application_number, document_codes, ...)` | Download multiple file-wrapper documents |
| `get_family(identifier)` | Build a patent family graph (continuations, divisionals) |
| `get_assignment(application_number)` | Get assignment and ownership history |
| `search_trial_proceedings(query, ...)` | Search PTAB trial proceedings (IPR, PGR, CBM) |
| `get_trial_proceeding(trial_number)` | Get a single PTAB trial proceeding |
| `search_trial_decisions(query, ...)` | Search PTAB trial decisions |
| `get_trial_decision(document_identifier)` | Get a single PTAB trial decision |
| `get_trial_decisions_by_trial(trial_number)` | Get all decisions for a PTAB trial |
| `search_trial_documents(query, ...)` | Search PTAB trial documents |
| `get_trial_document(document_identifier)` | Get a single PTAB trial document |
| `get_trial_documents_by_trial(trial_number)` | Get all documents for a PTAB trial |
| `search_appeal_decisions(query, ...)` | Search PTAB ex parte appeal decisions |
| `get_appeal_decision(document_identifier)` | Get a single PTAB appeal decision |
| `get_appeal_decisions_by_number(appeal_number)` | Get all decisions for a PTAB appeal |
| `search_interference_decisions(query, ...)` | Search PTAB interference decisions |
| `get_interference_decision(document_identifier)` | Get a single PTAB interference decision |
| `get_interference_decisions_by_number(interference_number)` | Get all decisions for a PTAB interference |
| `search_petitions(q, filters, ...)` | Search petition decisions |
| `get_petition(petition_decision_record_identifier)` | Get a specific petition decision |
| `search_bulk_datasets(query, ...)` | Search bulk data products |
| `get_bulk_dataset_product(product_identifier)` | Get a specific bulk data product with file listing |

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_applications` | Search USPTO patent applications by keyword or application number |
| `get_application` | Get full metadata for a patent application |
| `list_file_history` | List prosecution file-history documents with available formats per document |
| `get_file_history_item` | Get a file-history item's content (format="auto" returns readable text via XML → PDF text layer → OCR; "pdf" returns base64; "xml" returns raw ST.96) |
| `get_patent_family` | Get patent family relationships (continuations, divisionals) |
| `get_patent_assignment` | Get assignment and ownership history for an application |
| `get_patent_claims` | Structured patent claims from USPTO grant XML (falls back to Google Patents for non-US or when XML unavailable) |
| `search_ptab_proceedings` | Search PTAB trial proceedings (IPR, PGR, CBM, DER) |
| `get_ptab_proceeding` | Get details for a specific PTAB trial proceeding |
| `search_ptab_decisions` | Search PTAB trial decisions |
| `get_ptab_decisions_by_trial` | Get all decisions for a specific PTAB trial |
| `get_ptab_document` | Get a single PTAB trial document by identifier |
| `get_ptab_documents_by_trial` | Get all documents filed in a PTAB trial proceeding |
| `download_ptab_document` | Download a PTAB trial document PDF |
| `search_ptab_documents` | Search PTAB trial documents across all proceedings |
| `get_ptab_decision` | Get a single PTAB trial decision by document identifier |
| `search_ptab_appeals` | Search PTAB ex parte appeal decisions |
| `get_appeal_decisions` | Get appeal decisions for a specific application or appeal number |
| `get_appeal_decision` | Get a single PTAB appeal decision by document identifier |
| `search_ptab_interferences` | Search PTAB interference decisions |
| `get_interference_decision` | Get a single PTAB interference decision |
| `get_interference_decisions` | Get all decisions for a specific PTAB interference |
| `search_petitions` | Search USPTO petition decisions |
| `get_petition` | Get details for a specific petition decision |
| `search_bulk_datasets` | Search available USPTO bulk data products |
| `get_bulk_dataset` | Get details and file listing for a bulk data product |
