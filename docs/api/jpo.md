# JPO (Japan Patent Office)

Access the Japan Patent Office Patent Information Retrieval APIs for patents, designs, and trademarks.

## Quick Start

```python
from patent_client_agents.jpo import JpoClient

async with JpoClient() as client:
    # Get patent progress/status
    progress = await client.get_patent_progress("2020123456")

    # Get trademark information
    tm = await client.get_trademark_progress("2021098765")

    # Cross-reference numbers
    refs = await client.get_patent_number_reference("01", "2020123456")
```

## Configuration

Requires JPO-issued API credentials:

```bash
export JPO_API_USERNAME="your-jpo-username"
export JPO_API_PASSWORD="your-jpo-password"
```

!!! warning "Registration Required"
    JPO API access requires separate registration (not the same as J-PlatPat account).
    Contact: PA0630@jpo.go.jp

## Rate Limits

| Limit Type | Value |
|------------|-------|
| Requests per minute | 10 |
| Daily limit (most endpoints) | 200 |
| Daily limit (number reference) | 50 |

The client automatically enforces rate limiting via a sliding window.

## Patent Functions

| Function | Description |
|----------|-------------|
| `get_patent_progress()` | Full application status with classifications, procedures |
| `get_patent_progress_simple()` | Simplified status (fewer API credits) |
| `get_patent_divisional_info()` | Divisional/continuation relationships |
| `get_patent_priority_info()` | Priority claims |
| `get_patent_applicant_by_code()` | Applicant name from code |
| `get_patent_applicant_by_name()` | Applicant code from name |
| `get_patent_number_reference()` | Cross-reference app/pub/reg numbers |
| `get_patent_application_documents()` | Filed documents (amendments, responses) |
| `get_patent_mailed_documents()` | Office actions and decisions |
| `get_patent_refusal_notices()` | Notices of reasons for refusal |
| `get_patent_cited_documents()` | Prior art citations |
| `get_patent_registration_info()` | Registration details |
| `get_patent_jplatpat_url()` | Direct J-PlatPat link |
| `get_patent_pct_national_number()` | National phase from PCT number |

## Design Functions

| Function | Description |
|----------|-------------|
| `get_design_progress()` | Design application status |
| `get_design_progress_simple()` | Simplified design status |
| `get_design_priority_info()` | Design priority claims |
| `get_design_applicant_by_code()` | Applicant name from code |
| `get_design_applicant_by_name()` | Applicant code from name |
| `get_design_number_reference()` | Cross-reference numbers |
| `get_design_application_documents()` | Filed documents |
| `get_design_mailed_documents()` | Office actions |
| `get_design_refusal_notices()` | Refusal notices |
| `get_design_registration_info()` | Registration details |
| `get_design_jplatpat_url()` | Direct J-PlatPat link |

## Trademark Functions

| Function | Description |
|----------|-------------|
| `get_trademark_progress()` | Trademark application status |
| `get_trademark_progress_simple()` | Simplified trademark status |
| `get_trademark_priority_info()` | Trademark priority claims |
| `get_trademark_applicant_by_code()` | Applicant name from code |
| `get_trademark_applicant_by_name()` | Applicant code from name |
| `get_trademark_number_reference()` | Cross-reference numbers |
| `get_trademark_application_documents()` | Filed documents |
| `get_trademark_mailed_documents()` | Office actions |
| `get_trademark_refusal_notices()` | Refusal notices |
| `get_trademark_registration_info()` | Registration details |
| `get_trademark_jplatpat_url()` | Direct J-PlatPat link |

## Usage Examples

### Get Full Patent Prosecution History

```python
from patent_client_agents.jpo import JpoClient

async with JpoClient() as client:
    app_num = "2020123456"

    # Basic status
    progress = await client.get_patent_progress(app_num)
    print(f"Title: {progress.invention_title}")
    print(f"Filing Date: {progress.filing_date}")
    print(f"IPC: {[c.ipc_code for c in progress.ipc_classification]}")

    # Prosecution documents
    docs = await client.get_patent_application_documents(app_num)
    for doc in docs.documents:
        print(f"  {doc.receipt_date}: {doc.document_name}")

    # Office actions
    oas = await client.get_patent_mailed_documents(app_num)
    for oa in oas.documents:
        print(f"  {oa.sending_date}: {oa.document_name}")
```

### Cross-Reference Patent Numbers

```python
from patent_client_agents.jpo import JpoClient, NumberType

async with JpoClient() as client:
    # From application number, get publication and registration
    refs = await client.get_patent_number_reference(
        NumberType.APPLICATION,
        "2020123456"
    )
    for ref in refs:
        print(f"App: {ref.application_number}")
        print(f"Pub: {ref.publication_number}")
        print(f"Reg: {ref.registration_number}")
```

### Find Applicant Information

```python
from patent_client_agents.jpo import JpoClient

async with JpoClient() as client:
    # Search by name (partial match supported)
    applicants = await client.get_patent_applicant_by_name("[出願人名]")
    for a in applicants:
        print(f"{a.applicant_attorney_cd}: {a.name}")
```

### One-Shot Convenience Functions

```python
from patent_client_agents.jpo import get_patent_progress, get_patent_jplatpat_url

# No need for context manager - creates client automatically
progress = await get_patent_progress("2020123456")

# Get direct link to J-PlatPat
url = await get_patent_jplatpat_url("2020123456")
print(f"View on J-PlatPat: {url}")
```

## Number Formats

| Type | Format | Example |
|------|--------|---------|
| Application | 10 digits | `2020123456` |
| Publication | Year-Number | `2021-123456` |
| Registration | 7 digits | `7123456` |
| PCT Application | PCT/JP format | `PCT/JP2020/012345` |

## MCP Server

The `jpo-mcp` server exposes all functions as MCP tools:

```bash
jpo-mcp  # Starts the MCP server
```

### Available Tools

- `jpo.patent.get_progress` - Get patent application progress
- `jpo.patent.get_progress_simple` - Get simplified patent progress
- `jpo.patent.get_divisional_info` - Get divisional application info
- `jpo.patent.get_applicant_by_code` - Get applicant by code
- `jpo.patent.get_applicant_by_name` - Get applicant by name
- `jpo.patent.get_number_reference` - Cross-reference numbers
- `jpo.patent.get_application_documents` - Get filed documents
- `jpo.patent.get_mailed_documents` - Get office actions
- `jpo.patent.get_refusal_notices` - Get refusal notices
- `jpo.patent.get_cited_documents` - Get citations
- `jpo.patent.get_registration_info` - Get registration info
- `jpo.patent.get_jplatpat_url` - Get J-PlatPat URL
- `jpo.patent.get_pct_national_number` - Get national phase number
- `jpo.design.*` - Design equivalents
- `jpo.trademark.*` - Trademark equivalents

## API Reference

::: patent_client_agents.jpo.JpoClient
    options:
      show_root_heading: true
      members:
        - get_patent_progress
        - get_patent_progress_simple
        - get_patent_number_reference
