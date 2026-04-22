# JPO (Japan Patent Office)

> **DISABLED** -- Pending credential approval from JPO. This module is fully implemented but has no active MCP tools until credentials are obtained.

Patent, design, and trademark prosecution data from the Japan Patent Office API. Covers application progress, cited documents, divisional/priority information, registration status, and J-PlatPat URL resolution.

## Source

| | |
|---|---|
| Module | `ip_tools.jpo` |
| Client | `JpoClient` |
| Base URL | `https://ip-data.jpo.go.jp` |
| Auth | `JPO_API_USERNAME` + `JPO_API_PASSWORD` (OAuth2 password grant) |
| Rate limits | 10 requests per minute (sliding window) |
| Status | **Disabled** (pending credential approval) |

## Library API

```python
from ip_tools.jpo import JpoClient

async with JpoClient() as client:
    progress = await client.get_patent_progress("2020123456")
    cited = await client.get_patent_cited_documents("2020123456")
```

### Patent APIs

| Method | Returns | Description |
|--------|---------|-------------|
| `get_patent_progress(app_number)` | `PatentProgressData \| None` | Full patent progress/status |
| `get_patent_progress_simple(app_number)` | `SimplifiedPatentProgressData \| None` | Simplified progress |
| `get_patent_divisional_info(app_number)` | `list[DivisionalApplicationInfo]` | Divisional applications |
| `get_patent_priority_info(app_number)` | `list[PriorityInfo]` | Priority claims |
| `get_patent_applicant_by_code(code)` | `list[ApplicantAttorney]` | Applicant lookup by code |
| `get_patent_applicant_by_name(name)` | `list[ApplicantAttorney]` | Applicant lookup by name |
| `get_patent_number_reference(kind, number)` | `list[NumberReference]` | Cross-reference app/pub/reg numbers |
| `get_patent_application_documents(app_number)` | `ApplicationDocumentsData \| None` | Filed documents |
| `get_patent_mailed_documents(app_number)` | `ApplicationDocumentsData \| None` | Office actions and decisions |
| `get_patent_refusal_notices(app_number)` | `ApplicationDocumentsData \| None` | Refusal notices |
| `get_patent_cited_documents(app_number)` | `list[CitedDocumentInfo]` | Cited documents |
| `get_patent_registration_info(app_number)` | `RegistrationInfo \| None` | Registration data |
| `get_patent_jplatpat_url(app_number)` | `str \| None` | J-PlatPat fixed URL |
| `get_patent_pct_national_number(kind, number)` | `PctNationalPhaseData \| None` | PCT national phase lookup |

### Design APIs

Mirrors patent APIs with `get_design_*` prefix (progress, priority, applicant, number reference, documents, registration, J-PlatPat URL).

### Trademark APIs

Mirrors patent APIs with `get_trademark_*` prefix (progress, priority, applicant, number reference, documents, registration, J-PlatPat URL).

## MCP Tools

None (0 active tools -- pending credential approval).
