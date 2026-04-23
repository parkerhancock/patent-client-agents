"""Reusable documentation snippets for USPTO ODP-backed servers."""

from __future__ import annotations

from importlib import resources as importlib_resources

ODP_SEARCH_GUIDE_RESOURCE_URI = "resource://uspto-odp/search-guide"
ODP_FIELD_CATALOG_RESOURCE_URI = "resource://uspto-odp/field-catalog"
ODP_STATUS_CODES_RESOURCE_URI = "resource://uspto-odp/application-status-codes"
ODP_SWAGGER_RESOURCE_URI = "resource://uspto-odp/swagger"


def _read_text_resource(relative_path: str) -> str:
    return (
        importlib_resources.files("uspto_odp_mcp")
        .joinpath(relative_path)
        .read_text(encoding="utf-8")
    )


ODP_SEARCH_GUIDE = """\
## USPTO ODP Search Guide

Use this reference for every USPTO Open Data Portal endpoint that accepts the `q`, `fields`,
`filters`, `facets`, `rangeFilters`, `sort`, `offset`, or `limit` parameters (applications, bulk
data, petitions, PTAB trials, appeals, interferences, etc.). It summarizes the REST parameter
conventions documented in the ODP Swagger definition.

### Query (`q`)
- Lucene-style syntax: `field:value`, quotes for phrases, `AND/OR/NOT`, parentheses for grouping.
- Default field varies by dataset but typically searches the concatenated text for the record.
- Supports wildcards (`*`, `?`) and numeric/date comparisons (`field:[2020-01-01 TO 2020-12-31]`).

### Field selection and facets
- `fields`: CSV or array describing which fields to return; omit to receive the default schema.
- `facets`: CSV/array of aggregations to compute (e.g., `["applicationType","grantYear"]`).
- Each endpoint enforces its own maximum facet count (usually ≤10); extra entries are ignored.

### Filters
All ODP POST search endpoints (applications, petitions, PTAB) use **JSON-object filters**:

```json
{
  "filters": [
    {"name": "applicationMetaData.publicationCategoryBag", "value": ["Granted/Issued"]}
  ],
  "rangeFilters": [
    {"field": "applicationMetaData.filingDate", "valueFrom": "2022-01-01", "valueTo": "2023-12-31"}
  ]
}
```

**Important:** Application fields require the `applicationMetaData.` prefix in filter/sort names.

Common filter values for `applicationMetaData.publicationCategoryBag`:
- `"Granted/Issued"` — granted patents
- `"Pre-Grant Publications - PGPub"` — published applications

### Sorting & pagination
- `sort` accepts an array of objects:
  `[{"field": "applicationMetaData.filingDate", "order": "Desc"}]`.
- `limit` defaults to 25; most services cap it at 200.
- `offset` is zero-based.

### Tips
- Combine `q` with `filters` rather than embedding everything into the query string—filters are
  cached server-side and easier to debug.
- Use ISO dates (`YYYY-MM-DD`) for all date comparisons.
- When sending `raw_payload`, ensure it matches the shapes above; unknown keys are ignored after
  pruning.
- Need the official list of application status codes referenced by `applicationStatusCode`?
  Use `resource://uspto-odp/application-status-codes` (mirrors the USPTO ODP dataset) when you
  actually need the definitions—no need to fetch it just to follow the search examples here.

References: USPTO ODP Swagger specification (`docs/uspto_odp_swagger.yaml`), API portal examples
(<https://developer.uspto.gov>).
"""

