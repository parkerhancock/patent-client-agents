# PRV (Sweden)

October 27, 2026. `PrvClient` ([source](../packages/client/src/prv.ts)) ports
the Python `prv_se` package. It covers the unauthenticated JSON APIs behind
search.prv.se:

- patent and SPC search on `patents-search-api.prv.se`;
- trademark and design search on `dv-search-api.prv.se`;
- the patent register record on `api.prv.se`.

The [MCP adapter](../packages/mcp/src/prv.ts) serves the five Python PRV
tools with the same names and parameters. They need no credentials, so the
server always registers them, under the `prv:read` scope over HTTP. The
curated facade doesn't route to PRV.

The APIs are undocumented. Request shapes follow PRV's own web app bundle
(`search.prv.se/main.7a8cf370.js`, fetched October 27, 2026). Every request
identifies itself with a User-Agent that names data@prv.se, where PRV asks
reusers to register. Register data is reusable under Sweden's Open Data Act
(SFS 2022:818).

## Behavior the recordings established

- **Patent records go by the number's prefix.** `SE2616246-1` and
  `EP00108480.5` work. The compact forms Python documented (`26162461`,
  `2616246-1`) get HTTP 400, "Unknown applicationType", and the
  `applicationType` query parameter makes no difference.
  `prvApplicationNumber` adds the `SE` prefix and the check-digit dash, and
  the `EP` dot.
- **An unknown patent is HTTP 404** with a message, for example "There is no
  national patent with applicationNumber 99999999". The client raises
  `NOT_FOUND`.
- **`totalPages` is the last zero-based page index, not a count.** It's 1801
  for 3,604 hits at two per page, 0 for one hit and -1 for none. The client
  reports `total_pages` as a real count and computes `more_available` from
  `totalHits`.
- **The page-size limit is PRV's own choice, not the API's.** PRV accepts
  pages of 500. The client keeps Python's limit of 100.

## SPC search

The SPC request uses the field names PRV's app sends, not the names on its
search form:

| Filter | Request key | Match types PRV accepts |
| --- | --- | --- |
| substance | `substance` | CONTAINS (default), STARTS_WITH, EXACT |
| applicant | `applicants` | CONTAINS (default), STARTS_WITH, EXACT |
| SPC number | `applicationNumberSpc` | STARTS_WITH (default), EXACT; CONTAINS gets HTTP 500 |
| base patent | `applicationNumber` | STARTS_WITH (default), EXACT; CONTAINS gets HTTP 406 |
| marketing authorization | `firstMarketingAuthorization` | CONTAINS; STARTS_WITH gets HTTP 406 |
| announcement | `announcement` | EXACT, from PRV's fixed list of Swedish announcement types |

A requested `match_type` applies where the field accepts it. Otherwise the
field uses its default.

Substances are recorded as PRV writes them, often in Swedish, for example
"tabletter med modifierad frisättning innehållande naproxen och
esomeprazol". At least one filter is required. An empty SPC query returns no
rows; Python's note that it fails with HTTP 500 is out of date.

## Python bugs corrected

- **SPC filters:** Python sent the search form's field names
  (`substanceProduct`, `applicationNumberSPC`, `basePatentNumber`,
  `marketingAuthorizationNumber`). PRV ignores them, so four of its six SPC
  filters never found anything. Python also searched number fields with
  CONTAINS, which PRV rejects.
- **Paging:** `more_available` compared `page + 1` with `totalPages`, a last
  index. It read false on the second-to-last page.
- **Compact numbers:** the compact application numbers Python documented
  failed with HTTP 400.
- **Announcement filter:** Python treated it as free text. PRV matches it
  exactly against a fixed list.

## Evidence

[`scripts/record-prv.ts`](../scripts/record-prv.ts) (`bun run record:prv`)
records 17 cassettes:

- **13 library operations:** patent search with two pages, trademark search,
  design search, five SPC filters, national, compact and EP records, and an
  unknown number.
- **4 MCP tool calls.**

[Client tests](../tests/prv-client.test.ts) check the recorded responses and
the request bodies, number normalization, match-type fallback, paging and
error handling. [MCP tests](../tests/prv-mcp.test.ts) run the tools through
a real client and check `prv:read` on the authenticated HTTP listener.

## Not ported

PRV's app also calls trademark and design record endpoints
(`api.prv.se/trademarks/applications/{id}`, `/designs/applications/{id}`),
advanced searches, gazette searches and document downloads. Python never
wrapped them, and this port doesn't either.
