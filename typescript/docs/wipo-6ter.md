# WIPO Article 6ter

October 27, 2026. `Wipo6terClient` ([source](../packages/client/src/wipo-6ter.ts))
reads WIPO's Article 6ter Express database. It holds about 4,600 signs that
Paris Convention members must refuse to register as trademarks: state flags
and coats of arms, official signs and hallmarks, and the names,
abbreviations and emblems of intergovernmental organizations. This
connector is new; Python had none.

The [MCP adapter](../packages/mcp/src/wipo-6ter.ts) adds `search_wipo_6ter`
and `get_wipo_6ter_sign` under `wipo:read`, always registered. National
trademark registers don't carry these signs, so the tools fill a gap in
trademark clearance.

## API

WIPO documents the JSON API in an OpenAPI 3.0 file, version 1.2.0. It's
archived at
[references/wipo-6ter](../references/wipo-6ter/Article6ter_API_v1_OpenAPI.yaml)
with its URL, retrieval date and SHA-256. It needs no credentials. The
client uses all four operations:

| Operation | Client method |
| --- | --- |
| `GET /signs`: full-text search with `keywords`, `searchType`, `sortBy`, `limit`, `offset` | `search` |
| `GET /signs/{signId}`: one sign by alias | `getSign` |
| `GET /last-updated`: the database's update date (September 30, 2026 when recorded) | `lastUpdated` |
| `GET /publication`: the bulk 6ter.zip (272 MB) and its MD5 | `publication` |

What the recordings established:

- **STARTS_WITH doesn't work.** The specification lists it as a search
  type, but the API rejects it, answering "searchType parameter should only
  be PHRASE/ALL/ANY". The client offers ANY, ALL and PHRASE.
- **An unknown alias is HTTP 204 with no body**, which the client raises as
  `NOT_FOUND`. Aliases are a two-letter party code plus the sign number
  (`QO0088` for UNESCO, where `QO` marks an intergovernmental organization)
  and are case-insensitive.
- **Search covers every field.** "UNESCO" matches six signs, the phrase
  "united nations" 175, and "hallmark" 1,066. "Red cross" matches none,
  because that emblem is protected under the Geneva Conventions, not
  Article 6ter.

Each sign carries:

- its alias and communicating party;
- its nature (flag, emblem, name, abbreviation, official sign or hallmark,
  with the goods for hallmarks);
- the sign text or image and thumbnail URLs;
- Vienna classes;
- WIPO circulars;
- objections by states.

Lean output drops the index hash, index time and source file name.

## Evidence

[`scripts/record-wipo-6ter.ts`](../scripts/record-wipo-6ter.ts)
(`bun run record:wipo-6ter`) records nine cassettes:

- **Seven library calls:** three search modes, a sign, an unknown alias,
  the update date and the bulk publication.
- **Two tool calls.**

[Tests](../tests/wipo-6ter.test.ts) also check the archived specification
and `wipo:read` on the authenticated HTTP listener.
