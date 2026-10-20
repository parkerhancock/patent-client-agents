# Browser observation: ODP 5.0

- Observed: 2026-10-20.
- Observer: parent agent working in this same task, via rendered browser UI.
- Session: signed out.
- Page: https://data.uspto.gov/support/release/5.0
- Rendered page title reported: `5.0 Release notes | Open Data Portal`.
- Release date reported by the page: 2026-10-02.

This file records the task's browser observation. It is an observation summary,
not a byte-for-byte copy of the page or its accessibility tree. Direct HTTP
fetches returned an HTML application shell rather than the rendered article.

## Release features observed

Office Action Search includes applications/patents filed in 2001 or later.
It provides search/filtering over public Office Action text and metadata and
raw Office Action text downloads.

Final Petition Decisions were redesigned: petition-decision data is under the
Petition Decisions tab. Decision types include denied, dismissed, granted in
part, and granted. Search includes document text for Final Petition Decisions
and Petition Decisions. Attributes Status and Decided Type Description were
added; the page links to Patent Petitions support.

## Account notice observed

The registration banner says keys for accounts missing required additional
profile fields as of October 8, 2026 were deactivated. It directs users to
update their profiles and select Activate API Key.

This does not identify a new API endpoint or schema. Those still require
separate review of the current Swagger assets and live API behavior.

## Swagger UI observations

The main Open Data Portal API definition declares `info.version: 1.0.0`.
The browser downloaded its original YAML; it is archived as
`swagger-2026-10-20.yaml`. Its declared source URL is
https://data.uspto.gov/swagger/swagger.yaml.

The Swagger UI offered these eight definitions:

1. Open Data Portal API
2. TSDR API
3. Petition Decisions API
4. Office Actions API
5. USPTO Office Action Rejection API
6. USPTO Office Action Text Retrieval API
7. USPTO Office Action Citations API
8. USPTO Enriched Citation API v3

The rendered Office Actions API declares `info.version: 1.0.0` and exposes
these six operations. Its validator link identifies the source as
https://data.uspto.gov/swagger/office-actions.yaml. The raw YAML has not yet
been obtained; these are rendered UI observations, not an archived schema.

| Method | Path |
| --- | --- |
| GET | `/api/v1/patent/office-action/search` |
| POST | `/api/v1/patent/office-action/search` |
| GET | `/api/v1/patent/office-action/search/download` |
| POST | `/api/v1/patent/office-action/search/download` |
| GET | `/api/v1/patent/office-action/{officeActionRecordIdentifier}` |
| GET | `/api/v1/patent/office-action/{officeActionRecordIdentifier}/download/officeActionText` |

## Subsequent Office Actions schema acquisition

The same task later downloaded the original Office Actions YAML through a
plain source-link browser click. It is archived as
`office-actions-2026-10-20.yaml` with its hash and schema inventory in
`office-actions-operations.json`. The earlier raw-schema-unavailable statement
above describes the earlier observation stage; it is superseded by that
archived source for the Office Actions definition. Main companion files remain
unavailable through the attempted direct fetch approach.
