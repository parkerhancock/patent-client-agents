# Federal Court of Canada court files

October 22, 2026. `CanadaFederalCourtClient`
([source](../packages/client/src/canada-federal-court.ts)) ports the Python
`canada_federal_court` package: party searches, case metadata with parties,
counsel, IP references and related files, and recorded docket entries with a
conservative inferred status.

## Source

The Court's Court Files page
(https://www-u.fct-cf.gc.ca/en/court-files-and-decisions/court-files) loads
its data from keyless JSON endpoints under `/CourtFilesAndDecisions/`, each
answering `{ Count, data: [...] }`. The client sends plain GET requests with
the project's user agent; no cookie, session or browser header is needed.

| Operation | Endpoints |
| --- | --- |
| `searchPartyCases` | `ProceedingsQueriesPartyInfo`, or `ProceedingsQueriesPartyInfoDates` with `from`/`to` as `MM-DD-YYYY` |
| `getCase` | `proceedingQueriesAddInfo`, `PublicPartiesListInfo`, `PartyInfoIntlProp` and `RelatedListInfo`, in parallel |
| `listDocketEntries` | `proceedingQueriesRE` |

`division` selects the Federal Court (`t`, the default), the Federal Court of
Appeal (`a`) or both (`b`). A search matches the party name on either side of
a file. `patentOnly` (the default) keeps files whose English or French nature
label contains "patent" or "brevet", which includes Patented Medicines (NOC)
actions. Results are sorted newest filing first and cut to `limit` (1-100);
`upstream_count` is the Registry's count before filtering.

A file number the Registry does not know returns an empty array, which
`getCase` reports as `ApiError` 404 `NOT_FOUND`. A payload without a `data`
array, or a row missing its file number, style of cause, entry number or
entry text, fails as `INVALID_RESPONSE` rather than becoming an empty result.

Docket entries carry `download_url` when the Registry marks the document
publishable and not confidential, mirroring the page's own download button.
On October 22 both the client and curl received `200 application/pdf` with
an empty body from that URL for a publishable 2024 statement of claim, so the
link is reported but not fetched.

## Status assessment

The Court publishes no open/closed field. `assessDocketStatus` reproduces
Python's heuristic: a terminal phrase ("notice of discontinuance", "final
judgment", ...) in any of the ten most recent entries means `likely_closed`;
otherwise a prospective phrase ("hearing scheduled", "seeking first case
management conference", ...) in the latest entry means `likely_pending`;
anything else is `unknown`. Every status carries `inferred: true` and the
phrase it rests on.

## Differences from Python

- **Periods in names.** Python, copying the page's script, sends every `.`
  in a party name as `xxyxx`. The current endpoint does not decode it, so any
  name with a period matches nothing ("Apotex Incxxyxx": 0 files; "Apotex
  Inc.": 2). The client sends the name as typed. The Registry stores most
  corporate names without periods, so "Apotex Inc" (684 files) still beats
  "Apotex Inc."; the tool description says so.
- **Filing dates.** `/Date(ms)/` values are local Eastern times serialized as
  UTC instants with the current daylight-saving rule applied to every year.
  Python took the UTC date, which is a day late for evening filings: T-649-23
  was filed at 23:41 Eastern on March 30, 2023 (the IP endpoint's ISO
  `FILE_DT` says so) and Python reports March 31. The client inverts the
  server's conversion; 1982 files filed at local midnight come back as the
  right day too.
- **Whitespace in status phrases.** The Registry writes `seeking  first case
  management conference` with a double space, so Python's marker never
  matched. The client collapses whitespace before matching; T-2962-24 now
  reads `likely_pending` where Python said `unknown`.
- **Duplicate rows.** The party search sometimes lists one file twice (28 rows
  for 27 files in the recording). The client keeps one row per file and
  merges party names; `upstream_count` still reports the Registry's count.
- Entry summaries and registry notes are trimmed of the leading spaces the
  Registry adds.

## MCP tools

The full toolset serves `search_canada_federal_court_patent_cases`,
`get_canada_federal_court_case` and `list_canada_federal_court_docket_entries`
under the `fct:read` scope, with Python's parameter names, lean projections
and summaries. The search fetches up to five dockets at a time to attach a
status to each hit; a failed lookup leaves that hit `unknown` instead of
failing the search. `get_canada_federal_court_case` accepts one file number
or a list of up to 50: a single missing file is an error, missing list
members go to `not_found`. Provenance points at the Court Files page (with
`?courtNumber=` for dockets), as in Python, and `as_of_status` carries the
inferred status. The connector is not routed by the curated facade, matching
Python.

Browsers reach the Court through the relay, which allows `www-u.fct-cf.gc.ca`;
the Court sends no CORS headers.

## Tests

`bun run record:canada-federal-court` records one session
([recorder](../tests/canada-federal-court-recordings.ts)): patent-only and
unfiltered searches for "Taro Pharmaceuticals", a dated Pfizer search, a
dotted name, two case records, a docket, a missing file and the three MCP
helpers. The [tests](../tests/canada-federal-court.test.ts) replay it offline
and cover date parsing, status markers, input validation, malformed
payloads, the full-toolset tools and the `fct:read` scope over HTTP.
