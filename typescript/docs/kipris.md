# KIPO KIPRIS Plus (Korea)

October 21, 2026. `KiprisClient` ([source](../packages/client/src/kipris.ts))
ports the Python `kipo_kipris` package: word search, advanced search and
by-number retrieval over the three KIPRIS Plus information-search services
(patents and utility models, trademarks, designs). The
[MCP adapter](../packages/mcp/src/kipris.ts) serves the nine Python tools and
the curated facade's Korean branches. Nothing here has been checked against
the live API.

## Credentials and endpoint

KIPRIS Plus authenticates with a per-user `serviceKey` query parameter. Its
terms (§11) forbid sharing a key, so the connector is bring-your-own-key only.
As in Python, two variables are required:

- `KIPO_KIPRIS_API_KEY`, the serviceKey. Supply the decoded form of the key;
  the client URL-encodes it. (data.go.kr issues both an "encoding" and a
  "decoding" key; the encoded one would be encoded twice.)
- `KIPO_KIPRIS_BASE_URL`, an HTTPS endpoint the operator has verified. KIPRIS
  documents only `http://kipo-api.kipi.or.kr/openapi/service`, and an HTTP
  request would carry the key in clear text, so the client refuses any
  non-HTTPS base URL.

The client also accepts `serviceKey`/`apiKey` and `baseUrl` options, so it runs
in Bun, Node and browsers without environment variables. The MCP server builds
the client lazily, and only when the key is set and the base URL starts with
`https://`. Otherwise the nine `*_kipo_*` tools are not registered (Python's
`conditional_tool` rule), and the facade's KR branches report
`... is not enabled on this server (KIPO_KIPRIS_API_KEY/KIPO_KIPRIS_BASE_URL is
not configured)` with the alternative Python suggests. The tools use the
`kipo:read` scope. `patent_client_status` lists both variables under `kipo`.

The browser relay is unchanged. It injects the operator's office keys for
relay users; doing that for KIPRIS would share one key among users, which §11
forbids.

## Requests and parsing

Each operation is a GET to `{base}/{service}/{operation}` with Python's
parameter names (`word`, `patent=Y|N`, `utility=Y|N`, `inventionTitle`,
`inventors`, `ipcNumber`, `applicantName`, `viennaCode`, `locCode`,
`numOfRows`, `pageNo`, ...). `numOfRows` is capped at 1000. Extra filters pass
through verbatim, but no caller value can replace `serviceKey`. By-number
retrieval is advanced search with `applicationNumber`, since KIPRIS has no
fetch endpoint. MCP fan-out over a list is serial (Python's quota caution), and
a number with no rows lands in `not_found`, for a single string as well as a
list, as in Python.

Responses are parsed with fast-xml-parser, as EPO OPS and TSDR are. A
`resultCode` other than `00` is an `ApiError` (`UPSTREAM_ERROR`) carrying the
code and message. The data.go.kr gateway's `OpenAPI_ServiceResponse` error
envelope is recognized the same way. Rows keep their camelCase element names;
modeled dates become ISO dates by Python's `parse_iso_date` rules, empty
elements become null, and unmodeled elements are kept as text. Provenance
names the operation URL on the configured endpoint without the key, and its
`source_name` is Python's ToS §11 attribution line.

Lean stubs match Python's `_lean_patent`, `_lean_trademark` and `_lean_design`
field for field; `full=true` returns the whole row. Summaries,
`more_available` and `next_cursor: null` follow Python.

## Differences from Python

These are Python bugs or gaps; Python is unchanged.

1. Python provenance cites the documented HTTP endpoint even though requests go
   to `KIPO_KIPRIS_BASE_URL`. TypeScript cites the endpoint actually used.
2. The Python facade enables KR routing when only `KIPO_KIPRIS_API_KEY` is
   set; without `KIPO_KIPRIS_BASE_URL` the call then fails with a client
   configuration error. TypeScript requires both before routing to KIPRIS.
3. Python's `full=True` documentation promises the upstream row, but its
   Pydantic models drop unmodeled elements. TypeScript keeps them.
4. Python computes `more_available` from the requested page size even when the
   client capped it at 1000. TypeScript uses the capped size.
5. Python accepts a missing `<body>` as an empty result. TypeScript treats it
   as `INVALID_RESPONSE`, so a malformed reply never looks like zero hits. It
   also rejects DTD and entity declarations, and validates `num_of_rows` and
   `page_no` as positive integers (Python passed any integer through).
6. `right_type` is an enum (`patent`, `utility_model`, `both`). Python accepted
   any string, and an unknown value silently searched neither subset.

## Evidence

The Python fixtures in `../tests/kipo_kipris/fixtures/` are synthetic. The
Python conftest says so: no key has been issued, because signup requires
Korean phone or i-PIN verification. One sign is the error fixture, which pairs
result code `30` with `SERVICE_KEY_DAILY_QUOTA_EXCEEDED`; on data.go.kr, code
`30` means an unregistered key and quota errors are `22`. So the service
names, parameter names, row fields and envelope shape all rest on the
[spec](../../research/specs/kr-kipo-connector-spec.md) and the Python author's
reading of KIPRIS documentation, not observed traffic. In particular, the
patent service path `patUtliInfoSearchService` was not confirmed against
KIPRIS documentation, and it is not known whether advanced search accepts a
publication number in `applicationNumber`, as the Python tool descriptions
suggest.

The [tests](../tests/kipris.test.ts) replay those fixtures through a synthetic
fetch: configuration rules, request parameters for every operation, row
normalization, result-code and gateway errors, malformed bodies, pagination,
all nine MCP tools (lean and full output, summaries, not-found batches,
registration only when configured) and both facade branches with and without
a client. No test touches the network.

## Live check once a key exists

Put the key and endpoint in the ignored `typescript/.env` (Bun loads it), never
on the command line or in a committed file. Then, from `typescript/`:

```bash
bun -e '
import { KiprisClient } from "@patent-client-agents/client";
const client = new KiprisClient();
for (const [label, page] of [
  ["patents", await client.searchPatentsWord("battery", { numOfRows: 2 })],
  ["patent by number", await client.getPatent("1020230012345")],
  ["trademarks", await client.searchTrademarksWord("galaxy", { numOfRows: 2 })],
  ["designs", await client.searchDesignsWord("phone", { numOfRows: 2 })],
])
  console.log(label, JSON.stringify(page.pagination), page.items.length, Object.keys(page.items[0] ?? {}).join(","));
'
```

A pass prints a `00` result code, a numeric `totalCount` and rows for each
call. Compare the printed element names with the modeled fields in
`kipris.ts`; unexpected names are kept in full rows but may deserve lean-stub
fields. A 404 or a non-XML error points at the service paths; a result code
other than `00` names the problem. Then run `PCA_TOOLSET=curated` with the same
variables and call `search_patents` with `jurisdiction='kr'` and `get_patent`
with `view='biblio'` on a KR number. If the check succeeds, record real
responses as fixtures with the serviceKey removed, run
`gitleaks protect --staged --redact`, and replace or supplement the synthetic
ones.
