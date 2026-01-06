# EPO OPS

European Patent Office Open Patent Services API.

**Required**: `EPO_OPS_API_KEY` and `EPO_OPS_API_SECRET` environment variables.

## Client

```python
from ip_tools.epo_ops import EpoOpsClient, client_from_env

# From environment variables
async with client_from_env() as client:
    ...

# Or explicit credentials
async with EpoOpsClient(api_key="...", api_secret="...") as client:
    ...
```

## Methods

### search_published(query, range) -> SearchResponse

Search published documents using CQL.

```python
async with client_from_env() as client:
    results = await client.search_published(
        query='ta="machine learning" and pd>=2020',
        range="1-25"
    )

    for doc in results.documents:
        doc.doc_number
        doc.country
        doc.kind
        doc.family_id
```

### search_families(query, range) -> SearchResponse

Search grouped by patent family.

```python
results = await client.search_families(
    query='applicant="Google"',
    range="1-25"
)
```

### fetch_biblio(doc_id) -> BiblioResponse

Get bibliographic data.

```python
biblio = await client.fetch_biblio("EP1234567A1")
biblio.title
biblio.abstract
biblio.applicants
biblio.inventors
biblio.classifications
biblio.priorities
biblio.publication_date
biblio.filing_date
```

### fetch_fulltext(doc_id, part) -> FullTextResponse

Get claims or description.

```python
# Get claims
claims = await client.fetch_fulltext("EP1234567A1", "claims")
for claim in claims.claims:
    claim.number
    claim.text
    claim.dependencies

# Get description
desc = await client.fetch_fulltext("EP1234567A1", "description")
desc.text
```

### fetch_family(doc_id) -> FamilyResponse

Get patent family members.

```python
family = await client.fetch_family("EP1234567A1")
for member in family.members:
    member.doc_number
    member.country
    member.kind
    member.publication_date
```

### fetch_legal_events(doc_id) -> LegalEventsResponse

Get legal status history.

```python
events = await client.fetch_legal_events("EP1234567A1")
for event in events.events:
    event.code
    event.description
    event.date
```

### download_pdf(doc_id) -> PdfDownloadResponse

Download patent PDF.

```python
pdf = await client.download_pdf("EP1234567A1")
pdf.content_base64  # Base64-encoded PDF
```

### retrieve_cpc(cpc_code) -> CpcRetrievalResponse

Get CPC classification details.

```python
cpc = await client.retrieve_cpc("G06N3/08")
cpc.title
cpc.definition
```

### search_cpc(query) -> CpcSearchResponse

Search CPC classifications.

```python
results = await client.search_cpc("neural network")
```

## CQL Query Syntax

EPO uses Cooperative Query Language:

```
# Title/abstract search
ta="machine learning"

# Applicant
applicant="Google"

# Inventor
inventor="Smith"

# Publication date
pd>=2020 and pd<=2023

# Classification
cpc="G06N"

# Combined
ta="neural" and applicant="IBM" and pd>=2020
```

## Rate Limits

EPO OPS has quota limits:
- **Traffic light**: Check response headers for quota status
- **Weekly quota**: Resets Sunday midnight CET
- **Throttling**: Automatic backoff on 429 responses
