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

## EP Register Methods

The EP Register provides prosecution-specific data for European applications.

### search_register(query, range) -> RegisterSearchResponse

Search EP Register for European applications.

```python
results = await client.search_register(
    query='pa="Siemens"',  # Applicant search
    range_begin=1,
    range_end=25
)

for app in results.results:
    app.application_number
    app.publication_number
    app.title
    app.status
```

### fetch_register_biblio(number) -> RegisterBiblioResponse

Get detailed EP Register data for an application.

```python
biblio = await client.fetch_register_biblio(
    number="EP20200001",
    doc_type="application",
    fmt="epodoc"
)

biblio.application_number
biblio.publication_number
biblio.application_date
biblio.grant_date
biblio.title
biblio.applicants
biblio.inventors
biblio.representatives
biblio.status
biblio.status_description

# Designated states
for state in biblio.designated_states:
    state.country_code
    state.status
    state.effective_date

# Opposition data (if applicable)
if biblio.opposition:
    biblio.opposition.opposition_date
    biblio.opposition.status
    for party in biblio.opposition.parties:
        party.name
        party.role  # "opponent" or "patent_owner"
```

### fetch_register_procedural_steps(number) -> RegisterProceduralStepsResponse

Get prosecution history (procedural steps).

```python
steps = await client.fetch_register_procedural_steps("EP20200001")

for step in steps.procedural_steps:
    step.phase
    step.step_code
    step.step_description
    step.step_date
    step.office
```

### fetch_register_events(number) -> RegisterEventsResponse

Get EPO Bulletin events.

```python
events = await client.fetch_register_events("EP20200001")

for event in events.events:
    event.event_code
    event.event_date
    event.event_description
    event.bulletin_number
    event.bulletin_date
```

### fetch_register_upp(number) -> RegisterUppResponse

Get Unitary Patent (UPP) data.

```python
upp = await client.fetch_register_upp("EP20200001")

if upp.unitary_patent:
    upp.unitary_patent.upp_status
    upp.unitary_patent.registration_date
    upp.unitary_patent.participating_states  # List of country codes
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
