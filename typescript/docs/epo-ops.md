# EPO Open Patent Services

October 21, 2026. `EpoOpsClient` ports the Python `epo_ops` and `cpc` modules
to TypeScript against OPS 3.2 (`https://ops.epo.org/3.2/rest-services`). It is
the first TypeScript connector with an upstream OAuth2 token lifecycle.

## Credentials and tokens

Set `EPO_OPS_API_KEY` and `EPO_OPS_API_SECRET` (the legacy `EPO_API_KEY` and
`EPO_API_SECRET` also work), or pass `apiKey` and `apiSecret`. The MCP server
registers EPO OPS tools only when both are configured or a client is injected.
Over HTTP the tools require the `epo:read` scope, shared with the EPO legal
corpora.

The client exchanges the key and secret for a client-credentials bearer token
at `/3.2/auth/accesstoken`. Expiry is measured on the local clock from receipt,
minus 30 seconds, so neither server clock skew nor replayed recordings make a
fresh token look expired. Concurrent callers share one in-flight refresh. A
data request that returns 401, or 400 with `invalid_access_token`, refreshes
once (unless another caller already replaced that token) and retries once; a
second rejection fails with `AUTHENTICATION_FAILED` instead of looping.
Rejected credentials at the token endpoint fail the same way. Token 429/5xx
responses are retryable `HTTP_ERROR`s. The bearer token is sent only to the
OPS origin through the shared transport's same-origin header rule.

## Errors

The shared transport gained an opt-in `readErrorBody` option. It exposes Ky's
already-bounded error body (at most 64 KiB) as `HttpResponseError` for the
connector to inspect; nothing surfaces that body verbatim. `EpoOpsError`
carries a status, a code, the parsed OPS fault code and a `retryable` flag:

| Upstream | Code | Notes |
| --- | --- | --- |
| 403 or 429 | `RATE_LIMITED` | Message includes `X-Rejection-Reason`, `X-Throttling-Control` and quota headers when present |
| 404 | `NOT_FOUND` | Fault code and message, clipped to 300 characters |
| Token rejected | `AUTHENTICATION_FAILED` | Propagates through the family-evidence aggregate |
| Other | `HTTP_ERROR` | `retryable` for 5xx |

Only a `SERVER.EntityNotFound` fault saying "No results found" becomes an
empty search page. Other 404s stay errors. Responses must be well-formed XML
with `world-patent-data` as the document element, or they fail with
`INVALID_RESPONSE`; entity declarations are rejected.

## Operations

| Python | TypeScript | MCP |
| --- | --- | --- |
| `search_published`, `search_families` | `search`, `searchFamilies` | `search_epo` (`group_by`) |
| `fetch_biblio`, `fetch_fulltext`, `fetch_citations`, `fetch_equivalents`, `fetch_family`, `fetch_legal_events`, `fetch_cpci_biblio` | `getBiblio`, `getFullText`, `getCitations`, `getEquivalents`, `getFamily`, `getLegalEvents`, `getCpciBiblio` | `get_epo_publication` (`view`) |
| `fetch_register`, `fetch_register_biblio`, `fetch_register_events`, `fetch_register_procedural_steps`, `get_unitary_patent_package` | `getRegisterXml`, `getRegisterBiblio`, `getRegisterEvents`, `getRegisterProceduralSteps`, `getUnitaryPatentPackage` | `get_ep_register` (`view`) |
| MCP-only family intelligence aggregate | `getFamilyEvidence` | `get_epo_family_evidence` |
| `convert_number` | `convertNumber` | `convert_epo_number` |
| `download_pdf` | `downloadPdf` | `download_epo_pdf` (artifact) |
| `retrieve_cpc`, `map_classification` | `retrieveCpc`, `mapClassification` | `lookup_cpc` (`map_to`) |
| `search_cpc` | `searchCpc` | `search_cpc` |
| `fetch_cpc_media` | `getCpcMedia` | Library only, as in Python |

Python's 17 EPO/CPC MCP tools consolidate into eight by intent. Python's
`get_epo_cql_help` tool becomes the `resource://epo-ops/cql-query-guide`
resource, next to `resource://epo-ops/cpc-parameters`; both are copied verbatim
from the Python package and labeled historical. Batch tools accept up to 20
numbers, fetch four at a time, and report list members that are not found in
`not_found`; a single not-found number is an error.

Behavior kept from Python: printed US pre-grant numbers (`US20050262543A1`)
are converted to the OPS 6-digit serial form for docdb/epodoc paths; register
data is normalized to the request number; `getFullText` turns a 404 into a
message explaining OPS full-text coverage; family evidence attempts register
views only for EP numbers, records failures per view and fails only when every
attempted view fails.

Deliberate differences: each claim records its `language`, because OPS sends
one `claim` element per language holding every claim; type names that collided
with USPTO exports carry an `Epo` prefix; `getFamilyEvidence` lives in the
library rather than the MCP layer; CPC/IPC/ECLA symbols and media ids are
validated before any request. The PDF merger uses `pdf-lib` 1.17.1 (pure
JavaScript, last published 2021) and resets 90-degree page rotation as Python
did with pypdf. Pages default to a 500-page limit.

## Verification

`bun run record:epo-ops -- --deployed-secret` recorded 22 operations on
October 21, 2026, reading the existing `epo-ops-api-key` and
`epo-ops-api-secret` Secret Manager entries into memory only. Every operation
succeeded, including a 557,860-byte merged PDF for EP1000000A1. Cassetter's
defaults remove the Authorization header and `access_token`; the recorder also
removes `client_id` and the `x-epo-client-ip`/`x-epo-forwarded` headers, which
echo the caller's IP address. A replay test asserts those removals for every
cassette.

[Replay tests](../tests/epo-ops-recordings.test.ts) check real values from
those recordings: EP1000000 biblio, citations, equivalents, three-language
claims, family, legal events, register views, the registered Unitary Patent
EP4108782 and its absence for EP1000000, CPC retrieval/search/mapping, CPCI
allocations, family evidence and the PDF page count. [Synthetic client
tests](../tests/epo-ops-client.test.ts) cover single-flight tokens, refresh
and retry, refresh failure, rejected credentials, throttling, fault mapping,
malformed XML and routes. [MCP tests](../tests/epo-ops-mcp.test.ts) cover
registration, option forwarding, query-bound cursors, batch not-found, artifacts
and the `epo:read` scope on the authenticated HTTP listener.

This verifies the recorded samples, not every parameter combination or OPS
service. Nothing is deployed. OPS fair-use quotas apply per registered key; the
recorder pauses 1.5 seconds between operations.
