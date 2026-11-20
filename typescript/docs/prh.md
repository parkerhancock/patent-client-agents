# PRH (Finland)

October 27, 2026. `PrhClient` ([source](../packages/client/src/prh.ts)) ports
the Python `prh_fi` package. It covers the unauthenticated JSON APIs behind
PRH's three search services:

- patents, utility models, EP validations and SPCs on
  `patenttitietopalvelu.prh.fi`, with search and the register record;
- national trademarks and the well-known trademarks register on
  `tavaramerkkitietopalvelu.prh.fi`;
- national designs on `mallioikeustietopalvelu.prh.fi`;
- mark and design images from both of the last two.

The [MCP adapter](../packages/mcp/src/prh.ts) serves the seven Python PRH
tools with the same names. They need no credentials, so the server always
registers them, under `prh:read` over HTTP. The curated facade doesn't route
to PRH.

The APIs are undocumented. Request shapes follow PRH's patent app
(`static/js/main.05f306a4.js`, the same build Python decoded on May 18 and
still current on October 27). Every request's User-Agent names
avoindata@prh.fi, where PRH asks reusers to register.

## Inclusion lists

The patent search takes three inclusion lists. A patent is returned only if
its status, its type and its publication types all appear in them, and an
empty list returns nothing.

The client sends the app's defaults (`In`, `Mn` and `Ln` in the bundle):
117 statuses, 4 patent types and 42 publication types. Python's copies had
only 36 of the statuses, plus 8 the app doesn't use, and an outdated
publication list missing 14 types. Its searches found a fraction of the
matches. Measured live on October 27:

| Query | Python's lists | App's lists |
| --- | --- | --- |
| applicant "Nokia" | 208 | 7,513 |
| applicant "Kone" | 359 | 1,617 |
| IPC H04W | 1,568 | 6,997 |
| filed in 2015 | 2,478 | 7,576 |
| Nokia, filed February 2024 (recorded) | 8 | 84 |

## Behavior the recordings established

- **No paging.** Searches return every match in one response, up to 3,000
  rows, and `totalResults` gives the full count. A "tuoli" (chair) design
  search returns all 491 dossiers, 527 KB. The library returns the rows PRH
  sends and sets `capped` when `totalResults` is larger.
- **The MCP tools return a window.** They take `limit` (default 25, at most
  200) and `offset`, and `more_available` reports whether more rows exist.
  Python returned every row at once.
- **Dates.** Filters take `YYYY-MM-DD`. Other formats get HTTP 400, so the
  client checks dates before sending.
- **Record numbers.** Records take the bare application number
  (`20245203`). `FI20245203` gets HTTP 400, so the client drops an `FI`
  prefix. An unknown number is HTTP 404, which the client raises as
  `NOT_FOUND`.
- **Images.** These are GIF or JPEG. A body that isn't an image is an
  error, such as the HTML 404 page PRH serves for unknown marks.

Rows keep PRH's camelCase shape. The lean projections are Python's:

- search rows drop `ordinal`;
- trademark and design rows also drop the thumbnail URLs;
- records drop `documents`, `paymentDetails` and `events`.

Pass `full` to keep all of them.

## Evidence

[`scripts/record-prh.ts`](../scripts/record-prh.ts) (`bun run record:prh`)
records 14 cassettes:

- 10 library operations:
  - the same patent search with the app's lists and with Python's;
  - a patent record, with and without the `FI` prefix, plus an unknown
    number;
  - trademark, well-known and design searches;
  - a trademark thumbnail and a design thumbnail;
- 4 MCP tool calls.

[Client tests](../tests/prh-client.test.ts) check the recorded responses,
the 30-field patent body, date and field validation, and errors.
[MCP tests](../tests/prh-mcp.test.ts) run the tools through a real client,
including an image artifact, and check `prh:read` on the authenticated HTTP
listener.
