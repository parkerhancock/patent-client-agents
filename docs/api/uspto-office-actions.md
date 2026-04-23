# USPTO Office Actions

Office-action analytics: rejection counts, cited references, full text,
and enriched citation metadata. Uses the USPTO ODP office-action
endpoints (separate namespace from applications/PTAB).

## Quick Start

```python
from ip_tools.uspto_office_actions import OfficeActionClient

async with OfficeActionClient() as client:
    # Structured rejection records per application
    rejections = await client.search_rejections(
        "patentApplicationNumber:16123456"
    )

    # Prior-art citations, with examiner-vs-applicant flag
    citations = await client.search_citations(
        "patentApplicationNumber:16123456 AND examinerCitedReferenceIndicator:true"
    )

    # Full office-action text
    text = await client.search_office_action_text(
        "patentApplicationNumber:16123456"
    )
```

## Configuration

Requires a USPTO ODP API key (same key as the main ODP client):

```bash
export USPTO_ODP_API_KEY="your-api-key"
```

## Client

`OfficeActionClient` inherits from `law_tools_core.BaseAsyncClient`.

## Functions

| Function | Description |
|---|---|
| `search_rejections(criteria, start, rows)` | 101/102/103/112/DP rejection records |
| `search_citations(criteria, start, rows)` | Prior-art references cited |
| `search_office_action_text(criteria, start, rows)` | Full `bodyText` of office actions |
| `search_enriched_citations(criteria, start, rows)` | Citations with inventor names, passage locations |

## Query syntax

Lucene-style, over ODP's office-action index. Common fields:

**Rejections:** `patentApplicationNumber`, `hasRej101`, `hasRej102`,
`hasRej103`, `hasRej112`, `hasRejDP`, `legalSectionCode`, `nationalClass`,
`groupArtUnitNumber`, `submissionDate`, `aliceIndicator`,
`allowedClaimIndicator`.

**Citations:** `patentApplicationNumber`, `referenceIdentifier`,
`parsedReferenceIdentifier`, `legalSectionCode`,
`examinerCitedReferenceIndicator`, `applicantCitedExaminerReferenceIndicator`,
`groupArtUnitNumber`, `techCenter`.

**Office-action text:** `patentApplicationNumber`, `inventionTitle`,
`submissionDate`, `legacyDocumentCodeIdentifier` (CTNF, CTFR, NOA),
`patentNumber`, `applicationTypeCategory`.

**Enriched citations:** `citedDocumentIdentifier`, `inventorNameText`,
`countryCode`, `kindCode`, `officeActionCategory`, `citationCategoryCode`,
`officeActionDate`, `nplIndicator`.

## Result shape

Each search returns a `SearchResponse` (Pydantic v2) with a `results` list
plus `total_count`. See `ip_tools/uspto_office_actions/models.py` for
the full schema.

## Usage patterns

```python
# Find applications with 103 rejections invoking an "Alice" test
async with OfficeActionClient() as client:
    hits = await client.search_rejections(
        "hasRej103:1 AND aliceIndicator:1",
        rows=50,
    )
    for r in hits.results[:10]:
        print(f"{r.patentApplicationNumber}: {r.inventionTitle}")
```

## Error handling

Inherits typed exceptions from `law_tools_core`:
`AuthenticationError` (401/403), `RateLimitError` (429, with `retry_after`),
`NotFoundError` (404), `ApiError`.
