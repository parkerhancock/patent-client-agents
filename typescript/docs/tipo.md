# TIPO OpenData (Taiwan)

October 27, 2026. `TipoClient` ([source](../packages/client/src/tipo.ts)) ports
the Python `tipo_opdata` package: the 15 GET endpoints of TIPO's OpenData REST
API for patents, utility models, designs and trademarks. The
[MCP adapter](../packages/mcp/src/tipo.ts) serves the fourteen Python TIPO
tools with the same names. The data is bibliographic only, with no claims,
abstracts or figures. The curated facade doesn't route to TIPO, in Python or
here.

Every endpoint was recorded live on October 27 with the demo token TIPO
publishes for data.gov.tw dataset 35466. That token is cited in
`research/specs/tw-tipo-connector-spec.md` and is never stored here.

## Specification and credentials

Endpoints and filters follow TIPO's Swagger 2.0 specification, "OpenData -
Patent & TMark" version 1.0, archived at
[references/tipo/oas.json](../references/tipo/oas.json). Its URL, retrieval
date and SHA-256 are in `sources.json`. `TIPO_ENDPOINTS` lists each endpoint's
documented filters, and a test checks the table against the archived file.

Auth is a `tk` UUID token in the query string. TIPO issues it on application
to ipoid@tipo.gov.tw. `TIPO_API_KEY` (or the `tk` option) enables the
connector. The MCP server registers the tools only when it is set, under the
`tipo:read` scope. The token is filtered from cassettes. The shared transport
now also drops a `tk` parameter from provenance URLs, as it already did for
`key`, `token` and the like.

## Behavior the recordings established

- An unknown token is not an HTTP error. TIPO answers 200 with
  `"status": "sample"`, a message saying the token failed, and 25 rows of
  sample data. The client raises `AUTHENTICATION_FAILED`.
- TIPO ignores filter names it doesn't recognize and returns the unfiltered
  dataset. The client refuses any filter the specification doesn't document
  for that endpoint, before sending.
- `applno` is an exact match. A partial number finds nothing.
- An empty result is `"status": "ok"`, `total-count` 0 and the message
  輸入條件查無資料 ("no data for these conditions"). The client returns an
  empty page.
- Dates in filters must be `YYYY/MM/DD` or `YYYYMMDD`. ISO dates get HTTP 400
  with 參數 日期格式 錯誤 ("date format error"). The client accepts ISO,
  slash or compact dates and sends `YYYY/MM/DD`.
- Nice classes (`goodclasscode`) are three digits: `017` matches and `17`
  doesn't. The client zero-pads one- and two-digit classes.
- `tmarkclass` is the kind of mark (trademark, collective mark, ...), not the
  Nice class.
- `PatentTwins` answers with two parallel lists, `twins-announceds` and
  `twins-approveds`. Rows from both are returned, each tagged with `list`.
- `TmarkPics` sends `tmark-image-url` as an object. The other trademark
  endpoints send it as a list.
- Divided trademark registrations keep the parent's application number, so
  `TmarkRights` for one application can return a whole family of
  registrations.
- The specification marks `applclass` required on `PatentAppl`,
  `PatentRights` and `PatentTwins`, and `querytype` on `PatentDivide`. The live
  API answers lookups without `applclass`. `querytype` is still sent.

Rows keep TIPO's shape: kebab-case keys and `-sequence`, which is only the
row's position on the page. `YYYY/MM/DD` strings anywhere in a row become ISO
dates, and all-zero placeholder dates become null. Python converted only the
dates its models named. The page carries `total_count`, `more_available`, the
dataset build date (`created`) and TIPO's message. Library queries default to
100 rows (Python's default was the 6,000-row maximum). `paginate` walks past
the cap.

## Library surface

| Python | TypeScript |
| --- | --- |
| `search_patent_appl`, `search_tmark_appl` and the 13 `get_*` methods | `query(endpoint, { filters, top, skip, orderby })` with documented filter names |
| any method's `appl_no=` | `getByApplicationNumber(endpoint, number)` on the 14 endpoints that document `applno`; `TmarkDivide` has none |
| `paginate` | `paginate(endpoint, options)` |

## MCP tools

The tool names are Python's. Parameters keep Python's names and are mapped
onto documented filters:

- `search_tipo_patents`:
  - `q` searches the title (`patentname`).
  - `applicant` uses `applnamec` for Chinese names and `applnamee` for
    others.
  - The dates map to `applbdate` and `appledate`.
  - A new `register` parameter picks the dataset: `rights` (the default:
    granted patents of all three classes), `publications` (published
    invention applications) or `applications` (every application). Python
    searched `PatentAppl`, which has no title or applicant filter at all. The
    `applications` register refuses `q` and `applicant`.
- `search_tipo_trademarks`:
  - `q` searches the mark name (`tmarkname`).
  - `tmark_class` is the Nice class (`goodclasscode`).
  - `applicant` and the dates map as for patents.
- The lookup tools use `applno`:
  - `get_tipo_patent` and `get_tipo_trademark` report numbers with no record
    in `not_found`. The facet tools (rights, priority, annuity, images and so
    on) don't.
  - `get_tipo_patent_twins` tries the number as a utility model (`applno`),
    then as an invention (`twinsapplno`).
- `get_tipo_patent_events` merges assignments (`PatentAlteration`) with
  conversions (`PatentChange`) and divisionals (`PatentDivide`). Conversions
  and divisionals are searched in both directions, by `applno` and by
  `newapplno`.
- `get_tipo_trademark_events` merges transfers (`TmarkChange`) with
  divisions. `TmarkDivide` can't be searched by application number, so the
  tool looks up the registrations (`TmarkRights`) first, then searches
  divisions by `examno` and `originexamno`. Events that several queries
  return are listed once.

Lean output, the default, drops nulls, empty strings and `ftps://` pointers
to TIPO's XML mirror. Python's lean list named keys TIPO rows never carry, so
it dropped nothing. Every envelope carries the Taiwan Open Government Data
License attribution as `attribution`.

## Python bugs corrected

Python's lookups had never worked:

- Python sent `appl-no`, `q`, `appl-date-from`, `appl-date-to`, `applicant`
  and `tmark-class`, none of which TIPO documents. TIPO ignored them, so
  `get_tipo_patent("113105712")` returned the first rows of the whole
  database (`06202104`, `06210001`), and `not_found` could never fire. Every
  lookup and filtered search returned unrelated records.
- A rejected token's sample data was returned as real data, because Python
  never read `status`.
- `TmarkPics` rows failed Python's model, which expected a list.
- `PatentTwins` lost its `twins-approveds` list.
- `TmarkDivide` was queried by application number, a filter it doesn't have.
- The `sequence` field was always null, because rows carry `-sequence`.

## Evidence

[`scripts/record-tipo.ts`](../scripts/record-tipo.ts) (`bun run
record:tipo`, with `TIPO_API_KEY` set) records 32 cassettes:

- 20 library operations covering all 15 endpoints, including searches, an
  unknown number and an invalid date;
- one unknown-token response;
- 11 MCP tool calls.

[Client tests](../tests/tipo-client.test.ts) replay them and check the
filter table against the specification, the absence of tokens on disk, date
and class normalization, error statuses and pagination.
[MCP tests](../tests/tipo-mcp.test.ts) run the tools through a real client
and check `tipo:read` on the authenticated HTTP listener.

The recordings use the demo token. A token issued to a production user may
see the same data with different daily limits; none are documented.
