# JPO

Japan Patent Office API for patent, design, and trademark data.

**Required**: `JPO_API_USERNAME` and `JPO_API_PASSWORD` environment variables.

## Client

```python
from ip_tools.jpo import JpoClient
```

## Rate Limits

- 10 requests per minute (enforced by built-in rate limiter)
- Daily access limits apply

## Patent Methods

### get_patent_progress(application_number) -> PatentProgressData

Get full application status with examination history.

```python
async with JpoClient() as client:
    progress = await client.get_patent_progress("2020-123456")

    progress.application_number
    progress.filing_date
    progress.status_code
    progress.publication_number
    progress.registration_number
    progress.examination_history
```

### get_patent_progress_simple(application_number) -> SimplifiedPatentProgressData

Get simplified status.

```python
simple = await client.get_patent_progress_simple("2020-123456")
```

### get_patent_documents(application_number) -> ApplicationDocumentsData

Get documents filed by applicant.

```python
docs = await client.get_patent_application_documents("2020-123456")
```

### get_patent_mailed_documents(application_number) -> MailedDocumentsData

Get office actions and decisions.

```python
actions = await client.get_patent_mailed_documents("2020-123456")
```

### get_patent_cited_documents(application_number) -> CitedDocumentInfo

Get cited prior art.

```python
cited = await client.get_patent_cited_documents("2020-123456")
```

### get_patent_family_info(application_number) -> FamilyInfo

Get divisional and priority information.

```python
divisional = await client.get_patent_divisional_info("2020-123456")
priority = await client.get_patent_priority_info("2020-123456")
```

### get_patent_registration_info(registration_number) -> RegistrationInfo

Get registration details for granted patents.

```python
reg = await client.get_patent_registration_info("6123456")
```

### get_patent_jplatpat_url(application_number) -> str

Get J-PlatPat link.

```python
url = await client.get_patent_jplatpat_url("2020-123456")
```

### get_patent_pct_national_number(pct_number) -> PctNationalPhaseData

Look up Japanese national phase from PCT number.

```python
jp_app = await client.get_patent_pct_national_number("PCT/US2020/012345")
```

## Design Methods

Similar methods available for designs:
- `get_design_progress()`
- `get_design_progress_simple()`

## Trademark Methods

Similar methods available for trademarks:
- `get_trademark_progress()`
- `get_trademark_progress_simple()`

## Application Number Formats

Japanese application numbers use format: `YYYY-NNNNNN`
- `2020-123456` - Patent application
- `2020-012345` - Design application
