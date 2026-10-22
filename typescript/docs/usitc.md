# USITC

October 21, 2026. Port of the Python `usitc` connector and its MCP tools:
EDIS (Section 337 and other investigation dockets), the Harmonized Tariff
Schedule REST API, the IDS investigations feed and DataWeb trade statistics.
Client: [`packages/client/src/usitc.ts`](../packages/client/src/usitc.ts).
MCP: [`packages/mcp/src/usitc.ts`](../packages/mcp/src/usitc.ts), scope
`usitc:read`. Tests: [`tests/usitc.test.ts`](../tests/usitc.test.ts) and
[`tests/facade-usitc-contract.test.ts`](../tests/facade-usitc-contract.test.ts).

## What is served

| Tools | Gate |
| --- | --- |
| `search_usitc_investigations`, `get_usitc_investigation`, `search_usitc_documents`, `list_usitc_attachments`, `download_usitc_attachment`, `download_usitc_investigation_documents` | Registered only when `USITC_EDIS_TOKEN` or the file named by `USITC_EDIS_TOKEN_FILE` holds a token (or an `edis` client is injected), as in Python |
| `search_hts_tariffs`, `list_ids_investigations` | Always; no credential |
| `run_dataweb_report` | Always, as in Python; fails closed without `USITC_DATAWEB_TOKEN` (or `USITC_DATAWEB_TOKEN_FILE`) |

The curated facade follows the Python facade's EDIS gate. Without an EDIS
token its tools and schemas are unchanged (the existing
[`facade-contract.test.ts`](../tests/facade-contract.test.ts) still passes;
it assumes `USITC_EDIS_TOKEN` is unset in the test environment). With one,
`get_litigation` gains `forum='usitc'`, `download_document` gains
`usitc_attachment` (`document_id` + `attachment_id`) and `usitc_investigation`
(identifier, `item_ids`, `document_types`, `after`, `before`, 25-attachment
cap), and `search_usitc_investigations`, `search_usitc_documents` and
`list_usitc_attachments` are served. That surface is checked against
[`python-facade-tools-edis.json`](../tests/fixtures/facade/python-facade-tools-edis.json),
exported from `patent_client_facade.facade_mcp.list_tools()` with a
placeholder `USITC_EDIS_TOKEN` set only in that process.

Library-only operations, as in Python: `HtsClient.exportRange`,
`DataWebClient.getAllCountries`, `getGlobalVars`, `listSavedQueries` and
`buildDataWebQuery`.

## Upstream behavior found by live probing

- Akamai bot management fronts every USITC host. It answers 403 to Bun's,
  Node's and browser-like user agents and admits common programmatic clients
  (curl, python-httpx, python-requests, Go, okhttp, axios). Python passes
  because httpx sends its own name. The client sends `curl/8.7.1`
  (`USITC_USER_AGENT`, overridable with `userAgent`). The edge also blocks an
  address for about 20 to 25 minutes after a short burst; the recording
  script spaces requests 15 seconds apart.
- EDIS investigation, document and attachment metadata are public. Only
  `/data/download/{doc}/{att}` needs the bearer token (401 without one, 403
  with an expired one).
- An expired bearer token turns public metadata routes into an HTML 503. A
  nonexistent attachment list also returns HTML 503.
- EDIS double-escapes some titles (`Nokia&amp;#39;s`); the client decodes
  the remaining entity.
- `/reststop/exportList` answers JSON as `application/octet-stream`.
- The IDS feed was 37 MB and 4,434 rows on October 21, 2026, not the 11 MB
  Python documents. The client allows 128 MiB and two minutes.
- DataWeb's `getAllSavedQueries` answers `{"list": [...]}`, even without a
  token.

## Verification

Live, October 21, 2026: EDIS investigation lookups (with and without phase,
and an empty result), a document page and an empty page for 337-1380,
attachments for document 856966, HTS keyword search and `exportList` are
recorded in [`tests/cassettes/usitc.yaml`](../tests/cassettes/usitc.yaml)
(`bun run record:usitc`; no token is sent). The IDS fixture holds three real
rows with lists cut to one entry and staff contacts removed.

Not live-verified: EDIS attachment download and DataWeb `runReport`. Both
deployed tokens in Secret Manager (`usitc-edis-token`, `usitc-dataweb-token`
in `patentclient-mcp`) are expired JWTs (EDIS on May 27, 2026; DataWeb on
September 27, 2026), so those paths are tested with synthetic responses only.
Mint new tokens to verify them. Whether EDIS accepts the `337-TA-1234` form
was not probed (the edge blocked the probe); tools pass the number through as
Python does, and EDIS's own form is `337-1234`.

## Differences from Python

These are Python defects; Python is unchanged.

- Python checks the EDIS token's `exp` before every request, so an expired
  token breaks the public search tools too. TypeScript sends the token on
  metadata requests only while it is unexpired and requires a fresh token
  only for downloads (`AUTH_REQUIRED` / `AUTH_EXPIRED`).
- Python drops `phase` when `search_usitc_investigations` has no
  investigation number. TypeScript sends it as the `investigationPhase`
  filter.
- Python returns the raw `Content-Disposition` header as the attachment
  filename. TypeScript parses the filename.
- Python's HTS model reads `heading` and `chapter` fields the API does not
  have, so they are always null. TypeScript derives them from the HTS number
  and, with `full=true`, keeps every upstream field (rates, units, indent,
  footnotes) instead of four.
- Python's `list_saved_queries` expects a bare list and always returns
  nothing. TypeScript unwraps `list`.
- Python's DataWeb row count looks for `dto.rows`/`results`/`data`, which the
  API does not return. TypeScript counts `dto.tables[].row_groups[].rowsNew`.
- Python's date-filtered document search and investigation bulk download
  stop silently at 30 and 50 pages. TypeScript says when the 3,000-document
  scan was truncated and refuses a bulk download whose listing exceeds 50
  pages, asking for `item_ids`.
- Python's `item_ids` parsing accepts any middle segment; TypeScript requires
  `{doc}/attachments/{att}`. Dates must be valid ISO dates.
- Python's `get_*_resource` helpers read from a nonexistent `law_tools`
  package and are not registered as MCP resources. They are not ported.
- DataWeb also fails fast on an expired token rather than returning
  Akamai's 403.

Other differences: multi-attachment downloads return one ZIP with
`manifest.json` (Python returned resource links plus a ZIP manifest), as the
PTAB downloads here do; attachment listing runs 8 at a time instead of 20;
there is no HTTP cache, so every `list_ids_investigations` call downloads the
whole IDS feed (Python's hishel cache served repeats).
