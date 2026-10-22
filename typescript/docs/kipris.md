# KIPO KIPRIS Plus (Korea)

October 22, 2026. `KiprisClient` ([source](../packages/client/src/kipris.ts))
ports the Python `kipo_kipris` package and retargets it at the live KIPRIS
Plus API. It covers word search, advanced search, by-number lookup and
bibliography detail for patents and utility models, trademarks and designs.
The [MCP adapter](../packages/mcp/src/kipris.ts) serves the nine Python tools
and the curated facade's Korean branches. Nothing here has run against the API
with a registered key.

## Endpoint and credentials

The Python connector targeted `http://kipo-api.kipi.or.kr/openapi/service`.
That host is gone: on October 22 it redirected to a 503 page over HTTP and gave
no HTTPS response. The live API is
`https://plus.kipris.or.kr/kipo-api/kipi/{service}/{operation}`, and that is
the client's default. Without a registered key it answers every path with HTTP
200 and a `<response><header>` envelope carrying result code 30.

Authentication is a per-user `ServiceKey` query parameter (the casing every
documented sample uses). KIPRIS Plus terms (§11) forbid sharing a key, so the
connector is bring-your-own-key only:

- `KIPO_KIPRIS_API_KEY` is required. It alone enables the family: the MCP
  server registers the nine `*_kipo_*` tools under the `kipo:read` scope, the
  facade routes KR search and biblio to KIPRIS, and `patent_client_status`
  reports `kipo` as configured. Supply the key as issued; the client
  URL-encodes it.
- `KIPO_KIPRIS_BASE_URL` is an optional override, for a proxy or mirror. It
  must use HTTPS, because the key travels in the query string. An HTTP
  override makes the client refuse to start, and the server then leaves the
  tools unregistered.

Library callers can pass `serviceKey` (or `apiKey`) and `baseUrl` instead, so
the client runs in Bun, Node and browsers without environment variables. When
the key is missing, the facade's KR branches say
`... is not enabled on this server (KIPO_KIPRIS_API_KEY is not configured)`
with the alternative Python suggests.

The browser relay is unchanged. It injects the operator's office keys for
relay users; doing that for KIPRIS would share one key, which §11 forbids.

## Documentation followed

Operation names, parameters and response elements come from the KIPRIS Plus
Open API pages, fetched October 22, 2026:

- Patent-Utility Model Publications (`patUtiModInfoSearchSevice`):
  https://plus.kipris.or.kr/eng/data/clas/DBII_000000000000001/view.do?menuNo=310000
- Trademark Bulletins (`trademarkInfoSearchService`):
  https://plus.kipris.or.kr/eng/data/clas/DBII_000000000000012/view.do?menuNo=310000
- Designs (`designInfoSearchService`):
  https://plus.kipris.or.kr/eng/data/clas/DBII_000000000000008/view.do?menuNo=310000

Each page loads an operation's parameter tables and sample request and
response from `.../{bCode}/{ADI id}/ajaxOperation.do`. The nine operation
fragments used here (word search, advanced search and bibliography detail per
service) are archived in [references/kipris](../references/kipris) with URLs
and SHA-256 receipts in `sources.json`. `operations.json` there is the
extracted parameter tables and samples.

What the documentation establishes:

- Search responses are `<response><header>…</header><body><items><item>…`
  with paging in `<count>` (`numOfRows`, `pageNo`, `totalCount`), a sibling of
  `<body>`, not inside it.
- Every search allows at most 500 rows per page. Patent flags (`patent`,
  `utility`) are `true`/`false`.
- Patent word search takes `word`; advanced search takes `inventionTitle`,
  `astrtCont`, `claimScope`, `applicant`, `inventors`, `ipcNumber`,
  `applicationNumber`, date ranges such as `applicationDate=YYYYMMDD~YYYYMMDD`,
  and more.
- Trademark word search takes `searchString`. Advanced search takes
  `trademarkName`, `applicantName`, `classification`, `viennaCode`,
  `applicationDate`, `registerDate` and others, and rejects a request unless at
  least one flag is true in each of three groups (status, mark type, mark
  composition). The client sends all 30 flags as `true` by default, as the
  documented sample does; callers can override any of them through `extra`.
- Design word search takes `articleName` (which also matches applicants and
  designers). Advanced search takes `articleName`, `applicantName`,
  `designMainClassification`, `registrationDate` and others, plus status and
  type flags (`open`, `rejection`, `destroy`, `cancle` [sic], `notice`,
  `registration`, `invalid`, `abandonment`, `simi`, `part`, `etc`), which the
  client also sends as `true`.
- Bibliography detail (`getBibliographyDetailInfoSearch?applicationNumber=`)
  returns a nested record: under `<body><items>` for patents and `<body><item>`
  for trademarks and designs. The client returns it as a tree (repeated
  elements become arrays, `type` attributes are dropped). There is no MCP tool
  for it, as in Python.
- Dates appear as `YYYYMMDD`, `YYYY.MM.DD` (bibliography) and, in older
  samples, `YYYY/MM/DD 00:00:00`. All become ISO dates. Multi-value IPC and
  applicant fields are separated by `|`; trademark classes and Vienna codes by
  spaces.

