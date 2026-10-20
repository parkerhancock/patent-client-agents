# USPTO ODP source review

Checked October 20, 2026. **The current portal release is 5.0, dated October 2,
2026**, verified in the rendered official portal. The current main OpenAPI file
was downloaded through the official Swagger UI; its external companion schemas
still need to be retrieved and compared. All eight Swagger dropdown definition entry files are now archived.
The separate current Office Actions specification is also archived and fully
reference-resolved. The TypeScript port can start from the existing Python
contracts, but must account for the newer Office Action
and Petition Decision features before claiming current feature completeness.

## What was verified

The rendered [5.0 release notes](https://data.uspto.gov/support/release/5.0)
were accessible while signed out. Release 5.0 includes:

- Office Action Search for applications/patents filed from 2001 onward, with
  search/filtering over public Office Action text and metadata, plus raw
  Office Action text downloads.
- A Petition Decisions redesign that places petition-decision data under the
  Petition Decisions tab and covers denied, dismissed, granted-in-part, and
  granted decisions. Search includes document text for Final Petition
  Decisions and Petition Decisions; new attributes include Status and
  Decided Type Description.
- The portal banner says API keys for profiles missing required additional
  fields as of October 8 were deactivated; users can update their profile and
  activate the key from Manage API Key. This is separate from API-schema
  versioning.

The [browser observation summary](../references/odp/release-5.0-browser-observation.md)
is preserved alongside the source receipts. It records the observer and method;
it is not a byte-for-byte page archive.

Direct requests to the official [release notes](https://data.uspto.gov/support/release),
[Swagger UI](https://data.uspto.gov/swagger/index.html),
[main YAML](https://data.uspto.gov/swagger/swagger.yaml), and shared schema URL
returned HTTP 200 with the same 20,666-byte HTML application shell. The
requested YAML, JavaScript initializer, and PDF mapping documents were not
returned. A successful HTTP status therefore does not establish a successful
schema refresh. Swagger paths on `api.uspto.gov` returned HTTP 403.

The archived shell is evidence of this response, not an archived release page
or specification. The release page did render in a signed-out browser. The
direct-request behavior is therefore a limitation of this fetch approach,
not proof of an authentication requirement or removal of the APIs/schemas.
No access controls were bypassed.

Two official announcements were available independently of the portal:

- The [June 3 registration announcement](https://www.uspto.gov/subscription-center/2026/register-access-usptos-open-data-portal)
  says a USPTO.gov account is required to access, search, and download ODP
  datasets starting June 18, 2026. API-key configuration alone should not be
  assumed to establish access to the portal documentation.
- The [March 26 API announcement](https://content.govdelivery.com/accounts/USPTO/bulletins/40fd1a0)
  confirms that legacy Office Action APIs migrated from Developer Hub to ODP,
  and that the TSDR Swagger UI was added to ODP. A port limited to the old
  application API does not cover all API families available through ODP.

Original HTML, requested URLs, retrieval date, content type, response status,
and SHA-256 digests are under [`../references/odp/`](../references/odp/).
The full receipt is [`sources.json`](../references/odp/sources.json).

## Current specification and feature inventory

The official browser download is archived as
[`swagger-2026-10-20.yaml`](../references/odp/swagger-2026-10-20.yaml)
(81,460 bytes; SHA-256
`6c01165869e2c806969281baea75daaa84caf3b4db038cb4cc5246366e2f4f32`).
Its declared source is `https://data.uspto.gov/swagger/swagger.yaml`;
OpenAPI is 3.0.1 and `info.version` remains 1.0.0 despite portal release 5.0.

The main file is an index into a multi-file specification: 36 path entries,
19 inline operations, 19 path references, and 41 schema entries. It contains
63 unique external references across seven companion files. There are no
unresolved local-only references in the index; the referenced companion
files have not yet been archived, so the complete schema bundle is not
resolved. The seven files are `odp-common-base.yaml`, `trial-common.yaml`,
`trial-proceedings.yaml`, `trial-decisions.yaml`, `trial-documents.yaml`,
`trial-appeal-decisions.yaml`, and `trial-interferences.yaml`.

Compared with the historical packaged snapshot, the main file no longer
contains the three Petition Decision paths (five operations). The current
Swagger UI offers Petition Decisions as a separate definition; this is not
evidence of API retirement. Application search/get/document route names and
GET parameter names are unchanged. The document-list endpoint supports
`documentCodes`, `officialDateFrom`, and `officialDateTo`. Current response
field-shape comparison still requires `odp-common-base.yaml`.

`/api/v1/patent/applications/text-to-search` is a metadata-only placeholder in
both snapshots: no HTTP method is declared. Do not implement it as a confirmed
Smart Search API from that entry alone.

The Swagger UI currently offers eight definitions: Open Data Portal API,
TSDR API, Petition Decisions API, Office Actions API, Office Action Rejection,
Office Action Text Retrieval, Office Action Citations, and Enriched Citation
API v3. The rendered Office Actions API (`info.version: 1.0.0`) exposes six
operations:

| Method | Path |
| --- | --- |
| GET / POST | `/api/v1/patent/office-action/search` |
| GET / POST | `/api/v1/patent/office-action/search/download` |
| GET | `/api/v1/patent/office-action/{officeActionRecordIdentifier}` |
| GET | `/api/v1/patent/office-action/{officeActionRecordIdentifier}/download/officeActionText` |

Its source link is `https://data.uspto.gov/swagger/office-actions.yaml`.
The original Office Actions YAML was subsequently downloaded through the
Swagger UI source link and is archived as
[`office-actions-2026-10-20.yaml`](../references/odp/office-actions-2026-10-20.yaml).
It is 30,138 bytes; SHA-256
`77b568c679bec7c9a6b60676268538c3e9f2cb09e3f8684e3a59c4d68c0440d6`.
It declares OpenAPI 3.0.3 and `info.version: 1.0.0`; generated-at metadata is
`2026-08-06T21:27:37.243116Z`. Its four paths contain the six operations above,
15 schemas, and 32 unique local references, all resolved. There are no
external references. These are verified schema contracts, not implemented or
live-tested TypeScript coverage. The other seven definition entry files are now archived as described below. Source verification does not establish implementation or live behavior.

[`current-operations.json`](../references/odp/current-operations.json) tracks
the downloaded index and separate Office Actions definition separately.
[`office-actions-operations.json`](../references/odp/office-actions-operations.json)
records the full Office Actions schema inventory.
[`companion-fetch-receipts.json`](../references/odp/companion-fetch-receipts.json)
records attempts with YAML Accept, Swagger Referer, and no-cache headers.
All eight companion/Office Actions requests still returned the same HTML shell.

## Existing repository baseline

The initial contract reference remains
[`../../src/patent_client_agents/uspto_odp/data/odp_swagger.yaml`](../../src/patent_client_agents/uspto_odp/data/odp_swagger.yaml).
It declares OpenAPI 3.0.1 and `info.version: 1.0.0`.
Its SHA-256 is
`10f50e96546fc658c7b13e47593fe25f3baa0dcf6958a5c780183789321e70f1`.
The adjacent `release_state.json` records a January 27, 2026 review against
portal version 3.0. The Python client separately tracks portal release 3.6,
reviewed April 14, 2026. These are historical repository facts, not confirmation
of the current release. Portal version and per-specification version must be
recorded separately.

The baseline has 39 paths, 53 GET/POST operations, and 41 named schemas:

| Family | Baseline operations | Initial port status |
| --- | ---: | --- |
| Patent applications | 14 | First implementation slice |
| Application status codes | 2 | Follow-up |
| Bulk products and downloads | 3 | Follow-up |
| Petition decisions | 5 | Follow-up |
| PTAB trial proceedings, decisions, documents | 17 | Follow-up |
| PTAB appeals | 6 | Follow-up |
| PTAB interferences | 6 | Follow-up |
| Office Action APIs | Absent from this baseline | Current Office Actions spec archived; implement separately |
| TSDR | Absent from this baseline | Separate server/key; retrieve current specs |

The machine-readable inventory is
[`baseline-operations.json`](../references/odp/baseline-operations.json).
It lists operations and schemas for review; it is **not** a current coverage
manifest. The baseline also contains 17 unresolved local schema references,
including `Filter`, `Range`, `Sort`, and `Pagination`. Some PTAB references differ
in case from declared schema names. Resolve these from complete official source
files before relying on generated validators. Unknown response properties
should remain available so additive upstream fields are not silently lost.

## Office Actions implementation implications

The new Office Actions definition is distinct from both application file
wrapper document listing and the older Office Action Rejection/Citations/Text
Retrieval definitions. Do not equate an application-document port with support
for Office Action Search.

- Search and get-by-record-ID both use an `officeActionDataBag` envelope;
  search additionally declares `count`, `requestIdentifier`, and `facets`.
- `officeActionText` in an OfficeAction record is documented as up to 500
  characters with highlighting. Full raw text requires the dedicated
  `download/officeActionText` endpoint, which returns `text/plain`.
- Pagination defaults to 25, requires offset >= 0, and permits limits 1–500.
  An MCP-facing limit of 100 can remain a separate interface bound; do not
  mistake it for an upstream maximum.
- POST filters use `name` plus string-array `value`. Filter names are limited
  to `applicationNumberText`, `documentCode`,
  `documentCodeDescriptionText`, `patentNumber`, `rejectionTypeBag`, and
  `groupArtUnitNumber`. Range fields are `filingDate`, `submissionDate`, or
  `groupArtUnitNumber`. Sort orders are `asc`/`desc`, documented as
  case-insensitive.
- `groupArtUnitNumber` is declared integer/int64. `lastModifiedDateTime` is
  declared `format: date`, but its example is `2026-08-10 20:50:02`. Treat
  this as a schema/example inconsistency and validate against real responses
  before imposing an ISO-date-only validator.
- Search downloads default to CSV, permit JSON, and do not support facets.
  The JSON download schema declares only `officeActionDataBag`, without
  `count` or `requestIdentifier`; do not apply the search wrapper blindly.
- Request and record schemas do not declare required response fields. Preserve
  unknown fields and validate actual recordings before strengthening contracts.

These are follow-up port requirements. The initial application methods remain
search, get, and document listing; Office Actions support is not implied by
those methods or by successful source-schema validation.

## First implementation slice

Start with application search, single application retrieval, and document
listing. Use the existing Python behavior as the compatibility contract and
keep the original USPTO field names available. In particular:

- POST `/api/v1/patent/applications/search` accepts `q`, `fields`, `facets`,
  `filters`, `rangeFilters`, `sort`, and `pagination`. Keep the request body
  intact in cassette matching; matching just the POST URL can replay an
  unrelated search result.
- GET `/api/v1/patent/applications/{applicationNumberText}` returns application
  records under `patentFileWrapperDataBag`. Preserve unfamiliar properties.
- GET `.../{applicationNumberText}/documents` returns `documentBag`.
  Associated publication/grant metadata is a separate GET
  `.../{applicationNumberText}/associated-documents`.

The Python client normalizes application-number separators, defaults to lean
search fields, and optionally flattens `applicationMetaData`. Search 404 means
an empty result; application/document retrieval 404 remains an error.
Associated-documents 404 becomes an empty list. These distinctions are existing
client behavior, not inferred from a generic HTTP status rule.

Use synthetic contract fixtures for edge cases and actual recorded HTTP for
upstream compatibility. Existing Python application tests use in-code mocks;
there are no checked-in application VCR responses to re-label as live recordings.
PTAB recordings do exist. Identify the origin of every new cassette.

## Complete the current-feature review

The browser can display the latest release notes while signed out. Retrieve
the actual Swagger assets using the links exposed by that rendered portal,
and complete the following checks:

1. Save the original release notes, remaining OpenAPI/shared files, relevant
   data dictionaries, and current query/rate-limit documentation. Verify MIME
   type and parseability before replacing any baseline.
2. Record source URLs, retrieval timestamps, hashes, portal release, and each
   spec's own version. Resolve all external and local `$ref` values.
3. Diff paths, methods, parameters, required fields, enums, response schemas,
   and documented limits. Give each operation an implemented/tested status.
4. Refresh a bounded set of real search/get/documents cassettes using an active
   ODP key. Review changed responses and credentials scrubbing before commit.
5. Test pagination, missing-record behavior, filters/ranges, throttling, and
   downloads. A matching schema does not establish working behavior.

Do not infer API endpoints for the new Office Action Search or Petition
Decision features solely from the release descriptions. Do not claim support
for portal Smart Search, new trademark datasets, or altered limits from stale
local files or third-party client descriptions. Track those as review
questions until their current official schemas and behavior can be inspected.

## Petition definition and remaining archive gaps

A further signed-out Swagger UI review on October 20 confirmed the separate
Petition Decisions API (`info.version: 1.0.0`, OAS 3.0) and its source link,
[`petition-decisions.yaml`](https://data.uspto.gov/swagger/petition-decisions.yaml).
The rendered page exposes GET/POST `.../petition/decisions/search`, GET/POST
`.../petition/decisions/search/download`, and GET
`.../petition/decisions/{petitionDecisionRecordIdentifier}`. Fifteen schema names
are visible, including separate search/download request types and a
`PetitionDecisionDocument` model. The
[observation receipt](../references/odp/petition-decisions-browser-observation.md)
records the exact route and model list. The raw YAML was subsequently downloaded through a plain source-link click in Chrome and is included in the archive inventory below.

The in-app browser became unavailable after a turn interruption. A fresh public Chrome research tab successfully retrieved all six remaining dropdown definition entry files through their visible source links. Earlier direct navigation to the common-base YAML was blocked by ChatGPT; no bypass was attempted. Seven main companion files remain unarchived, so the full current schema bundle is still incomplete. No complete current-schema claim follows from successful code tests.

The [Python USPTO feature inventory](uspto-feature-inventory.md) enumerates 70
public domain-client methods across 12 clients, delegating facades, local XML
and claims parsing helpers, and bundled documentation resources. It provides
the parity checklist beyond ODP alone. Implementation and behavioral evidence
remain separately tracked in [port-status.md](port-status.md).

## Additional current source archives

Retrieved October 20 through the visible source links in the official Swagger UI using a new public Chrome tab. Original bytes are preserved; the TSDR asset uses JSON syntax despite its `.yaml` filename. All six files parse and all their local references resolve. They contain no external references.

| Original source filename | Archive | Operations | Schemas | SHA-256 |
| --- | --- | ---: | ---: | --- |
| [petition-decisions.yaml](https://data.uspto.gov/swagger/petition-decisions.yaml) | [petition-decisions-2026-10-20.yaml](../references/odp/petition-decisions-2026-10-20.yaml) | 5 | 15 | `7165b546a7754cb699028d36cb07d23f562110debc5acddbc622e53d18437d09` |
| [tsdr-swagger.yaml](https://data.uspto.gov/swagger/tsdr-swagger.yaml) | [tsdr-swagger-2026-10-20.yaml](../references/odp/tsdr-swagger-2026-10-20.yaml) | 25 | 289 | `2e72951da2b0e26e1dcdcf625f08a93b4fcbf0e770b3a7d2d153e25234658d16` |
| [oa-rejections.yaml](https://data.uspto.gov/swagger/oa-rejections.yaml) | [oa-rejections-2026-10-20.yaml](../references/odp/oa-rejections-2026-10-20.yaml) | 2 | 0 | `028af96714af6d30392be0bc8b830d4618ec86d70fa9d3463efad38401acf5c9` |
| [oa-text-retrieval.yaml](https://data.uspto.gov/swagger/oa-text-retrieval.yaml) | [oa-text-retrieval-2026-10-20.yaml](../references/odp/oa-text-retrieval-2026-10-20.yaml) | 2 | 0 | `e0c5398114e22a20fbd6687efd9793d89c0d22e988d159a5ac605d997da17529` |
| [oa-citations.yaml](https://data.uspto.gov/swagger/oa-citations.yaml) | [oa-citations-2026-10-20.yaml](../references/odp/oa-citations-2026-10-20.yaml) | 2 | 0 | `5388cd1728405286215180987b5aeaf27ab955f5b646c26c418631efc04091cf` |
| [oa-enriched-citations.yaml](https://data.uspto.gov/swagger/oa-enriched-citations.yaml) | [oa-enriched-citations-2026-10-20.yaml](../references/odp/oa-enriched-citations-2026-10-20.yaml) | 2 | 0 | `10df3aa6688dd5856b0285789f04a7eb766da5f4e5ebb00a0162dba245682052` |

The four migrated analytics definitions each declare GET searchable-field metadata and POST record search, so their current eight operations exceed the four Python search helpers. Each uses `application/x-www-form-urlencoded` for POST search rather than the new Office Action API’s JSON body. TSDR declares 25 GET operations, covering case status, single documents/pages, multi-case status, bundles, and downloads. Its specification describes limited availability during upgrades without a dated outage window; that text is a source observation and does not establish current service health.

Each archive has a matching `*-operations.json` inventory, with URL, retrieval date, byte count, digest, own version, operation list, schema names, and reference validation. The main operation catalog includes these six inventories alongside the main index and current Office Actions schema. The source receipt flag `current_schema_bundle_complete` remains false because the seven main companions have not been retrieved.