ODP_FIELD_CATALOG = """\
## USPTO ODP Field Catalog (most common)

Use these field names in `fields`, `facets`, `filters`, `rangeFilters`, or `sort`. The listings
focus on the patent datasets exposed by our MCPs; consult the Swagger spec for exhaustive schemas.

### Patent Applications API (`/api/v1/patent/applications/search`)
| Field | Type | Notes |
| --- | --- | --- |
| `applicationNumberText` | string | Primary identifier (e.g., `16999555`). |
| `applicationMetaData.applicationTypeCategory` | string | `UTILITY`, `DESIGN`, `PLANT`, `REAEX`. |
| `applicationMetaData.filingDate` | date | ISO `YYYY-MM-DD`. |
| `applicationMetaData.grantDate` | date | Empty for unpublished. |
| `applicationMetaData.publicationNumber` | string | Linked PGPub when present. |
| `applicationMetaData.patentNumber` | string | Linked grant when present. |
| `applicationMetaData.applicationStatusDescriptionText` | string | Human-readable status. |
| `applicationMetaData.publicationCategoryBag` | string | `"Granted/Issued"`, `"PGPub"`. |
| `applicationMetaData.cpcClassificationBag` | string | CPC classification codes. |
| `applicationMetaData.examinerName` | string | Primary examiner. |
| `applicationMetaData.examinerArtUnitNumber` | string | Art unit number. |
| `applicationMetaData.customerNumber` | string | Correspondence customer number. |
| `applicationMetaData.inventionTitle` | string | Title text. |
| `applicationMetaData.firstInventorToFileIndicator` | boolean | FITF flag. |
| `applicationMetaData.entityStatusData.businessEntityStatusCategory` | string | Entity size. |

**Note:** For `filters`, `rangeFilters`, and `sort`, application fields require the
`applicationMetaData.` prefix. In query (`q`), fields can be used with or without the prefix.

Common facets: `applicationMetaData.applicationTypeCategory`,
`applicationMetaData.publicationCategoryBag`, `applicationMetaData.examinerArtUnitNumber`.

### Bulk Data (BDSS) API (`/bdss-datastore/v1/datasets`)
| Field | Type | Notes |
| --- | --- | --- |
| `productIdentifier` | string | Short name (e.g., `patent-grant-red-book-text`). |
| `productTitle` | string | Human title. |
| `productCategory` | string | `PATENT`, `TRADEMARK`, etc. |
| `description` | string | Abstract/summary. |
| `keywords` | array | Descriptive tags. |
| `productFileFormat` | string | `ZIP`, `JSON`, `CSV`. |
| `productUpdateFrequency` | string | e.g., `WEEKLY`, `MONTHLY`. |
| `lastUpdatedDate` | date | Product metadata update. |
| `availability` | string | `PUBLIC`, `LIMITED`. |
| `bulkDownloadUrl` | string | Base URL when publicly hosted. |
| `dataContactEmail` | string | Maintainer contact. |

Common facets: `productCategory`, `productUpdateFrequency`, `productFileFormat`.

### Petitions API (`/ptab/v1/petitions/decision`)
| Field | Type | Notes |
| --- | --- | --- |
| `petitionDecisionRecordIdentifier` | string | Primary ID used by `petitions.get`. |
| `applicationNumberText` | string | Related application. |
| `patentNumber` | string | Related grant when applicable. |
| `petitionFilingDate` | date | Date petition filed. |
| `petitionDecisionMailDate` | date | Decision mailed date. |
| `petitionDecisionStatusCategory` | string | `GRANTED`, `DENIED`, `DISMISSED`, etc. |
| `petitionDecisionCode` | string | Specific decision code (e.g., `130`). |
| `petitionSubjectMatterCategory` | string | Subject bucket (e.g., `ENTITY STATUS`). |
| `petitionDecisionBodyName` | string | deciding office (e.g., `Office of Petitions`). |
| `petitionerName` | string | Applicant/petitioner. |
| `docketNumber` | string | If assigned. |

Common facets: `petitionDecisionStatusCategory`, `petitionSubjectMatterCategory`,
`petitionDecisionBodyName`, `petitionDecisionMailYear`.

### PTAB Trial Proceedings API (`/api/v1/patent/trials/proceedings`)
| Field | Type | Notes |
| --- | --- | --- |
| `trialNumber` | string | Unique trial identifier (e.g., `IPR2024-00001`). |
| `trialMetaData.trialTypeCode` | string | `IPR`, `PGR`, `CBM`, or `DER`. |
| `trialMetaData.trialStatusCategory` | string | Current status (e.g., `Terminated`). |
| `trialMetaData.petitionFilingDate` | date | Date petition was filed. |
| `trialMetaData.accordedFilingDate` | date | Official filing date assigned. |
| `trialMetaData.institutionDecisionDate` | date | Date institution was granted/denied. |
| `trialMetaData.terminationDate` | date | Date proceeding was terminated. |
| `patentOwnerData.patentNumber` | string | Challenged patent number. |
| `patentOwnerData.applicationNumberText` | string | Application number of challenged patent. |
| `patentOwnerData.patentOwnerName` | string | Name of patent owner. |
| `patentOwnerData.realPartyInInterestName` | string | Real party in interest. |
| `patentOwnerData.technologyCenterNumber` | string | Technology center. |
| `patentOwnerData.groupArtUnitNumber` | string | Art unit. |
| `regularPetitionerData.realPartyInInterestName` | string | Petitioner's real party. |
| `regularPetitionerData.counselName` | string | Petitioner's counsel. |

Common facets: `trialMetaData.trialTypeCode`, `trialMetaData.trialStatusCategory`,
`patentOwnerData.technologyCenterNumber`.

### PTAB Trial Decisions API (`/api/v1/patent/trials/decisions`)
| Field | Type | Notes |
| --- | --- | --- |
| `trialNumber` | string | Associated trial number. |
| `decisionData.trialOutcomeCategory` | string | Outcome (e.g., `Denied`, `Institution Granted`). |
| `decisionData.decisionTypeCategory` | string | Type (e.g., `Final Written Decision`). |
| `decisionData.decisionIssueDate` | date | Date decision was issued. |
| `documentData.documentIdentifier` | string | Unique document ID. |
| `documentData.documentName` | string | Document filename. |
| `documentData.filingPartyCategory` | string | Who filed (e.g., `Board`, `Petitioner`). |

Common facets: `decisionData.trialOutcomeCategory`, `decisionData.decisionTypeCategory`.

### PTAB Appeals API (`/api/v1/patent/appeals/decisions`)
| Field | Type | Notes |
| --- | --- | --- |
| `appealNumber` | string | Unique appeal identifier. |
| `decisionData.appealOutcomeCategory` | string | Outcome (e.g., `Affirmed`, `Reversed`). |
| `decisionData.decisionTypeCategory` | string | Type (e.g., `Decision`, `Rehearing`). |
| `decisionData.decisionIssueDate` | date | Date decision was issued. |
| `appellantData.applicationNumberText` | string | Application on appeal. |
| `appellantData.patentNumber` | string | Patent number if granted. |
| `appellantData.inventorName` | string | Inventor name(s). |
| `appellantData.technologyCenterNumber` | string | Technology center. |
| `documentData.documentIdentifier` | string | Unique document ID. |

Common facets: `decisionData.appealOutcomeCategory`, `decisionData.decisionTypeCategory`.

### PTAB Interferences API (`/api/v1/patent/interferences/decisions`)
| Field | Type | Notes |
| --- | --- | --- |
| `interferenceNumber` | string | Unique interference identifier. |
| `interferenceMetaData.interferenceStyleName` | string | Party names in interference. |
| `decisionDocumentData.interferenceOutcomeCategory` | string | Outcome of interference. |
| `decisionDocumentData.decisionTypeCategory` | string | Decision type. |
| `decisionDocumentData.decisionIssueDate` | date | Date decision was issued. |
| `seniorPartyData.patentNumber` | string | Senior party's patent. |
| `seniorPartyData.patentOwnerName` | string | Senior party name. |
| `juniorPartyData.patentNumber` | string | Junior party's patent. |
| `juniorPartyData.patentOwnerName` | string | Junior party name. |

Common facets: `decisionDocumentData.decisionTypeCategory`.

**Tip:** All ODP search endpoints use JSON-object filters. For application searches, use the
`applicationMetaData.` prefix for nested fields:
```json
{"name": "applicationMetaData.publicationCategoryBag", "value": ["Granted/Issued"]}
```
"""

ODP_STATUS_CODES = _read_text_resource("status_codes.md")


def get_odp_swagger_spec() -> str:
    """Return the upstream USPTO ODP swagger YAML."""
    return _read_text_resource("data/odp_swagger.yaml")