## Result codes

A `resultCode` other than `00` becomes an `ApiError` naming the code and
message, with a hint. A success without `<body>` is `INVALID_RESPONSE`, never
an empty result; an empty `<body/>` is an empty result. No KIPRIS-specific
code table was found in the documentation. Codes 10
(`INVALID_REQUEST_PARAMETER_ERROR`, status 400) and 30
(`SERVICE_KEY_IS_NOT_REGISTERED_ERROR`, status 401) were observed live. The
client also maps the data.go.kr common codes KIPRIS appears to share (11, 12,
20, 22, 23, 31, 32), but those meanings are unconfirmed for KIPRIS Plus.
Anything else is status 502, `UPSTREAM_ERROR`.

## Differences from Python

Python is unchanged; these are what the TypeScript port does differently.

1. Endpoint: the live HTTPS endpoint by default, not the dead
   `kipo-api.kipi.or.kr` host, and a key alone enables the family. Python
   required an operator-supplied HTTPS URL.
2. Key parameter `ServiceKey`, not `serviceKey`; patent service
   `patUtiModInfoSearchSevice`, not `patUtliInfoSearchService`.
3. `patent`/`utility` flags are `true`/`false`, not `Y`/`N`; the row cap is
   500, not 1000.
4. Trademark word search sends `searchString` (Python sent `word`); advanced
   search sends `trademarkName` and `registerDate` (Python sent `title` and
   `registrationDate`) and the required flag groups.
5. Design word search sends `articleName` (Python sent `word`); advanced
   search sends `designMainClassification` for the tool's `loc_code` (Python
   sent `locCode`, which is not documented). KIPRIS offers no Locarno filter,
   so `loc_code` filters the KIPO design classification (for example `M1110`).
   The parameter keeps its Python name for compatibility.
6. Paging is read from `<count>`; Python read it from `<body>` and so would
   have reported no total against the live API.
7. Row fields follow the documented elements. Patent search rows have no
   `inventionTitleEnglish`, `inventorName` or `agentName`, so the lean patent
   stub drops `invention_title_english` and `inventor_name`. Design rows have
   no `drawing`, `registerStatus` or `locCode`; the lean design stub maps
   `register_status` from `applicationStatus`, `drawing` from `imagePath`, and
   replaces `loc_code` with `design_classification` from
   `designMainClassification`. Trademark stubs keep Python's keys.
8. Bibliography detail is new in the client.
9. Carried over from the first port: provenance names the endpoint actually
   used, without the key; `full=true` keeps unmodeled elements; a missing
   `<body>` is an error; DTDs are rejected; `num_of_rows`/`page_no` must be
   positive; `right_type` is an enum.
10. `get_kipo_*` look up by application number only. Python's descriptions
    also offered publication or registration numbers, but it sent only
    `applicationNumber`; the descriptions now say application number.

## Evidence

The [fixtures](../tests/fixtures/kipris) are doc-derived, not recorded: the
sample responses printed on the operation pages above, trimmed to two items
for searches. Each file says so in a comment. The two error fixtures
(`result-10-…`, `result-30-…`) have the envelope observed live on October 22
without a registered key. Inline responses in the tests (empty, paged and
malformed bodies, other codes) are synthetic. The Python fixtures are no
longer used: they were synthetic too, and their envelope and field names do
not match the documentation.

The [tests](../tests/kipris.test.ts) replay these through a synthetic fetch:
endpoint and key rules, the documented parameters for every operation, row
normalization, bibliography trees, result codes, malformed bodies,
pagination, all nine MCP tools, registration with and without a key, and both
facade branches. No test touches the network. A cassette replay test is
skipped until a cassette exists.

## Live check and recording once a key exists

Export the key in the shell, or inject it from a secret manager, for the one
command. Do not put it in a file in the repository, including
`typescript/.env`. From `typescript/`:

```bash
read -rs KIPO_KIPRIS_API_KEY && export KIPO_KIPRIS_API_KEY
bun run record:kipris
```

or, with the key in Secret Manager (substitute your secret and project):

```bash
KIPO_KIPRIS_API_KEY="$(gcloud secrets versions access latest --secret=kipris-api-key)" bun run record:kipris
```

`record:kipris` ([script](../scripts/record-kipris.ts),
[session](../tests/kipris-recordings.ts)) runs a word search, an advanced search, a
by-number lookup and a bibliography detail call per service (ten requests),
prints only counts, and writes `tests/cassettes/kipris.yaml` with the
`ServiceKey` replaced by `REDACTED`. If the key appears in the cassette in any
encoding, the script moves it to `kipris.yaml.unsafe` and fails; delete that
file. A pass shows result code 00 with rows for each search. A result-code
error names the problem (30: key not registered or not approved for that
service; 10: a parameter the operation rejected).

Then run `bun test tests/kipris.test.ts`; the replay test runs once the
cassette exists. Compare the recorded element names with the modeled fields in
`kipris.ts`, and replace or supplement the doc-derived fixtures where they
differ. Finally `git add` the cassette and run
`gitleaks protect --staged --redact` before committing. The cassette helper's
query filter and replay with the `REDACTED` key are untested until the first
recording.
